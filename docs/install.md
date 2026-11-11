# Installing and updating Polaris

## Quick start on a new Omarchy machine

```bash
git clone https://github.com/mstio/polaris-connector ~/Projects/polaris-connector
cd ~/Projects/polaris-connector
# check the release signature before installing (see "Signed updates" below)
awk '{print $3, $4}' keys/allowed_signers | ssh-keygen -lf -   # = release key fingerprint?
git -c gpg.program=false -c gpg.openpgp.program=false -c gpg.x509.program=false \
  -c gpg.minTrustLevel=fully -c gpg.ssh.program=ssh-keygen \
  -c gpg.ssh.allowedSignersFile="$PWD/keys/allowed_signers" log -1 --format='%G? %GS'
                                               # expected: G polaris-release
./install.sh                                   # guided: asks, shows a summary, confirms
./install.sh --dry-run --projects ~/Projekte   # no questions: only show what would happen
./install.sh --yes --projects ~/Projekte       # no questions: set up
polaris-curator llm-check --call               # model CLI logged in? (costs one small call)
```

`install.sh` is idempotent (a no-op on a machine that is already set up) and
downloads nothing. It creates:

- symlinks `~/.local/bin/polaris` and `polaris-curator`
- the bridge configuration and `project_roots`
- a `curator.yaml` from `curator/curator.example-{default,codex,claude}.yaml`, only
  if none exists (Omarchy's default agent, or an explicit `--runtime`;
  chat sources with `--chat-sources both|chatgpt|claude|none`;
  language with `--language en|de`, default `de` for a German system
  language, otherwise `en`)
- the systemd units (bridge path/timer, curator timer, radar timer)
- the Firefox native messaging host and the Omarchy widget

Replaced files are backed up to `~/.local/share/polaris/install-backups/<time>/`.
Requirements: `python3` with PyYAML (`python-yaml`), `bubblewrap` (sandbox for
foreign content; without it nothing is curated), `jq` for the widget,
`codex` or `claude` (logged in) for the curator, Firefox for the extension.
The Omarchy default agent must be set to Claude or Codex for the Curator's
default runtime. An explicit `runtime` in `curator.yaml` takes precedence.
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

`update.sh` runs `git fetch`, checks the signature of the new state (see
"Signed updates" below), fast-forward only, then
`install.sh --yes --only-existing` for what is already set up (units,
widgets, dock, memory; nothing new is added), then `polaris-curator health`,
and finally checks the companion parts: the omarchy-backup checkout in
`~/.local/share/polaris/extras/` and the git-managed widgets. New commits are
shown first and only pulled after you confirm in the terminal, or with
`POLARIS_UPDATE_EXTRAS=1 polaris update` (with `--yes` they are only shown).
An active Claude guard hook is never replaced by an update; after reviewing
the shown diff, adopt it with `POLARIS_ADOPT_GUARD=1 ~/.local/share/polaris/app/install.sh --yes --only-existing`. Local commits or modified files abort the update
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

### Signed updates

Since 2026-11-11 (suggested by a user) `polaris update` only takes a new
state whose newest commit carries a valid SSH signature from a key in
`~/.config/polaris/allowed_signers`. Without it, anyone who can push to the
GitHub repository (a stolen token, a compromised account) would decide which
code runs on every machine at the next update.

- **New install:** `install.sh` trusts the key in the clone once (trust on
  first use). The check in the quick start only helps if you compare the
  fingerprint with one you got outside GitHub, for example from the
  maintainer directly; the value below comes from the same repository and
  would be swapped together with the key. Without such a second channel you
  trust GitHub at install time, and from then on only the pinned key.
- `install.sh` creates `~/.config/polaris/allowed_signers` once from
  `keys/allowed_signers` and never replaces it. The trust anchor is your copy,
  not the file in the repository, so a compromised repository cannot swap the
  key unnoticed. If they differ, `install.sh` warns and leaves yours alone.
- Release key fingerprint (compare once, on a second channel if you can):
  `SHA256:/dq2rdkVooggf6DNSBzEJ6d5rb6L0/RZ6BOYi3+xvQQ` (ED25519)
- No signature, or a key that is not in your anchor: the update stops, with
  `--yes` too, and nothing changes. There is no switch to skip the check.
  Take it seriously: either the repository was tampered with, or the key was
  changed (then the changelog says so, and the new key is announced first).
- Key change: check the new fingerprint, then replace the file by hand
  (`cp ~/.local/share/polaris/app/keys/allowed_signers ~/.config/polaris/`).
- **Existing installs, once:** the update that brings this check is itself
  still taken unchecked by your old `update.sh`. Check it before you update:

  ```bash
  APP=~/.local/share/polaris/app
  git -C "$APP" fetch
  git -C "$APP" show '@{u}:keys/allowed_signers' > /tmp/polaris-signers
  awk '{print $3, $4}' /tmp/polaris-signers | ssh-keygen -lf -   # = fingerprint above?
  git -C "$APP" -c gpg.program=false -c gpg.openpgp.program=false \
    -c gpg.x509.program=false -c gpg.minTrustLevel=fully -c gpg.ssh.program=ssh-keygen \
    -c gpg.ssh.allowedSignersFile=/tmp/polaris-signers log -1 --format='%G? %GS' '@{u}'
  # expected output: G polaris-release
  ```

  Only if the fingerprint matches the one you got on a second channel and
  the last command prints `G polaris-release`, run `polaris update`. It then
  prints the anchor's fingerprint once more.
- Limits: the very first install trusts GitHub. A compromised machine of the
  publisher is not covered. Companion parts (omarchy-backup, widgets) are not
  signed yet; they are only shown before they are pulled.
- Check by hand (PGP and X.509 switched off, so only the SSH anchor counts;
  expected output `G polaris-release`):
  `git -C ~/.local/share/polaris/app -c gpg.program=false -c gpg.openpgp.program=false -c gpg.x509.program=false -c gpg.minTrustLevel=fully -c gpg.ssh.program=ssh-keygen -c gpg.ssh.allowedSignersFile=$HOME/.config/polaris/allowed_signers log -1 --format='%G? %GS' '@{u}'`

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
systemctl --user list-units 'polaris-*' --state=active --no-legend  # must print nothing; else stop them first
cp -a "$APP" "$APP.vor-git-$(date +%Y%m%d-%H%M%S)"  # full copy: the checkout below overwrites local changes
cd "$APP"
[ -d .git ] || git init -q
git remote set-url origin https://github.com/mstio/polaris-connector.git 2>/dev/null \
  || git remote add origin https://github.com/mstio/polaris-connector.git
git fetch origin
git branch bundle-old 2>/dev/null || true        # keeps your own commits, if any (needs a commit; the copy above covers the rest)
git checkout -B main origin/main --force         # replaces the files with this repository
# 3. set up again and check
./install.sh --dry-run --yes --storage-unit none # or your own drive unit instead of none
./install.sh --yes --storage-unit none
omarchy restart shell
polaris update --check                           # "up to date"
# once everything works for a few days: rm -r "$APP".vor-git-*
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
