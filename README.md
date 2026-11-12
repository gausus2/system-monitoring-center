# System Monitoring Center — Stable

System Monitoring Center for Linux, with expanded **Services**, **System Logs** and **SMART** disk monitoring.

Original project: [hakandundar34coding/system-monitoring-center](https://github.com/hakandundar34coding/system-monitoring-center).

## Features

- **Services:** search, filter by state (including failed services), sort and copy the visible table; inspect units, dependencies, boot plots, edit overrides and view service logs
- **System Logs:** system and kernel journal, namespace, boot, time, priority and unit-type filters, searchable logs, optional color highlighting and right-click copy
- **Other Logs:** view and filter log files under `/var/log`
- **SMART:** health, temperature, power-on hours, total writes, manufacturer TBW, NVMe wear, media errors and firmware; currently mounted filesystems and ext4/NTFS filesystem date metadata
- Copy table and Copy details for convenient plain-text output

## Install (Ubuntu / Debian)

This version updates an **existing system-installed** System Monitoring
Center v3 (Tkinter). Install the original application first. The installer
needs its files at
`/usr/share/system-monitoring-center/systemmonitoringcenter`;
a Flatpak installation alone is not sufficient.

### 1. Install the original application (.deb)

Download the upstream v3.4.1 Debian package from the
[original project's releases](https://github.com/hakandundar34coding/system-monitoring-center/releases/tag/v3.4.1):

```bash
wget https://github.com/hakandundar34coding/system-monitoring-center/releases/download/v3.4.1/system-monitoring-center_3.4.1_all.deb
sudo apt install ./system-monitoring-center_3.4.1_all.deb
```

This installs the original program and lets APT resolve its package
dependencies. If it is already installed in the required location, skip
this step. **Do not reinstall the original .deb over an already customized
installation**, as that can overwrite modified files.

### 2. Install tools for the extra features

```bash
sudo apt install git smartmontools nvme-cli ntfs-3g e2fsprogs util-linux
```

`smartctl` reads SMART data; `ntfsinfo` (from `ntfs-3g`) reads NTFS
root-directory timestamps; `tune2fs` reads ext4 creation dates.

### 3. Clone stable and apply the updates

The update script replaces selected Python modules in the system-installed
application, while retaining backups of the originals.

```bash
git clone --branch stable --single-branch https://github.com/gausus2/system-monitoring-center.git
cd system-monitoring-center
bash ./update-services.sh
```

## Update an existing installation

If you already have a checkout with the `stable` branch, use:

```bash
git switch stable
bash ./update-services.sh
```

The script checks the branch, pulls the latest version, runs regression
tests and installs the updated modules using `sudo`. Close and restart
System Monitoring Center after installation.



```bash
git clone --branch stable --single-branch https://github.com/gausus2/system-monitoring-center.git
cd system-monitoring-center
bash ./update-services.sh
```

## Notes

- SMART reads are read-only. Some disks require the **Read SMART (Admin)** button.
- Filesystem creation timestamps are **not** SSD manufacturing dates or guaranteed first-use dates. NTFS timestamps are taken from the root directory and can be older than the current physical drive after cloning.
- Backups of original installed modules are kept as `*.pre-services-enhancements`.

For detailed technical change notes, see [SERVICES_ENHANCEMENTS_README.md](SERVICES_ENHANCEMENTS_README.md).
