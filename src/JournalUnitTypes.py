"""Systemd unit-type filtering and journal-backed type discovery.

Type filtering is performed by journalctl itself, before --lines limits
results. Names are collected from the journal, not the currently loaded
set of systemctl units.
"""
import re
import subprocess

COMMON_TYPES = ("service", "mount", "socket", "timer", "target",
                "device", "swap", "path", "automount", "slice", "scope")
UNIT_NAME = re.compile(r"^[^\s/]+\.([a-z][a-z0-9-]*)$")


def unit_type(name):
    if not isinstance(name, str):
        return None
    match = UNIT_NAME.fullmatch(name)
    return match.group(1) if match else None


def unit_glob(suffix):
    if suffix is None:
        return None
    if not re.fullmatch(r"[a-z][a-z0-9-]*", suffix):
        raise ValueError("Invalid systemd unit type: " + str(suffix))
    return "*." + suffix


def manager_unit_label(entry):
    """Return the unit referenced by a PID 1 manager event, if recorded.

    UNIT= describes the unit that systemd is reporting about, while
    _SYSTEMD_UNIT describes the process emitting an ordinary log message.
    Never infer unit names by parsing free-form MESSAGE text.
    """
    sender = entry.get("SYSLOG_IDENTIFIER") or entry.get("_COMM")
    pid = str(entry.get("SYSLOG_PID") or entry.get("_PID") or "")
    if sender != "systemd" or pid != "1":
        return None
    name = entry.get("UNIT") or entry.get("OBJECT_SYSTEMD_UNIT")
    return name if unit_type(name) else None


def discover_types(namespace=None, timeout=7):
    """Enumerate unit suffixes recorded in the selected journal namespace.

    Includes UNIT= records emitted by systemd itself, which are especially
    important for .mount, .target and .device units.
    """
    found = set()
    for field in ("_SYSTEMD_UNIT", "UNIT"):
        command = ["journalctl", "--no-pager", "--quiet", "--field=" + field]
        if namespace is not None:
            command.append("--namespace=" + namespace)
        try:
            run = subprocess.run(command, capture_output=True, text=True,
                                 errors="replace", timeout=timeout, check=False)
        except (OSError, subprocess.TimeoutExpired):
            continue
        if run.returncode != 0:
            continue
        for unit in run.stdout.splitlines():
            suffix = unit_type(unit.strip())
            if suffix:
                found.add(suffix)
    return sorted(found)
