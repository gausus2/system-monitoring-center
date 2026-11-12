"""Regression tests for read-only smartctl disk scanning and SMART parsing."""
import importlib.util
import json
from pathlib import Path
import subprocess
import unittest
from unittest import mock

path = Path(__file__).resolve().parents[1] / "src" / "SmartctlData.py"
spec = importlib.util.spec_from_file_location("SmartctlData", path)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


def process(data=None, code=0, stderr=""):
    return subprocess.CompletedProcess([], code, json.dumps(data) if
                                       data is not None else "", stderr)


class SmartctlTests(unittest.TestCase):
    def test_disk_discovery_skips_partitions_and_virtual_devices(self):
        block = {"blockdevices": [
            {"name":"sda", "path":"/dev/sda", "type":"disk",
             "model":" SATA drive ", "size":1000000000, "tran":"sata"},
            {"name":"sda1", "path":"/dev/sda1", "type":"part"},
            {"name":"nvme0n1", "path":"/dev/nvme0n1", "type":"disk",
             "model":"NVMe", "size":2000000000, "tran":"nvme"},
            {"name":"zram0", "path":"/dev/zram0", "type":"disk", "model":""},
            {"name":"loop0", "path":"/dev/loop0", "type":"loop"},
            {"name":"sr0", "path":"/dev/sr0", "type":"rom"},
        ]}
        # lsblk marks zram as "disk" on some distributions; the
        # discovery function must explicitly exclude it.
        with mock.patch.object(module, "LSBLK", ["lsblk"]):
            disks = module.physical_disks(run=lambda *a, **kw: process(block))
        self.assertEqual([d["path"] for d in disks],
                         ["/dev/sda", "/dev/nvme0n1"])

    def test_sata_health_and_wear_attributes(self):
        raw = {"smart_status":{"passed":True}, "temperature":{"current":33},
               "power_on_time":{"hours":7500}, "device":{"protocol":"ATA"},
               "ata_smart_attributes":{"table":[
                   {"id":5, "raw":{"value":0}},
                   {"id":197, "raw":{"value":2}},
                   {"id":198, "raw":{"value":0}}]}}
        data = module.parse_smart(raw)
        self.assertEqual(data["health"], "Passed")
        self.assertEqual(data["temperature"], 33)
        self.assertEqual(data["hours"], 7500)
        self.assertEqual(data["attributes"]["Current pending sectors"], 2)

    def test_nvme_warning_and_media_errors(self):
        raw = {"nvme_smart_health_information_log":{
            "critical_warning":1, "temperature":42,
            "percentage_used":7, "media_errors":5}}
        data = module.parse_smart(raw)
        self.assertEqual(data["health"], "FAILED / Warning")
        self.assertEqual(data["percentage_used"], 7)
        self.assertEqual(data["media_errors"], 5)

    def test_status_not_assumed_good_without_evidence(self):
        self.assertEqual(module.parse_smart({})["health"], "Unknown")
        self.assertEqual(module.parse_smart({"smart_status":{"passed":False}})
                         ["health"], "FAILED / Warning")
        self.assertEqual(module.parse_smart({"smart_status":{"passed":True}},
                                            returncode=2)["health"], "Unavailable")

    def test_unreadable_and_missing_smartctl(self):
        run = lambda *a, **kw: process(
            {"smartctl":{"messages":[{"severity":"error",
                                       "string":"Permission denied"}]}},
            code=2)
        self.assertEqual(module.inspect_disk("/dev/sda", run)["health"],
                         "Unavailable")
        def missing(*a, **kw):
            raise FileNotFoundError("smartctl")
        self.assertIn("not installed",
                      module.inspect_disk("/dev/sda", missing)["messages"][0])


if __name__ == "__main__":
    unittest.main()
