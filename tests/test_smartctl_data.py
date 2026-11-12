"""Regression tests for read-only smartctl disk scanning and SMART parsing."""
import importlib.util
import json
from pathlib import Path
import subprocess
import unittest
from unittest import mock

import sys
import types

path = Path(__file__).resolve().parents[1] / "src"
pkg = types.ModuleType("smarttests")
pkg.__path__ = []
sys.modules[pkg.__name__] = pkg

endurance_spec = importlib.util.spec_from_file_location(
    "smarttests.SmartEndurance", path / "SmartEndurance.py")
endurance = importlib.util.module_from_spec(endurance_spec)
sys.modules[endurance_spec.name] = endurance
endurance_spec.loader.exec_module(endurance)

spec = importlib.util.spec_from_file_location(
    "smarttests.SmartctlData", path / "SmartctlData.py")
module = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = module
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

    def test_mounts_on_partitions_and_nested_mappers(self):
        tree = {"blockdevices": [
            {"path": "/dev/nvme0n1", "type": "disk", "mountpoints": [None],
             "children": [
                 {"path": "/dev/nvme0n1p1", "type": "part",
                  "mountpoints": ["/boot/efi"]},
                 {"path": "/dev/nvme0n1p2", "type": "part",
                  "mountpoints": [None],
                  "children": [
                      {"path": "/dev/mapper/cryptroot", "type": "crypt",
                       "mountpoints": ["/", "/home", None]}]}]},
            {"path": "/dev/sda", "type": "disk", "mountpoints": [None],
             "children": [{"path": "/dev/sda1", "type": "part",
                           "mountpoints": ["/mnt/backup", "/mnt/backup"]}]},
            {"path": "/dev/nvme1n1", "type": "disk", "mountpoints": [None]},
        ]}
        mounts = module.mounted_paths(run=lambda *a, **kw: process(tree))
        self.assertEqual(mounts["/dev/nvme0n1"], [
            ("/dev/mapper/cryptroot", "/"),
            ("/dev/nvme0n1p1", "/boot/efi"),
            ("/dev/mapper/cryptroot", "/home"),
        ])
        self.assertEqual(mounts["/dev/sda"],
                         [("/dev/sda1", "/mnt/backup")])
        self.assertEqual(mounts["/dev/nvme1n1"], [])

    def test_mount_error_does_not_hide_smart_results(self):
        disk = {"path": "/dev/nvme0n1", "model": "Test",
                "size": 2_000_000_000_000, "transport": "nvme"}
        with mock.patch.object(module, "physical_disks", return_value=[disk]), \
             mock.patch.object(module, "mounted_paths",
                               side_effect=RuntimeError("cannot list mounts")), \
             mock.patch.object(module, "inspect_disk",
                               return_value={"health": "Passed"}):
            results = module.collect()
        self.assertEqual(results[0][1]["health"], "Passed")
        self.assertEqual(results[0][0]["mount_error"], "cannot list mounts")
        self.assertEqual(results[0][0]["mount_points"], [])

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

    def test_nvme_total_written_uses_decimal_512000_byte_units(self):
        # NVMe Data Units Written is rounded up in 1000 x 512-byte blocks.
        data = module.parse_smart({
            "nvme_smart_health_information_log": {
                "data_units_written": 2000000, "critical_warning": 0}})
        self.assertEqual(data["writes_bytes"], 1024000000000)
        self.assertEqual(
            module.parse_smart({"nvme_smart_health_information_log": {
                "data_units_written": "100000000000000000000"}})["writes_bytes"],
            51200000000000000000000000)
        self.assertIsNone(
            module.parse_smart({"nvme_smart_health_information_log": {
                "data_units_written": 0}})["writes_bytes"])
        self.assertIsNone(module.parse_smart({})["writes_bytes"])
        self.assertIsNone(
            module.parse_smart({"nvme_smart_health_information_log": {
                "data_units_written": "invalid"}})["writes_bytes"])

    def test_ata_same_id_241_has_vendor_specific_units(self):
        samsung = module.parse_smart({
            "model_name": "Samsung SSD 870 EVO 1TB",
            "ata_smart_attributes": {"table": [{
                "id": 241, "name": "Total_LBAs_Written",
                "raw": {"value": 2_000_000_000}}]}})
        self.assertEqual(samsung["writes_bytes"], 1_024_000_000_000)
        self.assertIn("Samsung", samsung["writes_source"])
        kingston = module.parse_smart({
            "model_name": "KINGSTON SA400S37240G",
            "ata_smart_attributes": {"table": [{
                "id": 241, "name": "Host_Writes_GB",
                "raw": {"value": 1024}}]}})
        self.assertEqual(kingston["writes_bytes"], 1_024_000_000_000)
        self.assertIn("Kingston", kingston["writes_source"])

    def test_ata_unknown_id_241_is_not_guessed(self):
        for model, name in (
            ("Unknown SSD", "Total_LBAs_Written"),
            ("KINGSTON SA400S37240G", "Total_LBAs_Written"),
            ("Samsung SSD 870 EVO 1TB", "Host_Writes_GB"),
            ("Some Other SSD", "NAND_Writes_1GiB"),
        ):
            with self.subTest(model=model, name=name):
                data = module.parse_smart({
                    "model_name": model,
                    "ata_smart_attributes": {"table": [{
                        "id": 241, "name": name,
                        "raw": {"value": 100}}]}})
                self.assertIsNone(data["writes_bytes"])
                self.assertIsNone(data["writes_source"])

    def test_nvme_counter_takes_precedence_over_ata_guess(self):
        data = module.parse_smart({
            "model_name": "Samsung SSD NVMe",
            "nvme_smart_health_information_log": {"data_units_written": 2000},
            "ata_smart_attributes": {"table": [{
                "id": 241, "name": "Total_LBAs_Written",
                "raw": {"value": 2000}}]}})
        self.assertEqual(data["writes_bytes"], 1_024_000_000)
        self.assertIn("NVMe", data["writes_source"])

    def test_status_not_assumed_good_without_evidence(self):
        self.assertEqual(module.parse_smart({})["health"], "Unknown")
        self.assertEqual(module.parse_smart({"smart_status":{"passed":False}})
                         ["health"], "FAILED / Warning")
        self.assertEqual(module.parse_smart({"smart_status":{"passed":True}},
                                            returncode=2)["health"], "Unavailable")

    def test_admin_uses_passwordless_sudo_before_polkit(self):
        calls = []
        denied = {"smartctl":{"messages":[{
            "severity":"error", "string":"Permission denied"}]}}
        good = {"smart_status":{"passed":True},
                "temperature":{"current":36}}
        def runner(command, **kwargs):
            calls.append(command)
            return process(denied if command[0] == "smartctl" else good,
                           code=2 if command[0] == "smartctl" else 0)
        which = lambda name: {"smartctl":"/usr/sbin/smartctl",
                              "sudo":"/usr/bin/sudo",
                              "pkexec":"/usr/bin/pkexec"}.get(name)
        outcome = module.read_admin("/dev/nvme0n1", runner, which)
        self.assertEqual(outcome["health"], "Passed")
        self.assertEqual([entry[0] for entry in calls], ["smartctl", "sudo"])
        self.assertEqual(calls[1],
                         ["sudo", "-n", "--", "/usr/sbin/smartctl",
                          "-a", "-j", "/dev/nvme0n1"])

    def test_admin_falls_back_to_pkexec_after_sudo_denied(self):
        calls = []
        denied = {"smartctl":{"messages":[{
            "severity":"error", "string":"Permission denied"}]}}
        good = {"smart_status":{"passed":True}, "power_on_time":{"hours":20}}
        def runner(command, **kwargs):
            calls.append(command)
            if command[0] == "smartctl":
                return process(denied, code=2)
            if command[0] == "sudo":
                return subprocess.CompletedProcess(
                    command, 1, "", "sudo: a password is required")
            return process(good)
        which = lambda name: {"smartctl":"/usr/sbin/smartctl",
                              "sudo":"/usr/bin/sudo",
                              "pkexec":"/usr/bin/pkexec"}.get(name)
        outcome = module.read_admin("/dev/nvme0n1", runner, which)
        self.assertEqual(outcome["health"], "Passed")
        self.assertEqual([entry[0] for entry in calls],
                         ["smartctl", "sudo", "pkexec"])
        self.assertEqual(calls[2],
                         ["pkexec", "/usr/sbin/smartctl", "-a", "-j",
                          "/dev/nvme0n1"])

    def test_admin_cancelled_or_no_polkit_is_unavailable(self):
        denied = {"smartctl":{"messages":[{
            "severity":"error", "string":"Permission denied"}]}}
        def runner(command, **kwargs):
            if command[0] == "smartctl":
                return process(denied, code=2)
            if command[0] == "sudo":
                return subprocess.CompletedProcess(
                    command, 1, "", "sudo: not in the sudoers file")
            return subprocess.CompletedProcess(
                command, 126, "", "Authentication cancelled")
        which = lambda name: {"smartctl":"/usr/sbin/smartctl",
                              "sudo":"/usr/bin/sudo",
                              "pkexec":"/usr/bin/pkexec"}.get(name)
        failed = module.read_admin("/dev/nvme0n1", runner, which)
        self.assertEqual(failed["health"], "Unavailable")
        self.assertIn("cancelled", failed["messages"][0])
        no_polkit = module.read_admin(
            "/dev/nvme0n1", runner,
            lambda name: which(name) if name != "pkexec" else None)
        self.assertEqual(no_polkit["health"], "Unavailable")

    def test_admin_does_not_escalate_without_permission_error(self):
        calls = []
        def runner(command, **kwargs):
            calls.append(command)
            return process({"smart_status":{"passed":False}}, code=8)
        result = module.read_admin(
            "/dev/nvme0n1", runner,
            lambda name: "/usr/bin/" + name)
        self.assertEqual(result["health"], "FAILED / Warning")
        self.assertEqual(len(calls), 1)

    def test_regular_collect_does_not_request_admin(self):
        disk = {"path":"/dev/nvme0n1", "model":"Test",
                "size":1000, "transport":"nvme"}
        with mock.patch.object(module, "physical_disks", return_value=[disk]), \
             mock.patch.object(module, "mounted_paths", return_value={}), \
             mock.patch.object(module, "inspect_disk",
                               return_value={"health":"Unavailable"}) as plain, \
             mock.patch.object(module, "read_admin") as admin:
            module.collect()
            plain.assert_called_once()
            admin.assert_not_called()

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
