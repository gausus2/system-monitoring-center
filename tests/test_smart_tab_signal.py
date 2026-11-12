"""Guard that SMART main tab has a click callback, not just a widget."""
import ast
from pathlib import Path
import unittest

MAIN = Path(__file__).resolve().parents[1] / "src" / "MainWindow.py"


class SmartTabSignalTests(unittest.TestCase):
    def test_main_tab_switch_signal_is_connected(self):
        tree = ast.parse(MAIN.read_text(encoding="utf-8"))
        cls = next(node for node in tree.body
                   if isinstance(node, ast.ClassDef) and node.name == "MainWindow")
        signal_methods = [
            method for method in cls.body
            if isinstance(method, (ast.FunctionDef, ast.AsyncFunctionDef))
            and any(isinstance(node, ast.Call)
                    and isinstance(node.func, ast.Attribute)
                    and node.func.attr == "config"
                    and isinstance(node.func.value, ast.Attribute)
                    and node.func.value.attr == "smartctl_tb"
                    and any(kw.arg == "command"
                            and isinstance(kw.value, ast.Attribute)
                            and kw.value.attr == "main_gui_tab_switch"
                            for kw in node.keywords)
                    for node in ast.walk(method))
        ]
        self.assertTrue(signal_methods, "SMART tab button needs a command callback")


if __name__ == "__main__":
    unittest.main()
