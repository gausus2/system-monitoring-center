"""SMART disk status tab (read-only)."""
import queue
import threading
import tkinter as tk
from tkinter import ttk

from . import Common
from . import SmartctlData


def format_size(size):
    if not isinstance(size, (int, float)):
        return "-"
    for suffix in ("B", "KiB", "MiB", "GiB", "TiB", "PiB"):
        if size < 1024 or suffix == "PiB":
            return "%.1f %s" % (size, suffix)
        size /= 1024
    return "-"


def format_hours(hours):
    """Present accumulated power-on hours as whole days and remaining hours."""
    if not isinstance(hours, (int, float)) or hours < 0:
        return "-"
    days, remaining = divmod(int(hours), 24)
    return "%d d %d h" % (days, remaining)


def format_writes(value, unit="Auto"):
    """Decimal GB/TB/PB. Unit selection changes display, not SMART data."""
    if not isinstance(value, (int, float)) or value < 0:
        return "-"
    factors = {"GB": 10**9, "TB": 10**12, "PB": 10**15}
    if unit == "Auto":
        unit = ("PB" if value >= factors["PB"] else
                "TB" if value >= factors["TB"] else "GB")
    if unit not in factors:
        return "-"
    return "%.2f %s" % (value / factors[unit], unit)


def details_text(disk, smart, writes_unit="Auto"):
    parts = [
        "Device: " + disk["path"],
        "Model: " + (smart.get("model") or disk["model"] or "-"),
        "Serial: " + (smart.get("serial") or "-"),
        "Transport: " + disk["transport"],
        "Size: " + format_size(disk["size"]),
        "Health: " + smart.get("health", "Unknown"),
        "Total writes: " + format_writes(smart.get("writes_bytes"), writes_unit),
    ]
    for key, label, suffix in (
        ("temperature", "Temperature", " °C"),
        ("hours", "Power-on time", ""),
        ("percentage_used", "NVMe endurance used", " %"),
        ("media_errors", "NVMe media errors", ""),
    ):
        value = smart.get(key)
        if value is not None:
            parts.append("%s: %s%s" % (
                label, format_hours(value) if key == "hours" else value, suffix))
    for name, value in smart.get("attributes", {}).items():
        if name not in ("Temperature", "Power-on hours"):
            parts.append("%s: %s" % (name, value))
    for message in smart.get("messages", []):
        parts.append("smartctl: " + message)
    return "\n".join(parts) + "\n"


class SmartctlTab(ttk.Frame):
    """Load once on activation; refresh via button or global F5."""
    def __init__(self, parent):
        super().__init__(parent, padding=6)
        self.columnconfigure(0, weight=1)
        self.rowconfigure(2, weight=1)
        self._loaded = False
        self._generation = 0
        self._queue = queue.Queue()
        self._rows = {}
        self._data = []

        toolbar = ttk.Frame(self)
        toolbar.grid(row=0, column=0, sticky="ew", pady=(0, 8))
        ttk.Label(toolbar, text="SMART disk health",
                  font=Common.font_bold).pack(side="left")
        style = ttk.Style(self)
        style.configure("SmartRefresh.TButton",
                        font=Common.font_normal, foreground="#65c76b",
                        padding=(5, 2))
        style.map("SmartRefresh.TButton",
                  foreground=[("disabled", "#777777"), ("!disabled", "#65c76b")])
        self.refresh_button = ttk.Button(
            toolbar, text="Apply / Refresh", command=self.refresh,
            style="SmartRefresh.TButton")
        self.refresh_button.pack(side="right")
        style.configure(
            "SmartAdmin.TButton", font=Common.font_normal, padding=(5, 2))
        self.admin_button = ttk.Button(
            toolbar, text="Read SMART (Admin)", command=self.refresh_admin,
            style="SmartAdmin.TButton")
        self.admin_button.pack(side="right", padx=(0, 8))
        ttk.Label(toolbar, text="Writes unit:", font=Common.font_normal).pack(
            side="right", padx=(0, 5))
        self.writes_unit_var = tk.StringVar(value="Auto")
        self.writes_unit_selector = ttk.Combobox(
            toolbar, textvariable=self.writes_unit_var, state="readonly",
            width=6, values=("Auto", "GB", "TB", "PB"),
            font=Common.font_normal)
        self.writes_unit_selector.pack(side="right", padx=(0, 12))
        self.writes_unit_selector.bind(
            "<<ComboboxSelected>>", self._on_writes_unit_changed)
        self.status = ttk.Label(
            self, text="SMART data is read-only. Some disks may require root access.",
            font=Common.font_normal)
        self.status.grid(row=1, column=0, sticky="w", pady=(0, 6))

        frame = ttk.Frame(self)
        frame.grid(row=2, column=0, sticky="nsew")
        frame.columnconfigure(0, weight=1)
        frame.rowconfigure(0, weight=1)
        columns = ("device", "model", "size", "health", "temp", "hours", "writes")
        self.table = ttk.Treeview(
            frame, columns=columns, show="headings", selectmode="browse")
        widths = (140, 240, 100, 125, 95, 110, 120)
        labels = ("Disk", "Model", "Size", "SMART", "Temp °C",
                  "Power-on", "Total writes")
        for column, label, width in zip(columns, labels, widths):
            self.table.heading(column, text=label)
            self.table.column(column, width=width, stretch=(column == "model"))
        self.table.grid(row=0, column=0, sticky="nsew")
        scroll = ttk.Scrollbar(frame, orient="vertical", command=self.table.yview)
        scroll.grid(row=0, column=1, sticky="ns")
        self.table.configure(yscrollcommand=scroll.set)
        self.table.bind("<<TreeviewSelect>>", self._select)

        detail_frame = ttk.Frame(self)
        detail_frame.grid(row=3, column=0, sticky="nsew", pady=(8, 0))
        detail_frame.columnconfigure(0, weight=1)
        ttk.Label(detail_frame, text="Disk details",
                  font=Common.font_bold).grid(row=0, column=0, sticky="w")
        self.details = tk.Text(
            detail_frame, height=9, state="disabled", wrap="word",
            font=Common.font_normal)
        self.details.grid(row=1, column=0, sticky="ew", pady=(4, 0))
        self.after(150, self._poll)

    def activate(self):
        if not self._loaded:
            self._loaded = True
            self.refresh()

    def refresh(self):
        self._refresh(admin=False)

    def refresh_admin(self):
        """Explicit user request to authenticate for read-only SMART data."""
        self._refresh(admin=True)

    def _refresh(self, admin=False):
        self._generation += 1
        generation = self._generation
        self.refresh_button.configure(state="disabled")
        self.admin_button.configure(state="disabled")
        self.status.configure(text=(
            "Reading SMART with administrator access (authentication may appear)…"
            if admin else "Scanning disks and reading SMART status…"))

        def worker():
            try:
                data = SmartctlData.collect(admin=admin)
                self._queue.put((generation, data, None))
            except (OSError, RuntimeError, ValueError) as error:
                self._queue.put((generation, [], str(error)))
        threading.Thread(target=worker, daemon=True).start()

    def _set_details(self, value):
        self.details.configure(state="normal")
        self.details.delete("1.0", "end")
        self.details.insert("end", value)
        self.details.configure(state="disabled")

    def _select(self, event=None):
        selected = self.table.selection()
        if selected and selected[0] in self._rows:
            disk, smart = self._rows[selected[0]]
            self._set_details(
                details_text(disk, smart, self.writes_unit_var.get()))

    def _on_writes_unit_changed(self, event=None):
        """Convert existing bytes instantly; do not rerun smartctl."""
        self._render_data()

    def _render_data(self):
        selected = self.table.selection()
        current = selected[0] if selected else None
        self.table.delete(*self.table.get_children())
        self._rows = {}
        for disk, smart in self._data:
            path = disk["path"]
            temp = smart.get("temperature")
            self.table.insert("", "end", iid=path, values=(
                path, smart.get("model") or disk["model"] or "-",
                format_size(disk["size"]), smart.get("health", "Unknown"),
                "-" if temp is None else str(temp),
                format_hours(smart.get("hours")),
                format_writes(smart.get("writes_bytes"),
                              self.writes_unit_var.get())))
            self._rows[path] = disk, smart
        if self._data:
            unavailable = sum(
                smart.get("health") == "Unavailable" for _, smart in self._data)
            self.status.configure(
                text="%d disk(s) · read-only · %d unavailable%s"
                % (len(self._data), unavailable,
                   " · select a disk for details" if unavailable else ""))
            self.table.selection_set(
                current if current in self._rows else self._data[0][0]["path"])
            self._select()
        else:
            self.status.configure(text="No physical disks discovered")
            self._set_details("")

    def _poll(self):
        try:
            while True:
                generation, data, error = self._queue.get_nowait()
                if generation != self._generation:
                    continue
                self.refresh_button.configure(state="normal")
                self.admin_button.configure(state="normal")
                if error:
                    self.status.configure(text="Unable to read disks: " + error)
                    continue
                self._data = data
                self._render_data()
        except queue.Empty:
            pass
        self.after(150, self._poll)

    def destroy(self):
        self._generation += 1
        super().destroy()
