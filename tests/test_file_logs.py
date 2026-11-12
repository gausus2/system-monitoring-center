"""Regression tests for the /var/log text-file reader."""
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

    def test_binary_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "binary.log"
            path.write_bytes(b"hello\x00world\n")
            with mock.patch.object(logs, "ROOT", directory):
                with self.assertRaisesRegex(ValueError, "Binary"):
                    logs.read_lines(str(path), 100)


if __name__ == "__main__":
    unittest.main()
