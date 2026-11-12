"""Regression tests for the Services Failed state filter without importing GUI."""
import ast
from pathlib import Path
import types
import unittest


def load_filter():
    source = (Path(__file__).resolve().parents[1] / "src" / "Services.py").read_text()
    module = ast.parse(source)
    service_class = next(node for node in module.body
                         if isinstance(node, ast.ClassDef) and node.name == "Services")
    method = next(node for node in service_class.body
                  if isinstance(node, ast.FunctionDef)
                  and node.name == "apply_state_filter")
    isolated = ast.Module(body=[ast.ClassDef(
        name="TestableServices", bases=[], keywords=[], body=[method],
        decorator_list=[])], type_ignores=[])
    ast.fix_missing_locations(isolated)
    namespace = {
        "_tr": lambda value: value,
        "Common": types.SimpleNamespace(sort_columns_on_every_loop=lambda _: None),
        "tk": types.SimpleNamespace(TclError=Exception),
    }
    exec(compile(isolated, "<services-filter>", "exec"), namespace)
    return namespace["TestableServices"]


class FakeTree:
    def __init__(self):
        self.attached = set()

    def get_children(self, parent=""):
        return tuple(self.attached)

    def detach(self, item):
        self.attached.discard(item)

    def reattach(self, item, parent, index):
        self.attached.add(item)


class FailedFilterTests(unittest.TestCase):
    def setUp(self):
        cls = load_filter()
        self.obj = cls()
        self.obj.treeview = FakeTree()
        self.obj.selected_data_rows = {
            "bad.service": ["bad.service"],
            "good.service": ["good.service"],
            "off.service": ["off.service"],
        }
        self.obj.piter_dict = {name: name for name in self.obj.selected_data_rows}
        self.obj.rows_data_dict_prev = {
            "bad.service": {"unit_file_state": "Enabled", "active_state": "Failed"},
            "good.service": {"unit_file_state": "Enabled", "active_state": "Active"},
            "off.service": {"unit_file_state": "Disabled", "active_state": "Inactive"},
        }
        self.obj.state_filter_var = types.SimpleNamespace(get=lambda: self.state)
        self.obj.searchentry_text_var = types.SimpleNamespace(get=lambda: self.search)
        self.search = ""

    def test_failed_is_active_state_not_unit_file_state(self):
        self.state = "Failed"
        self.obj.apply_state_filter()
        self.assertEqual(self.obj.treeview.attached, {"bad.service"})

    def test_other_filters_unchanged(self):
        self.state = "Enabled"
        self.obj.apply_state_filter()
        self.assertEqual(self.obj.treeview.attached,
                         {"bad.service", "good.service"})
        self.state = "All states"
        self.obj.apply_state_filter()
        self.assertEqual(self.obj.treeview.attached,
                         {"bad.service", "good.service", "off.service"})

    def test_failed_combines_with_search(self):
        self.state = "Failed"
        self.search = "good"
        self.obj.apply_state_filter()
        self.assertFalse(self.obj.treeview.attached)


if __name__ == "__main__":
    unittest.main()
