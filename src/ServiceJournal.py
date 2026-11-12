"""Embedded, read-only systemd journal viewer for the Services tab."""
import datetime
import json
import queue
import subprocess
import threading
import tkinter as tk
import tkinter.font as tkfont
from tkinter import ttk

from . import Common


class ServiceJournal(ttk.Frame):
    """Filter and display a service's journal without blocking the Tk event loop."""

    def __init__(self, parent, system_mode=False):
        super().__init__(parent, padding=5)
        self.system_mode = system_mode
        self.log_source = "system"
        self.service = None
        self._generation = 0
        self._results = queue.Queue()
        self._records = []
        self._pending = None
        self._closed = False

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
        self.lines_var = tk.StringVar(value="500")
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
            "Last hour": "1 hour ago", "Last 24 hours": "24 hours ago",
            "Last 7 days": "7 days ago", "All available": None,
        }

        for column, (label, var, values, width) in enumerate((
            ("Boot", self.boot_var, tuple(self.boot_values), 15),
            ("Priority", self.level_var, tuple(self.level_values), 19),
            ("Time range", self.time_var, tuple(self.time_values), 19),
            ("Lines", self.lines_var, ("100", "500", "1000", "5000"), 7),
        )):
            box = ttk.Frame(controls)
            box.grid(row=0, column=column, sticky="w", padx=(0, 7))
            ttk.Label(box, text=label, font=Common.font_normal).pack(anchor="w")
            ttk.Combobox(box, textvariable=var, state="readonly",
                         values=values, width=width, font=Common.font_normal).pack(fill="x")

        self.refresh_button = ttk.Button(controls, text="Apply / Refresh", command=self.refresh)
        self.refresh_button.grid(row=0, column=4, sticky="s", padx=(1, 0))

        searchrow = ttk.Frame(self)
        searchrow.pack(fill="x", pady=(0, 5))
        ttk.Label(searchrow, text="Search in loaded messages:", font=Common.font_normal).pack(side="left", padx=(0, 6))
        searchentry = ttk.Entry(searchrow, textvariable=self.search_var, font=Common.font_normal)
        searchentry.pack(side="left", fill="x", expand=True)
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
        self.log.tag_configure("critical", foreground="#e05a60")
        self.log.tag_configure("warning", foreground="#dca640")
        self.log.tag_configure("info", foreground="#5594cc")
        self.log.tag_configure("normal", foreground="#9eacbc")
        self.log.tag_configure("error", foreground="#e05a60")

        self.after(100, self._poll_results)

    def open_system(self, source="system"):
        """Reuse the journal display for system-wide or kernel-only messages."""
        if source not in ("system", "kernel"):
            raise ValueError("Unknown journal source: " + str(source))
        self.system_mode = True
        self.log_source = source
        self.service = None
        self.heading.configure(text="System Journal" if source == "system"
                               else "Kernel Journal")
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

    def refresh(self):
        if self._closed or (not self.system_mode and not self.service):
            return
        self._generation += 1
        generation = self._generation
        service = self.service
        command = ["journalctl", "--namespace=*", "--no-pager", "--quiet",
                   "--output=json", "--lines", self.lines_var.get()]
        if self.system_mode:
            if self.log_source == "kernel":
                # Unlike --kernel, this field match does not imply current boot.
                command.append("_TRANSPORT=kernel")
        else:
            command.extend(["--unit", service])
        boot = self.boot_values.get(self.boot_var.get())
        level = self.level_values.get(self.level_var.get())
        since = self.time_values.get(self.time_var.get())
        if boot is not None:
            command.extend(["--boot", boot])
        if level:
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
                run = subprocess.run(command, capture_output=True, text=True,
                                     errors="replace", timeout=45, check=False)
                if run.returncode:
                    self._results.put((generation, None, (run.stderr.strip()
                                      or "journalctl failed (exit %s)" % run.returncode)))
                    return
                records = []
                for line in run.stdout.splitlines():
                    try:
                        entry = json.loads(line)
                    except (ValueError, TypeError):
                        continue
                    message = entry.get("MESSAGE", "")
                    if not isinstance(message, str):
                        message = str(message)
                    try:
                        priority = int(entry.get("PRIORITY", 6))
                    except (TypeError, ValueError):
                        priority = 6
                    try:
                        stamp = int(entry.get("__REALTIME_TIMESTAMP", "0")) / 1000000
                        when = datetime.datetime.fromtimestamp(stamp).strftime("%Y-%m-%d %H:%M:%S")
                    except (ValueError, OSError, OverflowError):
                        when = "unknown time"
                    records.append((when, max(0, min(7, priority)), message))
                self._results.put((generation, records, None))
            except (OSError, subprocess.TimeoutExpired) as error:
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
        shown = [record for record in self._records
                 if not needle or needle in record[2].casefold()]
        self.status.configure(text="%s / %s entries" % (len(shown), len(self._records)))
        self.log.configure(state="normal")
        self.log.delete("1.0", "end")
        if not shown:
            self.log.insert("end", "No journal entries match these filters.\n")
        else:
            names = ("EMERG", "ALERT", "CRIT", "ERROR", "WARN", "NOTICE", "INFO", "DEBUG")
            for when, priority, message in shown:
                tag = "critical" if priority <= 3 else ("warning" if priority == 4
                       else ("info" if priority >= 6 else "normal"))
                line = "%s  %-6s %s\n" % (when, names[priority],
                                           message.replace("\r", "").replace("\n", " ⏎ "))
                self.log.insert("end", line, tag)
        self.log.configure(state="disabled")
        self.log.yview_moveto(1.0)

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
