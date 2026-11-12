"""Read-only, bounded text-file viewer for selectable /var/log files."""
import collections
import datetime
import os
import queue
import re
import threading
import tkinter as tk
import tkinter.font as tkfont
from tkinter import ttk

from . import Common
from . import LogHighlight
from . import FileLogBoot


ROOT = "/var/log"
SKIP_EXTENSIONS = (".gz", ".xz", ".bz2", ".zst", ".journal", ".journal~",
                   ".sqlite", ".db", ".html", ".png", ".jpg")
SKIP_NAMES = {"wtmp", "btmp", "lastlog", "faillog", "utmp", "seq_highwater"}
SKIP_DIRS = {"journal", "private"}
MAX_SCAN_BYTES = 64 * 1024 * 1024


class NoRecognizableTimestamps(ValueError):
    """The requested boot filter cannot be applied to an undated file."""




def available_logs():
    """Discover current regular text logs, including in subdirectories.

    Paths are derived from /var/log and validated again at read time. Do not
    traverse symlinked directories or follow individual file symlinks.
    """
    result = []
    for directory, dirs, files in os.walk(ROOT, followlinks=False):
        depth = os.path.relpath(directory, ROOT).count(os.sep)
        dirs[:] = sorted(d for d in dirs if d not in SKIP_DIRS and
                         not os.path.islink(os.path.join(directory, d))
                         and depth < 5)
        for name in sorted(files):
            if (name in SKIP_NAMES or name.endswith(SKIP_EXTENSIONS)
                    or re.search(r"\.\d+(?:\.[A-Za-z0-9]+)?$", name)):
                continue
            path = os.path.join(directory, name)
            if not os.path.isfile(path) or os.path.islink(path):
                continue
            result.append(path)
            if len(result) >= 300:
                return result
    return result


def read_lines(path, count, first=False, needle="", boot="All available"):
    """Search before limiting lines, with bounded memory and a scan limit."""
    path = os.path.abspath(path)
    if not path.startswith(ROOT + os.sep) or os.path.islink(path):
        raise ValueError("Log file must be a regular file under /var/log")
    if not os.path.isfile(path):
        raise ValueError("Selected log file no longer exists")
    match = needle.casefold()
    window = FileLogBoot.boot_window(boot)
    reference = datetime.datetime.fromtimestamp(os.path.getmtime(path)).astimezone()
    if window is not None:
        reference = window[1] or reference
    recognized = 0
    last_date = None
    found = collections.deque(maxlen=count) if not first else []
    scanned = 0
    truncated = False
    with open(path, "rb") as stream:
        if b"\x00" in stream.read(4096):
            raise ValueError("Binary log file; use a suitable log-specific viewer")
        size = stream.seek(0, os.SEEK_END)
        if not first and size > MAX_SCAN_BYTES:
            # Last N must scan the newest bytes, not the oldest bytes.
            stream.seek(size - MAX_SCAN_BYTES)
            stream.readline()  # Discard an incomplete line at the boundary.
            truncated = True
        else:
            stream.seek(0)
        for raw_line in stream:
            scanned += len(raw_line)
            if scanned > MAX_SCAN_BYTES:
                truncated = True
                break
            line = raw_line.decode("utf-8", errors="replace").rstrip("\r\n")
            if window is not None:
                stamp = FileLogBoot.timestamp(line, reference)
                if stamp is not None:
                    recognized += 1
                    last_date = stamp
                if last_date is None or not (
                        window[0] <= last_date
                        and (window[1] is None or last_date <= window[1])):
                    continue
            if match and match not in line.casefold():
                continue
            if first:
                found.append(line)
                if len(found) == count:
                    break
            else:
                found.append(line)
    if window is not None and recognized == 0:
        raise NoRecognizableTimestamps(
            "No recognizable timestamps in this log.")
    return list(found), truncated


def read_with_boot_fallback(path, count, first=False, needle="", boot="All available"):
    """Use plain text when the selected file has no recognizable dates.

    Only unsupported timestamps trigger fallback; access, binary, missing
    boot history, and other errors are never suppressed.
    """
    try:
        lines, truncated = read_lines(path, count, first, needle, boot)
        return lines, truncated, False
    except NoRecognizableTimestamps:
        lines, truncated = read_lines(path, count, first, needle, "All available")
        return lines, truncated, True


class FileLogViewer(ttk.Frame):
    """Same display region as the system journal, without fake journal fields."""

    def __init__(self, parent):
        super().__init__(parent, padding=5)
        self.path = None
        self._generation = 0
        self._results = queue.Queue()
        self._closed = False
        self.columnconfigure(0, weight=1)
        self.rowconfigure(3, weight=1)

        self.heading = ttk.Label(self, text="File Logs", font=Common.font_bold)
        self.heading.grid(row=0, column=0, sticky="w", pady=(0, 5))

        toolbar = ttk.Frame(self)
        toolbar.grid(row=1, column=0, sticky="ew", pady=(0, 5))
        ttk.Label(toolbar, text="Lines:", font=Common.font_normal).pack(side="left")
        self.boot_var = tk.StringVar(value="Current boot")
        ttk.Label(toolbar, text="Boot:", font=Common.font_normal).pack(side="left")
        self.boot_selector = ttk.Combobox(
            toolbar, textvariable=self.boot_var, state="readonly", width=19,
            values=FileLogBoot.BOOT_LABELS, font=Common.font_normal)
        self.boot_selector.pack(side="left", padx=(5, 10))
        self.boot_selector.bind("<<ComboboxSelected>>", lambda event: self.refresh())
        self.lines_var = tk.StringVar(value="Last 500")
        self.lines = ttk.Combobox(
            toolbar, textvariable=self.lines_var, state="readonly", width=13,
            values=("Last 100", "Last 500", "Last 1000", "Last 5000",
                    "First 100", "First 500", "First 1000", "First 5000"),
            font=Common.font_normal)
        self.lines.pack(side="left", padx=(5, 10))
        self.lines.bind("<<ComboboxSelected>>", lambda event: self.refresh())
        ttk.Button(toolbar, text="Apply / Refresh", command=self.refresh).pack(side="left")

        search = ttk.Frame(self)
        search.grid(row=2, column=0, sticky="ew", pady=(0, 5))
        ttk.Label(search, text="Search file (Enter / Apply):",
                  font=Common.font_normal).pack(side="left", padx=(0, 6))
        self.search_var = tk.StringVar()
        entry = ttk.Entry(search, textvariable=self.search_var, font=Common.font_normal)
        entry.pack(side="left", fill="x", expand=True)
        entry.bind("<Return>", lambda event: self.refresh())
        self.status = ttk.Label(search, text="Choose a log file", font=Common.font_normal)
        self.status.pack(side="right", padx=(8, 0))

        frame = ttk.Frame(self)
        frame.grid(row=3, column=0, sticky="nsew")
        frame.columnconfigure(0, weight=1)
        frame.rowconfigure(0, weight=1)
        fixed = tkfont.nametofont("TkFixedFont").actual("family")
        font = tkfont.Font(family=fixed, size=Common.font_normal.actual("size"))
        self.log = tk.Text(frame, wrap="none", state="disabled", height=11, font=font)
        self.log.grid(row=0, column=0, sticky="nsew")
        scrollbar = ttk.Scrollbar(frame, orient="vertical", command=self.log.yview)
        scrollbar.grid(row=0, column=1, sticky="ns")
        horizontal = ttk.Scrollbar(frame, orient="horizontal", command=self.log.xview)
        horizontal.grid(row=1, column=0, sticky="ew")
        self.log.configure(yscrollcommand=scrollbar.set, xscrollcommand=horizontal.set)
        self.log.tag_configure("normal", foreground="#cccccc")
        self.log.tag_configure("error", foreground="#e05a60")
        self.log.tag_configure("warning", foreground="#dca640")
        self.log.tag_configure("success", foreground="#65c76b")
        self.log.tag_configure("timestamp", foreground="#91b9e9")
        self.log.tag_configure("ip", foreground="#c6a0e9")
        self.log.tag_configure("hex", foreground="#c6a0e9")
        self.log.tag_configure("path", foreground="#7cbacb")
        self.log.tag_configure("quoted", foreground="#b1c68c")
        self.log.tag_configure("key", foreground="#74c4bd")
        bold = font.copy()
        bold.configure(weight="bold")
        self.highlight_font = bold
        self.log.tag_configure("timestamp", font=bold)
        self.after(100, self._poll_results)

    def open_file(self, path):
        self.path = path
        self.heading.configure(text="File Logs — " + path)
        self.refresh()

    def _set_text(self, content, error=False):
        self.log.configure(state="normal")
        self.log.delete("1.0", "end")
        self.log.insert("end", content, "error" if error else ())
        self.log.configure(state="disabled")
        self.log.yview_moveto(0 if self.lines_var.get().startswith("First ") else 1)

    def refresh(self):
        if self._closed or not self.path:
            return
        self._generation += 1
        generation = self._generation
        path = self.path
        first = self.lines_var.get().startswith("First ")
        count = int(self.lines_var.get().split()[-1])
        needle = self.search_var.get()
        boot = self.boot_var.get()
        self.status.configure(text="Loading…")
        self._set_text("Reading " + path + "…\n")

        def worker():
            try:
                lines, truncated, fallback = read_with_boot_fallback(
                    path, count, first, needle, boot)
                self._results.put((generation, lines, truncated, fallback, None))
            except (OSError, ValueError, RuntimeError) as exc:
                self._results.put((generation, [], False, False, str(exc)))

        threading.Thread(target=worker, daemon=True).start()

    def _poll_results(self):
        if self._closed:
            return
        try:
            while True:
                generation, lines, truncated, fallback, error = self._results.get_nowait()
                if generation != self._generation:
                    continue
                if error:
                    self.status.configure(text="Error")
                    self._set_text("Unable to read file:\n" + error + "\n", True)
                else:
                    now = datetime.datetime.now().strftime("%H:%M:%S")
                    suffix = " · partial scan (64 MiB limit)" if truncated else ""
                    if fallback:
                        suffix += " · plain text (boot filter unavailable)"
                    elif self.boot_var.get() != "All available":
                        suffix += " · estimated boot range"
                    self.status.configure(text=str(len(lines)) + " entries · Updated " + now + suffix)
                    self._set_lines(lines)
        except queue.Empty:
            pass
        self.after(100, self._poll_results)

    def _set_lines(self, lines):
        """Show bounded text with semantic coloring, preserving line contents."""
        self.log.configure(state="normal")
        self.log.delete("1.0", "end")
        if not lines:
            self.log.insert("end", "No file lines match these filters.\n")
        else:
            for line in lines:
                clean = LogHighlight.ANSI.sub("", line)
                start = self.log.index("end-1c")
                self.log.insert("end", clean + "\n", LogHighlight.classify_line(clean))
                for begin, end, style in LogHighlight.highlight_spans(clean):
                    self.log.tag_add(style, f"{start}+{begin}c", f"{start}+{end}c")
        self.log.configure(state="disabled")
        self.log.yview_moveto(0 if self.lines_var.get().startswith("First ") else 1)

    def destroy(self):
        self._closed = True
        self._generation += 1
        super().destroy()
