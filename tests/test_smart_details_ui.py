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
        self.assertIn("round(abs(original_size) * 1.2)", source)
        self.assertIn('state="disabled", wrap="word"', source)
        self.assertIn("font=self.details_font", source)

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
