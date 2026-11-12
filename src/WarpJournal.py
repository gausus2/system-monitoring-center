"""Streaming reader for Warp's embedded log levels in its journald namespace.

Journal metadata records Warp's stdout as INFO, while the actual severity is
embedded after Warp's ISO timestamp. Read newest-first and stop after the
requested number of matching entries rather than buffering the whole journal.
"""
import json
import re
import subprocess
import threading
import time


ANSI = re.compile(r"\x1b\[[0-?]*[ -/]*[@-~]")
WARP_LEVEL = re.compile(
    r"^\s*\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}"
    r"(?:\.\d+)?(?:Z|[+-]\d{2}:\d{2})\s+"
    r"(TRACE|DEBUG|INFO|WARN|ERROR)\b"
)
LEVEL_PRIORITY = {"TRACE": 7, "DEBUG": 7, "INFO": 6, "WARN": 4, "ERROR": 3}
FILTER_PRIORITY = {
    None: 7, "emerg": 0, "alert": 1, "crit": 2, "err": 3,
    "warning": 4, "info": 6, "debug": 7,
}


def timestamp_microseconds(entry):
    """Journal timestamps used to normalize normal and reverse query output."""
    try:
        return int(entry.get("__REALTIME_TIMESTAMP", 0))
    except (TypeError, ValueError, AttributeError):
        return 0


def message_text(value):
    """journalctl JSON encodes non-UTF8/binary MESSAGE fields as byte lists."""
    if isinstance(value, list) and all(
            isinstance(byte, int) and 0 <= byte <= 255 for byte in value):
        value = bytes(value).decode("utf-8", errors="replace")
    if not isinstance(value, str):
        value = str(value)
    return ANSI.sub("", value)


def effective_priority(entry):
    """Use an embedded Warp severity only for actual Warp process records."""
    identifier = entry.get("SYSLOG_IDENTIFIER")
    unit = entry.get("_SYSTEMD_UNIT")
    comm = entry.get("_COMM")
    try:
        priority = int(entry.get("PRIORITY", 6))
    except (TypeError, ValueError):
        priority = 6
    if identifier != "warp-svc.service" and unit != "warp-svc.service" and comm != "warp-svc":
        return max(0, min(7, priority))
    match = WARP_LEVEL.match(message_text(entry.get("MESSAGE", "")))
    return LEVEL_PRIORITY[match.group(1)] if match else max(0, min(7, priority))


def read_entries(command, max_entries, level, timeout=45):
    """Return newest matching entries in chronological order, memory-bounded.

    command has the usual boot, namespace, time, and optional message query.
    It must not contain --lines or --priority, which would discard candidates
    before Warp's embedded levels can be evaluated.
    """
    max_entries = max(1, min(5000, int(max_entries)))
    threshold = FILTER_PRIORITY[level]
    collected = []
    deadline = time.monotonic() + timeout
    process = subprocess.Popen(
        command + ["--reverse"], stdout=subprocess.PIPE,
        stderr=subprocess.PIPE, text=True, errors="replace",
    )
    stopped_early = False
    expired = threading.Event()

    def stop_on_timeout():
        if process.poll() is None:
            expired.set()
            process.kill()

    watchdog = threading.Timer(timeout, stop_on_timeout)
    watchdog.daemon = True
    watchdog.start()
    try:
        for line in process.stdout:
            if expired.is_set() or time.monotonic() > deadline:
                raise subprocess.TimeoutExpired(command, timeout)
            try:
                entry = json.loads(line)
            except (ValueError, TypeError):
                continue
            priority = effective_priority(entry)
            if priority <= threshold:
                entry["_VIEW_PRIORITY"] = priority
                collected.append(entry)
                if len(collected) >= max_entries:
                    stopped_early = True
                    break
        if expired.is_set():
            raise subprocess.TimeoutExpired(command, timeout)
        if stopped_early:
            # Do not continue reading a noisy Warp journal after finding
            # the requested N matching messages.
            if process.poll() is None:
                try:
                    process.terminate()
                except ProcessLookupError:
                    pass
            try:
                process.wait(timeout=2)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait()
        else:
            stderr = process.stderr.read().strip()
            returncode = process.wait(timeout=max(1, deadline-time.monotonic()))
            no_match = (returncode == 1
                        and any(arg.startswith("--grep=") for arg in command)
                        and not stderr and not collected)
            if returncode and not no_match:
                raise RuntimeError(stderr or "journalctl failed (exit %s)" % returncode)
    finally:
        watchdog.cancel()
        if process.poll() is None:
            process.kill()
            process.wait()
        process.stdout.close()
        process.stderr.close()
    collected.reverse()
    return collected
