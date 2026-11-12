"""Boot-window and text timestamp regression tests."""
import datetime as dt
import importlib.util
from pathlib import Path
import tempfile
import unittest
from unittest import mock

base = Path(__file__).resolve().parents[1] / "src"
spec = importlib.util.spec_from_file_location("FileLogBoot", base / "FileLogBoot.py")
boot = importlib.util.module_from_spec(spec)
spec.loader.exec_module(boot)
TZ = dt.timezone(dt.timedelta(hours=1))


class BootTests(unittest.TestCase):
    def test_current_and_previous_boot_bounds(self):
        current = dt.datetime(2026, 11, 12, 12, 8, 22, tzinfo=TZ)
        previous_start = dt.datetime(2026, 11, 11, 13, 0, tzinfo=TZ)
        previous_end = dt.datetime(2026, 11, 12, 0, 11, tzinfo=TZ)
        with mock.patch.object(boot, "current_boot_start", return_value=current), \
             mock.patch.object(boot, "_journal_edge",
                               side_effect=[previous_start, previous_end]) as edge:
            self.assertEqual(boot.boot_window("Current boot"), (current, None))
            self.assertEqual(boot.boot_window("Previous boot (-1)"),
                             (previous_start, previous_end))
            self.assertEqual([c.args for c in edge.call_args_list],
                             [(-1, True), (-1, False)])
        self.assertIsNone(boot.boot_window("All available"))

    def test_old_boot_not_present(self):
        with mock.patch.object(boot, "current_boot_start",
                               return_value=dt.datetime.now().astimezone()), \
             mock.patch.object(boot, "_journal_edge", return_value=None):
            with self.assertRaisesRegex(ValueError, "not available"):
                boot.boot_window("Boot -3")

    def test_iso_syslog_apache_and_undated(self):
        ref = dt.datetime(2026, 11, 12, 22, 0, tzinfo=TZ)
        self.assertEqual(
            boot.timestamp("2026-11-12 20:15:00 ERROR foo", ref),
            dt.datetime(2026, 11, 12, 20, 15, tzinfo=TZ))
        self.assertEqual(
            boot.timestamp("Nov 12 20:15:00 sshd[8]: connected", ref),
            dt.datetime(2026, 11, 12, 20, 15, tzinfo=TZ))
        self.assertEqual(
            boot.timestamp('10.0.0.1 - - [12/Nov/2026:20:15:00 +0100] "GET /"', ref),
            dt.datetime(2026, 11, 12, 20, 15, tzinfo=TZ))
        self.assertIsNone(boot.timestamp("  indented continuation line", ref))

    def test_syslog_year_boundary(self):
        ref = dt.datetime(2027, 1, 2, tzinfo=TZ)
        self.assertEqual(boot.timestamp("Dec 31 23:59:59 message", ref).year, 2026)


if __name__ == "__main__":
    unittest.main()
