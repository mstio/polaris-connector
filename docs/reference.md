# Reference: paths, uninstalling, tests

## Paths

| What | Path |
|---|---|
| Code (git checkout) | `~/Projects/polaris-connector/` (older installs from the bundle: `~/.local/share/polaris/app`) |
| Companion CLI | `~/.local/share/polaris/extras/omarchy-backup/` (git checkout, if no own installation exists) |
| CLIs | `~/.local/bin/polaris`, `polaris-curator`, `polaris-radar`, `polaris-memory-mirror` |
| Configuration | `~/.config/polaris/` (`config.yaml` with `project_roots`, `projects.yaml` mappings, `curator.yaml`, `radar.yaml`) |
| Browser inbox | `~/Downloads/polaris-inbox/` |
| Pending / processed / failed | `~/.local/share/polaris/{pending,processed,failed}/` |
| State and logs | `~/.local/state/polaris/` (`polaris.log`, `security.json`, `nvd.json`, install logs) |
| systemd units | `~/.config/systemd/user/polaris-*.{service,path,timer}` (copies from `systemd/`; curator units see `curator/README.md`) |
| Widget | `~/.config/omarchy/plugins/mst.polaris-curator/` (copy of `omarchy-plugin/`) |
| Machine memory | `~/.config/ai-agents/` |

## Uninstalling

```bash
systemctl --user disable --now polaris-bridge.path polaris-bridge.timer polaris-radar.timer polaris-memory-mirror.timer
rm ~/.config/systemd/user/polaris-bridge.{path,service,timer} ~/.config/systemd/user/polaris-radar.{service,timer} \
   ~/.config/systemd/user/polaris-memory-mirror.{service,timer}
systemctl --user daemon-reload

bridge/install-native-host.sh --remove   # before deleting the repository

rm ~/.local/bin/polaris ~/.local/bin/polaris-radar ~/.local/bin/polaris-memory-mirror
rm -rf ~/Projects/polaris-connector
rm -rf ~/.config/polaris ~/.local/share/polaris ~/.local/state/polaris ~/Downloads/polaris-inbox
```

Curator units and files are removed separately (see `curator/README.md`).
Archived raw data under `<project>/raw/` and the curated files stay in your
project folders on purpose: they are your data. The machine memory
(`~/.config/ai-agents`) is left alone as well. Extension: `about:addons` →
Polaris → Remove.

## Tests

```bash
(cd tests && POLARIS_NO_NOTIFY=1 python3 -m unittest discover)          # bridge, privacy check, extension (if node exists)
node --test tests/extension/                                              # extension only
(cd curator/tests && POLARIS_NO_NOTIFY=1 python3 -m unittest discover)   # curator, health check
python3 -m unittest discover -s memory/tests                             # memlint, radar, mirror
```

Plain `unittest`, no extra packages, no network. Extension tests run in a
`vm` sandbox with fake clock, timers, DOM and fetch (`harness.mjs`,
`minidom.mjs`); `POLARIS_CONTENT_JS=<file>` runs them against another state of
`content.js`. Tests only touch temporary directories; start them with
`POLARIS_NO_NOTIFY=1` and, to be safe, a redirected `HOME`.

---

[Back to the README](../README.md)
