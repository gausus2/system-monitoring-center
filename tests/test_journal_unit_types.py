"""Tests for journal-backed systemd unit type selection."""
import importlib.util
from pathlib import Path
import subprocess
import unittest
from unittest import mock

module_path = Path(__file__).resolve().parents[1] / "src" / "JournalUnitTypes.py"
spec = importlib.util.spec_from_file_location("JournalUnitTypes", module_path)
types = importlib.util.module_from_spec(spec)
spec.loader.exec_module(types)


class UnitTypesTests(unittest.TestCase):
    def test_known_unit_types(self):
        self.assertEqual(types.unit_type("warp-svc.service"), "service")
        self.assertEqual(types.unit_type("home.mount"), "mount")
        self.assertEqual(types.unit_type("systemd-journald@warp.service"), "service")
        self.assertEqual(types.unit_type("dev-disk-by\\x2duuid-123.device"), "device")
        self.assertIsNone(types.unit_type("no suffix"))
        self.assertIsNone(types.unit_type(None))
        self.assertIsNone(types.unit_type("foo/bar.service"))

    def test_glob_is_safe(self):
        self.assertEqual(types.unit_glob("mount"), "*.mount")
        self.assertIsNone(types.unit_glob(None))
        for invalid in ("*", "*.service", "service extra", "SERVICE"):
            with self.subTest(invalid=invalid), self.assertRaises(ValueError):
                types.unit_glob(invalid)

    def test_discovery_reads_journal_fields_for_selected_namespace(self):
        def result(command, **kwargs):
            if "--field=_SYSTEMD_UNIT" in command:
                stdout = "warp-svc.service\nsome.socket\nmalformed value\n"
            else:
                stdout = "home.mount\nbasic.target\nwarp-svc.service\n"
            return subprocess.CompletedProcess(command, 0, stdout, "")
        with mock.patch.object(types.subprocess, "run", side_effect=result) as run:
            names = types.discover_types("warp")
        self.assertEqual(names, ["mount", "service", "socket", "target"])
        self.assertEqual(run.call_count, 2)
        for call in run.call_args_list:
            self.assertIn("--namespace=warp", call.args[0])

    def test_discovery_keeps_working_if_journal_not_accessible(self):
        with mock.patch.object(types.subprocess, "run",
                               side_effect=subprocess.TimeoutExpired(["journalctl"], 7)):
            self.assertEqual(types.discover_types(), [])


if __name__ == "__main__":
    unittest.main()
