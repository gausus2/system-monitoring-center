"""Systemd unit-type filtering and journal-backed type discovery.

Type filtering is performed by journalctl itself, before --lines limits
results. Names are collected from the journal, not the currently loaded
set of systemctl units.
"""
import re
import subprocess

COMMON_TYPES = ("service", "mount", "socket", "timer", "target",
                "device", "swap", "path", "automount", "slice", "scope")
UNIT_NAME = re.compile(r"^[^\\s/]+\\.([a-z][a-z0-9-]*)$")


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
