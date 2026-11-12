"""Tests for the offline manufacturer's rated-TBW catalog."""
import importlib.util
from pathlib import Path
import unittest

root = Path(__file__).resolve().parents[1] / "src"
spec = importlib.util.spec_from_file_location("SmartEndurance", root / "SmartEndurance.py")
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class RatedTBWTests(unittest.TestCase):
    def test_actual_model_names_and_capacities(self):
        kingston = module.lookup("KINGSTON SKC3000D2048G", 2_048_000_000_000)
        samsung = module.lookup("Samsung SSD 970 EVO Plus 2TB", 2_000_000_000_000)
        self.assertEqual(kingston["tbw"], 1600)
        self.assertEqual(samsung["tbw"], 1200)
        self.assertEqual(module.lookup("KINGSTON SKC3000S1024G",
                                       1_024_000_000_000)["tbw"], 800)
        self.assertEqual(module.lookup("Samsung SSD 970 EVO Plus 500GB",
                                       500_000_000_000)["tbw"], 300)

    def test_do_not_guess_unknown_wrong_capacity_or_neighbor_model(self):
        self.assertIsNone(module.lookup("NE-256", 256_000_000_000))
        self.assertIsNone(module.lookup("Samsung SSD 970 EVO 2TB", 2_000_000_000_000))
        self.assertIsNone(module.lookup("Samsung SSD 970 EVO Plus 2TB", 500_000_000_000))
        self.assertIsNone(module.lookup("KINGSTON SKC3000D2048G", 1_000_000_000_000))
        self.assertIsNone(module.lookup("Samsung SSD 970 EVO Plus 2TB", None))

    def test_usage_pct_is_not_nvme_percentage_used(self):
        disk = {"model": "KINGSTON SKC3000D2048G", "size": 2_048_000_000_000}
        smart = {"writes_bytes": 400_000_000_000_000, "percentage_used": 4}
        annotated = module.annotate(disk, smart)
        self.assertEqual(annotated["rated_tbw"], 1600)
        self.assertEqual(annotated["rated_tbw_used_pct"], 25)
        self.assertEqual(annotated["percentage_used"], 4)
        self.assertIn("kingston.com", annotated["rated_tbw_source"])

    def test_missing_writes_does_not_infer_a_percentage(self):
        disk = {"model": "Samsung SSD 970 EVO Plus 2TB", "size": 2_000_000_000_000}
        annotated = module.annotate(disk, {"writes_bytes": None})
        self.assertEqual(annotated["rated_tbw"], 1200)
        self.assertIsNone(annotated["rated_tbw_used_pct"])


if __name__ == "__main__":
    unittest.main()
