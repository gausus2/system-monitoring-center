# System Monitoring Center — Stable

System Monitoring Center for Linux, with expanded **Services**, **System Logs** and **SMART** disk monitoring.

Original project: [hakandundar34coding/system-monitoring-center](https://github.com/hakandundar34coding/system-monitoring-center).

## Features

- **Services:** search, filter by state (including failed services), sort and copy the visible table; inspect units, dependencies, boot plots, edit overrides and view service logs
- **System Logs:** system and kernel journal, namespace, boot, time, priority and unit-type filters, searchable logs, optional color highlighting and right-click copy
- **Other Logs:** view and filter log files under `/var/log`
- **SMART:** health, temperature, power-on hours, total writes, manufacturer TBW, NVMe wear, media errors and firmware; currently mounted filesystems and ext4/NTFS filesystem date metadata
- Copy table and Copy details for convenient plain-text output

## Install / update

**Prerequisite:** System Monitoring Center must already be installed on the system at
`/usr/share/system-monitoring-center/systemmonitoringcenter`.
The script updates its Python modules; it is **not** a standalone
installer of the original application. For the original application
and its dependencies, see the link above.

Install `smartmontools` and `ntfs-3g` if you want SMART data and NTFS
filesystem timestamps. The application uses `lsblk` and `tune2fs`
for mount information and ext4 filesystem timestamps.

Clone this stable branch and apply the updates:

```bash
git clone --branch stable --single-branch https://github.com/gausus2/system-monitoring-center.git
cd system-monitoring-center
bash ./update-services.sh
```

To update an existing checkout:

```bash
git switch stable
bash ./update-services.sh
```

The script checks the branch, pulls the latest version, runs regression
tests and installs the updated modules using `sudo`. Close and restart
System Monitoring Center after installation.

## Notes

- SMART reads are read-only. Some disks require the **Read SMART (Admin)** button.
- Filesystem creation timestamps are **not** SSD manufacturing dates or guaranteed first-use dates. NTFS timestamps are taken from the root directory and can be older than the current physical drive after cloning.
- Backups of original installed modules are kept as `*.pre-services-enhancements`.

For detailed technical change notes, see [SERVICES_ENHANCEMENTS_README.md](SERVICES_ENHANCEMENTS_README.md).
