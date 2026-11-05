# Health check

`polaris-curator health` (and the widget) shows one line per area: capture,
project separation, curator, storage and backup, machine memory, security,
update, system (disk usage, failed systemd units, battery, recent crashes).
`--all` shows every single check. Exit codes and JSON output are meant for
agents as well as for people.

Hints on things that are easy to overlook (since 2026-11-05):

- **Backup destination:** shows the result of omarchy-backup's last
  destination check right away (red if files there changed outside this
  machine), not only after the next `omarchy-backup doctor`.
- **Repos:** a git repository in the backup has new files that git does not
  track. omarchy-backup saves a repository as its git content, so such a file
  is in **no** snapshot. The line names the file. What to do:
  - the file matters: commit it (`git -C <repo> add <file>` and
    `git -C <repo> commit`), or ask your agent to do it;
  - it does not (build output, scratch): add it to the repo's `.gitignore`.
  The line then says "resolved"; the next snapshot (nightly) backs it up.
  A repository that went missing (moved or deleted): fix its path in
  `~/.config/omarchy-backup/paths.conf`.
- **Reboot:** the kernel was updated but the machine not restarted (the
  running kernel's modules are gone).
- **Disk errors:** btrfs read, write and checksum error counters (sysfs, no
  root needed); anything above 0 is red.

All of them only read local files; no extra timers or network access.

Not every hint is always a line, even with `--all`:

- **Reboot** appears only when a reboot is actually due.
- **Backup destination** appears only when omarchy-backup has a remote
  destination and has checked it at least once (omarchy-backup from
  2026-11-05 on; written by a snapshot, `omarchy-backup doctor` or an upload
  to `~/.local/share/omarchy-backup/integrity-status.json`). No line means:
  no check result yet, not "everything fine".
- **Disk errors** appears only on machines with btrfs.

In the widget every problem line offers **Ask agent**: it opens your agent
(the curator's runtime, `claude` or `codex`) in a terminal with the message
and the request to find the cause and propose a fix, changing nothing before
you agree. Safer than running a command blindly. Where the check knows a
fitting command, the agent gets it as a suggestion; nothing is run from the
widget. From a terminal: `polaris-curator health --ask <id>` (ids in
`polaris-curator health --json`).

---

[Back to the README](../README.md)
