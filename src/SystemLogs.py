"""System Logs main tab.

The source registry intentionally separates source selection from log rendering.
Additional file-backed providers can be added later without altering the
existing Services journal or the main window's tab implementation.
"""
from tkinter import ttk

from . import Common
from .ServiceJournal import ServiceJournal


class SystemLogs(ttk.Frame):
    """Standalone system log tab using the shared journal renderer."""

    # Currently implemented sources. Future sources may have other providers.
    SOURCES = {
        "System journal": ("journal", "system"),
        "Kernel journal": ("journal", "kernel"),
    }

    def __init__(self, parent):
        super().__init__(parent, padding=4)
        self.columnconfigure(0, weight=1)
        self.rowconfigure(1, weight=1)

        toolbar = ttk.Frame(self)
        toolbar.grid(row=0, column=0, sticky="ew", pady=(0, 8))
        toolbar.columnconfigure(1, weight=1)

        ttk.Label(toolbar, text="System Logs", font=Common.font_bold).grid(
            row=0, column=0, sticky="w", padx=(0, 20))
        ttk.Label(toolbar, text="Log source:", font=Common.font_normal).grid(
            row=0, column=1, sticky="e", padx=(0, 6))
        self.source = ttk.Combobox(
            toolbar, state="readonly", width=21, font=Common.font_normal,
            values=tuple(self.SOURCES),
        )
        self.source.grid(row=0, column=2, sticky="e")
        self.source.set("System journal")
        self.source.bind("<<ComboboxSelected>>", self.select_source)

        self.journal = ServiceJournal(self, system_mode=True)
        self.journal.grid(row=1, column=0, sticky="nsew")
        self._loaded = False

    def select_source(self, event=None):
        """Dispatch to a provider; current providers share ServiceJournal."""
        kind, name = self.SOURCES[self.source.get()]
        if kind == "journal":
            self.journal.open_system(name)
        self._loaded = True

    def activate(self):
        """Load the default source only once when the user first opens the tab."""
        if not self._loaded:
            self.select_source()

    def refresh(self):
        """Refresh current source (also used by the main window's F5 key)."""
        self.select_source()
