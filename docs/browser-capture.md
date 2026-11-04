# Browser capture (ChatGPT and Claude)

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

## Installing the extension (Firefox)

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

## Turning sync on

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

## ChatGPT via the web app API (since 0.4.0)

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

## Claude (since 0.2.0)

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

## Memory guard for ChatGPT and Claude tabs (since 0.4.4)

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

## Bridge and systemd

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

## Troubleshooting

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

## Repairing after ChatGPT or Claude changes

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

## Known assumptions and risks

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

## Shipping a new extension version (maintainer)

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

---

[Back to the README](../README.md)
