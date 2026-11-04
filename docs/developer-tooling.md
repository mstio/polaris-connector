# Developer tooling

## Guided setup and offline installs

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
and the guide [`docs/AGENTEN-LEITFADEN.md`](AGENTEN-LEITFADEN.md)
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

## Privacy check and protected folders

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

## Public mirror (maintainer)

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
contributors and their AI agents: [`CONTRIBUTING.md`](../CONTRIBUTING.md).

---

[Back to the README](../README.md)
