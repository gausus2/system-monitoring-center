#!/usr/bin/env bash
# Test installer for file-logs-development; production untouched.
set -Eeuo pipefail

cd -- "$(dirname -- "${BASH_SOURCE[0]}")"

DEST="/usr/share/system-monitoring-center/systemmonitoringcenter"
BRANCH="file-logs-development"

if [[ "$(git branch --show-current)" != "$BRANCH" ]]; then
    printf 'ERROR: Switch to the %s branch first.\n' "$BRANCH" >&2
    exit 1
fi

if [[ -n "$(git status --porcelain --untracked-files=no)" ]]; then
    printf 'ERROR: Local tracked changes detected. Commit or stash them before updating.\n' >&2
    exit 1
fi

printf '==> Fetching the latest Services enhancements\n'
git pull --ff-only origin "$BRANCH"

printf '==> Checking Python syntax\n'
python3 - <<'PY'
from pathlib import Path

for name in ("Services.py", "Libsysmon.py", "MainWindow.py", "ServiceBootPlot.py", "ServiceJournal.py", "SystemLogs.py", "WarpJournal.py", "JournalUnitTypes.py", "FileLogs.py"):
    path = Path("src") / name
    compile(path.read_bytes(), str(path), "exec")
    print(f"{name}: syntax OK")
PY

printf '==> Testing Warp internal-priority parser\n'
python3 tests/test_warp_journal.py
python3 tests/test_journal_unit_types.py
python3 tests/test_file_logs.py

if [[ ! -f "$DEST/Services.py" || ! -f "$DEST/Libsysmon.py" || ! -f "$DEST/MainWindow.py" ]]; then
    printf 'ERROR: System Monitoring Center installation not found at %s\n' "$DEST" >&2
    exit 1
fi

printf '==> Installing modified Python files (sudo required)\n'
for name in Services.py Libsysmon.py MainWindow.py; do
    if ! sudo test -e "$DEST/$name.pre-services-enhancements"; then
        sudo cp -a -- "$DEST/$name" "$DEST/$name.pre-services-enhancements"
        printf 'Created original backup for %s\n' "$name"
    fi
    sudo install -m 644 -- "src/$name" "$DEST/$name"
    printf 'Installed %s\n' "$name"
done

# Install the new helper (not present in original upstream packages).
for name in ServiceBootPlot.py ServiceJournal.py SystemLogs.py WarpJournal.py JournalUnitTypes.py FileLogs.py; do
    sudo install -m 644 -- "src/$name" "$DEST/$name"
    printf 'Installed %s\n' "$name"
done

printf '\nDone. Close and restart System Monitoring Center to use the updates.\n'
