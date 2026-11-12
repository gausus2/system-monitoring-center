"""Embedded, read-only systemd journal viewer for the Services tab."""
import datetime
import json
import queue
import re
import subprocess
import threading
import tkinter as tk
import tkinter.font as tkfont
from tkinter import ttk

from . import Common
from . import WarpJournal
from . import JournalUnitTypes
from . import JournalColors


class ServiceJournal(ttk.Frame):
    """Filter and display a service's journal without blocking the Tk event loop."""

    def __init__(self, parent, system_mode=False):
        super().__init__(parent, padding=5)
        self.system_mode = system_mode
        self.log_source = "system"
        self.namespace = "*"  # Existing Services behavior remains all namespaces.
        self.service = None
        self._generation = 0
        self._results = queue.Queue()
        self._records = []
        self._last_refresh = None
        self._pending = None
        self._closed = False
        self.advanced_colors = False

        # Match the application font scale while keeping the log monospaced.
        fixed_family = tkfont.nametofont("TkFixedFont").actual("family")
        self.log_font = tkfont.Font(
            family=fixed_family, size=Common.font_normal.actual("size")
        )

        header = ttk.Frame(self)
        header.pack(fill="x", pady=(0, 5))
        self.heading = ttk.Label(header, text="Service Journal", font=Common.font_bold)
        self.heading.pack(side="left")
        self.close_button = ttk.Button(header, text="Close", command=self.close, width=8)
        if not self.system_mode:
            self.close_button.pack(side="right")

        controls = ttk.Frame(self)
        controls.pack(fill="x", pady=(0, 5))

        self.boot_var = tk.StringVar(value="Current boot")
        self.level_var = tk.StringVar(value="All levels")
        self.time_var = tk.StringVar(value="Last 24 hours")
        self.lines_var = tk.StringVar(value="Last 500")
        self.unit_type_var = tk.StringVar(value="All types")
        self.search_var = tk.StringVar()
        self.boot_values = {
            "Current boot": "-0", "Previous boot": "-1", "All boots": None,
        }
        self.level_values = {
            "All levels": None, "Emergency": "emerg", "Alert": "alert",
            "Critical": "crit", "Error and higher": "err",
            "Warning and higher": "warning", "Info and higher": "info",
            "Debug (all)": "debug",
        }
        self.time_values = {
            "Last minute": "1 minute ago", "Last 10 minutes": "10 minutes ago",
            "Last hour": "1 hour ago", "Last 24 hours": "24 hours ago",
            "Last 7 days": "7 days ago", "All available": None,
        }

        for column, (label, var, values, width) in enumerate((
            ("Boot", self.boot_var, tuple(self.boot_values), 15),
            ("Priority", self.level_var, tuple(self.level_values), 19),
            ("Time range", self.time_var, tuple(self.time_values), 19),
            ("Lines", self.lines_var, (
                "Last 100", "Last 500", "Last 1000", "Last 5000",
                "First 100", "First 500", "First 1000", "First 5000"), 12),
        )):
            box = ttk.Frame(controls)
            box.grid(row=0, column=column, sticky="w", padx=(0, 7))
            ttk.Label(box, text=label, font=Common.font_normal).pack(anchor="w")
            selector = ttk.Combobox(box, textvariable=var, state="readonly",
                                    values=values, width=width, font=Common.font_normal)
            selector.pack(fill="x")
            if label == "Lines":
                selector.bind("<<ComboboxSelected>>", self.on_lines_selected)

        if self.system_mode:
            typebox = ttk.Frame(controls)
            typebox.grid(row=0, column=4, sticky="w", padx=(0, 7))
            ttk.Label(typebox, text="Type", font=Common.font_normal).pack(anchor="w")
            self.unit_type_selector = ttk.Combobox(
                typebox, textvariable=self.unit_type_var, state="readonly",
                values=("All types",) + tuple(
                    item.capitalize() for item in JournalUnitTypes.COMMON_TYPES),
                width=13, font=Common.font_normal,
            )
            self.unit_type_selector.pack(fill="x")
            refresh_column = 5
        else:
            self.unit_type_selector = None
            refresh_column = 4

        style = ttk.Style(self)
        style.configure(
            "JournalRefresh.TButton", font=Common.font_normal,
            foreground="#65c76b", padding=(5, 2))
        style.map(
            "JournalRefresh.TButton",
            foreground=[("disabled", "#777777"), ("!disabled", "#65c76b")])
        style.configure(
            "JournalColors.TButton", font=Common.font_normal,
            padding=(5, 2))
        self.refresh_button = ttk.Button(
            controls, text="Apply / Refresh", command=self.refresh,
            style="JournalRefresh.TButton")
        self.refresh_button.grid(row=0, column=refresh_column, sticky="s", padx=(1, 0))
        if self.system_mode:
            self.color_button = ttk.Button(
                controls, text="Colors: Current",
                style="JournalColors.TButton",
                command=self.toggle_journal_colors)
            self.color_button.grid(
                row=1, column=0, columnspan=2, sticky="w", pady=(6, 0))
        else:
            self.color_button = None

        searchrow = ttk.Frame(self)
        searchrow.pack(fill="x", pady=(0, 5))
        search_label = ("Search journal (Enter / Apply):" if self.system_mode
                        else "Search in loaded messages:")
        ttk.Label(searchrow, text=search_label, font=Common.font_normal).pack(side="left", padx=(0, 6))
        searchentry = ttk.Entry(searchrow, textvariable=self.search_var, font=Common.font_normal)
        searchentry.pack(side="left", fill="x", expand=True)
        if self.system_mode:
            # Search across journal entries only when explicitly submitted.
            searchentry.bind("<Return>", lambda event: self.refresh())
        else:
            self.search_var.trace_add("write", self._search_changed)
        self.status = ttk.Label(searchrow, text="Ready" if self.system_mode else "Choose a service", font=Common.font_normal)
        self.status.pack(side="right", padx=(8, 0))

        logframe = ttk.Frame(self)
        logframe.pack(fill="both", expand=True)
        logframe.columnconfigure(0, weight=1)
        logframe.rowconfigure(0, weight=1)
        self.log = tk.Text(logframe, wrap="none", state="disabled", height=11,
                           font=self.log_font, takefocus=True)
        self.log.grid(row=0, column=0, sticky="nsew")
        vertical = ttk.Scrollbar(logframe, orient="vertical", command=self.log.yview)
        vertical.grid(row=0, column=1, sticky="ns")
        horizontal = ttk.Scrollbar(logframe, orient="horizontal", command=self.log.xview)
        horizontal.grid(row=1, column=0, sticky="ew")
        self.log.configure(yscrollcommand=vertical.set, xscrollcommand=horizontal.set)
        # Explicit menu for the read-only Text widget; relying on a
        # theme/system context menu does not reliably copy selections.
        self.log_menu = tk.Menu(self.log, tearoff=False)
        self.log_menu.add_command(
            label="Copy", command=self._copy_journal_selection)
        self.log_menu.add_command(
            label="Select all", command=self._select_all_journal)
        self.log.bind("<Button-3>", self._show_journal_menu)
        self.log.tag_configure("critical", foreground="#e05a60")
        self.log.tag_configure("warning", foreground="#dca640")
        self.log.tag_configure("info", foreground="#cccccc")
        self.log.tag_configure("normal", foreground="#cccccc")
        self.log.tag_configure("sender", foreground="#65c76b")
        self.log.tag_configure("error", foreground="#e05a60")
        self.log.tag_configure("boot", foreground="#a3b5cb")
        # Bold the timestamp without overriding the severity color.
        bold_log_font = self.log_font.copy()
        bold_log_font.configure(weight="bold")
        self.timestamp_font = bold_log_font
        for name, color in (
            ("timestamp-normal", "#cccccc"),
            ("timestamp-warning", "#dca640"),
            ("timestamp-critical", "#e05a60"),
        ):
            self.log.tag_configure(name, foreground=color, font=self.timestamp_font)
        if self.system_mode:
            for style, color in JournalColors.STYLES.items():
                self.log.tag_configure("advanced-" + style, foreground=color)
            self.log.tag_configure("advanced-timestamp", font=self.timestamp_font)

        self.after(100, self._poll_results)

    def _copy_journal_selection(self):
        """Copy the selection regardless of Text's disabled state."""
        try:
            value = self.log.get("sel.first", "sel.last")
        except tk.TclError:
            return
        self.clipboard_clear()
        self.clipboard_append(value)

    def _select_all_journal(self):
        self.log.tag_add("sel", "1.0", "end-1c")
        self.log.mark_set("insert", "1.0")
        self.log.focus_set()

    def _show_journal_menu(self, event):
        # Right-click should preserve the text selection made with
        # the left mouse button.
        self.log_menu.entryconfigure(
            "Copy", state="normal" if self.log.tag_ranges("sel")
            else "disabled")
        try:
            self.log_menu.tk_popup(event.x_root, event.y_root)
        finally:
            self.log_menu.grab_release()
        return "break"

    def toggle_journal_colors(self):
        """Switch colors without rereading the journal."""
        if not self.system_mode:
            return
        self.advanced_colors = not self.advanced_colors
        self.color_button.configure(
            text=("Colors: Log advanced (Kate)" if self.advanced_colors
                  else "Colors: Current"))
        self._render_records()

    def set_available_unit_types(self, types):
        """Merge journal-discovered unit types with the common predefined ones."""
        if self.unit_type_selector is None:
            return
        all_types = list(JournalUnitTypes.COMMON_TYPES)
        all_types.extend(
            item for item in types
            if item not in all_types
            and JournalUnitTypes.unit_glob(item)
        )
        self.unit_type_selector.configure(
            values=("All types",) + tuple(item.capitalize() for item in all_types)
        )

    def open_system(self, source="system", namespace=None):
        """Reuse the journal display for system-wide or kernel-only messages."""
        if source not in ("system", "kernel"):
            raise ValueError("Unknown journal source: " + str(source))
        self.system_mode = True
        self.log_source = source
        if source == "kernel":
            self.unit_type_var.set("All types")
        if self.unit_type_selector is not None:
            self.unit_type_selector.configure(
                state="readonly" if source == "system" else "disabled"
            )
        self.namespace = namespace  # None means default; "*" means all.
        self.service = None
        heading = "System Journal" if source == "system" else "Kernel Journal"
        if source == "system" and namespace == "warp":
            heading += " — Warp levels"
        self.heading.configure(text=heading)
        self.refresh()

    def open_service(self, service, errors=False):
        if not service or not service.endswith(".service"):
            return
        changed = self.service != service
        self.service = service
        self.heading.configure(text="Service Journal — " + service)
        if errors:
            self.level_var.set("Error and higher")
            self.boot_var.set("Current boot")
        elif changed:
            self.level_var.set("All levels")
        self.refresh()

    def on_lines_selected(self, event=None):
        """Default First N selections to the full available time range."""
        if self.lines_var.get().startswith("First "):
            self.time_var.set("All available")

    def refresh(self):
        if self._closed or (not self.system_mode and not self.service):
            return
        self._generation += 1
        generation = self._generation
        service = self.service
        count, first = WarpJournal.parse_line_selection(self.lines_var.get())
        warp_mode = (self.system_mode and self.log_source == "system"
                     and self.namespace == "warp")
        type_name = (self.unit_type_var.get().lower()
                     if self.system_mode and self.log_source == "system"
                     else "all types")
        unit_glob = (None if type_name == "all types"
                     else JournalUnitTypes.unit_glob(type_name))
        command = ["journalctl", "--no-pager", "--quiet", "--output=json"]
        if not warp_mode:
            # journalctl -n +N selects the first N matching entries.
            command.extend(["--lines", ("+" if first else "") + str(count)])
        namespace = self.namespace if self.system_mode else "*"
        if namespace is not None:
            command.append("--namespace=" + namespace)
        if self.system_mode:
            if unit_glob is not None:
                command.append("--unit=" + unit_glob)
            if self.log_source == "kernel":
                # Unlike --kernel, this field match does not imply current boot.
                command.append("_TRANSPORT=kernel")
            query = self.search_var.get().strip()
            if query:
                if (self.log_source == "system"
                        and JournalUnitTypes.unit_type(query) is not None):
                    # -u includes manager messages about the unit.
                    if unit_glob is not None:
                        # Avoid OR semantics of two --unit flags. An exact
                        # unit selection is already narrower than its type.
                        if JournalUnitTypes.unit_type(query) != type_name:
                            self._records = []
                            self._last_refresh = datetime.datetime.now().strftime("%H:%M:%S")
                            self._render_records()
                            return
                        command.remove("--unit=" + unit_glob)
                    command.append("--unit=" + query)
                else:
                    # Search MESSAGE on disk before limiting the results.
                    command.append("--grep=" + re.escape(query))
                    command.append("--case-sensitive=no")
        else:
            command.extend(["--unit", service])
        boot = self.boot_values.get(self.boot_var.get())
        level = self.level_values.get(self.level_var.get())
        since = self.time_values.get(self.time_var.get())
        if boot is not None:
            command.extend(["--boot", boot])
        if level and not warp_mode:
            command.extend(["--priority", level])
        if since:
            command.extend(["--since", since])
        self._records = []
        self.refresh_button.configure(state="disabled")
        self.status.configure(text="Loading…")
        title = ("kernel" if self.log_source == "kernel" else "system") if self.system_mode else service
        self._set_text("Loading journal for " + title + "…\n")

        def worker():
            try:
                if warp_mode:
                    # Reverse-stream until N matching effective priorities.
                    # Never read an unbounded Warp journal into Tkinter.
                    try:
                        entries = WarpJournal.read_entries(
                            command, count, level, first=first)
                    except RuntimeError as error:
                        if JournalUnitTypes.empty_unit_filter_result(
                                command, 1, str(error)):
                            entries = []
                        else:
                            raise
                else:
                    run = subprocess.run(command, capture_output=True, text=True,
                                         errors="replace", timeout=45, check=False)
                    no_matches = (
                        run.returncode == 1
                        and any(arg.startswith("--grep=") for arg in command)
                        and not run.stdout.strip() and not run.stderr.strip()
                    )
                    no_unit_data = JournalUnitTypes.empty_unit_filter_result(
                        command, run.returncode, run.stderr, run.stdout)
                    if run.returncode and not (no_matches or no_unit_data):
                        self._results.put((generation, None, (run.stderr.strip()
                                          or "journalctl failed (exit %s)" % run.returncode)))
                        return
                    entries = []
                    for line in run.stdout.splitlines():
                        try:
                            entries.append(json.loads(line))
                        except (ValueError, TypeError):
                            continue
                # journalctl --grep combined with --lines implies reverse
                # output; normalize before showing newest entries at bottom.
                entries.sort(key=WarpJournal.timestamp_microseconds)
                records = []
                for entry in entries:
                    message = entry.get("MESSAGE", "")
                    if isinstance(message, list) and all(
                            isinstance(value, int) and 0 <= value <= 255
                            for value in message):
                        # journalctl --output=json represents binary MESSAGE
                        # fields as arrays of byte values (e.g. Warp logs).
                        message = bytes(message).decode("utf-8", errors="replace")
                    elif not isinstance(message, str):
                        message = str(message)
                    # Do not interpret embedded terminal control sequences
                    # as source text; this viewer applies its own colors.
                    message = re.sub(r"\x1b\[[0-?]*[ -/]*[@-~]", "", message)
                    try:
                        priority = int(entry.get("_VIEW_PRIORITY", entry.get("PRIORITY", 6)))
                    except (TypeError, ValueError):
                        priority = 6
                    try:
                        stamp = int(entry.get("__REALTIME_TIMESTAMP", "0")) / 1000000
                        when = datetime.datetime.fromtimestamp(stamp).strftime("%Y-%m-%d %H:%M:%S")
                    except (ValueError, OSError, OverflowError):
                        when = "unknown time"
                    sender = JournalUnitTypes.display_sender(entry)
                    # Preserve boot boundaries when displaying multiple boots.
                    boot_id = entry.get("_BOOT_ID") or ""
                    if not isinstance(boot_id, str):
                        boot_id = str(boot_id)
                    records.append((when, max(0, min(7, priority)),
                                    sender, message, boot_id))
                self._results.put((generation, records, None))
            except (OSError, RuntimeError, subprocess.TimeoutExpired) as error:
                self._results.put((generation, None, str(error)))
        threading.Thread(target=worker, daemon=True).start()

    def _poll_results(self):
        if self._closed:
            return
        try:
            while True:
                generation, records, error = self._results.get_nowait()
                if generation != self._generation:
                    continue  # Ignore stale results when service/filters change.
                self.refresh_button.configure(state="normal")
                if error:
                    self.status.configure(text="Error")
                    self._set_text("Unable to read journal:\n" + error + "\n", "error")
                else:
                    self._records = records
                    self._last_refresh = datetime.datetime.now().strftime("%H:%M:%S")
                    self._render_records()
        except queue.Empty:
            pass
        self.after(100, self._poll_results)

    def _search_changed(self, *_):
        if self._pending is not None:
            self.after_cancel(self._pending)
        self._pending = self.after(180, self._render_records)

    def _render_records(self):
        self._pending = None
        needle = self.search_var.get().casefold()
        shown = (list(self._records) if self.system_mode else
                 [record for record in self._records
                  if not needle or needle in record[2].casefold()
                  or needle in record[3].casefold()])
        status = "%s / %s entries" % (len(shown), len(self._records))
        if self._last_refresh:
            status += " · Updated " + self._last_refresh
        self.status.configure(text=status)
        self.log.configure(state="normal")
        self.log.delete("1.0", "end")
        if not shown:
            self.log.insert("end", "No journal entries match these filters.\n")
        else:
            names = ("EMERG", "ALERT", "CRIT", "ERROR", "WARN", "NOTICE", "INFO", "DEBUG")
            previous_boot = None
            for when, priority, sender, message, boot_id in shown:
                if self.boot_var.get() == "All boots" and boot_id:
                    if previous_boot is not None and boot_id != previous_boot:
                        self.log.insert("end", "-- Boot " + boot_id + " --\n", "boot")
                    previous_boot = boot_id
                tag = "critical" if priority <= 3 else ("warning" if priority == 4
                       else ("info" if priority >= 6 else "normal"))
                # Keep warning/error lines uniformly colored. For normal
                # priorities, color only the identifier/PID in green.
                timestamp_tag = ("timestamp-critical" if priority <= 3
                                 else "timestamp-warning" if priority == 4
                                 else "timestamp-normal")
                if self.system_mode and self.advanced_colors:
                    line, base, spans = JournalColors.advanced_line(
                        when, priority, sender, message)
                    start = self.log.index("end-1c")
                    self.log.insert("end", line, "advanced-" + base)
                    for begin, end, style in spans:
                        self.log.tag_add(
                            "advanced-" + style,
                            f"{start}+{begin}c", f"{start}+{end}c")
                    continue
                self.log.insert("end", when, timestamp_tag)
                prefix = "  %-6s " % names[priority]
                sender_part = "%-26s " % sender
                message_part = message.replace("\r", "").replace("\n", " ⏎ ") + "\n"
                self.log.insert("end", prefix, tag)
                self.log.insert("end", sender_part,
                                tag if priority <= 4 else "sender")
                self.log.insert("end", message_part, tag)
        self.log.configure(state="disabled")
        self.log.yview_moveto(0.0 if self.lines_var.get().startswith("First ") else 1.0)

    def _set_text(self, text, tag=None):
        self.log.configure(state="normal")
        self.log.delete("1.0", "end")
        if tag:
            self.log.insert("end", text, tag)
        else:
            self.log.insert("end", text)
        self.log.configure(state="disabled")

    def close(self):
        self._generation += 1
        if callable(getattr(self, "close_callback", None)):
            self.close_callback()
        else:
            self.grid_remove()
        self.refresh_button.configure(state="normal")

    def destroy(self):
        self._closed = True
        self._generation += 1
        if self._pending is not None:
            self.after_cancel(self._pending)
        super().destroy()
