"""Regression checks for Warp's embedded severity and bounded reverse reader."""
import importlib.util
import io
import json
from pathlib import Path
import unittest
from unittest import mock


module_path = Path(__file__).resolve().parents[1] / "src" / "WarpJournal.py"
spec = importlib.util.spec_from_file_location("WarpJournal", module_path)
warp = importlib.util.module_from_spec(spec)
spec.loader.exec_module(warp)


def record(level, *, sender="warp-svc.service", priority="6"):
    return {
        "SYSLOG_IDENTIFIER": sender,
        "PRIORITY": priority,
        "MESSAGE": "2026-11-12T11:08:45.699Z " + level + " warp_edge::handler: test",
    }


class FakeProcess:
    def __init__(self, entries):
        self.stdout = io.StringIO("".join(json.dumps(row) + "\n" for row in entries))
        self.stderr = io.StringIO("")
        self.code = None

    def poll(self):
        return self.code

    def wait(self, timeout=None):
        if self.code is None:
            self.code = 0
        return self.code

    def terminate(self):
        self.code = -15

    def kill(self):
        self.code = -9


class WarpJournalTests(unittest.TestCase):
    def test_effective_levels(self):
        for level, expected in (("DEBUG", 7), ("INFO", 6),
                                ("WARN", 4), ("ERROR", 3)):
            with self.subTest(level=level):
                self.assertEqual(warp.effective_priority(record(level)), expected)

    def test_ansi_and_binary_messages(self):
        original = b"\x1b[2m2026-11-12T11:08:45.699Z\x1b[0m \x1b[31mERROR\x1b[0m test"
        entry = record("INFO")
        entry["MESSAGE"] = list(original)
        self.assertEqual(warp.effective_priority(entry), 3)
        self.assertNotIn("\x1b", warp.message_text(entry["MESSAGE"]))

    def test_unrelated_process_keeps_journal_priority(self):
        self.assertEqual(warp.effective_priority(record("ERROR", sender="netdata",
                                                         priority="6")), 6)

    def test_internal_word_is_not_severity(self):
        entry = record("DEBUG")
        entry["MESSAGE"] = "2026-11-12T11:08:45.699Z INFO no ERROR should override INFO"
        self.assertEqual(warp.effective_priority(entry), 6)

    def test_reverse_reader_limits_after_effective_filter(self):
        # Input is newest-first, as emitted by journalctl --reverse.
        entries = [record("ERROR"), record("INFO"), record("WARN"), record("DEBUG")]
        fake = FakeProcess(entries)
        with mock.patch.object(warp.subprocess, "Popen", return_value=fake) as popen:
            results = warp.read_entries(["journalctl", "--namespace=warp",
                                         "--output=json"], 2, "warning")
        self.assertEqual([row["_VIEW_PRIORITY"] for row in results], [4, 3])
        self.assertEqual(len(results), 2)
        self.assertIn("--reverse", popen.call_args.args[0])
        self.assertNotIn("--lines", popen.call_args.args[0])


if __name__ == "__main__":
    unittest.main()
