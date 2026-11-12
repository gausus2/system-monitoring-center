"""Offline manufacturer TBW lookup, keyed by exact model and capacity.

Manufacturer rated write endurance is a reference specification, not
SMART Percentage Used and not a guarantee that a device will fail at TBW.
Unrecognized models always return None; never infer TBW by vendor alone.
"""
import json
from pathlib import Path
import re

CATALOG_PATH = Path(__file__).with_name("SmartEndurance.json")


def load_catalog():
    with CATALOG_PATH.open(encoding="utf-8") as stream:
        doc = json.load(stream)
    if doc.get("schema_version") != 1:
        raise ValueError("Unsupported SMART endurance catalog")
    return doc["entries"]


def lookup(model, capacity_bytes, catalog=None):
    """Return a vetted endurance entry only for an exact model/capacity."""
    if not isinstance(model, str) or not model.strip():
        return None
    if isinstance(capacity_bytes, bool) or not isinstance(capacity_bytes, int) or capacity_bytes <= 0:
        return None
    records = load_catalog() if catalog is None else catalog
    model = " ".join(model.upper().split())
    matches = []
    for row in records:
        if re.fullmatch(row["model_regex"], model, flags=re.IGNORECASE) is None:
            continue
        nominal_bytes = row["capacity_gb"] * 10**9
        # Account for reserve/over-provisioning and model-label capacity.
        # Do not silently match the wrong capacity variant.
        if not (0.88 * nominal_bytes <= capacity_bytes <= 1.12 * nominal_bytes):
            continue
        matches.append(row)
    return matches[0] if len(matches) == 1 else None


def annotate(disk, smart, catalog=None):
    """Attach independently sourced TBW rating and comparison with host writes."""
    result = dict(smart)
    model = smart.get("model") or disk.get("model", "")
    rating = lookup(model, disk.get("size"), catalog)
    result["rated_tbw"] = rating["tbw"] if rating else None
    result["rated_tbw_series"] = rating["series"] if rating else None
    result["rated_tbw_source"] = rating["source"] if rating else None
    written = result.get("writes_bytes")
    result["rated_tbw_used_pct"] = (
        written * 100 / (rating["tbw"] * 10**12)
        if rating and isinstance(written, (int, float)) and not isinstance(written, bool)
        and written >= 0 else None)
    return result
