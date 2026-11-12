"""Regression checks for SMART Copy table export."""
import ast
from pathlib import Path
import unittest

SOURCE = (Path(__file__).resolve().parents[1] / "src" / "SmartctlTab.py").read_text(encoding="utf-8")
tree = ast.parse(SOURCE)
helper = next(node for node in tree.body
              if isinstance(node, ast.FunctionDef)
              and node.name == "format_table_text")
module = ast.Module(body=[helper], type_ignores=[])
ast.fix_missing_locations(module)
scope = {}
exec(compile(module, "<smart-copy-table>", "exec"), scope)
format_table_text = scope["format_table_text"]


class SmartCopyTableTests(unittest.TestCase):
    def test_copy_preserves_headers_rows_values_and_alignment(self):
        result = format_table_text(
            ["Disk", "Model", "Size", "SMART", "Writes", "TBW %"],
            [["/dev/nvme0n1", "KINGSTON SKC3000D2048G", "1.9 TiB",
              "Passed", "11.18 TB", "0.70 %"],
             ["/dev/nvme2n1", "Samsung SSD 970 EVO Plus 2TB", "1.8 TiB",
              "Passed", "23.87 TB", "1.99 %"]])
        lines = result.splitlines()
        self.assertEqual(len(lines), 3)
        self.assertTrue(lines[0].startswith("Disk "))
        self.assertIn("Model", lines[0])
        self.assertIn("/dev/nvme0n1", lines[1])
        self.assertIn("Samsung SSD 970 EVO Plus 2TB", lines[2])
        self.assertEqual(lines[0].index("Model"), lines[1].index("KINGSTON"))
        self.assertEqual(lines[0].index("Model"), lines[2].index("Samsung"))
        self.assertTrue(result.endswith("\n"))

    def test_empty_rows_and_headings(self):
        self.assertEqual(format_table_text([], []), "")
        self.assertEqual(format_table_text(["Disk", "SMART"], []), "Disk  SMART\n")

    def test_gui_wiring_uses_current_treeview_data(self):
        self.assertIn('text="Copy table", command=self._copy_table', SOURCE)
        self.assertIn('label="Copy table", command=self._copy_table', SOURCE)
        self.assertIn('self.table["displaycolumns"]', SOURCE)
        self.assertIn('self.table.heading(column, "text")', SOURCE)
        self.assertIn('self.table.get_children("")', SOURCE)
        self.assertIn('self.table.set(item, column)', SOURCE)


if __name__ == "__main__":
    unittest.main()
