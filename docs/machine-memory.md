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

---

[Back to the README](../README.md)
