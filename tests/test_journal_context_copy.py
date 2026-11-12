"""Regression tests for read-only System/Kernel journal context copying."""
import ast
from pathlib import Path
import tkinter as tk
import types
import unittest
from unittest import mock

SOURCE = (Path(__file__).resolve().parents[1] / "src" / "ServiceJournal.py").read_text(encoding="utf-8")
tree = ast.parse(SOURCE)
service = next(n for n in tree.body if isinstance(n, ast.ClassDef)
               and n.name == "ServiceJournal")
method_names = {"_copy_journal_selection", "_select_all_journal",
                "_show_journal_menu"}
methods = [n for n in service.body if isinstance(n, ast.FunctionDef)
           and n.name in method_names]
isolated = ast.Module(body=[ast.ClassDef(
    name="JournalCopy", bases=[], keywords=[], body=methods,
    decorator_list=[])], type_ignores=[])
ast.fix_missing_locations(isolated)
namespace = {"tk": types.SimpleNamespace(TclError=tk.TclError)}
exec(compile(isolated, "<journal-copy>", "exec"), namespace)
JournalCopy = namespace["JournalCopy"]


class JournalCopyTests(unittest.TestCase):
    def test_explicit_context_menu_wired_to_journal(self):
        self.assertIn('self.log.bind("<Button-3>", self._show_journal_menu)', SOURCE)
        self.assertIn('label="Copy", command=self._copy_journal_selection', SOURCE)
        self.assertIn('label="Select all", command=self._select_all_journal', SOURCE)

    def test_copy_selection_to_clipboard(self):
        obj = JournalCopy()
        obj.log = mock.Mock()
        obj.log.get.return_value = "Selected journal text\n"
        obj.clipboard_clear = mock.Mock()
        obj.clipboard_append = mock.Mock()
        obj._copy_journal_selection()
        obj.log.get.assert_called_once_with("sel.first", "sel.last")
        obj.clipboard_clear.assert_called_once_with()
        obj.clipboard_append.assert_called_once_with("Selected journal text\n")

    def test_copy_with_no_selection_does_not_clobber_clipboard(self):
        obj = JournalCopy()
        obj.log = mock.Mock()
        obj.log.get.side_effect = tk.TclError("no selection")
        obj.clipboard_clear = mock.Mock()
        obj.clipboard_append = mock.Mock()
        obj._copy_journal_selection()
        obj.clipboard_clear.assert_not_called()
        obj.clipboard_append.assert_not_called()

    def test_context_menu_preserves_selection(self):
        obj = JournalCopy()
        obj.log = mock.Mock()
        obj.log.tag_ranges.return_value = ("1.0", "1.5")
        obj.log_menu = mock.Mock()
        event = types.SimpleNamespace(x_root=150, y_root=300)
        self.assertEqual(obj._show_journal_menu(event), "break")
        obj.log_menu.entryconfigure.assert_called_once_with(
            "Copy", state="normal")
        obj.log_menu.tk_popup.assert_called_once_with(150, 300)
        obj.log_menu.grab_release.assert_called_once()
        obj.log.tag_remove.assert_not_called()

    def test_select_all_preserves_read_only_text(self):
        obj = JournalCopy()
        obj.log = mock.Mock()
        obj._select_all_journal()
        obj.log.tag_add.assert_called_once_with("sel", "1.0", "end-1c")
        obj.log.mark_set.assert_called_once_with("insert", "1.0")
        obj.log.focus_set.assert_called_once()


if __name__ == "__main__":
    unittest.main()
