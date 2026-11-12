# System Monitoring Center – Services enhancements

## Empty journal searches (test branch)

A `journalctl --grep` search with no matches can return exit status 1.
The System Logs viewer now treats this specific case (no output and no
error details) as an empty result rather than a journal read failure.
Actual command errors remain visible.

## Boot boundaries in journal results (test branch)

When **All boots** is selected, the viewer retains the journal's `_BOOT_ID`
for each returned entry and inserts a separator of the form
`-- Boot UUID --` whenever the boot ID changes. It does not count these
visual separators toward the Lines limit. Timestamps, severity highlighting,
sender/PID and log messages remain unchanged. A separator is only shown
between boots present among the returned entries; there is no synthetic
separator before the first displayed entry.

## Single System Logs search with full-journal filtering (test branch)

System Logs has **one search box**, immediately above the messages. Enter a
query and press **Enter** or **Apply / Refresh** to search the selected journal
*before* applying the **Lines** limit. A query such as `webmin.service` uses
`journalctl --unit=webmin.service`, including manager messages about the unit;
the latest 100 matching records are returned when Lines is 100. Other queries
use a case-insensitive, literal `journalctl --grep` search of the MESSAGE
field. Choose **All boots** and **All available** to include older entries.
Boot, priority and namespace filters apply as usual.

The search box inside **Services → Service Journal** is intentionally unchanged:
it still filters only the bounded messages already loaded for that service.
Neither view has unbounded output; available line limits are 100–5000, to
protect GUI responsiveness.

## Journal sender and PID (test branch)

The shared journal viewer now displays **Timestamp | Level | Source [PID] |
Message**. The source uses `SYSLOG_IDENTIFIER`, falling back to `_COMM`,
`_SYSTEMD_UNIT`, `_TRANSPORT`, or `-` when identifiers are unavailable.
The PID is read from `SYSLOG_PID` or `_PID` when provided. Search matches both
message text and source. This restores information visible in ordinary
`journalctl` output without removing severity labels or colors.

## System Logs test branch

**Branch:** `system-logs-development` (created from the working `services-enhancements` production branch). Production and `services-stable` are not modified.

This experiment introduces a **sixth main tab: System Logs**, next to System. Its
initial log-source selector supports **System journal** and **Kernel journal**.
Both use the existing `ServiceJournal.py` filtering, search, JSON decoding,
background loading, severity colors and font scaling. The service-specific
journal under Services is unchanged. The new `SystemLogs.py` has a small source
registry, so future file-log readers can be added as separate providers without
redesigning the page. Regular file logs are **not implemented yet**.

The System Logs **Namespace** selector defaults to **Default** (journalctl without
a namespace switch), avoiding noisy named logs. **All namespaces** passes
`--namespace=*`, while selecting a discovered named namespace passes
`--namespace=NAME`. Names are discovered from local journal directories
and `systemd-journald@NAME.service` instances. Kernel journal matches
`_TRANSPORT=kernel` (rather than `--kernel`, so **All boots** remains usable).
The namespace choice is independent of the log-source choice. Systemd normally
records kernel messages only in the default namespace. The usual boot, priority, time,
line-count and search controls remain available. Reads follow the current
user's journal permissions; the displayed results are snapshots, not live
follow. The tab deliberately does not save index 5 as the default tab, so
switching back to production does not leave a config value that the five-tab
build cannot restore. During this test the new tab reuses System's icon.

### Install for testing

Close System Monitoring Center, then run in the local clone:

```bash
git fetch origin
git switch -c system-logs-development --track origin/system-logs-development
bash ./update-services.sh
```

If this test branch already exists locally, use `git switch system-logs-development` instead. The test-branch updater checks that the current branch is `system-logs-development` and installs `SystemLogs.py` alongside the existing modified files.

### Restore production

```bash
git switch services-enhancements
bash ./update-services.sh
```

Close and restart the application after installing either version. In testing,
check that Services and the service journal continue to work and that the
new System Logs tab loads both journal sources without opening a terminal.


## Integrated journal viewer (production)

The journal viewer was tested on the `journal-development` branch and promoted to
`services-enhancements`. It adds a resizable embedded journal panel below the
existing Services list **without reparenting the original Treeview**. The panel
supports boot, priority, time range and line-count filters, search, color-coded
messages, and refresh. The original `services-stable` branch retains the
pre-journal version as a rollback reference.

The usual production installer remains:

```bash
bash ./update-services.sh
```

## Production update — State filtering and journal improvements

The tested improvements from `journal-development` are included in production:

- **Services State filter:** A drop-down next to the existing name search, with options such as All states, Enabled, Disabled, Static, and Masked. State and name search work together; column-header sorting remains available.
- **All journal namespaces:** The embedded viewer uses `journalctl --namespace=*`, so it can display service logs in both the default journal and named namespaces such as `netdata`. Journal permissions still apply.
- **Font Scale support:** Journal labels and controls use the application's configured scaled font. Log messages retain a monospaced font sized to the application's Font Scale setting.

The original `services-stable` branch remains unchanged for rollback. The `journal-development` branch is retained for further experiments.

## Changes

- **Single-process Services loading:** In `src/Libsysmon.py`, `get_services_information()` uses the existing single-process code path by setting `number_of_logical_cores = 2` locally. This worked around a Services-tab loading failure on Xubuntu 24.04.5 / AMD Ryzen 7 5700G. The setting does **not** change actual CPU core availability or other CPU-monitoring features.
- **New Services context-menu actions:** `View unit (cat)`, `Boot plot (focus service)`, `List dependencies`, `Reverse dependencies`, `Show ordering`, `Ordering: After (tree)`, `Ordering: Before (tree)`, `Verify unit (syntax)`, `Service journal (viewer)`, `Service errors (journal)`, `Daemon reload`, `Edit override`, and `Edit full unit` in `src/Services.py`. The journal actions open an embedded, resizable Tkinter panel rather than a terminal; other command actions use Xfce Terminal. Read-only actions run without `sudo`, while editing actions use `sudo systemctl edit` and the `nano` editor. This integration targets Xubuntu/Xfce; it has not been verified on all desktop environments.

- **Fork identifier in About:** The About dialog displays `3.4.1 services-enhancements` without modifying the upstream `src/__version__` file. This is implemented in `src/MainWindow.py`.\n\n## First-time clone using SSH

```bash
git clone git@github.com:gausus2/system-monitoring-center.git
cd system-monitoring-center
git fetch origin
git switch --track origin/services-enhancements
```

If the branch already exists locally, use `git switch services-enhancements` instead.

## Install and update — one command

After cloning the repository and switching to `services-enhancements`, use **the same command every time**, from the repository root:

```bash
bash ./update-services.sh
```

This script:

1. Verifies that the local branch is `services-enhancements` and stops if tracked files contain uncommitted changes.
2. Runs `git pull --ff-only origin services-enhancements` over your configured GitHub connection (SSH when cloned using the SSH URL).
3. Checks Python syntax in `src/Services.py`, `src/Libsysmon.py`, `src/MainWindow.py`, and `src/ServiceBootPlot.py` and `src/ServiceJournal.py` without creating `__pycache__`.
4. Checks for the installed application under `/usr/share/system-monitoring-center/systemmonitoringcenter/`.
5. Creates one-time backups of the three installed files named `.pre-services-enhancements`; it **does not overwrite existing backups**.
6. Installs the three modified upstream Python files plus the `ServiceBootPlot.py` and `ServiceJournal.py` helpers using `sudo install -m 644`.
7. Reminds you to restart System Monitoring Center.

If the syntax check or Git update fails, the script stops before copying files. Close the application before running the update, then restart it after installation.

The script currently targets the standard **Xubuntu / system-package installation path**. It is not intended for Flatpak installations. `sudo`, `git`, `bash`, and `python3` must be available.

For the first clone:

```bash
git clone git@github.com:gausus2/system-monitoring-center.git
cd system-monitoring-center
git fetch origin
git switch --track origin/services-enhancements
bash ./update-services.sh
```

For all subsequent updates:

```bash
cd /path/to/system-monitoring-center
bash ./update-services.sh
```

If a local change prevents the pull, use `git status` and commit or stash the changes first. Do not use `git reset --hard` unless you intend to discard those changes.

## How to use the new actions

Right-click a systemd service in the **Services** tab. The menu now groups inspection, dependencies and editing into submenus:\n\n- **Inspect / Logs:** unit content, browser-based boot plot focused on a selected service, embedded filterable journal viewer, error-only journal preset, syntax/configuration verification\n- **Dependencies / Ordering:** dependency trees, reverse dependencies and ordering information\n- **Edit unit:** override and full unit editing\n- **Daemon reload:** manager-wide unit-file reload (separate from the existing service **Reload** action)\n\nThe commands below operate on the selected systemd service:

| Menu action | Equivalent command | Purpose |
| --- | --- | --- |
| **Boot plot (focus service)** | `systemd-analyze plot` (via `ServiceBootPlot.py`) | Generates the boot SVG, opens a compact dark-theme timeline in the default browser, highlights the selected service and focuses its row. Includes search, a unit-type selector (All units, Services, Mounts, Devices, Sockets, Targets, Timers, etc., with counts based on the boot SVG), horizontal zoom, a Focus selected button, and an Original SVG toggle. Hover over a unit for its original SVG tooltip; click a unit row or bar to open a dismissible details panel with the relationships that systemd includes (such as After, Before, Requires, and Wants, when available). The default filter is Services; select All units to display every supported unit type represented in the boot plot. If the unit is missing from the boot plot, a message is shown. |\n| **View unit (cat)** | `systemctl cat --no-pager NAME.service` | Displays the unit file and its drop-ins in a terminal, without sudo or editing. |
| **List dependencies** | `systemctl list-dependencies --no-pager NAME.service` | Displays the selected service’s dependency tree (by default, dependencies it needs), without sudo or editing. | 
| **Reverse dependencies** | `systemctl list-dependencies --reverse --no-pager NAME.service` | Shows units that depend on the selected service, as a tree. |
| **Show ordering** | `systemctl show --property=After,Before --no-pager NAME.service` | Shows the unit's direct ordering relationships as `After=` and `Before=` properties. |
| **Ordering: After (tree)** | `systemctl list-dependencies --after --no-pager NAME.service` | Shows ordering-after relationships as a tree. |
| **Ordering: Before (tree)** | `systemctl list-dependencies --before --no-pager NAME.service` | Shows ordering-before relationships as a tree. |
| **Verify unit (syntax)** | `systemd-analyze verify NAME.service` | Checks unit configuration and dependencies; prints an explicit OK message when the command succeeds, or FAILED with the exit code otherwise. Messages may refer to related units. |
| **Service journal (viewer)** | `journalctl --unit NAME.service --output=json --no-pager` with configurable boot, priority, time range and count | Opens the embedded resizable journal panel under Services. Filters, search, refresh and color-coded severity use structured journal fields. Defaults: current boot, all priorities, last 24 hours, latest 500 entries. |\n| **Service errors (journal)** | Opens the same embedded viewer with priority `err` (or higher) and current boot | A convenient preset. Choose another boot, priority, time range or entry count and press Apply / Refresh. |
| **Daemon reload** | `sudo systemctl daemon-reload` | Asks systemd to reread unit files globally. Does not reload or restart the selected service. |
| **Edit override** | `sudo systemctl edit NAME.service` | Creates or edits a drop-in, usually under `/etc/systemd/system/NAME.service.d/`. Recommended for most local customizations. |
| **Edit full unit** | `sudo systemctl edit --full NAME.service` | Edits a complete local unit file under `/etc/systemd/system/`. This may override subsequent vendor unit-file updates. |

The new boot plot action starts a helper in `xfce4-terminal` and opens the generated HTML in the default browser; the terminal remains available for errors. Other command actions launch `xfce4-terminal`. Viewing/inspection actions are read-only (no editor, no sudo); their terminals remain open for scrolling and copying. **Daemon reload** is a system-wide privileged operation and prompts for sudo; it does not restart a service. **Show ordering** displays direct ordering properties, while the two **Ordering: ... (tree)** entries recursively expand ordering relationships. An ordering relationship alone does not necessarily imply a requirement dependency. The two editing actions use `nano`. Press `Ctrl+X` to exit; choose **N** if prompted to save changes you do not want. On successful save, `systemctl edit` normally runs `daemon-reload`, but does **not** restart the service.

The following programs must be available: `xfce4-terminal`, `systemctl`, `systemd-analyze`, `journalctl`, `sudo`, `nano`, `python3`, and a default browser. The boot plot uses only Python standard-library modules. An active graphical Xfce session is expected.

**Note:** The existing upstream **Reload** menu action runs `systemctl reload NAME.service` (service-specific configuration reload, if supported). The new **Daemon reload** action runs `systemctl daemon-reload` (systemd manager reload after unit file changes). Neither is a service restart. Verification now reports an explicit OK or FAILED result, and the embedded journal viewer reports when no entries match the selected filters. These checks do not guarantee that a service is functioning correctly: verification tests unit configuration, and the error-only journal view only covers error-priority entries from the current boot. The embedded journal view defaults to all priorities from the current boot within the last 24 hours, and can be reconfigured.\n\n**Caution:** Editing the full unit is more invasive than using a drop-in. Prefer **Edit override** where possible, and test carefully before changing critical services.

## Embedded Service Journal

The Services list and journal viewer share a **vertical Panedwindow**; drag the separator to resize each section. The journal panel is opened from **Inspect / Logs → Service journal (viewer)** or **Service errors (journal)** and has its own Close button. While it is open, selecting a different service updates the journal without closing the panel.

The controls offer **Current boot / Previous boot / All boots**, priority levels (including Error and higher, Warning and higher, Info and higher), time ranges (Last hour / Last 24 hours / Last 7 days / All available), and a bounded record count (100, 500, 1000 or 5000). Click **Apply / Refresh** to load data. The search box filters already loaded messages immediately and does not query the journal again. Text is copyable, and message colors distinguish critical/error, warning, and information-level events. Log reads run in a background thread and stale responses are ignored when the selection changes.

The viewer runs `journalctl` without sudo; readable entries depend on the current account's journal permissions. It is a snapshot viewer, not live-follow (`journalctl -f`). A 45-second timeout and a maximum of 5000 loaded records protect the UI on extremely verbose services. A journal with no matches shows an explicit message. Selecting Previous boot requires persistent journal data to be available.

## Boot plot limitations\n\n`systemd-analyze plot` covers the most recent available unit startup timestamps and may omit services that were not started, unloaded or otherwise absent from the current manager timing data. The viewer only focuses the selected unit when its label can be found in the SVG; otherwise it reports that the unit is not present. This is a boot timing graph, **not** a live service history. The new compact timeline derives unit names and bar positions from the SVG elements. It is experimental and may require adjustment on other systemd versions. Its horizontal scale is relative to the source SVG (percentage), not a calibrated seconds axis; the original SVG is available via the **Original SVG** button for accurate source time labels and detailed phases. Each plot opens a temporary local HTML file.\n\n## Restore the previous installed files

Close the application and run:

```bash
DEST=/usr/share/system-monitoring-center/systemmonitoringcenter
sudo cp -a "$DEST/Services.py.pre-services-enhancements" "$DEST/Services.py"
sudo cp -a "$DEST/Libsysmon.py.pre-services-enhancements" "$DEST/Libsysmon.py"\nsudo cp -a "$DEST/MainWindow.py.pre-services-enhancements" "$DEST/MainWindow.py"
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
- **Confirmed by the user:** The integrated Service Journal works with service selection, boot filters, priority highlighting and loaded entries in Xubuntu.\n- **Not fully tested:** All services, other desktop environments, or future upstream versions.

The original project is licensed under **GNU GPL v3**. Retain upstream copyright notices and license terms when redistributing modified versions.
