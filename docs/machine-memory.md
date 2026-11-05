# Machine memory

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

## Agent guard and /home snapshots (opt-in)

An AI agent that reads a mail or web page can meet hidden instructions
("prompt injection"). `install.sh` places two tools in
`~/.config/ai-agents/tools/`, but **never switches them on**; you decide.

- **Claude Code guard hook** (`claude-guard-hook.py`, switch with
  `claude-guard-einschalten.sh standard|streng|aus`): logs every action
  (`~/.claude/guard/audit.jsonl`, private), always asks before an agent writes
  to business systems via MCP (send, create, change …) or changes its own
  protection. Level `streng` additionally asks before every action with
  consequences once a session has read untrusted content (web, mail and chat
  connectors, downloads, your Polaris project folders). On errors it asks
  instead of letting things through; ~44 ms per action, no background process.
  Limit: obfuscated shell commands get past the text check at level
  `standard`; snapshots and the log are the backstop.
- **Hourly btrfs snapshots of /home** (`home-snapshots-einrichten.sh`, dry
  run without options, `--ausfuehren` in a terminal): owned by root, so no
  program running as you, including an agent, can read or delete them. Caches,
  Steam and Games become separate subvolumes first and are not snapshotted.

---

[Back to the README](../README.md)
