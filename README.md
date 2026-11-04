<div align="center">

# Polaris

### *Your project chats, documents and mails become a project memory you own, for [Omarchy](https://omarchy.org)*

<p>
  <a href="#install"><b>Install</b></a> •
  <a href="#what-you-get"><b>What you get</b></a> •
  <a href="#architecture-core-and-modules"><b>Architecture</b></a> •
  <a href="#module-browser-capture-chatgpt-and-claude"><b>Browser capture</b></a> •
  <a href="#cross-cutting-modules"><b>Health, radar, memory</b></a> •
  <a href="#privacy-and-legal-notice"><b>Privacy</b></a>
</p>

</div>

You work on projects with ChatGPT and Claude, and the decisions, facts and
open questions end up scattered across dozens of chats, documents and mails.
Polaris collects them per project while you work and has the coding agent you
already use write a short, sourced memory for each project: **what is known,
what was decided, what is still open.** It lives as plain Markdown in your own
project folders, readable by you, your editor and every AI agent on your
machine.

No account, no cloud service, no database. The only thing that leaves your
computer is what the curator hands to your own agent CLI (Codex, Claude Code,
or any command, local models included). Every entry links back to the chat
message or file it came from.

In daily use with **ChatGPT and Claude**, whose project chats are captured
automatically. Any other assistant that organises work in projects (Gemini,
Grok, Perplexity, …) can feed Polaris today through the inbox, as exported
or pasted chats and documents. Automatic capture for another assistant means
one more extension module plus its mapping in the bridge; contributions are
welcome (see [CONTRIBUTING.md](CONTRIBUTING.md)).

## Install

```bash
git clone https://github.com/mstio/polaris-connector ~/Projects/polaris-connector
~/Projects/polaris-connector/install.sh     # guided: asks, shows a summary, then sets up
```

Then install the signed Firefox extension from the
[latest release](https://github.com/mstio/polaris-connector/releases/latest)
and switch sync on for a ChatGPT or Claude project. `polaris update` keeps
everything current. Details: [Quick start](#quick-start-on-a-new-omarchy-machine).

## What you get

- **Chats archived as you go.** A Firefox extension saves finished turns of
  ChatGPT and Claude *project* chats into the matching project folder. No
  copy and paste, nothing from chats outside a project. Other assistants:
  via the inbox for now.
- **Documents and mails, too.** Drop files or `.eml` mails (with attachments,
  Word, Excel, PowerPoint) into a project's `inbox/`.
- **A memory per project.** `knowledge.md`, `decisions.md` and
  `open-loops.md`: condensed, deduplicated, kept current, every entry with its
  source. Unclear cases wait for you; Polaris never guesses a project.
- **One glance in your bar.** A theme-aware Omarchy widget shows new material
  per project, starts curation, opens the knowledge files and tells you when
  something is broken: capture, curation, backup, disk, security.
- **Cheap in the background.** No polling daemons: systemd path units,
  timers and on-demand processes only.
- **Optional extras:** a daily security check for your Omarchy machine
  (Arch advisories, kernel, actively exploited CVEs), a shared memory for all
  your local AI agents, and [omarchy-backup](https://github.com/mstio/omarchy-backup)
  for snapshots and fresh-install recovery.

Current extension version: see `extension/manifest.json`. What changed between
versions: [`CHANGELOG.md`](CHANGELOG.md) (German). Most detailed documents in
this repository are written in German.

## Privacy and legal notice

Polaris is a tool, not a compliance solution. You are responsible for using
it in line with the law that applies to you (in the EU: the GDPR) and with
your providers' terms. Please check before you use it, especially at work.

- **What it stores:** copies of your project chats, documents and mails, and
  curated summaries that can attribute statements to named people. All of
  it stays in your own folders; delete a project folder and it is gone.
- **What leaves your machine:** whatever the curator hands to the agent CLI
  you configure. That provider's terms and data processing apply (for
  example OpenAI for Codex, Anthropic for Claude Code). To keep everything
  local, use a local model via `runtime: command`.
- **Other people's data:** chats and mails often contain names, contact
  details and opinions of third parties. Purely personal use may fall under
  the household exemption; professional use usually does not. Then you
  typically need a legal basis, a data processing agreement with the model
  provider, information for the people concerned and deletion rules. Ask
  your data protection officer or legal adviser.
- **Provider terms:** the extension reads your own chats through the web
  apps' internal interfaces. Check that this is compatible with the terms of
  the services you use.

This notice is not legal advice. Polaris comes without warranty (MIT
licence).

## Architecture: core and modules

Polaris is a small **core** with **modules** around it. The core is the
project memory; everything else feeds it, shows it or keeps the machine
healthy.

| Part | What it is | Lives in |
|---|---|---|
| **Core: project memory** | Project folder layout, the curator that condenses sources into knowledge, the `polaris` / `polaris-curator` CLIs | `curator/`, `bridge/polaris/mapping.py`, `bridge/bin/polaris` |
| Source: browser capture | Firefox extension + native messaging host + bridge; archives ChatGPT and Claude project chats turn by turn into `raw/` | `extension/`, `bridge/` |
| Source: ChatGPT data export | Fills gaps from the official export, or files old chats as Markdown without curation | `polaris import-export`, `polaris archive-export` |
| Source: inbox | Documents, notes and mails dropped into `<project>/inbox/` | `curator/` (see `curator/README.md`) |
| Model runtimes | The curator calls an agent CLI: `codex`, `claude` or any command | `curator/curator.example-*.yaml` |
| Display: curator widget | Omarchy bar widget: pending sources, start runs, open knowledge files, health check | `omarchy-plugin/mst.polaris-curator/` |
| Cross-cutting: health check | One overview of capture, curation, backup, memory, security and system state | `curator/polaris_curator/systemhealth.py` |
| Cross-cutting: radar | Omarchy news, plugin updates and a daily security check (Arch tracker, kernel, CISA KEV, NVD) | `memory/tools/polaris-radar` |
| Cross-cutting: machine memory | Shared Markdown memory for all local AI agents, with linter, template and mirror | `memory/` |
| Companion repos | [omarchy-backup](https://github.com/mstio/omarchy-backup) and [its widget](https://github.com/mstio/mst.omarchy-backup), [agent launchers](https://github.com/mstio/mst.agent-launchers), dock | fetched by `install.sh` via git |
| Developer tooling | Privacy check with protected folders, template sync check, public mirror | `scripts/` |

```
 ChatGPT / Claude (Firefox)     official export      documents, mails
          |                          |                      |
   extension -> native host     polaris import-export       |
          |      -> bridge           |                      |
          v                          v                      v
   <project>/raw/<chatgpt|claude>/  ...................  <project>/inbox/
                         \                              /
                          `----> polaris-curator <-----'      model runtime
                                       |                  <-- (codex, claude,
                                       v                       any command)
              <project>/knowledge.md, decisions.md, open-loops.md
                                       |
          curator widget, health check, your agents, your editor
```

Direction of travel: the health check should only read one state file per
module (the radar already works that way with
`~/.local/state/polaris/security.json`), so that it can become a standalone
package and modules can be installed one by one. Today `install.sh` still
sets up all modules together and the health check knows each of them.

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
  `--runtime`; chat sources with `--chat-sources both|chatgpt|claude|none`)
- the systemd units (bridge path/timer, curator timer, radar timer)
- the Firefox native messaging host and the Omarchy widget

Replaced files are backed up to `~/.local/share/polaris/install-backups/<time>/`.
Requirements: `python3` with PyYAML (`python-yaml`), `jq` for the widget,
`codex` or `claude` (logged in) for the curator, Firefox for the extension.
The extension itself is installed by hand (see
[Installing the extension](#installing-the-extension-firefox)).

`monitoring.chat_sources` in `~/.config/polaris/curator.yaml` decides which
browser chats the health check watches: `[chatgpt, claude]`, `[chatgpt]`,
`[claude]` or `[]`. It is independent of the model runtime: with `[]` the
curator can still use another model via `runtime: command` and process inbox
documents, and the missing extension is not reported. Grok chats are not
captured.

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

## Core: project memory

### Project folders

Polaris works on ordinary folders below one or more **project roots**. Each
project folder gets:

```
<project>/
  raw/chatgpt/messages/<message-id>.json         archived turns (browser capture, export)
  raw/chatgpt/conversations/<conversation-id>.json
  raw/claude/...                                 the same for Claude
  inbox/{documents,notes,mail}/                  drop documents and mails here
  knowledge.md  decisions.md  open-loops.md      curated knowledge
  dokumente-index.md                             index of processed documents
  .polaris/                                      curator state, journal, backups
```

Raw data is append-only and never summarised; the curated files are written
by the curator and stay readable and editable.

```bash
polaris roots                     # roots with number of project folders
polaris roots add <folder>        # folder that contains the project folders
polaris roots remove <folder>     # refused while mappings point into it (--force)
```

On first start only `~/Projekte` is added automatically, if it exists. A root
does not have to be a cloud drive; any local or mounted folder works. Keep
code and program state outside the project roots so that no git repository or
bridge state ends up in a cloud sync. The health check (line "project
folders") checks every root: a missing root or missing mapped project folders
(typically a dropped mount) is an error; for rclone mounts it also watches the
upload backlog.

### Project mapping

Chat projects are mapped to project folders automatically, in this order:
known mapping → exact name → normalised name (case, `_`/`-`, numbering
prefixes) → fuzzy match only when it is unambiguous. When unsure, the
messages wait as **pending**; Polaris never guesses.

```bash
polaris projects                          # known mappings
polaris pending                           # unknown projects with candidates (informational only)
polaris map <project-id> <local-path>     # also re-processes waiting messages of that project
polaris unmap <project-id>
polaris status                            # inbox size, events, projects, conversations, last run
```

The target must be inside a configured project root; anything else is refused
(protection against wrong assignments and path traversal).

### Curator

`polaris-curator` reads new raw turns and inbox documents per project, asks
the configured model runtime for changes and merges them atomically into
`knowledge.md`, `decisions.md` and `open-loops.md`, with a source reference
for every entry. A systemd timer runs it; the widget can start it by hand.
Classification rules, budgets, journal, compaction, retraction and document
handling are described in [`curator/README.md`](curator/README.md) (German).

## Module: browser capture (ChatGPT and Claude)

Archives selected ChatGPT and Claude **project** conversations locally, turn
by turn, as raw data. No summary, no AI, no cloud infrastructure.

```
ChatGPT (chatgpt.com) / Claude (claude.ai), in Firefox
   |  ChatGPT: raw conversation snapshot from the web app API (chatgpt_api.js),
   |           page DOM (extractor.js) only as a fallback
   |  Claude:  JSON API of the web app (claude.js)
   v
extension/  (Firefox WebExtension, MV3)
   |
   |  main path: native messaging -> bridge/bin/polaris-native-host
   |     Firefox starts the host on demand (~50 ms, ~14 MB); the port
   |     closes after 30 s idle. No download, no downloads folder.
   |  fallback (host not registered/reachable): downloads.download()
   |     -> blob: URL (Firefox refuses data: URLs for this)
   v
~/Downloads/polaris-inbox/*.json      (bridge inbox; the host writes atomically
   |                                   and processes immediately)
   |  fallback downloads: systemd --user path unit (polaris-bridge.path),
   |  safety net every 10 min: polaris-bridge.timer
   v
polaris-bridge.service  ->  `polaris process`
   |
   v
bridge/polaris/  (Python, stdlib + PyYAML)
   - schema.py    validation
   - snapshot.py  conversation snapshot / data export -> turns (the only interpretation)
   - mapping.py   project ID (ChatGPT/Claude) -> local project folder (persisted)
   - matching.py  exact / normalised / fuzzy
   - storage.py   atomic, append-only storage, conflict checks
   v
<project>/raw/<chatgpt|claude>/messages/<message-id>.json
<project>/raw/<chatgpt|claude>/conversations/<conversation-id>.json
```

The parts are deliberately separate: the extension knows no project paths and
does not interpret chats; the bridge knows no ChatGPT DOM.

### Installing the extension (Firefox)

The extension is registered at addons.mozilla.org (AMO) as an **unlisted**
add-on (add-on ID 3070992, extension ID
`polaris-chatgpt-connector@mstarchy.local`) and signed there. A signed `.xpi`
installs permanently, also on release Firefox. The newest one is attached to
[the latest release](https://github.com/mstio/polaris-connector/releases/latest):
download it and drag it into a Firefox window.

Since 0.4.2 the manifest has an `update_url`
(`raw.githubusercontent.com/mstio/polaris-connector/main/updates.json`):
installed copies check about once a day and update themselves. 0.4.1 and
older must be brought to 0.4.2 once by hand. Never change the `update_url`,
or old installations ask into the void. Granted permissions stay with the
extension ID and survive updates.

**Permissions for chatgpt.com / claude.ai:** Firefox treats `host_permissions`
of MV3 extensions as optional. Without them the extension only runs after a
click on its icon. Click "allow access permanently" in the popup, or grant
both sites in `about:addons` → Polaris → Permissions.

**Native messaging:**

```bash
bridge/install-native-host.sh           # registers polaris_bridge with Firefox
bridge/install-native-host.sh --remove  # removes the registration
```

This writes `~/.mozilla/native-messaging-hosts/polaris_bridge.json` (pointing
to `bridge/bin/polaris-native-host`). Firefox also looks there when the
profile lives under `~/.config/mozilla/`. The script does not create
`~/.mozilla` itself, so start Firefox once first. Without the registration the
extension keeps working through downloads. Protocol and behaviour:
`bridge/polaris/native_host.py`.

The extension remembers per conversation which messages it already handed
over (`storage.local`, IDs only, at most 500 conversations), so returning to a
conversation does not export again.

**Development: loading temporarily.** To test an unsigned state:
`about:debugging#/runtime/this-firefox` → "Load Temporary Add-on…" →
`extension/manifest.json`. It overrides the installed version until the next
Firefox restart; the health check shows the override in yellow.

### Turning sync on

1. Open a ChatGPT chat that belongs to a ChatGPT project.
2. Click the extension icon in the toolbar.
3. The detected project name appears. Switch "Sync project" on. For new
   Claude projects (and ChatGPT projects that cannot be mapped unambiguously)
   pick the target under "storage folder" and click "assign".
4. From now on new, finished turns of this project are exported
   automatically. Single chats can be left out with "Exclude this chat".
5. "Sync now" exports by hand (fallback, for example right after enabling,
   for messages already in the current chat).

New projects start with sync off.

### ChatGPT via the web app API (since 0.4.0)

The extension reads ChatGPT conversations through the web app's own API
(`extension/chatgpt_api.js`: `/api/auth/session` for the session token, then
`/backend-api/conversation/<id>`) and passes the **raw** JSON to the bridge
as a snapshot (native host `export-snapshot`, otherwise a snapshot file in
the inbox). It interprets nothing. Only the bridge turns it into turns
(`bridge/polaris/snapshot.py`), with the same function as for the official
data export, which has the same format:

- The project comes from the provider data (`gizmo_id`); the page's hint
  (project/chat from the address) is only cross-checked. If they differ,
  nothing is stored. Chats without a project are never archived.
- A turn is a user message, or everything between two user messages
  (assistant, tool steps, reasoning); its ID is the earliest message,
  `member_ids` lists all. If a part is already archived under another ID
  (for example from the old DOM capture), that ID wins: no duplicates.
- A last answer still in progress (tool step, `in_progress`,
  `end_turn=false`) waits for the next snapshot. The extension polls every
  20 s (visible tab only) and sends only when `update_time` changed.

Why: up to 0.3.0, DOM capture, API mode and export import decided separately
what a turn is, which ID it has and when it is finished, which caused mixed
up projects, duplicates and truncated answers. The DOM is now read only when
the API does not answer (the popup shows why). That fallback is guarded
against stale page content (no export without a chat ID, snapshot on chat
switch, text keys for turns without ID, last answer only after 8 s without
change) and also sends `member_ids`. It can be switched off in the popup.

### Claude (since 0.2.0)

The same extension exports Claude project conversations (`extension/claude.js`).
It reads the JSON API the Claude web app loads itself
(`/api/organizations/<org>/chat_conversations/<id>?tree=True...`): only the
current branch, only text (no reasoning, no tool calls), file names from
`attachments`/`files`. Project IDs look like `claude-p-<uuid>`, storage is
`<project>/raw/claude/`. Claude project names rarely match folder names, so
new Claude projects first wait in the queue (`polaris pending`). Assign them
in the popup under "storage folder" (choices come from the project roots via
the native host; waiting messages are processed immediately) or with
`polaris map claude-p-<uuid> <folder>`. `suggested_folder_for_claude` in
`~/.config/polaris/config.yaml` sets the suggestion for new Claude projects
(never applied automatically). Enable sync per project in the popup as for
ChatGPT; Firefox must have the claude.ai permission.

### Memory guard for ChatGPT and Claude tabs (since 0.4.4)

ChatGPT tabs have grown to 20–26 GB (RAM + swap), after which systemd-oomd
killed all of Firefox. Firefox gives extensions no access to a tab's memory,
so the native host measures it (`bridge/polaris/tab_memory.py`): as a child
of the Firefox main process it reads the tab processes from `/proc` and
counts VmRSS + VmSwap of the largest.

- `background.js` asks every minute (`alarms`), only while a ChatGPT or
  Claude tab is open.
- From **4 GiB** a desktop notification (normal), from **8 GiB** urgent;
  repeated only on a higher level, another process, or every 10 min while
  critical (state: `~/.local/state/polaris/tab-memory.json`).
- `memory_banner.js` shows a bar in ChatGPT and Claude tabs with the size and
  "press F5 (reload)"; once dismissed it stays hidden until the level rises.
- `/proc` does not tell which process belongs to which page, so the message
  says "probably". No automatic reload (drafts and running answers would be
  lost).
- Cost: one host start (~60 ms CPU) per minute, only with an open tab.

### Bridge and systemd

```bash
polaris process        # processes the inbox and all unresolved pending events once
```

`install.sh` installs the units; by hand:

```bash
cp systemd/polaris-bridge.{service,path,timer} ~/.config/systemd/user/
systemctl --user daemon-reload
systemctl --user enable --now polaris-bridge.path polaris-bridge.timer
```

A new inbox file → `polaris-bridge.path` → `polaris-bridge.service`
(oneshot) → `polaris process` → exits. No permanent polling process.
`polaris-bridge.timer` also starts the service 5 min after boot and every
10 min as a safety net. The service has `StartLimitIntervalSec=0` so that
many inbox files do not disable it. The log
(`~/.local/state/polaris/polaris.log`) contains technical metadata only (IDs,
roles, mapping, target path, status), never chat content.

### Troubleshooting

- File stays in `~/Downloads/polaris-inbox/`: the extension download failed or
  the bridge has not run (`polaris process`,
  `systemctl --user status polaris-bridge.path`).
- File ends up in `~/.local/share/polaris/failed/`: invalid JSON or schema;
  the reason is in the log.
- File ends up in `~/.local/share/polaris/pending/<project-id>/`: the project
  could not be mapped safely. Use `polaris pending` and `polaris map`.
- Reason `dom-after-no-project`: ChatGPT last reported this chat as having no
  project; a fallback capture from the page (project only from a possibly
  stale address) is refused for 7 days. Reload the chat once it is in a
  project again.
- Conflicts (`polaris conflicts`): one by one with
  `--resolve <file> --keep existing|rejected`. If a chat was moved to another
  project in ChatGPT (same chat, other project), all at once with
  `polaris conflicts --resolve-chat <chat-id> --keep rejected`. Conflicts
  between different chats (mix-ups) are deliberately not resolved that way.
- Last answer missing: the bridge holds back an answer still in progress
  until a finished snapshot arrives. `polaris held-back` lists those chats
  (`--clear <key>|all`); opening the chat or "Sync now" helps.
- Extension exports nothing: check the DevTools console on the ChatGPT or
  Claude page (`[Polaris]` errors), check in the popup whether a project was
  detected and the API is usable, check the permissions.

### Repairing after ChatGPT or Claude changes

Both web APIs (`extension/chatgpt_api.js`, `extension/claude.js`) are
undocumented. If their format changes, the popup says "API currently not
usable …" and the health check reports missing archiving. Start there; gaps
can be filled from the data export.

The DOM is only a fallback; all DOM logic lives in `extension/extractor.js`.
If ChatGPT changes its UI:

1. Open DevTools on chatgpt.com and inspect a turn element.
2. Messages: `getUnitTurns()` reads elements with
   `data-chatgpt-search-unit-key` (role at the end, e.g. `...:assistant`),
   `data-chatgpt-search-message-ids` (ID) and `data-markdown-text-style`
   (text); the older markup (`conversation-turn-*`, `data-message-id`,
   `data-message-author-role`) is tried first. A structure probe that prints
   attributes only is described above `UNIT_SELECTOR` in `extractor.js`.
3. Streaming detection: check whether `STREAMING_SELECTOR` still matches a
   "Stop generating" button while an answer is generated. This is the one
   assumption never verified against a real, running generation.
4. Project detection comes from the address (`/g/g-p-<id>[-slug]/c/...` or
   `/project`, `PATH_PROJECT_RE`); the DOM only provides the display name.
5. Load the extension temporarily, check on a test conversation (watch the
   console), then ship it as a new version (see below).

The other files (`content.js`, `background.js`, `popup.*`) should not be
affected by markup changes.

### Known assumptions and risks

- The ChatGPT and Claude APIs are undocumented and may change without notice.
  Symptom: the popup reports the API as unusable, the health check says "no
  ChatGPT message for N days".
- The DOM fallback depends on the current ChatGPT markup. There `innerText`
  gives rendered text without Markdown, parent relations come from DOM order
  (`parent_id_source: "dom-order"`), and `STREAMING_SELECTOR` is the weakest
  assumption.
- Claude messages have no revisions: a Claude answer that was unfinished when
  captured stays incomplete.
- Only chats opened in the browser are archived; ChatGPT gaps can be filled
  from the official export.

### Shipping a new extension version (maintainer)

1. Raise the version in `extension/manifest.json`.
2. Build a ZIP of the contents of `extension/` (`manifest.json` at the ZIP
   root): `(cd extension && zip -r ../polaris-chatgpt-connector-v<X.Y.Z>.zip .)`.
3. Upload it at https://addons.mozilla.org/developers/addon/3070992/versions as
   a new **unlisted** version; AMO signs it.
4. Download the signed `.xpi` and install it in Firefox.
5. Commit it as `dist/polaris-chatgpt-connector-<X.Y.Z>-signed.xpi` (remove
   the old one); `install.sh` points to the newest.
6. `scripts/publish-public.sh --push` checks the unpacked `.xpi` (version, ID,
   signature, privacy), creates the release `v<X.Y.Z>` with the `.xpi` in the
   public repository and updates `updates.json` there.

## Module: ChatGPT data export

The extension only archives conversations that are opened in the browser.
Missing ones can be fetched from the official export: ChatGPT → Settings →
Data controls → Export data, download the ZIP from the mail, then:

```bash
polaris import-export ~/Downloads/<export>.zip --since 2026-09-14 --dry-run   # show
polaris import-export ~/Downloads/<export>.zip --since 2026-09-14             # import
```

Only project conversations (`gizmo_id` = `g-p-...`), only the current branch;
existing messages are skipped. Projects without a mapping are reported
(`polaris map <id> <folder>`). The curator then processes the new material
day by day as usual.

**Old chats as readable Markdown, without curation.** For large amounts of
old chats, curation is expensive and skews the weighting. `archive-export`
files them as Markdown instead; nothing goes to `raw/`, the curator ignores
them:

```bash
polaris archive-export ~/Downloads/<unpacked-export>/ --since 2025-10-02 --min-turns 6 \
    --project Customer-A --project Customer-B --dry-run
```

Result: `<project>/ChatGPT-Archiv/<YYYY-MM-DD> <title>.md` (front matter with
chat ID, period, `kuratiert: nein`) and
`ChatGPT-Archiv/Dateien/<chat>/<original name>`. Branched chats refer to the
original chat for the shared history. `.pst/.mbox/.zip` are only noted;
uploaded files missing from the export are linked to a file of the same name
in the project folder if there is one. Repeatable (already filed chat IDs are
skipped). Single chats can be curated later by moving them into `inbox/`.

## Module: inbox (documents and mail)

Drop documents, notes or `.eml` mails into `<project>/inbox/documents/`,
`inbox/notes/` or `inbox/mail/`. The curator extracts text (also from
`.docx`/`.xlsx`/`.pptx` and mail attachments), curates it like a chat and
archives the file. Details: [`curator/README.md`](curator/README.md).

## Module: model runtimes

The curator does not talk to a model API itself; it calls an agent CLI that
is already logged in: `runtime: codex`, `runtime: claude`, or
`runtime: command` with any CLI (template `curator/curator.example-command.yaml`).
`polaris-curator llm-check` shows whether the runtime works. The evaluation
of an exchangeable agent runtime is in
[`docs/agent-runtime-evaluation.md`](docs/agent-runtime-evaluation.md), the
decision in [`docs/adr/001-agent-runtime.md`](docs/adr/001-agent-runtime.md),
an isolated proof of concept in
[`experiments/agent-runtime-poc/`](experiments/agent-runtime-poc/README.md)
(German).

## Module: curator widget

A theme-aware Omarchy bar widget in `omarchy-plugin/mst.polaris-curator/`. It
shows new chat and inbox sources per project, starts one or all open curator
runs, opens the curated knowledge files and shows the health check in its
tooltip. The widget is a thin UI; all logic stays in the `polaris-curator`
CLI. Installation: [its README](omarchy-plugin/mst.polaris-curator/README.md).

## Cross-cutting modules

### Health check

`polaris-curator health` (and the widget) shows one line per area: capture,
project separation, curator, storage and backup, machine memory, security,
update, system (disk usage, failed systemd units, battery, recent crashes).
`--all` shows every single check. Exit codes and JSON output are meant for
agents as well as for people.

### Radar and security check

`polaris-radar` collects what matters before you customise Omarchy: updates
and local changes of installed git plugins, watched issues and repositories,
Omarchy commits, releases and newly listed plugins matching your keywords,
and Omarchy news. It writes `handoff/omarchy-radar.md` into the machine
memory; all third-party text is defused and marked as data.

The security section compares installed packages with the
[Arch Security Tracker](https://security.archlinux.org), the running kernel
with kernel.org stable of the same branch, and actively exploited
vulnerabilities from [CISA KEV](https://www.cisa.gov/known-exploited-vulnerabilities-catalog)
with the kernel and installed packages. For package matches it checks the
affected version ranges in the [NVD](https://nvd.nist.gov), so a package that
is already fixed does not stay yellow. It runs once a day
(`polaris-radar.timer`, about 3 MB) and after `omarchy update`. Details and
switches: [`memory/README.md`](memory/README.md) (German).

### Machine memory

A shared Markdown memory under `~/.config/ai-agents/` for all local AI agents
(Claude Code, Codex, Gemini, …): one rules file linked into every agent's
global instruction file, a short index, and topic files in three layers
(current state, durable knowledge, history). `memlint.py` checks structure,
links, tags, secrets and backup coverage; the health check shows the result.

- `install.sh` creates it from `memory/template/`, or restores it from the
  mirror if one exists there. An existing memory is never changed; only
  `memlint.py` and the shared skills are updated.
- **Mirror** (`memory_mirror:` in `~/.config/polaris/config.yaml`): work
  always happens locally; the mirror is a one-way copy into a folder of your
  choice, every 30 min. Deleted or changed files are kept under
  `.alt/<date>/`. If the drive is not mounted the run ends with 75 and
  creates nothing below the mount point. The health check turns yellow if
  the last successful run is older than 2 days.
- `--no-memory` skips all of this.

### Companion repos: omarchy-backup, agent launchers, dock

[omarchy-backup](https://github.com/mstio/omarchy-backup) (snapshots, baseline
drift, verified remote backup, fresh-install recovery) with
[its widget](https://github.com/mstio/mst.omarchy-backup), the
[agent launcher widget](https://github.com/mstio/mst.agent-launchers) and the
[dock](https://github.com/thepathless/omadock) are separate projects.
`install.sh` fetches them from git, `polaris update` keeps them current. An
existing installation of your own (for example an omarchy-backup checkout
elsewhere) is left alone. `--no-backup`, `--no-widget` and `--no-dock` leave
them out. On an existing installation, `install.sh --yes` does not add
widgets you never had; it prints the `omarchy plugin add` command instead.

## Developer tooling

### Guided setup and offline installs

Polaris is distributed through git only (the former install bundle was
retired on 2026-11-04). `./install.sh` without options runs the guided setup.
It asks for the projects folder, the curator model, background services and
widgets, omarchy-backup with its target folder, and the machine memory with
an optional mirror folder; it shows a summary and only then sets things up.

For a machine without network, carry a git bundle on a stick and clone from
it; `polaris update` works normally once the machine is online:

```bash
git -C ~/Projects/polaris-connector bundle create /run/media/<stick>/polaris.bundle --all   # on a connected machine
git clone /run/media/<stick>/polaris.bundle ~/Projects/polaris-connector                    # on the new machine
git -C ~/Projects/polaris-connector remote set-url origin https://github.com/mstio/polaris-connector.git
```

The companion repos need the network once; without it, `install.sh` warns
and you run it again later.

The guided setup asks for the projects folder, the curator model, background
services and widgets, omarchy-backup with its target folder, and the machine
memory with an optional mirror folder; it shows a summary and only then sets
things up. Every run writes a log to `~/.local/state/polaris/install-<time>.log`.
The machine memory is created first, including `handoff/polaris.md` with
state and open items. If the installation stops, it names step, reason, log
and the guide [`docs/AGENTEN-LEITFADEN.md`](docs/AGENTEN-LEITFADEN.md)
(German), so that a local AI agent can carry on by itself.

Started without `.git` (an old install bundle or a GitHub "Download ZIP"),
`install.sh` copies the program files to `~/.local/share/polaris/app` and
installs from there; switch to a git checkout to get updates (see above).
`install.sh` also sets up omarchy-backup (link, default configuration,
widget) and registers the program folder in its `paths.d/`; with a target
folder it enables daily snapshots. You set the baseline yourself.

**Template sync (maintainer).** `scripts/check-sync.sh` checks that
`memory/tools/memlint.py`, the shared skills and the generated
`memory/template/AGENTS.md` match the live copies under `~/.config/ai-agents`.
`publish-public.sh` refuses to publish otherwise.

### Privacy check and protected folders

Before packing, `scripts/privacy-check.py` scans every file for private data:
your home path, your git e-mail, the names of the project folders below your
project roots and the terms in `~/.config/polaris/bundle-deny.txt`. Any hit
stops the build. General folder names can be allowed in
`~/.config/polaris/bundle-allow.txt`; both lists stay local.

**Protected folders.** Nothing from a protected folder may be published, not
even its name. A folder is protected by an empty file `.polaris-protected`
inside a project folder, or by a line in `~/.config/polaris/protected.txt`
(one folder per line, `~` allowed). Then these are blocked:

- its name (exact spelling, whole word, also in file paths) and its path
- every file from it, byte for byte, including PDF, Office files and images
- every text line with content (4 or more letters/digits) as a whole line,
  and every sequence of 5 words from it (25+ characters) inside other text

Only lines Polaris writes into every project are exempt (standard headings,
the curator meta line, `polaris-` comments, JSON scaffolding with Polaris
keys). Hits name file and line, never the text; `bundle-allow.txt` cannot lift
the protection. Folders are read only during the check, and the fingerprints
are not stored. Limit: rephrased or translated content cannot be detected by
any mechanical check.

### Public mirror (maintainer)

Development happens in a private repository with full history. Released
states go to this public repository with
`scripts/publish-public.sh [<ref>] [--push]`, one commit per release, without
history and without binary archives, after the template sync check and the
same privacy check. Tests and
comments therefore use invented names only (Kunde-A, Musterfirma, …). A
`pre-push` hook in the mirror clone (`scripts/public-pre-push`, linked by
`publish-public.sh`) runs the check on every pushed commit, including author,
committer and message, so a direct `git push` is checked too; mirror commits
use the GitHub noreply address. Pull requests are taken over with
`git format-patch | git am -3` (see the script header). Guide for
contributors and their AI agents: [`CONTRIBUTING.md`](CONTRIBUTING.md).

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

## License

MIT, see [`LICENSE`](LICENSE).
