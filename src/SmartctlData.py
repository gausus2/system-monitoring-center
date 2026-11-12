"""Read-only disk discovery and SMART health collection.

Never starts SMART tests or changes device state. JSON from smartctl is
preferred over locale-dependent terminal output. No sudo invocation:
unreadable devices remain visible with an explicit permissions status.
"""
import json
import os
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


def parse_smart(data, returncode=0):
    """Turn smartctl -a -j into a conservative, readable summary."""
    device = data.get("device") or {}
    passed = (data.get("smart_status") or {}).get("passed")
    nvme = data.get("nvme_smart_health_information_log") or {}
    ata = (data.get("ata_smart_attributes") or {}).get("table") or []
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
        "percentage_used": percentage_used,
        "media_errors": media_errors,
        "attributes": attributes,
        "model": data.get("model_name") or data.get("model_family") or "",
        "serial": data.get("serial_number") or "",
        "protocol": (device.get("protocol") or ""),
        "messages": errors,
    }


def inspect_disk(path, run=subprocess.run):
    """Inspect one discovered path; caller must not pass arbitrary user input."""
    command = SMARTCTL + [path]
    try:
        process = run(command, capture_output=True, text=True, errors="replace",
                      timeout=TIMEOUT, check=False)
    except FileNotFoundError:
        return {"health": "Unavailable", "messages": ["smartctl not installed"]}
    except subprocess.TimeoutExpired:
        return {"health": "Unavailable", "messages": ["smartctl timed out"]}
    try:
        data = json.loads(process.stdout)
    except (ValueError, TypeError):
        return {"health": "Unavailable", "messages": [
            (process.stderr or process.stdout or "Unable to read SMART data").strip()[:500]]}
    if not isinstance(data, dict):
        return {"health": "Unavailable", "messages": ["Unexpected SMART JSON"]}
    return parse_smart(data, process.returncode)


def collect(run=subprocess.run):
    """Return (disk, smart summary) pairs, preserving inaccessible devices."""
    disks = physical_disks(run)
    results = []
    for disk in disks:
        smart = inspect_disk(disk["path"], run)
        results.append((disk, smart))
    return results
