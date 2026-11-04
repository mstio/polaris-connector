# Installing and updating Polaris

## Quick start on a new Omarchy machine

```bash
git clone https://github.com/mstio/polaris-connector ~/Projects/polaris-connector
cd ~/Projects/polaris-connector
./install.sh                                   # guided: asks, shows a summary, confirms
./install.sh --dry-run --projects ~/Projekte   # no questions: only show what would happen
./install.sh --yes --projects ~/Projekte       # no questions: set up
polaris-curator llm-check --call               # model CLI logged in? (costs one small call)
```

`install.sh` is idempotent (a no-op on a machine that is already set up) and
downloads nothing. It creates:

- symlinks `~/.local/bin/polaris` and `polaris-curator`
- the bridge configuration and `project_roots`
- a `curator.yaml` from `curator/curator.example-{codex,claude}.yaml`, only
  if none exists (runtime `codex` if installed, otherwise `claude`, or
  `--runtime`; chat sources with `--chat-sources both|chatgpt|claude|none`;
  language with `--language en|de`, default `de` for a German system
  language, otherwise `en`)
- the systemd units (bridge path/timer, curator timer, radar timer)
- the Firefox native messaging host and the Omarchy widget

Replaced files are backed up to `~/.local/share/polaris/install-backups/<time>/`.
Requirements: `python3` with PyYAML (`python-yaml`), `jq` for the widget,
`codex` or `claude` (logged in) for the curator, Firefox for the extension.
The extension itself is installed by hand (see
[Installing the extension](browser-capture.md#installing-the-extension-firefox)).

`monitoring.chat_sources` in `~/.config/polaris/curator.yaml` decides which
browser chats the health check watches: `[chatgpt, claude]`, `[chatgpt]`,
`[claude]` or `[]`. It is independent of the model runtime: with `[]` the
curator can still use another model via `runtime: command` and process inbox
documents, and the missing extension is not reported. Grok chats are not
captured.

**Language.** `language: en` or `language: de` in
`~/.config/polaris/curator.yaml` sets the language of the widget and the
health check (takes effect at the next widget refresh). A `curator.yaml`
without this line stays German, so existing installations do not change.
The entries the curator writes into `knowledge.md`, `decisions.md` and
`open-loops.md` still use German field labels for now.

omarchy-backup and the machine memory (`~/.config/ai-agents`) are optional
(`--no-backup`, `--no-memory`); the health check then shows them as "not set
up". Companion parts come from their own public git repositories: the
backup and agent launcher widgets and the dock via `omarchy plugin add`, the
omarchy-backup CLI via `git clone` into `~/.local/share/polaris/extras/`.
Nothing else is downloaded and no packages are installed.

Running `install.sh` with options (`--yes`, `--projects`, `--backup-target`,
`--memory-mirror`, `--storage-unit`, `--no-units`, `--no-widget`, `--no-dock`,
`--no-backup`, `--no-memory`, …; see `install.sh --help`) or without a
terminal skips the questions.

### Updating: `polaris update`

A git checkout (for example a clone of this repository) updates like an
Omarchy plugin:

```bash
polaris update            # show changes, ask, update
polaris update --yes      # no question (for agents)
polaris update --check    # only look; exit 0 = update available
```

`update.sh` runs `git fetch`, fast-forward only, then
`install.sh --yes --only-existing` for what is already set up (units,
widgets, dock, memory; nothing new is added), then `polaris-curator health`,
and finally pulls the companion parts: the omarchy-backup checkout in
`~/.local/share/polaris/extras/` (fast-forward) and the git-managed widgets
(`omarchy plugin update`). Local commits or modified files abort the update
(your own changes belong in a branch or pull request). If the health check
turns red or `install.sh` fails, it goes back to the previous commit. At most
once a day the health check shows "Update: available …". The version number
is the extension's.

If your project folders live on a drive mounted by its own systemd unit (for
example rclone), bridge, curator and mirror start after it:
`install.sh --storage-unit <unit>` adds drop-ins
`<unit>.d/polaris-storage.conf` (default: `rclone-projekte.service` if it
exists). Local folders, such as a Nextcloud sync folder, need nothing
(`--storage-unit none`).

### Switching from the install bundle to a git checkout

An installation from the bundle keeps its program files in
`~/.local/share/polaris/app` without a shared git history, so
`polaris update` does not work there. **Careful:** this repository has no
`extras/` (omarchy-backup and the widgets `mst.omarchy-backup` and
`mst.agent-launchers`). If `~/.local/bin/omarchy-backup` points into the app
folder, switching breaks omarchy-backup. Move `extras/` out first:

```bash
APP=~/.local/share/polaris/app
readlink -f ~/.local/bin/omarchy-backup          # points into $APP/extras/...?
# 1. move extras/ out of the program folder
mkdir -p ~/.local/share/polaris-extras
cp -a "$APP"/extras/. ~/.local/share/polaris-extras/
~/.local/share/polaris-extras/omarchy-backup/install.sh   # re-links, keeps its configuration
printf 'include ~/.local/share/polaris-extras\n' > ~/.config/omarchy-backup/paths.d/polaris-extras.conf
omarchy-backup doctor                            # must report HEALTHY
# 2. switch the program folder to this repository, keep the old state
cd "$APP"
[ -d .git ] || git init -q
git remote set-url origin https://github.com/mstio/polaris-connector.git 2>/dev/null \
  || git remote add origin https://github.com/mstio/polaris-connector.git
git fetch origin
git branch bundle-old 2>/dev/null || true        # keeps your own commits, if any
git checkout -B main origin/main --force         # replaces the files with this repository
# 3. set up again and check
./install.sh --dry-run --yes --storage-unit none # or your own drive unit instead of none
./install.sh --yes --storage-unit none
omarchy restart shell
polaris update --check                           # "up to date"
```

The widgets keep running from their copies in `~/.config/omarchy/plugins/`,
but copies are never updated. Switch them to git once, so that
`polaris update` (via `omarchy plugin update`) keeps them current:

```bash
omarchy plugin remove mst.agent-launchers --yes && omarchy plugin add https://github.com/mstio/mst.agent-launchers.git --enable --yes
omarchy plugin remove mst.omarchy-backup --yes && omarchy plugin add https://github.com/mstio/mst.omarchy-backup.git --enable --yes
```

`install.sh` reminds you of this while a copy is in place. From then on
`polaris update` is enough.

---

[Back to the README](../README.md)
