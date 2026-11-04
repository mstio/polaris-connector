# Contributing to Polaris – a guide for AI agents (and their humans)

Give this file to an AI agent (Claude, Codex or similar) that looks after a
copy of Polaris on another machine. Afterwards it should know how to work
with this repository and how to propose changes as a pull request.

## The essentials

- **Repository:** https://github.com/mstio/polaris-connector, branch `main`.
  Public, MIT licence. Maintainer: GitHub user `mstio`.
- This repository is a **mirror**: development happens in a private
  repository. Released states arrive here as **one** commit each ("Polaris
  <version> (Stand <date>)"). There is no further history.
- Your local Polaris installation is yours and may drift from this
  repository. **The exception is the Firefox extension (`extension/`).** It is
  only developed here and signed by the maintainer. Your installation updates
  it automatically from here (see below).
- Improvements that help others too go in as a **pull request** against
  `main`. For the extension it is the only way.
- **Updating:** `polaris update`. It fast-forwards to the new state, runs
  `install.sh`, checks with `polaris-curator health` and rolls back on
  failure. Local commits on `main` block the update: your own changes belong
  in a branch.

## For the human: what is a pull request?

A pull request (PR) is a change proposal on GitHub. You copy the repository
into your own GitHub account (a "fork"), change something there and ask the
maintainer to take the change over. They see exactly which lines change, can
ask questions and decide whether to accept it. You cannot break anything:
the original only changes once the maintainer agrees.

You need a free GitHub account. The agent does the rest with the GitHub CLI
`gh` after you have logged in once with `gh auth login`.

## The Firefox extension (.xpi) – why it is special

- The extension ("Polaris ChatGPT Connector") has the fixed ID
  `polaris-chatgpt-connector@mstarchy.local`. Only the maintainer can create
  signed, permanently installable versions at Mozilla (AMO, unlisted).
- Since version 0.4.2 the manifest contains an `update_url`
  (`https://raw.githubusercontent.com/mstio/polaris-connector/main/updates.json`).
  Firefox checks it about once a day and installs new versions by itself. The
  `.xpi` is attached to the GitHub release `v<version>`.
- A one-time manual installation is needed if the installed version is older
  than 0.4.2. Settings and permissions are kept (same ID). The newest version
  is always at https://github.com/mstio/polaris-connector/releases/latest.
  Download it and hand it to Firefox:

  ```bash
  gh release download --repo mstio/polaris-connector --pattern '*.xpi' --dir ~/Downloads --clobber
  firefox ~/Downloads/polaris-chatgpt-connector-*-signed.xpi   # confirm the installation in the Firefox window
  ```

  Without `gh`: download the `.xpi` from the release page and drag it into a
  Firefox window. The human has to click "Add" themselves. Then check in
  `about:addons` → Polaris: the version, and under "Permissions" the access
  to chatgpt.com and claude.ai.
- Local changes to `extension/` only run **temporarily**
  (`about:debugging#/runtime/this-firefox` → "Load Temporary Add-on…" →
  `extension/manifest.json`). After a Firefox restart the signed version is
  back. A change only becomes permanent through a PR and the next signed
  version.
- **Never** change these in a PR: `browser_specific_settings.gecko.id`,
  `update_url` and `version` in `extension/manifest.json`. The maintainer
  sets the version when signing.
- To hold back a new version for now (for example because your own bridge
  does not fit yet): `about:addons` → Polaris → "Allow automatic updates: Off".

## Interface between the extension and your bridge

Because your bridge may drift from the original while the extension comes
from here, this interface has to stay stable:

- Native messaging host `polaris_bridge`, registered by
  `bridge/install-native-host.sh`.
- Protocol (`ping`, `export-events`, `export-snapshot`, `list-folders`,
  `map-project`, `capture-status`): outline at the top of
  `bridge/polaris/native_host.py`, all message types in `handle()` below it,
  counterpart in `extension/background.js`.
- Event format: `bridge/polaris/schema.py` (`schema_version` 1).

When a new release appears, check these files first:
`git diff <old-mirror-commit> <new> -- extension/ bridge/polaris/native_host.py bridge/polaris/schema.py`.
If something changed there, adapt your own bridge. Changes to the interface
itself only via PR, and say so explicitly in the description.

## How a PR works (for the agent)

Create a fork with a clone once. Work separately from the running
installation (your clone from `install.sh`, or `~/.local/share/polaris/app`
for older installs from the former bundle).

```bash
gh repo fork mstio/polaris-connector --clone ~/Projects/polaris-connector
cd ~/Projects/polaris-connector
```

For every proposal:

```bash
gh repo sync <your-github-name>/polaris-connector   # bring the fork's main up to date on GitHub
git switch main && git pull                         # fetch locally
git switch -c fix/<short-topic>     # one branch per topic
# ... change, test (see below) ...
git add -A && git commit -m "<what and why, short>"
git push -u origin HEAD
gh pr create --repo mstio/polaris-connector --base main \
  --title "<short title>" --body "<what, why, how it was tested>"
```

Rules:

- **Small and focused:** one topic per PR, no drive-by reformatting.
- **Never commit directly to `main` of the fork.** That keeps `gh repo sync`
  a simple fast-forward. If an open branch diverges after a new mirror
  commit: `git rebase main` and `git push --force-with-lease`.
- Say in the PR description what changed, why, and how it was tested. For
  `extension/`, say whether it was loaded temporarily in Firefox and checked
  against real ChatGPT/Claude pages.
- Cover new cases with tests. The tests run without network and without
  extra packages:

```bash
(cd tests && POLARIS_NO_NOTIFY=1 python3 -m unittest discover)    # bridge, also starts the node tests
node --test tests/extension/                                        # extension only
(cd curator/tests && POLARIS_NO_NOTIFY=1 python3 -m unittest discover)
python3 -m unittest discover -s memory/tests                       # memlint, radar
```

- Match the surrounding code: comments and messages are mostly German, in
  code usually written with ae/oe/ue instead of umlauts. Commit messages and
  PR texts may be German or English. No new dependencies.

## What happens after the PR

The maintainer applies the PR to the private repository (`git am`). It shows
up with the next mirror commit on `main`. On GitHub the PR is therefore not
shown as "Merged" but **closed** with a comment. That is normal. Then update
your fork as above and delete the branch. If it concerns the extension, the
change comes back with the next signed version via auto-update.

## Public repository: no private data

Everything here is public. So in code, tests, comments, commit messages and
PR texts: **no** real names of customers, projects or people, no chat
content, e-mail addresses, home paths (`/home/<name>`), credentials or
tokens. Use invented names in tests (Kunde-A, Musterfirma, …). Review your own
diff for this before every push. Enable "Keep my email addresses private" on
GitHub so that your commits carry the noreply address.

## Typical reasons for a PR

- ChatGPT or Claude change their web API or page, and capture breaks. See
  `docs/browser-capture.md`, section "Repairing after ChatGPT or Claude changes"
  (`extension/chatgpt_api.js`, `extension/claude.js`, `extension/extractor.js`).
- Bugs in bridge or curator that do not only affect your own setup.

Questions or ideas without finished code: open an issue
(`gh issue create --repo mstio/polaris-connector`).
