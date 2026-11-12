"""Read-only disk discovery and SMART health collection.

Never starts SMART tests or changes device state. JSON from smartctl is
preferred over locale-dependent terminal output. No sudo invocation:
unreadable devices remain visible with an explicit permissions status.
"""
import json
import os
import shutil
import subprocess

LSBLK = ["lsblk", "-J", "-d", "-b", "-o", "NAME,PATH,TYPE,MODEL,SIZE,TRAN"]
SMARTCTL = ["smartctl", "-a", "-j"]
TIMEOUT = 12
ATTRIBUTE_NAMES = {
    5: "Reallocated sectors",
    9: "Power-on hours",
    187: "Reported uncorrectable",
    188: "Command timeouts",
    194: "Temperature",
    197: "Current pending sectors",
    198: "Offline uncorrectable",
    199: "UDMA CRC errors",
}


def physical_disks(run=subprocess.run):
    """List block disks, not partitions, loop devices, zram or optical drives."""
    process = run(LSBLK, capture_output=True, text=True, timeout=TIMEOUT,
                  check=False)
    if process.returncode != 0:
        raise RuntimeError(process.stderr.strip() or "lsblk failed")
    try:
        blocks = json.loads(process.stdout).get("blockdevices", [])
    except (ValueError, TypeError) as error:
        raise RuntimeError("Invalid lsblk JSON") from error
    return [
        {
            "path": item["path"],
            "model": (item.get("model") or "").strip(),
            "size": item.get("size"),
            "transport": item.get("tran") or "-",
        }
        for item in blocks
        if item.get("type") == "disk"
        and isinstance(item.get("path"), str)
        and item["path"].startswith("/dev/")
        and os.path.basename(item["path"]).replace("-", "").isalnum()
        and not os.path.basename(item["path"]).startswith(
            ("zram", "ram", "loop", "nbd", "fd", "sr"))
    ]


def _number(value):
    if isinstance(value, dict):
        value = value.get("value")
    return value if isinstance(value, (int, float)) and not isinstance(value, bool) else None


def _counter(value):
    """NVMe counters can be JSON integers or decimal strings (up to 128 bits)."""
    if isinstance(value, dict):
        value = value.get("value")
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value if value >= 0 else None
    if isinstance(value, str) and value.isascii() and value.isdecimal():
        return int(value)
    return None


def nvme_total_written_bytes(log):
    """NVMe Data Units Written: 1000 * 512 bytes per reported unit.

    A zero counter means the controller did not report the value.
    """
    units = _counter(log.get("data_units_written"))
    return units * 512000 if units else None


def ata_total_written_bytes(data, attributes):
    """Decode a few documented model-specific host-write counters.

    ATA SMART IDs alone do not establish units. Only accept a
    recognized model family AND a matching vendor attribute name.
    Never confuse NAND writes (flash wear) with host writes.
    """
    model = str(data.get("model_name") or "").upper()
    for item in attributes:
        if item.get("id") != 241:
            continue
        name = str(item.get("name") or "").upper()
        raw = _counter((item.get("raw") or {}).get("value"))
        if raw is None:
            continue
        # Samsung SATA SSD documentation: attr 241 is the number of
        # 512-byte logical blocks written by the host.
        if (model.startswith("SAMSUNG SSD ")
                and name in ("TOTAL_LBAS_WRITTEN", "TOTAL_LBA_WRITTEN")):
            return raw * 512, "ATA Samsung attribute 241 (512-byte LBAs)"
        # Kingston SSD family documentation: attr 241 host writes in
        # decimal gigabytes. Require an explicitly descriptive name,
        # not an unknown generic vendor-specific SMART attribute.
        if (model.startswith("KINGSTON ")
                and name in ("HOST_WRITES_GB", "HOST_WRITES_GBYTES",
                             "HOST_WRITES_GIGABYTES",
                             "LIFETIME_WRITES_FROM_HOST_SYSTEM")):
            return raw * 10**9, "ATA Kingston attribute 241 (GB)"
    return None, None


def parse_smart(data, returncode=0):
    """Turn smartctl -a -j into a conservative, readable summary."""
    device = data.get("device") or {}
    passed = (data.get("smart_status") or {}).get("passed")
    nvme = data.get("nvme_smart_health_information_log") or {}
    ata = (data.get("ata_smart_attributes") or {}).get("table") or []
    if nvme_total_written_bytes(nvme) is not None:
        written = nvme_total_written_bytes(nvme)
        written_source = "NVMe Data Units Written (512000 bytes/unit)"
    else:
        written, written_source = ata_total_written_bytes(data, ata)
    attributes = {}
    for item in ata:
        identifier = item.get("id")
        if identifier in ATTRIBUTE_NAMES:
            raw = item.get("raw") or {}
            val = _number(raw.get("value"))
            if val is not None:
                attributes[ATTRIBUTE_NAMES[identifier]] = val
    temp = _number((data.get("temperature") or {}).get("current"))
    if temp is None:
        temp = _number(nvme.get("temperature"))
    if temp is None:
        temp = attributes.get("Temperature")
    hours = _number((data.get("power_on_time") or {}).get("hours"))
    if hours is None:
        hours = attributes.get("Power-on hours")
    percentage_used = _number(nvme.get("percentage_used"))
    media_errors = _number(nvme.get("media_errors"))
    warning = _number(nvme.get("critical_warning"))
    if passed is False or (warning is not None and warning != 0):
        health = "FAILED / Warning"
    elif passed is True or warning == 0:
        health = "Passed"
    else:
        health = "Unknown"
    errors = [
        item.get("string") or str(item.get("code"))
        for item in (data.get("smartctl") or {}).get("messages", [])
        if item.get("severity") in ("error", "warning")
    ]
    # Bit 0/1 indicate invocation or device access issues; bit 3 is
    # SMART failure and bit 4+ are error log / attribute findings.
    if returncode & 3:
        health = "Unavailable"
    elif returncode & 8:
        health = "FAILED / Warning"
    if health == "Unknown" and errors:
        health = "Unavailable"
    return {
        "health": health,
        "temperature": temp,
        "hours": hours,
        "writes_bytes": written,
        "writes_source": written_source,
        "percentage_used": percentage_used,
        "media_errors": media_errors,
        "attributes": attributes,
        "model": data.get("model_name") or data.get("model_family") or "",
        "serial": data.get("serial_number") or "",
        "protocol": (device.get("protocol") or ""),
        "messages": errors,
    }


def inspect_disk(path, run=subprocess.run, command=None, timeout=TIMEOUT):
    """Inspect one discovered path; caller must not pass arbitrary user input."""
    command = command if command is not None else SMARTCTL + [path]
    try:
        process = run(command, capture_output=True, text=True, errors="replace",
                      timeout=timeout, check=False)
    except FileNotFoundError:
        return {"health": "Unavailable", "messages": [
            "SMART reader or authentication command is not installed"]}
    except subprocess.TimeoutExpired:
        return {"health": "Unavailable", "messages": [
            "SMART read or authentication timed out"]}
    try:
        data = json.loads(process.stdout)
    except (ValueError, TypeError):
        return {"health": "Unavailable", "messages": [
            (process.stderr or process.stdout or "Unable to read SMART data").strip()[:500]]}
    if not isinstance(data, dict):
        return {"health": "Unavailable", "messages": ["Unexpected SMART JSON"]}
    return parse_smart(data, process.returncode)


def permission_denied(smart):
    """Only retry with administrator access for explicit access errors."""
    phrases = ("permission denied", "operation not permitted",
               "requires root", "must be root", "insufficient privileges")
    return (smart.get("health") == "Unavailable"
            and any(phrase in str(message).casefold()
                    for message in smart.get("messages", [])
                    for phrase in phrases))


def read_admin(path, run=subprocess.run, which=shutil.which):
    """Try normal access, sudo -n, then polkit on explicit user request.

    Only the fixed smartctl binary and discovered disk path are executed.
    No shell, no generic privileged Python helper, no password handling.
    """
    ordinary = inspect_disk(path, run)
    if not permission_denied(ordinary):
        return ordinary
    executable = which("smartctl")
    if not executable or not os.path.isabs(executable):
        return {"health": "Unavailable", "messages": ["smartctl not found"]}
    # No prompt and no password read from stdin. Preserve smartctl's own
    # nonzero health bitmask; judge results by actual access errors.
    if which("sudo"):
        sudo = inspect_disk(
            path, run, ["sudo", "-n", "--", executable, "-a", "-j", path])
        if sudo.get("health") != "Unavailable":
            return sudo
        # Authentication or policy failures should try polkit next.
        if not (permission_denied(sudo) or
                any(token in " ".join(sudo.get("messages", [])).casefold()
                    for token in ("password", "sudoers", "not allowed", "a terminal"))):
            return sudo
    if not which("pkexec"):
        return {"health": "Unavailable", "messages": [
            "Administrator access unavailable: pkexec not installed or configured"]}
    result = inspect_disk(
        path, run, ["pkexec", executable, "-a", "-j", path], timeout=90)
    if result.get("health") == "Unavailable":
        messages = result.get("messages", [])
        return {"health": "Unavailable", "messages": [
            "Administrator authentication denied, cancelled or unavailable."
            ] + messages[:2]}
    return result


def collect(run=subprocess.run, admin=False):
    """Return (disk, smart summary) pairs, optionally escalating read only."""
    disks = physical_disks(run)
    results = []
    for disk in disks:
        smart = (read_admin(disk["path"], run) if admin
                 else inspect_disk(disk["path"], run))
        results.append((disk, smart))
    return results
