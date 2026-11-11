# System Monitoring Center – Services enhancements

These are custom changes to [System Monitoring Center](https://github.com/hakandundar34coding/system-monitoring-center) v3.4.1, maintained in the [gausus2 fork](https://github.com/gausus2/system-monitoring-center) on the `services-enhancements` branch. They are **not** part of the original upstream project.

## Changes

- **Single-process Services loading:** In `src/Libsysmon.py`, `get_services_information()` uses the existing single-process code path by setting `number_of_logical_cores = 2` locally. This worked around a Services-tab loading failure on Xubuntu 24.04.5 / AMD Ryzen 7 5700G. The setting does **not** change actual CPU core availability or other CPU-monitoring features.
- **New Services context-menu actions:** `View unit (cat)`, `List dependencies`, `Reverse dependencies`, `Show ordering`, `Ordering: After (tree)`, `Ordering: Before (tree)`, `Verify unit (syntax)`, `Service errors (journal)`, `Daemon reload`, `Edit override`, and `Edit full unit` in `src/Services.py`. They use Xfce Terminal; read-only actions run without `sudo`, while editing actions use `sudo systemctl edit` and the `nano` editor. This integration targets Xubuntu/Xfce; it has not been verified on all desktop environments.

## First-time clone using SSH

```bash
git clone git@github.com:gausus2/system-monitoring-center.git
cd system-monitoring-center
git fetch origin
git switch --track origin/services-enhancements
```

If the branch already exists locally, use `git switch services-enhancements` instead.

## Get updates from this fork

Run from the repository directory:

```bash
git switch services-enhancements
git pull --ff-only origin services-enhancements
```

If local edits prevent the pull, check `git status` first and commit or stash them. Avoid `git reset --hard` unless you intend to discard local changes.

## Install or update the modified files

These instructions apply when System Monitoring Center is installed under `/usr/share/system-monitoring-center/systemmonitoringcenter/`. Run from the repository root, and close the application first.

```bash
DEST=/usr/share/system-monitoring-center/systemmonitoringcenter
test -f "$DEST/Services.py" && test -f "$DEST/Libsysmon.py" || { echo "Installation not found"; exit 1; }

# Back up the installed files once. Do not overwrite backups on later updates.
for file in Services.py Libsysmon.py; do
    if [ ! -e "$DEST/$file.pre-services-enhancements" ]; then
        sudo cp -a "$DEST/$file" "$DEST/$file.pre-services-enhancements"
    fi
done

# Validate syntax without generating __pycache__ files.
python3 - <<'PY'
from pathlib import Path
for name in ("Services.py", "Libsysmon.py"):
    path = Path("src") / name
    compile(path.read_bytes(), str(path), "exec")
    print(f"{name}: syntax OK")
PY

sudo install -m 644 src/Services.py "$DEST/Services.py"
sudo install -m 644 src/Libsysmon.py "$DEST/Libsysmon.py"
```

Restart the application and open **Services**.

**To update later:** first run `git pull --ff-only` as above, then reinstall the two modified Python files.

## How to use the new actions

Right-click a systemd service in the **Services** tab:

| Menu action | Equivalent command | Purpose |
| --- | --- | --- |
| **View unit (cat)** | `systemctl cat --no-pager NAME.service` | Displays the unit file and its drop-ins in a terminal, without sudo or editing. |
| **List dependencies** | `systemctl list-dependencies --no-pager NAME.service` | Displays the selected service’s dependency tree (by default, dependencies it needs), without sudo or editing. | 
| **Reverse dependencies** | `systemctl list-dependencies --reverse --no-pager NAME.service` | Shows units that depend on the selected service, as a tree. |
| **Show ordering** | `systemctl show --property=After,Before --no-pager NAME.service` | Shows the unit's direct ordering relationships as `After=` and `Before=` properties. |
| **Ordering: After (tree)** | `systemctl list-dependencies --after --no-pager NAME.service` | Shows ordering-after relationships as a tree. |
| **Ordering: Before (tree)** | `systemctl list-dependencies --before --no-pager NAME.service` | Shows ordering-before relationships as a tree. |
| **Verify unit (syntax)** | `systemd-analyze verify NAME.service` | Checks the unit for configuration, execution and dependency problems; messages may also refer to related units. |
| **Service errors (journal)** | `journalctl --boot --unit NAME.service --priority=err --lines=100 --no-pager` | Shows up to 100 errors (priority err or higher) for the selected unit from the current boot. |
| **Daemon reload** | `sudo systemctl daemon-reload` | Asks systemd to reread unit files globally. Does not reload or restart the selected service. |
| **Edit override** | `sudo systemctl edit NAME.service` | Creates or edits a drop-in, usually under `/etc/systemd/system/NAME.service.d/`. Recommended for most local customizations. |
| **Edit full unit** | `sudo systemctl edit --full NAME.service` | Edits a complete local unit file under `/etc/systemd/system/`. This may override subsequent vendor unit-file updates. |

All eleven custom actions launch `xfce4-terminal`. Eight viewing/inspection actions are read-only (no editor, no sudo); their terminals remain open for scrolling and copying. **Daemon reload** is a system-wide privileged operation and prompts for sudo; it does not restart a service. **Show ordering** displays direct ordering properties, while the two **Ordering: ... (tree)** entries recursively expand ordering relationships. An ordering relationship alone does not necessarily imply a requirement dependency. The two editing actions use `nano`. Press `Ctrl+X` to exit; choose **N** if prompted to save changes you do not want. On successful save, `systemctl edit` normally runs `daemon-reload`, but does **not** restart the service.

The following programs must be available: `xfce4-terminal`, `systemctl`, `systemd-analyze`, `journalctl`, `sudo`, and `nano`. An active graphical Xfce session is expected.

**Note:** The existing upstream **Reload** menu action runs `systemctl reload NAME.service` (service-specific configuration reload, if supported). The new **Daemon reload** action runs `systemctl daemon-reload` (systemd manager reload after unit file changes). Neither is a service restart. A successful verification may produce no output. The journal view intentionally filters to errors from the current boot; warnings and earlier-boot errors are not included.\n\n**Caution:** Editing the full unit is more invasive than using a drop-in. Prefer **Edit override** where possible, and test carefully before changing critical services.

## Restore the previous installed files

Close the application and run:

```bash
DEST=/usr/share/system-monitoring-center/systemmonitoringcenter
sudo cp -a "$DEST/Services.py.pre-services-enhancements" "$DEST/Services.py"
sudo cp -a "$DEST/Libsysmon.py.pre-services-enhancements" "$DEST/Libsysmon.py"
```

Restore commands require the backup files to exist. Package upgrades may overwrite the modified installed files; reinstall from this fork afterward if needed.

## Check for upstream changes

`origin` refers to **your fork**. The original project can be configured as a separate `upstream` remote:

```bash
git remote add upstream git@github.com:hakandundar34coding/system-monitoring-center.git
git fetch upstream
```

Only add `upstream` once; inspect configured remotes with `git remote -v`.

Compare before attempting to merge:

```bash
git log --oneline --left-right services-enhancements...upstream/master
git diff services-enhancements..upstream/master -- src/Services.py src/Libsysmon.py
```

Integrate upstream updates in a separate test branch and review conflicts, especially in `Services.py` and `Libsysmon.py`. The v3.4.1 modifications may need adjustment for newer upstream versions.

## Test status

- **Confirmed:** The Services tab loads using the single-process workaround on Xubuntu 24.04.5.
- **Confirmed by the user:** The context-menu editor launches successfully.
- **Not fully tested:** All services, other desktop environments, or future upstream versions.

The original project is licensed under **GNU GPL v3**. Retain upstream copyright notices and license terms when redistributing modified versions.
