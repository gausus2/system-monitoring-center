"""Check that SMART details remain read-only, scalable and copyable."""
import ast
from pathlib import Path
import unittest

source = (Path(__file__).resolve().parents[1] / "src" / "SmartctlTab.py").read_text(encoding="utf-8")
tree = ast.parse(source)
cls = next(node for node in tree.body
           if isinstance(node, ast.ClassDef) and node.name == "SmartctlTab")
methods = {node.name: node for node in cls.body
           if isinstance(node, ast.FunctionDef)}


class SmartDetailsUITests(unittest.TestCase):
    def test_font_scale_and_readonly(self):
        self.assertIn('state="disabled", wrap="word"', source)
        self.assertIn("font=Common.font_normal", source)
        self.assertNotIn("round(abs(original_size) * 1.2)", source)

    def test_treeview_uses_actual_gui_font(self):
        self.assertIn('"SmartDisk.Treeview", font=Common.font_normal', source)
        self.assertIn('"SmartDisk.Treeview.Heading", font=Common.font_normal', source)
        self.assertIn('style="SmartDisk.Treeview"', source)
        self.assertIn('Common.font_normal.metrics("linespace") + 4', source)

    def test_compact_columns_and_adjustable_details(self):
        self.assertIn("ttk.Panedwindow(self, orient=tk.VERTICAL)", source)
        self.assertIn("self.disk_panes.add(frame, weight=1)", source)
        self.assertIn("self.disk_panes.add(detail_frame, weight=3)", source)
        self.assertIn("self.disk_panes.sashpos(0,", source)
        self.assertIn('detail_frame, height=18, state="disabled"', source)
        self.assertIn('"NVMe wear %", "Media errs"', source)
        self.assertIn('widths = (86, 172, 64, 63, 53, 77, 78, 75, 62, 67, 78)', source)

    def test_nvme_endurance_and_error_columns(self):
        self.assertIn('"nvme_used", "nvme_errors"', source)
        self.assertIn('"NVMe wear %", "Media errs"', source)
        self.assertIn('smart.get("percentage_used")', source)
        self.assertIn('smart.get("media_errors")', source)

    def test_treeview_row_and_cell_copy(self):
        for method in ("_copy_table_row", "_copy_table_model",
                       "_copy_table_cell", "_show_table_menu"):
            self.assertIn(method, methods)
        self.assertIn('self.table.bind("<Control-c>"', source)
        self.assertIn('self.table.bind("<Button-3>"', source)
        self.assertIn('label="Copy cell"', source)
        self.assertIn('label="Copy model"', source)
        self.assertIn('label="Copy selected row"', source)

    def test_selection_copy_keyboard_and_context(self):
        for method in ("_copy_selected_details", "_copy_all_details",
                       "_select_all_details", "_show_details_menu"):
            self.assertIn(method, methods)
        for shortcut in ("<Control-c>", "<Control-a>", "<Button-3>"):
            self.assertIn(shortcut, source)
        self.assertIn("self.clipboard_append(value)", source)
        self.assertIn('text="Copy details"', source)


if __name__ == "__main__":
    unittest.main()
