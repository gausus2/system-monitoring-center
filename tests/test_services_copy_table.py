"""Services Copy table: copy only currently visible sorted rows."""
import ast
from pathlib import Path
import types
import unittest
from unittest import mock

source = (Path(__file__).resolve().parents[1] / "src" / "Services.py").read_text()
module = ast.parse(source)
cls = next(node for node in module.body if isinstance(node, ast.ClassDef) and node.name == "Services")
method = next(node for node in cls.body if isinstance(node, ast.FunctionDef)
              and node.name == "copy_visible_table")
isolated = ast.Module(body=[ast.ClassDef(name="FakeServices", bases=[],
    keywords=[], body=[method], decorator_list=[])], type_ignores=[])
ast.fix_missing_locations(isolated)
scope = {}
exec(compile(isolated, "<services-copy>", "exec"), scope)


class FakeTree:
    def __init__(self):
        self.items = {
            "service-b": ("b.service", {"state": "Failed", "pid": "0"}),
            "service-a": ("a.service", {"state": "Enabled", "pid": "42"}),
            "service-hidden": ("z.service", {"state": "Disabled", "pid": "5"}),
        }
        self.visible = ["service-b", "service-a"]
        self.displaycolumns = "#all"

    def __getitem__(self, key):
        if key == "displaycolumns":
            return self.displaycolumns
        if key == "columns":
            return ("state", "pid")
        raise KeyError(key)

    def heading(self, column, option):
        return {"#0": "Name", "state": "State",
                "pid": "Main PID"}[column]

    def get_children(self, parent=""):
        return tuple(self.visible)

    def item(self, item, option):
        assert option == "text"
        return self.items[item][0]

    def set(self, item, column):
        return self.items[item][1][column]


class ServicesCopyTableTests(unittest.TestCase):
    def setUp(self):
        self.gui = scope["FakeServices"]()
        self.gui.treeview = FakeTree()
        self.gui.tab_frame = types.SimpleNamespace(
            clipboard_clear=mock.Mock(), clipboard_append=mock.Mock())

    def test_filtered_sort_order_and_headings(self):
        self.gui.copy_visible_table()
        result = self.gui.tab_frame.clipboard_append.call_args.args[0]
        lines = result.splitlines()
        self.assertEqual(len(lines), 3)
        self.assertTrue(lines[0].startswith("Name"))
        self.assertIn("Main PID", lines[0])
        self.assertIn("b.service", lines[1])
        self.assertIn("a.service", lines[2])
        self.assertNotIn("z.service", result)
        self.assertIn("Failed", lines[1])

    def test_empty_filter_copies_only_headers(self):
        self.gui.treeview.visible = []
        self.gui.copy_visible_table()
        output = self.gui.tab_frame.clipboard_append.call_args.args[0]
        self.assertEqual(output.splitlines(), ["Name  State  Main PID"])

    def test_respects_display_columns(self):
        self.gui.treeview.displaycolumns = ("pid",)
        self.gui.copy_visible_table()
        result = self.gui.tab_frame.clipboard_append.call_args.args[0]
        self.assertIn("Name", result)
        self.assertIn("Main PID", result)
        self.assertNotIn("State", result)

    def test_copy_button_wired(self):
        self.assertIn('text="Copy table", command=self.copy_visible_table', source)
        self.assertIn('style="ServicesCopy.TButton"', source)


if __name__ == "__main__":
    unittest.main()
