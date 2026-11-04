# Backup and extras

## Backup: omarchy-backup

[omarchy-backup](https://github.com/mstio/omarchy-backup) freezes a working
Omarchy setup: snapshots, a baseline with drift detection, a verified remote
backup (`omarchy-backup doctor`) and recovery on a fresh install.
[Its bar widget](https://github.com/mstio/mst.omarchy-backup) (shown
[above](../README.md#what-you-get)) takes snapshots, marks baselines and sets the
schedule. Polaris uses it to back up the machine memory, and the health check
shows its state in the line "Storage & backup". `--backup-target <folder>`
turns on daily snapshots to that folder; `--no-backup` leaves it out.

## Extras: agent launchers and dock

The [agent launcher widget](https://github.com/mstio/mst.agent-launchers)
starts your AI agent CLIs from the bar; the
[dock](https://github.com/thepathless/omadock) is an app dock for Omarchy.
`--no-widget` and `--no-dock` leave them out.

## How companion repos are installed and updated

Backup and extras are separate projects. `install.sh` fetches them from git,
`polaris update` keeps them current. An existing installation of your own (for
example an omarchy-backup checkout elsewhere) is left alone. On an existing
installation, `install.sh --yes` does not add widgets you never had; it prints
the `omarchy plugin add` command instead.

---

[Back to the README](../README.md)
