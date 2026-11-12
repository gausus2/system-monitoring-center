"""System Logs main tab.

The source registry intentionally separates source selection from log rendering.
Additional file-backed providers can be added later without altering the
existing Services journal or the main window's tab implementation.
"""
from tkinter import ttk
import glob
import re
import subprocess

from . import Common
from .ServiceJournal import ServiceJournal


class SystemLogs(ttk.Frame):
    """Standalone system log tab using the shared journal renderer."""

    # Currently implemented sources. Future sources may have other providers.
    SOURCES = {
        "System journal": ("journal", "system"),
        "Kernel journal": ("journal", "kernel"),
    }

    @staticmethod
    def discover_namespaces():
        """Find named journals from journal directories and journald instances."""
        found = set()
        for root in ("/var/log/journal", "/run/log/journal"):
            for path in glob.glob(root + "/*.*"):
                name = path.rsplit("/", 1)[-1]
                if re.fullmatch(r"[0-9a-fA-F]{32}\.[A-Za-z0-9_.-]+", name):
                    found.add(name.split(".", 1)[1])
        try:
            result = subprocess.run(
                ["systemctl", "list-units", "--all", "--type=service",
                 "--plain", "--no-legend", "systemd-journald@*.service"],
                capture_output=True, text=True, timeout=2, check=False,
            )
            for line in result.stdout.splitlines():
                unit = line.split(None, 1)[0] if line.strip() else ""
                match = re.fullmatch(r"systemd-journald@([A-Za-z0-9_.-]+)\.service", unit)
                if match:
                    found.add(match.group(1))
        except (OSError, subprocess.TimeoutExpired):
            pass
        return sorted(found, key=str.casefold)

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

        ttk.Label(toolbar, text="Namespace:", font=Common.font_normal).grid(
            row=0, column=3, sticky="e", padx=(16, 6))
        self.namespace = ttk.Combobox(
            toolbar, state="readonly", width=18, font=Common.font_normal,
        )
        self.namespace.grid(row=0, column=4, sticky="e")
        self.namespace["values"] = ("Default", "All namespaces")
        self.namespace.set("Default")
        self.namespace.bind("<<ComboboxSelected>>", self.select_source)

        self.journal = ServiceJournal(self, system_mode=True)
        self.journal.grid(row=1, column=0, sticky="nsew")
        self._loaded = False
        self._namespaces_discovered = False

    def refresh_namespaces(self):
        """Refresh selectable names without changing the current selection."""
        selected = self.namespace.get()
        names = self.discover_namespaces()
        options = ["Default", "All namespaces", *names]
        self.namespace["values"] = options
        if selected not in options:
            self.namespace.set("Default")

    def select_source(self, event=None):
        """Dispatch to a provider; current providers share ServiceJournal."""
        kind, name = self.SOURCES[self.source.get()]
        if kind == "journal":
            selected = self.namespace.get()
            namespace = None if selected == "Default" else (
                "*" if selected == "All namespaces" else selected
            )
            self.journal.open_system(name, namespace=namespace)
        self._loaded = True

    def activate(self):
        """Load the default source only once when the user first opens the tab."""
        if not self._loaded:
            if not self._namespaces_discovered:
                self.refresh_namespaces()
                self._namespaces_discovered = True
            self.select_source()

    def refresh(self):
        """Refresh current source (also used by the main window's F5 key)."""
        self.select_source()
