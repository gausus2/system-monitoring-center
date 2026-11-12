"""Regression tests for the /var/log text-file reader."""
import datetime
import importlib.util
from pathlib import Path
import sys
import tempfile
import types
import unittest
from unittest import mock

pkg = types.ModuleType("filelogtests")
pkg.__path__ = []
sys.modules[pkg.__name__] = pkg
common = types.ModuleType("filelogtests.Common")
sys.modules[common.__name__] = common
highlight_spec = importlib.util.spec_from_file_location(
    "filelogtests.LogHighlight",
    Path(__file__).resolve().parents[1] / "src" / "LogHighlight.py")
highlight = importlib.util.module_from_spec(highlight_spec)
sys.modules[highlight_spec.name] = highlight
highlight_spec.loader.exec_module(highlight)
boot_spec = importlib.util.spec_from_file_location(
    "filelogtests.FileLogBoot",
    Path(__file__).resolve().parents[1] / "src" / "FileLogBoot.py")
boot = importlib.util.module_from_spec(boot_spec)
sys.modules[boot_spec.name] = boot
boot_spec.loader.exec_module(boot)
spec = importlib.util.spec_from_file_location(
    "filelogtests.FileLogs", Path(__file__).resolve().parents[1] / "src" / "FileLogs.py")
logs = importlib.util.module_from_spec(spec)
spec.loader.exec_module(logs)


class FileLogsTests(unittest.TestCase):
    def test_scan_first_last_and_search_before_limit(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "app.log"
            path.write_text("one\nERROR two\nthree\nERROR four\nfive\n",
                            encoding="utf-8")
            with mock.patch.object(logs, "ROOT", directory):
                self.assertEqual(logs.read_lines(str(path), 2)[0],
                                 ["ERROR four", "five"])
                self.assertEqual(logs.read_lines(str(path), 2, first=True)[0],
                                 ["one", "ERROR two"])
                self.assertEqual(logs.read_lines(str(path), 1, needle="error")[0],
                                 ["ERROR four"])
                self.assertEqual(logs.read_lines(str(path), 1, first=True,
                                                 needle="error")[0], ["ERROR two"])

    def test_discovery_ignores_binary_rotated_and_symlinks(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "syslog").write_text("ok\n")
            (root / "syslog.1").write_text("old\n")
            (root / "auth.log.gz").write_bytes(b"compressed")
            (root / "wtmp").write_bytes(b"binary")
            (root / "elsewhere").symlink_to(root / "syslog")
            sub = root / "nginx"
            sub.mkdir()
            (sub / "error.log").write_text("failure\n")
            with mock.patch.object(logs, "ROOT", directory):
                self.assertEqual(logs.available_logs(),
                                 [str(root / "syslog"), str(sub / "error.log")])

    def test_boot_filter_applies_before_last_line_count(self):
        tz = datetime.timezone(datetime.timedelta(hours=1))
        start = datetime.datetime(2026, 11, 12, 12, 8, 22, tzinfo=tz)
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "syslog"
            path.write_text(
                "Nov 12 00:10:56 Stopped logrotate.timer\n"
                "Nov 12 12:08:30 System started\n"
                "    continuation of startup\n"
                "Nov 12 12:10:00 ERROR failed\n"
                "Nov 12 21:11:00 Ready\n", encoding="utf-8")
            with mock.patch.object(logs, "ROOT", directory), \
                 mock.patch.object(logs.os.path, "getmtime", return_value=start.timestamp()), \
                 mock.patch.object(logs.FileLogBoot, "boot_window",
                                   return_value=(start, None)):
                lines, truncated = logs.read_lines(
                    str(path), 2, needle="", boot="Current boot")
                self.assertEqual(lines, [
                    "Nov 12 12:10:00 ERROR failed",
                    "Nov 12 21:11:00 Ready"])
                self.assertFalse(truncated)
                lines, _ = logs.read_lines(
                    str(path), 2, first=True, boot="Current boot")
                self.assertEqual(lines, [
                    "Nov 12 12:08:30 System started",
                    "    continuation of startup"])

    def test_boot_filter_rejects_undated_file(self):
        tz = datetime.timezone.utc
        start = datetime.datetime(2026, 11, 12, 12, tzinfo=tz)
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "plain.log"
            path.write_text("foo\nbar\n", encoding="utf-8")
            with mock.patch.object(logs, "ROOT", directory), \
                 mock.patch.object(logs.os.path, "getmtime", return_value=start.timestamp()), \
                 mock.patch.object(logs.FileLogBoot, "boot_window",
                                   return_value=(start, None)):
                with self.assertRaises(logs.NoRecognizableTimestamps):
                    logs.read_lines(str(path), 2, boot="Current boot")
                lines, partial, fallback = logs.read_with_boot_fallback(
                    str(path), 2, boot="Current boot")
                self.assertEqual(lines, ["foo", "bar"])
                self.assertFalse(partial)
                self.assertTrue(fallback)
                lines, partial, fallback = logs.read_with_boot_fallback(
                    str(path), 1, needle="bar", boot="Previous boot (-1)")
                self.assertEqual(lines, ["bar"])
                self.assertTrue(fallback)

    def test_last_scans_newest_bytes_in_large_file(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "large.log"
            path.write_text("old line\n" * 40 + "NEW last line\n",
                            encoding="utf-8")
            with mock.patch.object(logs, "ROOT", directory), \
                 mock.patch.object(logs, "MAX_SCAN_BYTES", 64):
                lines, partial = logs.read_lines(str(path), 1)
                self.assertEqual(lines, ["NEW last line"])
                self.assertTrue(partial)

    def test_binary_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "binary.log"
            path.write_bytes(b"hello\x00world\n")
            with mock.patch.object(logs, "ROOT", directory):
                with self.assertRaisesRegex(ValueError, "Binary"):
                    logs.read_lines(str(path), 100)


if __name__ == "__main__":
    unittest.main()
