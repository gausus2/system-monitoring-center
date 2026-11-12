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

    def test_catalog_has_broad_verified_model_coverage(self):
        rows = module.load_catalog()
        self.assertGreaterEqual(len(rows), 200)
        self.assertTrue(all(row.get("source", "").startswith("https://")
                            for row in rows))
        self.assertEqual(len({
            (row["model_regex"], row["capacity_gb"]) for row in rows
        }), len(rows))

    def test_other_manufacturer_families_and_wd_suffix(self):
        samples = (
            ("WDC WDS200T2X0E-00BCA0", 2_000_000_000_000, 1200),
            ("WDS100T3X0E", 1_000_000_000_000, 600),
            ("WDS200T1R0C", 2_000_000_000_000, 2500),
            ("CT2000MX500SSD1", 2_000_000_000_000, 700),
            ("CT4000P3PSSD8", 4_000_000_000_000, 800),
            ("SNV2S/1000G", 1_000_000_000_000, 320),
            ("ZP2000GM3A013", 2_000_000_000_000, 2550),
            ("Samsung SSD 9100 PRO 4TB", 4_000_000_000_000, 2400),
        )
        for name, size, rated_tbw in samples:
            with self.subTest(name=name):
                entry = module.lookup(name, size)
                self.assertIsNotNone(entry)
                self.assertEqual(entry["tbw"], rated_tbw)

    def test_invalid_sizes_must_not_match_even_if_model_code_matches(self):
        self.assertIsNone(
            module.lookup("WDC WDS200T2X0E-00BCA0", 1_000_000_000_000))
        self.assertIsNone(
            module.lookup("CT2000MX500SSD1", 500_000_000_000))
        self.assertIsNone(
            module.lookup("SNV2S/1000G", 2_000_000_000_000))

    def test_more_manufacturers_and_source_records(self):
        samples = (
            ("SHPP41-2000GM", 2_000_000_000_000, 1200),
            ("SHGP31-1000GM-2", 1_000_000_000_000, 750),
            ("LNM790X002T-RNNNG", 2_000_000_000_000, 1500),
            ("SFYRD/4000G", 4_000_000_000_000, 4000),
            ("WDS800T2XHE-00CDD0", 8_000_000_000_000, 4800),
        )
        for model, size, rated in samples:
            with self.subTest(model=model):
                row = module.lookup(model, size)
                self.assertIsNotNone(row)
                self.assertEqual(row["tbw"], rated)

    def test_missing_catalog_does_not_hide_smart_health(self):
        module.load_catalog.cache_clear()
        from unittest import mock
        with mock.patch.object(module, "load_catalog",
                               side_effect=FileNotFoundError("catalog")):
            disk = {"model": "KINGSTON SKC3000D2048G",
                    "size": 2_048_000_000_000}
            row = module.annotate(disk, {"health": "Passed"})
            self.assertEqual(row["health"], "Passed")
            self.assertIsNone(row["rated_tbw"])

    def test_old_samsung_970_evo_plus_matches_exactly_one_row(self):
        name = "Samsung SSD 970 EVO Plus 2TB"
        rows = module.load_catalog()
        import re
        matches = [
            row for row in rows
            if row["capacity_gb"] == 2000
            and re.fullmatch(row["model_regex"], name, flags=re.IGNORECASE)
        ]
        self.assertEqual(len(matches), 1)

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
