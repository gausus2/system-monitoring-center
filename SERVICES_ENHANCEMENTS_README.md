# System Monitoring Center – Services enhancements

## Journal unit-type filter (experimental)

Branch `journal-unit-type-development`, based on production
`services-enhancements`. **No production branch changes.**

The System Logs **System journal** view gains a **Type** dropdown:
**All types**, **Service**, **Mount**, **Socket**, **Timer**, **Target**,
**Device**, **Swap**, **Path**, **Automount**, **Slice**, and **Scope**.
Additional suffixes discovered in journal records can appear automatically.
Types are enumerated asynchronously from `journalctl --field=_SYSTEMD_UNIT`
and `journalctl --field=UNIT` for the selected namespace. The baseline
options remain available when discovery is slow, incomplete, or denied.
The list is deliberately **not** derived from just the loaded 100–5000 rows.

**No matching unit data:** For some types (notably `.device`),
`journalctl --unit=*.device` can exit with
`Failed to add filter for units: No data available` when the wildcard
cannot be expanded against recorded unit data. This specific condition is
now displayed as **0 journal entries** rather than a GUI error. Other
journalctl errors, including permission failures, remain visible. A
systemd device may exist without any matching journal events; this type
filter is not a device inventory.

The type selection is applied by `journalctl --unit=*.service`,
`--unit=*.mount`, etc. The glob is matched against unit names **in the
journal** and includes systemd manager messages about those units. This
filter is applied before the First/Last N limit. Other filters, including
search, priority, boot, time and namespace, remain operative. Exact unit
searches such as `warp-svc.service` are not accidentally OR'ed with the
selected type: a mismatching type gives an empty result. Type filtering is
not applicable to the Kernel journal; its dropdown is disabled and reset.
The embedded per-service journal in Services stays unchanged.

For messages emitted by the systemd manager itself (`systemd[1]`),
the sender column shows the referenced unit **instead of** `systemd[1]`
when journald provides a structured `UNIT=` (or
`OBJECT_SYSTEMD_UNIT=`) field, e.g. `systemd-udevd.service`.
Ordinary messages emitted by the service keep their original sender,
e.g. `systemd-udevd[524]`. The label is not guessed from free-form
log text; manager messages without a suitable unit field remain
`systemd[1]`. Original journal metadata is untouched; this affects
only the displayed sender label.

Service-owned helper processes additionally show their service context from
`_SYSTEMD_UNIT` before the original process name, for example
`systemd-udevd.service mtp-probe[648]` or
`systemd-udevd.service (udev-worker)[552]`. This deliberately differs from
the standard `journalctl -u` presentation, which prints the sender alone.
Messages from systemd PID 1 still use the referenced `UNIT` label when
available. Non-service records retain their normal sender, and when
`SYSLOG_IDENTIFIER` already names the service the unit is not repeated.
This is only a display change: filtering and journal content are unaffected.

Close the application and test with:

```bash
git fetch origin
git switch -c journal-unit-type-development --track origin/journal-unit-type-development
bash ./update-services.sh
```

If that branch exists locally, use `git switch journal-unit-type-development`.
The installer checks Python syntax, runs the existing Warp tests and new
unit-type tests, then installs the helper `JournalUnitTypes.py`.

To restore production, close the app, run `git switch services-enhancements`
and `bash ./update-services.sh`, then restart the app.


## Production release: minute filters and First/Last line windows

The tested changes from `journal-range-development` are now in
**`services-enhancements`**. Time range adds **Last minute** and
**Last 10 minutes**. Lines supports **First/Last 100, 500, 1000, and
5000**. Choosing a First value automatically sets Time range to
**All available**, while allowing a manual time-range change afterward.
Last preserves the selected range. Warp's special priority filtering
remains supported in both directions.

Production update (close System Monitoring Center first):

```bash
git switch services-enhancements
bash ./update-services.sh
```

The production updater validates Python syntax and runs the Warp journal
regression checks before installing. The earlier development instructions
below are preserved as history. The `journal-range-development` branch and
`services-stable` backup remain unchanged.


## Experimental time and line-range filters

Branch: `journal-range-development`, created from the tested production
`services-enhancements` branch. Production has not been changed.

**Time range** now offers **Last minute** and **Last 10 minutes** in addition
to the existing Last hour / Last 24 hours / Last 7 days / All available.

**Lines** offers **Last 100 / 500 / 1000 / 5000** and
**First 100 / 500 / 1000 / 5000**. "First" means the oldest matching
journal entries within the chosen boot, namespace, time range, priority and
search. Selecting any **First** option automatically changes **Time range** to
**All available**; the user can manually select a narrower range afterward.
"Last" means the newest matching entries and does not change Time range. The UI displays records
chronologically, scrolling to the top for First and to the bottom for Last.

Normal journal queries use systemd's `journalctl --lines=+N` for First
and `--lines=N` for Last. Warp's internal-priority reader instead uses a
bounded forward or reverse stream and stops after the specified number of
priority-matching entries, ensuring its special ERROR/WARN filtering remains
correct and no unbounded journal is loaded. The initial selection remains
equivalent to the previous Last 500.

To test, close the app and run:

```bash
git fetch origin
git switch -c journal-range-development --track origin/journal-range-development
bash ./update-services.sh
```

If the branch exists locally use `git switch journal-range-development`.
The installer runs Python syntax and Warp parser regression checks before
copying files. To restore production, close the app, run
`git switch services-enhancements` and `bash ./update-services.sh`,
then restart the application.


## Production update: Journal refresh (12 November 2026)

The tested `journal-refresh-development` improvements have been promoted to
`services-enhancements`. The journal viewer now sorts records chronologically
before display (including results of `journalctl --grep` with `--lines`), so
the newest entries appear at the bottom. The status shows `Updated HH:MM:SS`
after a successful reload to confirm **Apply / Refresh** was executed.

Use `bash ./update-services.sh` on the `services-enhancements` branch
to install this production version. The older test instructions below are
retained as development history; the test branch remains unchanged.


## Journal refresh ordering (experimental branch)

The `journal-refresh-development` branch tests a fix for a subtle
`journalctl` behavior: combining `--grep` with `--lines` implicitly
enables reverse chronological output. The viewer previously displayed that
output without sorting and then scrolled to the bottom, which could make the
newest matching entries appear to be missing after **Apply / Refresh**.

All journal entries are now sorted by their `__REALTIME_TIMESTAMP`
before display, so the newest entry appears at the bottom for both regular
journal queries and grep searches. The status shows `Updated HH:MM:SS`
after every successful read, even if there are no new matching entries.
All boot/namespace/priority/line-count and Warp-specific filtering is
unchanged.

Close the application, then test with:

```bash
git fetch origin
git switch -c journal-refresh-development --track origin/journal-refresh-development
bash ./update-services.sh
```

If the branch exists locally, use `git switch journal-refresh-development`.
To revert to production, close the app and run
`git switch services-enhancements` followed by `bash ./update-services.sh`,
then restart the app. No production code is changed by this experiment.


## Production release: System Logs and Warp-aware priorities (12 November 2026)

The previously tested `warp-log-levels-development` version has now been
promoted to **`services-enhancements`**, including the standalone sixth
**System Logs** main tab, kernel/system journal sources, named namespace
selector, boot boundaries, full-journal search before the line limit,
journal sender/PID, priority colors and the optional Warp-specific embedded
DEBUG/INFO/WARN/ERROR interpretation.

For production installation from the `services-enhancements` branch:

```bash
git switch services-enhancements
bash ./update-services.sh
```

The production updater now targets `services-enhancements` and installs
`SystemLogs.py` and `WarpJournal.py` alongside the other helpers, including
the Warp parser regression-test check. The development branches
(`warp-log-levels-development`, `journal-colors-development`,
`system-logs-development`) and the earlier `services-stable` backup
remain available and unchanged. Older sections below document the development
history and test instructions, not the current production installation.


## Warp embedded log levels (isolated test branch)

**Branch:** `warp-log-levels-development` (forked from the working
`journal-colors-development`). No production or earlier working branch
is modified.

In **System Logs → System journal → Namespace: warp**, the viewer now
recognizes the timestamp and embedded Warp log level at the **start** of
messages written by `warp-svc.service` / `warp-svc`. It maps:
`TRACE/DEBUG → DEBUG`, `INFO → INFO`, `WARN → WARN`,
`ERROR → ERROR`. Messages from other processes, and Warp entries that
do not match the expected format, continue using their original journald
`PRIORITY`. Colors and displayed level reflect the effective priority.

Unlike ordinary journald `--priority`, selecting **Error and higher** or
**Warning and higher** in the Warp namespace filters by these effective
priorities, including Warp errors registered as journald INFO. The reader
scans the selected journal **newest first** and stops once it has found
100/500/1000/5000 matching entries. It does not accumulate a huge Warp
journal in memory. Boot, time range, namespace, and optional text searches
remain active. An operation without enough matches may still need to scan a
large journal and may reach the existing 45-second timeout.

This is intentionally limited to **System journal + the named `warp`
namespace**. The Services journal and all other namespaces retain the
previous journalctl priority semantics. No other service's logging is
reinterpreted merely because its message contains the word `error`.
The approach does not modify Warp's systemd unit or its log files.

### Test

Close System Monitoring Center, then:

```bash
git fetch origin
git switch -c warp-log-levels-development --track origin/warp-log-levels-development
bash ./update-services.sh
```

If the branch already exists locally, use `git switch warp-log-levels-development`
instead. The test installer checks the active branch, compiles all modified
Python files (including the new `WarpJournal.py`) and installs the helper.

Test **Namespace: warp**, **All levels**, **Error and higher**,
**Warning and higher**, and **Debug (all)**. Compare against the
embedded levels in `journalctl --namespace=warp -o cat`. Filtering is
based on Warp's levels, not the journald `PRIORITY=6` field.

To restore the previous color version:

```bash
git switch journal-colors-development
bash ./update-services.sh
```

Restart the application after either installation. The earlier updater does
not delete the new `WarpJournal.py` helper, but its previous
`ServiceJournal.py` does not import it.

## Timestamp emphasis and binary journal messages (test branch)

The timestamp is now **bold for every priority**, retaining the color of its
severity class. Warning and error lines retain their full-line colors.
Some programs (notably Warp) write binary MESSAGE values; `journalctl
--output=json` encodes these as an array of byte numbers. The shared
viewer decodes valid byte arrays as UTF-8 with replacement for invalid bytes,
then removes terminal escape sequences so its own priority-based coloring
remains consistent. This does **not** change namespace routing. Named journal
namespaces can legitimately contain records written by several cooperating
processes (for example Netdata's plugin helpers).

## Journal color scheme test

**Branch:** `journal-colors-development`. This is isolated from both the
working `system-logs-development` branch and production
`services-enhancements`.

The first color experiment changes only rendering in the shared journal
viewer:

- Normal INFO, NOTICE and DEBUG messages: light gray (`#cccccc`).
- Sender identifier and PID on normal messages: green (`#65c76b`).
- WARN: entire line remains yellow (`#dca640`).
- ERROR, CRITICAL, ALERT and EMERGENCY: entire line remains red (`#e05a60`).
- Boot markers remain muted gray. Priority labels and all journal filters
  continue to work as before.

To test: `git switch journal-colors-development`, then
`bash ./update-services.sh`. Close and restart System Monitoring Center.
To restore the earlier tested appearance: `git switch system-logs-development`
and run its own `bash ./update-services.sh`. Restart the program afterward.

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


## File Logs test branch

`file-logs-development` adds **Other logs ▾** directly beneath the existing
**Log source** dropdown in System Logs. The original System journal / Kernel
journal choices, namespaces, boot/time/type and priority filtering are unchanged.

The new menu scans regular non-rotated text files under `/var/log` when opened,
grouping entries by full directory path. Selecting a file switches the viewer to
a separate read-only file mode with **First/Last 100–5000**, case-insensitive
substring search (applied before line count), and Apply / Refresh. The actual
file path appears in the heading. Selecting System journal or Kernel journal
returns to the original journal viewer; F5 refreshes whichever is visible.
Other logs files are not journal entries: journal boot, unit type and priority
filters do not apply to arbitrary text files.

Safety: file names are discovered locally, and files are revalidated on read.
Symlinks, binary log formats, compressed and rotated files are excluded;
64 MiB maximum per refresh is scanned to prevent unbounded work. File reads
run off the Tk thread. Permissions are not bypassed: unreadable files show a
clear error rather than escalating privileges.

Run on the test branch:
```bash
git fetch origin
git switch -c file-logs-development --track origin/file-logs-development
bash ./update-services.sh
```
If the test branch already exists locally, simply
`git switch file-logs-development && bash ./update-services.sh`.
Production remains on `services-enhancements`.

### Generic syntax colors in Other logs

The test branch colors file-log text with a lightweight, Kate-inspired
highlighting engine (`src/LogHighlight.py`): bold blue timestamps,
red error/failure/fatal indicators, amber warnings and timeouts,
green success/started/completed status, purple IP addresses and hex values,
cyan file paths and key=value names, and muted green quoted strings.
Whole-line severity is visual only, inferred from words rather than a
structured journal priority; specific tokens retain their own colors.
ANSI escape codes are removed from the displayed text rather than executed.
The original System/Kernel journal display colors and filters are unchanged.
`tests/test_log_highlight.py` checks matching and overlapping spans.

### Boot-based file selection for Other logs

The **Files since** selector in System Logs (beside the **Other logs**
menu) controls **which files are listed**, not what lines are shown
within an opened file. Available choices: **All available**,
**Current boot** (default), **Previous boot (-1)**, **Boot -2**, and
**Boot -3**. The menu discovers non-rotated readable-format candidates
below `/var/log` and filters their filesystem **last-modified time**
(`mtime`) against the chosen boot interval. **Current boot** uses
`/proc/stat` `btime` (as in `uptime -s`); earlier boots use the
first/last known journald message timestamp.

**Important limitation:** `mtime` is the **file's most recent
modification**, not a record of each boot in which it contained
messages. A file updated later than the chosen old boot will not be
listed for that older boot, even if it contains older lines. Missing
journal history can prevent calculating historical boot ranges.
The menu intentionally excludes rotated/compressed files, as before.

**Once a file is opened, the file viewer shows unfiltered text from
that file**, regardless of the menu's boot choice. **First/Last
100–5000 lines**, search, syntax coloring and refresh remain available.
The existing System journal and Kernel journal controls remain
unchanged.

### Journal advanced colors (test branch)

The `journal-advanced-colors-development` test branch adds a
**Colors: Current** button inside the System Logs journal viewer.
Clicking it switches between **Current** (the existing priority-based
scheme, default) and **Log advanced (Kate)** (the same Kate-inspired
timestamp, keyword, IP, path, hex, quoted-string and key/value coloring
as Other logs). The button is available for **System journal** and
**Kernel journal**. Switching colors rerenders already loaded records
without rerunning journalctl or altering boot, namespace, type, priority,
search, and line selection. The embedded service log viewer in the
Services tab and **Other logs** are unchanged.

Test with:
```bash
git fetch origin
git switch -c journal-advanced-colors-development --track origin/journal-advanced-colors-development
bash ./update-services.sh
```
If the local branch already exists: `git switch journal-advanced-colors-development`
then run the installer. Production stays on `services-enhancements`.

### Compact GUI-scaled log controls (test branch)

**Other logs** uses a narrower `CompactLogs.TMenubutton` ttk style,
with `Common.font_normal` and reduced padding. The journal color
switch uses `JournalColors.TButton` with the same application-scaled
font and compact padding. **Apply / Refresh** uses the
`JournalRefresh.TButton` style, also GUI-scaled and compact, with
green enabled-state text (`#65c76b`) and grey disabled-state text.
This does not alter log retrieval, highlighting, or the Services
journal embedded outside System Logs.

### Failed filter in Services (test branch)

The Services tab's **All states** dropdown now includes **Failed**.
This is based on the existing `ActiveState=failed` field, not the
unit-file `State` (Enabled/Disabled/Static/etc.). It matches the
**service units** shown by `systemctl --failed --type=service`;
plain `systemctl --failed` can also include non-service units that
are outside the Services tab. Name search and existing state filters
are unchanged. As before, refresh the Services tab to load changed
service statuses.

Test on branch `services-failed-filter-development` with
`bash ./update-services.sh`. No production changes yet.

### SMART disk health tab (test branch)

Branch `smartctl-development` adds a seventh main tab, **SMART**, alongside
System Logs. The view discovers physical disks with `lsblk -J -d -b`
(excluding loop, zram, ram, optical and other virtual devices). It collects
SMART data read-only using `smartctl -a -j /dev/DEVICE` in a worker thread.
The table shows device, model, size, overall SMART result, temperature and
power-on hours. Select a disk to see serial, protocol/transport, SATA SMART
attributes (reallocated/pending/uncorrectable sectors, CRC errors), and NVMe
critical warning, endurance percentage and media errors where reported.

The GUI **does not run as root, initiate SMART tests,
or modify any disk**. Normal **Apply / Refresh** uses unprivileged
`smartctl -a -j`. If SMART returns an explicit **Permission denied**,
the optional **Read SMART (Admin)** button uses `sudo -n` (no password
prompt or terminal interaction) and then, only when needed, `pkexec`
with a polkit graphical authentication dialog. These execute only
`smartctl -a -j` against discovered block disks; no shell or
privileged application-wide session is started. Multiple disks may
require multiple polkit authentications depending on the local agent.
Missing polkit, cancelled authentication, and refused permissions
appear as **Unavailable** with details. Some drives may also report
**Unavailable** due to an unsupported USB bridge, RAID, or missing
smartmontools. **Unknown** means SMART health is not reported; it is not
the same as Passed. SMART data may not predict all failures. A disk reporting
Passed may still have noteworthy error counters: inspect its details.

On Debian/Ubuntu, install the dependency if needed:
`sudo apt install smartmontools`. Diagnostics can be tested separately
with `sudo smartctl -a -j /dev/sdX` (use the actual disk device).
The application itself makes no privilege escalation attempts.

To test this branch:
```bash
git fetch origin
git switch -c smartctl-development --track origin/smartctl-development
bash ./update-services.sh
```
Use `git switch smartctl-development` if the branch already exists locally.
The change remains isolated from `services-enhancements` production.

### SMART Power-on time and Total writes (test branch)

SMART **Power-on** is now displayed as elapsed **days and hours** both
in the disk table and in Disk details (for example, 14791 hours becomes
`616 d 7 h`). Raw time is still retained internally from smartctl.

**Total writes** is now shown in the table and Disk details when the
drive reports a supported counter. For NVMe this uses smartctl JSON
`nvme_smart_health_information_log.data_units_written`: each reported
unit represents **1000 × 512 bytes = 512000 bytes**, rounded by the
device. A missing or zero (not reported) count shows `-`.
**Writes unit** provides **Auto / GB / TB / PB** in decimal units
(1 GB = 10^9 bytes, 1 TB = 10^12, 1 PB = 10^15).
Auto picks GB/TB/PB from magnitude. Changing the selector instantly
reformats the data already loaded; it does **not** rerun smartctl or
reauthenticate. ATA/SATA vendor-specific writes counters are **never converted
solely by SMART ID**. The code currently recognizes selected, documented
model/name combinations: Samsung SATA SSD attribute 241 named
`Total_LBAs_Written` uses 512 bytes per LBA, while Kingston SATA SSD
attribute 241 explicitly named `Host_Writes_GB` or
`Lifetime_Writes_from_Host_System` uses decimal GB. The model name and
attribute name must both match; unknown variants remain `-`.
Disk details expose `Writes source` for traceability. In particular,
NAND writes and host writes are not interchangeable.
Tests: `tests/test_smartctl_formatting.py` and
`tests/test_smartctl_data.py`.

### Manufacturer-rated TBW lookup (test branch)

The SMART tab now compares measured **Total writes** (host writes) with
the manufacturer's **rated TBW**, stored in a local, versioned
`src/SmartEndurance.json` table. A model is accepted only when its
model identifier matches a catalog record and the physical capacity is
consistent. The catalog provides model, capacity, decimal TBW and
manufacturer URL. It is entirely offline at runtime and can be extended
without changing SMART parsing code.

The expanded catalog currently contains **224 model/capacity entries**
across **Samsung, Western Digital (WD Blue/Black/Red/Green), Kingston,
Crucial, Seagate, SK hynix, and Lexar**. Records include exact model
matching patterns, capacity, rated decimal TBW, product series and a
source URL; the data is kept locally and does not require internet access
at application runtime. Sources are manufacturer warranty/endurance
tables and model datasheets, including:
- https://semiconductor.samsung.com/consumer-storage/support/warranty/
- https://support-en.sandisk.com/app/answers/detailweb/a_id/30797/~/wd-internal-ssd-endurance-and-warranty-periods
- https://content.crucial.com/content/dam/crucial/ssd-products/mx500/flyer/crucial-mx500-ssd-productflyer-en.pdf
- https://www.kingston.com/datasheets/snv2s_en.pdf
- https://www.seagate.com/files/www-content/datasheets/pdfs/firecuda-530-ssd-DS2059-3-2112US-en_US.pdf
- https://ssd.skhynix.com/platinum_p41/
- https://resources.lexar.com/download/1048/documents/13165/lexar-productsheet-ssd-nm790-en-202410.pdf

This replaces the 20-entry starter list, without enabling unsupervised
web downloads or guessing TBW from capacity alone. WD model codes
support the usual optional `WDC ` prefix and firmware/model suffix.
The optional catalog is cached and if missing/corrupt, SMART monitoring
continues without TBW data.
Kingston source:
https://www.kingston.com/en/ssd/kc3000-nvme-m2-solid-state-drive?capacity=2048gb
Samsung source:
https://semiconductor.samsung.com/consumer-storage/support/warranty/

New table columns: **Rated TBW** and **TBW used %**, the latter
calculated as `actual_host_writes_bytes / (rated_tbw * 10^12) * 100`.
Disk details show **Manufacturer rated TBW**, **Writes / rated TBW**
and **Rating source**. No match or unsupported write counter is
displayed as `-` rather than invented; e.g. `NE-256` is unknown.

**Important:** Rated TBW is manufacturer-specified endurance (often
a warranty limit), **not** the precise usable lifetime, a predicted
failure date, or a replacement for the NVMe controller's distinct
`Percentage Used`. The percentage can exceed 100 without proving a
drive has failed. It is intentionally labelled **TBW used %**, not
"remaining health".
The catalog is copied with the modules by `update-services.sh`, with
matching and ambiguity tests in `tests/test_smart_endurance.py`.

### SMART Disk details font and copying (test branch)

The **Disk details** text uses a font copied from `Common.font_normal`,
with size multiplied by **1.2** (rounded to the nearest available
font size). This follows the existing GUI font scale without changing
the general SMART table font. The panel remains **read-only**.
Copy text using **Ctrl+C** after selecting, **Ctrl+A** to select all,
right-click **Copy selection / Copy all**, or the **Copy details**
button beside the Disk details heading. These actions copy text to
the desktop clipboard and do not reread disk data or require admin.
