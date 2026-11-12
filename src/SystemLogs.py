"""System Logs main tab.

The source registry intentionally separates source selection from log rendering.
Additional file-backed providers can be added later without altering the
existing Services journal or the main window's tab implementation.
"""
import os
import tkinter as tk
from tkinter import ttk
import glob
import queue
import re
import subprocess
import threading

from . import Common
from .ServiceJournal import ServiceJournal
from . import JournalUnitTypes
from .FileLogs import FileLogViewer, available_logs
from . import FileLogBoot


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

        # Separate file-log dropdown below the original Log source control.
        style = ttk.Style(self)
        style.configure(
            "CompactLogs.TMenubutton", font=Common.font_normal,
            padding=(5, 2))
        self.file_button = ttk.Menubutton(
            toolbar, text="Other logs ▾", width=17,
            style="CompactLogs.TMenubutton")
        self.file_button.grid(row=1, column=2, sticky="ew", pady=(5, 0))
        self.file_menu = tk.Menu(self.file_button, tearoff=False)
        self.file_button.configure(menu=self.file_menu)
        self.file_menu.configure(postcommand=self._build_file_menu)
        self._file_path = None
        # This selects which filenames appear in Other logs, not which
        # lines are visible after opening a file.
        ttk.Label(toolbar, text="Files since:", font=Common.font_normal).grid(
            row=1, column=3, sticky="e", padx=(16, 6), pady=(5, 0))
        self.file_menu_boot = tk.StringVar(value="Current boot")
        self.file_boot_selector = ttk.Combobox(
            toolbar, textvariable=self.file_menu_boot, state="readonly",
            values=FileLogBoot.BOOT_LABELS, width=19, font=Common.font_normal)
        self.file_boot_selector.grid(
            row=1, column=4, sticky="e", pady=(5, 0))

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
        self.files = FileLogViewer(self)
        self.files.grid(row=1, column=0, sticky="nsew")
        self.files.grid_remove()
        self._loaded = False
        self._namespaces_discovered = False
        self._type_cache = {}
        self._type_pending = set()
        self._type_results = queue.Queue()
        self.after(200, self._poll_unit_types)

    def _build_file_menu(self):
        """Refresh available /var/log files when the menu opens."""
        self.file_menu.delete(0, "end")
        selection = self.file_menu_boot.get()
        try:
            paths = available_logs(selection)
        except (OSError, ValueError, RuntimeError, subprocess.TimeoutExpired) as error:
            self.file_menu.add_command(
                label="Boot history unavailable", state="disabled")
            return
        if not paths:
            self.file_menu.add_command(
                label="No log files modified in this boot period", state="disabled")
            return
        groups = {}
        for path in paths:
            directory = os.path.dirname(path)
            submenu = groups.get(directory)
            if submenu is None:
                submenu = tk.Menu(self.file_menu, tearoff=False)
                groups[directory] = submenu
            submenu.add_command(
                label=os.path.basename(path),
                command=lambda selected=path: self.open_file_log(selected),
            )
        for directory, submenu in sorted(groups.items()):
            self.file_menu.add_cascade(label=directory + "/", menu=submenu)

    def open_file_log(self, path):
        """Switch to a file without changing the Log source selection."""
        if path not in available_logs():
            return
        self._file_path = path
        self.file_button.configure(text="Other logs: " + os.path.basename(path))
        self.namespace.configure(state="disabled")
        self.journal.grid_remove()
        self.files.grid()
        self.files.open_file(path)
        self._loaded = True

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
        self._file_path = None
        self.file_button.configure(text="Other logs ▾")
        self.namespace.configure(state="readonly")
        self.files.grid_remove()
        self.journal.grid()
        if kind == "journal":
            selected = self.namespace.get()
            namespace = None if selected == "Default" else (
                "*" if selected == "All namespaces" else selected
            )
            self.journal.open_system(name, namespace=namespace)
            if name == "system":
                self._load_unit_types(namespace)
        self._loaded = True

    def _load_unit_types(self, namespace):
        """Enumerate available journal unit types outside the Tk event loop."""
        if namespace in self._type_cache:
            self.journal.set_available_unit_types(self._type_cache[namespace])
            return
        self.journal.set_available_unit_types([])
        if namespace in self._type_pending:
            return
        self._type_pending.add(namespace)

        def worker():
            found = JournalUnitTypes.discover_types(namespace)
            self._type_results.put((namespace, found))

        threading.Thread(target=worker, daemon=True).start()

    def _poll_unit_types(self):
        try:
            while True:
                namespace, found = self._type_results.get_nowait()
                self._type_pending.discard(namespace)
                self._type_cache[namespace] = found
                selected = self.namespace.get()
                current = (None if selected == "Default"
                           else "*" if selected == "All namespaces" else selected)
                if self.source.get() == "System journal" and current == namespace:
                    self.journal.set_available_unit_types(found)
        except queue.Empty:
            pass
        self.after(200, self._poll_unit_types)

    def activate(self):
        """Load the default source only once when the user first opens the tab."""
        if not self._loaded:
            if not self._namespaces_discovered:
                self.refresh_namespaces()
                self._namespaces_discovered = True
            self.select_source()

    def refresh(self):
        """Refresh the visible journal or file log (also bound to F5)."""
        if self._file_path:
            self.files.refresh()
        else:
            self.select_source()
