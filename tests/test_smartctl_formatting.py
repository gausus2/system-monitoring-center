"""Unit tests for SMART day/hour formatting and selectable write units."""
import ast
from pathlib import Path
import unittest

source = Path(__file__).resolve().parents[1] / "src" / "SmartctlTab.py"
tree = ast.parse(source.read_text(encoding="utf-8"))
names = {"format_size", "format_hours", "format_writes", "details_text"}
module = ast.Module(
    body=[node for node in tree.body if isinstance(node, ast.FunctionDef)
          and node.name in names],
    type_ignores=[])
ast.fix_missing_locations(module)
scope = {}
exec(compile(module, str(source), "exec"), scope)


class SmartFormattingTests(unittest.TestCase):
    def test_hours_to_days_and_hours(self):
        format_hours = scope["format_hours"]
        self.assertEqual(format_hours(14791), "616 d 7 h")
        self.assertEqual(format_hours(846), "35 d 6 h")
        self.assertEqual(format_hours(17228), "717 d 20 h")
        self.assertEqual(format_hours(0), "0 d 0 h")
        self.assertEqual(format_hours(None), "-")

    def test_disk_details_firmware(self):
        disk = {"path": "/dev/nvme0n1", "model": "Test",
                "size": 1_000_000_000_000, "transport": "nvme"}
        smart = {"health": "Passed", "firmware": "S5Z42105",
                 "attributes": {}, "messages": []}
        self.assertIn("Firmware: S5Z42105",
                      scope["details_text"](disk, smart))
        smart.pop("firmware")
        self.assertIn("Firmware: -", scope["details_text"](disk, smart))

    def test_ext4_dates_in_disk_details(self):
        disk = {"path": "/dev/nvme2n1", "model": "Samsung",
                "size": 2_000_000_000_000, "transport": "nvme",
                "filesystem_dates": [
                    ("2024-02-27 21:11:50", "/dev/nvme2n1p6"),
                    ("2024-03-20 14:56:20", "/dev/nvme2n1p4")]}
        smart = {"health": "Passed", "attributes": {}, "messages": []}
        details = scope["details_text"](disk, smart)
        self.assertIn("Filesystem date information:", details)
        self.assertIn("/dev/nvme2n1p6 (ext4): 2024-02-27 21:11:50"
                      " [filesystem created]", details)
        self.assertIn("/dev/nvme2n1p4 (ext4): 2024-03-20 14:56:20",
                      details)
        self.assertNotIn("Oldest filesystem", details)
        disk["ntfs_root_dates"] = [
            ("2017-09-29 08:45:11 UTC", "/dev/nvme2n1p2")]
        details = scope["details_text"](disk, smart)
        self.assertIn("/dev/nvme2n1p2 (NTFS): 2017-09-29 08:45:11 UTC"
                      " [root directory created]", details)
        self.assertLess(details.index("/dev/nvme2n1p2 (NTFS)"),
                        details.index("/dev/nvme2n1p6 (ext4)"))
        disk["filesystem_dates"] = []
        disk["ntfs_root_dates"] = []
        self.assertIn("Not available (try Read SMART (Admin)",
                      scope["details_text"](disk, smart))

    def test_disk_details_show_current_mounts(self):
        smart = {"health": "Passed", "attributes": {}, "messages": []}
        disk = {"path": "/dev/nvme0n1", "model": "NVMe",
                "size": 2_000_000_000_000, "transport": "nvme",
                "mount_points": [
                    ("/dev/nvme0n1p2", "/"),
                    ("/dev/nvme0n1p3", "/home")]}
        details = scope["details_text"](disk, smart)
        self.assertIn("Mount points (currently mounted):", details)
        self.assertIn("/dev/nvme0n1p2 → /", details)
        self.assertIn("/dev/nvme0n1p3 → /home", details)
        disk["mount_points"] = []
        self.assertIn("Mount points: Not mounted",
                      scope["details_text"](disk, smart))
        disk["mount_error"] = "lsblk not available"
        self.assertIn("Mount points: Unavailable (lsblk not available)",
                      scope["details_text"](disk, smart))

    def test_auto_and_manual_decimal_units(self):
        format_writes = scope["format_writes"]
        self.assertEqual(format_writes(1_024_000_000_000), "1.02 TB")
        self.assertEqual(format_writes(1_024_000_000_000, "GB"), "1024.00 GB")
        self.assertEqual(format_writes(1_024_000_000_000, "TB"), "1.02 TB")
        self.assertEqual(format_writes(1_024_000_000_000, "PB"), "0.00 PB")
        self.assertEqual(format_writes(1_500_000_000_000_000), "1.50 PB")
        self.assertEqual(format_writes(0), "0.00 GB")
        self.assertEqual(format_writes(None), "-")

    def test_disk_details_follow_writes_units(self):
        disk = {"path": "/dev/nvme0n1", "model": "NVMe",
                "size": 2_000_000_000_000, "transport": "nvme"}
        smart = {"health": "Passed", "hours": 14791,
                 "writes_bytes": 1_024_000_000_000,
                 "attributes": {}, "messages": []}
        text = scope["details_text"](disk, smart, "GB")
        self.assertIn("Power-on time: 616 d 7 h", text)
        self.assertIn("Total writes: 1024.00 GB", text)
        text = scope["details_text"](disk, smart, "TB")
        self.assertIn("Total writes: 1.02 TB", text)


if __name__ == "__main__":
    unittest.main()
