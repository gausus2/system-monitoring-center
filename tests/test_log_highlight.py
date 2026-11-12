"""Regression tests for Kate-inspired generic log highlighting."""
import importlib.util
from pathlib import Path
import unittest

spec = importlib.util.spec_from_file_location(
    "LogHighlight", Path(__file__).resolve().parents[1] / "src" / "LogHighlight.py")
highlight = importlib.util.module_from_spec(spec)
spec.loader.exec_module(highlight)


class HighlightTests(unittest.TestCase):
    def test_error_and_warning_classes(self):
        self.assertEqual(highlight.classify_line("connection FAILED"), "error")
        self.assertEqual(highlight.classify_line("WARN timeout"), "warning")
        self.assertEqual(highlight.classify_line("Started successfully"), "success")
        self.assertEqual(highlight.classify_line("ordinary message"), "normal")

    def test_timestamp_ipv4_key_and_path(self):
        line = '2026-11-12 20:12:13 INFO peer=192.168.1.20 path=/var/log/syslog'
        spans = highlight.highlight_spans(line)
        styles = [tag for _, _, tag in spans]
        self.assertIn("timestamp", styles)
        self.assertIn("ip", styles)
        self.assertIn("key", styles)
        self.assertIn("path", styles)
        for i, (begin, end, _) in enumerate(spans):
            self.assertGreater(end, begin)
            for other_begin, other_end, _ in spans[i+1:]:
                self.assertTrue(end <= other_begin or other_end <= begin)

    def test_syslog_date_and_error(self):
        line = 'Nov 12 21:10:02 sshd[123]: ERROR authentication failed'
        styles = [tag for _, _, tag in highlight.highlight_spans(line)]
        self.assertIn("timestamp", styles)
        self.assertIn("error", styles)

    def test_remove_ansi_control_codes(self):
        line = "\x1b[31mERROR\x1b[0m"
        self.assertEqual(highlight.ANSI.sub("", line), "ERROR")


if __name__ == "__main__":
    unittest.main()
