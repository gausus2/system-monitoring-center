"""Tests for the optional Kate-inspired System/Kernel journal color mode."""
import importlib.util
from pathlib import Path
import sys
import types
import unittest

root = Path(__file__).resolve().parents[1] / "src"
pkg = types.ModuleType("journalcolortests")
pkg.__path__ = []
sys.modules[pkg.__name__] = pkg
for name in ("LogHighlight", "JournalColors"):
    spec = importlib.util.spec_from_file_location(
        "journalcolortests." + name, root / (name + ".py"))
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)

from journalcolortests import JournalColors


class JournalColorsTests(unittest.TestCase):
    def test_display_retains_original_columns_and_content(self):
        line, base, spans = JournalColors.advanced_line(
            "2026-11-12 21:15:30", 6, "sshd.service sshd[52]",
            "Accepted connection from 192.168.1.2")
        self.assertEqual(
            line, "2026-11-12 21:15:30  INFO   "
                  + "%-26s " % "sshd.service sshd[52]"
                  + "Accepted connection from 192.168.1.2\n")
        self.assertEqual(base, "success")
        self.assertIn("timestamp", [tag for _, _, tag in spans])
        self.assertIn("ip", [tag for _, _, tag in spans])

    def test_error_and_warning_highlighting(self):
        error, base, spans = JournalColors.advanced_line(
            "2026-11-12 21:15:30", 3, "kernel", "ERROR failed at /var/log/syslog")
        self.assertEqual(base, "error")
        self.assertIn("error", [tag for _, _, tag in spans])
        self.assertIn("path", [tag for _, _, tag in spans])
        warning, base, spans = JournalColors.advanced_line(
            "2026-11-12 21:15:30", 4, "kernel", "WARN timeout")
        self.assertEqual(base, "warning")

    def test_multiline_messages_are_kept_on_single_visual_line(self):
        line, _, _ = JournalColors.advanced_line(
            "2026-11-12 21:15:30", 6, "sender", "first\nsecond\r")
        self.assertIn("first ⏎ second\n", line)
        self.assertNotIn("\r", line)

    def test_all_priority_names(self):
        expected = ("EMERG", "ALERT", "CRIT", "ERROR", "WARN",
                    "NOTICE", "INFO", "DEBUG")
        for priority, level in enumerate(expected):
            with self.subTest(priority=priority):
                line, _, _ = JournalColors.advanced_line(
                    "2026-11-12 21:15:30", priority, "unit", "message")
                self.assertIn(level, line)


if __name__ == "__main__":
    unittest.main()
