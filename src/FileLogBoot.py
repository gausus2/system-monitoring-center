"""Best-effort boot time windows and timestamps for ordinary text logs.

Plain text files have no _BOOT_ID. These windows use the current kernel
boot time and journal records for earlier boots; they are approximate.
"""
import datetime as dt
import json
import re
import subprocess

BOOT_LABELS = ("All available", "Current boot", "Previous boot (-1)",
               "Boot -2", "Boot -3")

ISO = re.compile(
    r"(?<!\d)(\d{4}-\d\d-\d\d)[T ](\d\d:\d\d:\d\d)"
    r"([.,]\d+)?(Z|[+-]\d\d:?\d\d)?")
SYSLOG = re.compile(
    r"^(?:\s*)?(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)"
    r"\s+(\d{1,2})\s+(\d\d:\d\d:\d\d)", re.I)
APACHE = re.compile(
    r"\[(\d{1,2})/([A-Za-z]{3})/(\d{4}):(\d\d:\d\d:\d\d)"
    r"\s+([+-]\d{4})\]")
MON = {name.lower(): i for i, name in
       enumerate(("Jan", "Feb", "Mar", "Apr", "May", "Jun",
                  "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"), 1)}


def current_boot_start():
    """Kernel btime (the same clock used by uptime -s)."""
    with open("/proc/stat", encoding="ascii") as stream:
        for line in stream:
            if line.startswith("btime "):
                return dt.datetime.fromtimestamp(int(line.split()[1])).astimezone()
    raise RuntimeError("Cannot determine current boot time")


def _journal_edge(boot_index, first):
    cmd = ["journalctl", "--boot", str(boot_index), "--no-pager",
           "--quiet", "--output=json", "--lines", "+1" if first else "1"]
    run = subprocess.run(cmd, capture_output=True, text=True,
                         errors="replace", timeout=10, check=False)
    if run.returncode:
        return None
    for line in run.stdout.splitlines():
        try:
            epoch = int(json.loads(line)["__REALTIME_TIMESTAMP"]) / 1e6
            return dt.datetime.fromtimestamp(epoch).astimezone()
        except (ValueError, KeyError, TypeError, OverflowError, OSError):
            continue
    return None


def boot_window(selection):
    """Return (start, end); unavailable older boots raise ValueError."""
    if selection == "All available":
        return None
    if selection not in BOOT_LABELS:
        raise ValueError("Unknown boot selection")
    start_current = current_boot_start()
    if selection == "Current boot":
        return start_current, None
    index = BOOT_LABELS.index(selection) - 1
    start = _journal_edge(-index, True)
    end = _journal_edge(-index, False)
    if start is None or end is None:
        raise ValueError("Boot %s is not available in journald" % (-index))
    return start, end


def timestamp(line, reference):
    """Parse common timestamps; return timezone-aware local datetime or None."""
    iso = ISO.search(line[:130])
    if iso:
        try:
            stamp = iso.group(1) + "T" + iso.group(2)
            if iso.group(3):
                stamp += iso.group(3).replace(",", ".")
            if iso.group(4):
                stamp += iso.group(4).replace("Z", "+00:00")
            value = dt.datetime.fromisoformat(stamp)
            return value.astimezone() if value.tzinfo else value.replace(
                tzinfo=reference.tzinfo)
        except ValueError:
            return None

    apache = APACHE.search(line[:130])
    if apache:
        try:
            stamp = "%s/%s/%s:%s %s" % apache.groups()
            return dt.datetime.strptime(stamp, "%d/%b/%Y:%H:%M:%S %z").astimezone()
        except ValueError:
            return None

    syslog = SYSLOG.match(line)
    if syslog:
        month, day, clock = syslog.groups()
        month_num = MON.get(month.lower())
        if not month_num:
            return None
        try:
            # Anchor year to the selected boot window rather than the wall
            # clock today, so older boots work across a new year.
            anchor = reference
            candidate = dt.datetime.strptime(
                "%d-%02d-%s" % (anchor.year, month_num, day) + " " + clock,
                "%Y-%m-%d %H:%M:%S").replace(tzinfo=anchor.tzinfo)
            if candidate > anchor + dt.timedelta(days=2):
                candidate = candidate.replace(year=candidate.year - 1)
            elif candidate < anchor - dt.timedelta(days=350):
                candidate = candidate.replace(year=candidate.year + 1)
            return candidate
        except ValueError:
            return None
    return None
