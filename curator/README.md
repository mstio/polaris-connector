# Polaris Curator v0.2

Condenses new ChatGPT messages (from the Polaris bridge) and new project
documents (`inbox/mail`, `inbox/documents`, `inbox/notes`) into curated,
reliable project knowledge: `knowledge.md`, `decisions.md`,
`open-loops.md`. No RAG, no embeddings, no vector DB - pure extraction,
editing and targeted merging. Works across projects (company, clients,
private ventures) - the classification/quality logic below is deliberately
project-neutral.

**v0.2 change (2026-09-14)**: After a quality review of a real test run
(see "Quality logic (v0.2)" below), extraction was switched from a
flat "is_assumption" flag to an enforced 5-category classification per
entry (fact / stakeholder statement / hypothesis / systemic implication /
decision), including scope, evidence strength, confidence, causal chains,
key-person detection and a mandatory self-review checklist before every
answer. The model and the single-call architecture were deliberately NOT
changed in v0.2; the main model was switched later (2026-09-24, see "Model
strategy").

## Architecture

```
raw/{chatgpt,claude}/messages/*.json --\
                                         +--> daily batches (project + local day)
inbox/{mail,documents,notes} ----------/       |
                                                v
                                  budget check (max_batches_per_run, ...)
                                         |
                                         v
                                  prompt (batch/document + current
                                  curated knowledge as context)
                                         |
                                         v
                          codex exec --output-schema (structured JSON)
                                         |
                                         v
                          local schema validation (change_schema.py)
                                         |
                                         v
                    self-review gate (change_schema.failed_self_review_checks)
                                         |
                                         v
                    output check (guard.py, quarantine on suspicion)
                                         |
                                         v
                    merge engine (merge.py) -> knowledge.md / decisions.md /
                                                open-loops.md (atomic)
                                         |
                                         v
                          curator-state.json ONLY after a successful merge
```

Extraction and curation still deliberately run in ONE step/one
`codex exec` call (no separate extraction vs. synthesis call) - see
"Model strategy" below for why this is (still) the case. What changed in
v0.2: the model must deliver a structured intermediate representation per
entry (classification, scope, evidence strength, confidence, ...), from
which `merge.py` only then builds the final Markdown wording - the
analytical assessment is thus separated from the wording (see "Quality
logic" below), even without a dedicated LLM call for it.

Modules (`curator/polaris_curator/`):
- `config.py` - global + project-specific configuration, model IDs
- `chatgpt_source.py` - reads raw/chatgpt/messages/ and raw/claude/messages/, returns only new ones
- `documents_source.py` - inbox scan, hash-based change detection,
  extraction (.eml incl. attachments/.pdf/.docx/.xlsx/.pptx/.csv/.md/.txt),
  storing mail attachments
- `office_extract.py` - DOCX/XLSX/PPTX text using only the standard library
- `batching.py` - daily batches, sub-batches when the budget is exceeded
- `prompts.py` - prompt building incl. prompt-injection protection
- `llm.py` - `codex exec` call, fallback model, error classification
- `change_schema.py` - JSON schema (for `--output-schema`) + validator
- `merge.py` - targeted merging into the three Markdown files
- `state.py` - `curator-state.json`
- `pipeline.py` - orchestration, budget, locking
- `reclassify.py` - one-off reclassification under rule 2a
- `integrity.py` - checks project separation of the raw data (lock before every run, health check)
- `retract.py` - `retract`: withdraw curated entries derived from specific messages
- `transfer.py` - `export`: curated knowledge as a ZIP for other providers
- `context.py` - curated context for the prompt (full text or index + relevant entries)
- `compact.py` - compaction of `knowledge.md`; `loops_review.py` - closes open loops that are done
- `review.py` - optional independent review by Claude (`reviewer_model`)
- `guard.py` - output check and quarantine; `sandbox.py` - bubblewrap sealing of model CLIs
- `journal.py` - run journal; `locking.py` - per-project lock; `storage.py`, `layout.py` - paths and atomic writes
- `ids.py` - entry IDs; `docs_index.py` - `dokumente-index.md`
- `health.py`, `systemhealth.py`, `healthagent.py`, `status_cache.py` - monitoring, health check, "ask agent"
- `usage.py` - local usage counter; `i18n.py` - widget/health check texts (de/en); `logging_setup.py`
- `cli.py` - `polaris-curator status/status-all/run/run-all/backfill/pending/export/...`

## Output check and quarantine

Chats, mails and attachments are third-party content; an instruction hidden
in them can make the model write it into the project knowledge, which agents
and chat projects later read as context. Before writing, `guard.py` checks
every model answer for secret-like strings (keys, tokens, the local canary
`~/.config/polaris/canary`) and for instructions to an AI or shell commands.
On a hit nothing is written; the answer is kept locally (never on the drive)
under `~/.local/state/polaris/quarantine/`, and the health check reports it.

    polaris-curator quarantine list          # angehaltene Antworten
    polaris-curator quarantine show <id>     # Befund (volle Antwort mit --full)
    polaris-curator quarantine release <id>  # nach Sichtung doch schreiben
    polaris-curator quarantine drop <id>     # verwerfen

(Held answers; finding, full answer with `--full`; write after review
anyway; discard.)

Before the check the text is normalised (full-width/special forms, invisible
characters, look-alike letters); invisible format characters are also never
written. The same check applies to the plans of compaction,
reclassification and open-loop cleanup (held, not releasable; the next run
plans again) and to subject, sender and file names in the document index.
Released answers keep their provenance (can be withdrawn with `retract`).
In addition, the prompt forbids adopting requests addressed to software,
commands or credentials, and records alleged outside changes to payments,
bank details or access as a "Verifizieren" (verify) item.

The check catches typical patterns, not cleverly obfuscated ones; the real
boundaries are the model CLI's sandbox and the fixed output fields. The
canary only works as long as `~/.config/polaris` is not opened up via
`command_sandbox_ro`.

## Configuration

Global: `~/.config/polaris/curator.yaml` (created with default values on the
first run). Project-specific override (optional):
`<project>/.polaris/curator-config.yaml` (same format, only the fields set
there override the global value). Only `batching`, `budget`, `context`,
`monitoring`, `compaction` and `attachments` are allowed there. Runtime,
command (`runtime: command`), provider and models come exclusively from the
local `curator.yaml`: project folders often live on a cloud drive that others
can write to as well. Other keys are ignored and reported in the health
check.

Language (since 2026-11-04): `language: de` or `language: en` in the global
`curator.yaml` switches the widget and health check. Without the line, `de`
applies (existing installations stay German); new installations set it via
`install.sh --language` or the system language. The field labels in
`knowledge.md` etc. stay German for now.

Built-in defaults (`config.py`, used for every key missing from
`curator.yaml`):

```yaml
provider: openai
runtime: codex
model: gpt-5.6-luna        # low-cost model, see note below
fallback_model: gpt-5.6-sol
permit_more_expensive_fallback: false
llm_timeout_seconds: 180
reasoning_effort: null     # CLI default
batching:
  min_messages_for_early_run: 10   # currently without effect, see below
  min_chars_for_early_run: 8000    # currently without effect, see below
budget:
  max_batches_per_run: 3
  max_llm_calls_per_run: 3
  max_messages_per_batch: 40
  max_input_chars_per_batch: 50000
  max_total_input_chars_per_run: 120000
context:
  max_curated_context_chars: 50000
  full_context_chars: 80000     # above this: index + full text of what is relevant
  index_cap: 0.25               # index at most 25 % of that (0 = all entries)
attachments:
  min_image_bytes: 300000       # smaller images = signature/logo, ignored
  max_images_per_document: 5
  max_chars_per_attachment: 20000
```

The template that `install.sh` writes for Codex
(`curator.example-codex.yaml`) deliberately overrides several of these:
`model: gpt-6-astra`, `reasoning_effort: medium`, `llm_timeout_seconds: 1200`,
`max_input_chars_per_batch: 100000`, `max_total_input_chars_per_run: 250000`,
`max_curated_context_chars: 200000`, plus `language`,
`monitoring.chat_sources`, `claude_fallback_model` and `reviewer_model`
(both `null` = off).

**Model IDs**: `gpt-5.6-luna` was identified on 2026-09-12 from
`~/.codex/models_cache.json` as "Fast and affordable agentic coding
model" - a good fit for a pure extraction/merge task - and is still the
built-in default. `gpt-5.6-sol` was the user's global Codex default model at
that time and serves as the fallback. Since 2026-09-24 the Codex template
uses `gpt-6-astra` (see "Model strategy"). Model catalogues go stale - adjust in `~/.config/polaris/curator.yaml`
as needed, without changing code.

**`min_messages_for_early_run` / `min_chars_for_early_run`**: Intended in
the task specification for a possible more frequent invocation interval.
Since v0.1 only runs via manual calls and the daily systemd timer - both of
which, per the task specification, already count as a valid trigger for
processing even small batches - these thresholds currently have no effect;
every run processes everything that fits into the budget. The configuration
is prepared in case a more frequent mode is added later.

**Runtime `claude` (since 2026-10-07)**: On machines without Codex, the
Claude Code CLI curates (`runtime: claude`, `model: opus`, `fallback_model:
sonnet`; template `curator.example-claude.yaml`). Same sealed-off call as
for the fallback model. Images from mail attachments are dropped (warning in
the log); the text is curated. Leave `reviewer_model` off there
- otherwise Claude reviews itself.

**Runtime `command` (since 2026-10-07, provider-neutral)**: any agent CLI as
an argument list (`command`), placeholders `{model}`, `{prompt_file}`,
`{schema_file}`, `{schema_json}`; without `{prompt_file}` the prompt comes
via stdin (in file mode stdin is closed). If a schema placeholder is
missing, the curator appends the JSON schema to the prompt. The answer is
read from plain JSON, a JSON wrapper (`command_output_key` or known fields
such as `response`/`result`) or the JSON block in text, and as always checked
by the curator itself. Template with a tested example (Gemini/Antigravity in
plan mode) and untested candidates: `curator.example-command.yaml`.
Security: the CLI runs in an empty working directory; switch off shell and
write tools via its own flags - the chats are third-party content. Error
messages contain only short error lines, never the prompt. Images from mail
attachments are dropped.

**Checking the setup**: `polaris-curator llm-check` shows runtime, model and
whether the required CLIs (runtime, possibly Claude as fallback/reviewer) are
on the `PATH`. `--call` additionally makes a tiny real call to the main model
without fallback stages (login, model name; with Codex about 20k tokens of
overhead). The health check reports a missing runtime CLI as an error
("Curator › Model"; German UI: „Curator › Modell“).

## First run / initialisation

The first run per project processes the complete ChatGPT stock present at
that point once (see task specification section 4). This is normal and
intended. After that only new messages are processed.

## CLI

```bash
polaris-curator status <project>       # overview: new sources, budget
polaris-curator status-all [--no-cache]  # overview of all known projects
polaris-curator run <project>          # perform a real run
polaris-curator run <project> --dry-run
polaris-curator run-all                # all known projects (bridge mapping)
polaris-curator backfill <project>     # reprocess the historical stock AGAIN
polaris-curator pending <project>      # units waiting beyond the budget
polaris-curator health [--json] [--all] [--ask <id>]  # health check; --ask opens the default agent on one finding
polaris-curator llm-check [--call]     # check runtime, CLIs, login (see "Configuration")
polaris-curator compact <project> [--dry-run] [--show-plan]  # compact knowledge.md (--dry-run first)
polaris-curator review-loops <project> [--dry-run]  # check open loops against the knowledge, close what is done
polaris-curator index-documents <project>|--all   # rebuild dokumente-index.md
polaris-curator export <project>|--all [-o ZIP] [--with-archive] [--json]  # curated knowledge for another provider
polaris-curator reclassify <project> [--apply]    # reclassify AI answers under rule 2a
polaris-curator retract <project> <IDs>|--ids-file F|--from-dir D [--apply [--rebuild]] [--force] [--json]  # withdraw knowledge derived from messages
polaris-curator journal <project> [--discard]     # show (or discard) the run journal
polaris-curator quarantine list|show|release|drop [<id>] [--full]  # output check quarantine
```

For local UIs and automation, `status`, `status-all`, `run` and `run-all`
provide a stable, machine-readable contract with `--json`. The Omarchy
widget under `omarchy-plugin/mst.polaris-curator/` uses only these JSON
outputs and thereby starts the same pipeline as the daily timer: new
ChatGPT messages and new files in `inbox/{documents,mail,notes}` are curated
together.

`<project>` is either the folder name (e.g. `Company`, must be mapped under
one of the bridge `project_roots`) or a direct path.

**Use `backfill` with care**: reprocesses messages regardless of the previous
state - can lead to redundant entries in `knowledge.md` if they were already
curated. Use only deliberately, e.g. after an intentional reset of the
curated files.

## Usage counter (since 2026-11-05)

`polaris_curator/usage.py` counts locally in `~/.local/state/polaris/usage.json`
how often each CLI command (`cli:<command>`) and the functions `compact`,
`loops_review` and `reviewer` run: only name, count, first and last date,
never contents, projects or paths. Purpose: remove unused code with evidence.
Tests switch it off with `POLARIS_USAGE_OFF=1`.

## Health check and monitoring (since 2026-09-25)

`polaris-curator health [--json]` checks Polaris' own components (capture:
ChatGPT/Claude archiving, bridge, chat-source configuration, Firefox
extension incl. site permissions, native host; project separation; curator:
timer, curation steps, last curation, model CLI, widget; storage & backup:
project folder, omarchy-backup, backup target, repos; machine memory;
security) and, briefly, a few system values (disks, failed units, battery,
pending reboot, btrfs disk errors, crashes). The Omarchy widget
(`omarchy-plugin/mst.polaris-curator`, display name "Polaris") shows this as
a traffic light in its Health Check section; "Ask agent" (`health --ask`)
hands a finding to the default agent, which proposes a fix and changes
nothing without consent. Only state files and metadata, no expensive checks.
Optional components (since 2026-10-07): if omarchy-backup is not installed
or `~/.config/ai-agents` does not exist, the line shows "not set up
(optional)" (German UI: „nicht eingerichtet (optional)“) instead of an error;
an installed omarchy-backup without a snapshot is a warning.

Silent failures (`health.py`): if no ChatGPT message arrives across all
projects for longer than `monitoring.max_days_without_chatgpt` (default 3;
Claude: `max_days_without_claude`, default 7),
or files remain in the bridge inbox, `status-all`/`run-all` warns; the timer
run sends at most one desktop notification per day and finding.
`monitoring.chat_sources` in `~/.config/polaris/curator.yaml` contains the
browser chat sources actually monitored: `[chatgpt, claude]` (default),
`[chatgpt]`, `[claude]` or `[]` (no browser chats). The health check checks
archiving and Firefox permissions only for selected sources; without browser
chats it checks neither the extension nor the native host. A Claude message
does not automatically disable the ChatGPT check. If `claude` is explicitly
in the list, "never a Claude message" or missing access to claude.ai is red;
without a `chat_sources` entry (older configurations) Claude stays lenient.
Case does not matter; unknown entries are ignored and reported as a
configuration error. With
`max_days_without_chatgpt: 0` only the ChatGPT time check can be suspended.
The choice of chat sources is independent of `runtime: codex|claude|command`:
anyone who uses e.g. Grok or a local model as the curator runtime can set
`[]` and keep curating documents via the inbox. Grok chats are not archived
without a dedicated capture adapter.

## Project knowledge transfer between providers (since 2026-09-25)

```bash
polaris-curator export Company        # ~/Downloads/polaris-projektwissen-Company-<time>.zip
polaris-curator export --all -o /path.zip  # all known projects in one ZIP
polaris-curator export Company --with-archive --json
```

The return path for curated knowledge: what was curated from ChatGPT, Claude
or documents should be available to every provider (and other agents) as
project context, without the knowledge belonging to any one provider. The
Markdown files in the project folder remain canonical; `export` packs a
snapshot of them: `knowledge.md`, `decisions.md`, `open-loops.md`,
`dokumente-index.md` (with `--with-archive` also `knowledge-archiv.md`)
unchanged incl. `polaris-source` provenance, plus a generated
`LIESMICH.md` (reading guide, provenance count per file). **Not** included:
`raw/` (raw chats), `inbox/`, original documents, `.polaris/`. ZIP with
permissions 0600, written atomically.

Deliberately kept separate from the machine memory (`~/.config/ai-agents`):
the curator never writes there, and machine state does not belong in a
project context - which is why the machine-memory ZIP contained no project
knowledge.

## Re-curating the classification (since 2026-09-25)

```bash
polaris-curator reclassify Company           # create plan -> .polaris/reclassify-plan.json
polaris-curator reclassify Company --apply   # apply exactly this plan (backup first)
```

Since prompt rule 2a ("an AI assistant is never a stakeholder"), new runs
classify answers from ChatGPT/Claude differently; a normal run does not
change existing entries. `reclassify` takes only `[Stakeholder-Aussage]`
(stakeholder statement) entries with chat-only provenance, has the model
deliver a plan and checks every change locally: known ID, valid values,
scope/evidence strength do not increase, no number from the old text is
lost. Inadmissible changes are discarded individually. `--apply` applies
only the saved plan and refuses if `knowledge.md` has changed since;
provenance stays unchanged, backup under `.polaris/backups/`.

## Project separation and retraction (since 2026-09-29)

Background: on 2026-09-29, after a chat switch, the extension exported the
still visible messages of the old chat under the new address; the messages
of two client projects ended up in each other's project. Since then: capture
as a chat snapshot (project taken from the provider data, see the main
README), the bridge rejects a message already archived elsewhere, the curator
locks, and retraction is possible.

**Lock (`integrity.py`):** Before every run the curator reads all
`raw/*/messages/` of the known projects. Blocking (project is **not
curated**, `aborted_reason=integrity`, health line "Project separation"
(German UI: „Projekttrennung“) red): `duplicate_id` (same ID in several
projects/chats), `foreign_project`, `url_mismatch` and `bridge_conflict`
(file in `~/.local/share/polaris/conflicts/` - locks **both** projects,
because the copy archived first may be the wrong one). Non-blocking, yellow:
`index_mismatch`, `unreadable`, `unknown_project`.

**Resolving a conflict:** `polaris conflicts` lists, `polaris conflicts
--resolve <file> --keep existing|rejected` resolves: the discarded copy
moves to `~/.local/share/polaris/quarantine/conflicts-<date>/`; with
`rejected` the rejected copy is filed regularly. If the wrong copy was
already curated, the output names the `retract` command. Do not simply
delete conflict files - that could lose the correct copy.

**Retraction (`retract`):**

```
polaris-curator retract Client-B --from-dir ~/.local/share/polaris/quarantine/X/Client-B          # show
polaris-curator retract Client-B --from-dir ... --apply              # remove only pure entries
polaris-curator retract Client-B --from-dir ... --apply --rebuild    # re-curate affected batches
```

Provenance lists all messages of a daily batch, so an imported foreign
message usually sits in the same entry as genuine ones. `--apply` removes
only entries whose sources are exclusively retracted messages. `--rebuild`
removes all entries that name a message of the affected batches
(transitively via compacted entries) and marks their clean messages as
unprocessed in the state; the next run rebuilds the knowledge from them.
Entries with an additional document source stay and are reported for manual
review. Retracted IDs stay marked as processed. IDs that are still in this
project's raw stock are skipped without `--force` (protection against
passing in the quarantine folder of the *other* project). Backup beforehand
under `.polaris/backups/`, removed entries verbatim in
`.polaris/retracted/<time>.md`.

## Coverage, journal, robustness (since 2026-09-29)

- **Every text of a chat is curated exactly once** (`chatgpt_source.
  load_new_messages`): a paragraph (normalised, >= 20 characters) that
  already appears in a curated version of the same chat is not sent to the
  model again - regardless of the ID, capture path or formatting it arrives
  with. Fully covered messages are recorded without a model call; partial
  pieces go with the chat title and the preceding question. Retracted
  messages (`retracted_ids`) never again; turns of discarded branches
  (`active_message_ids` from the chat snapshot) are skipped.
- **Write-ahead journal** (local under `~/.local/state/polaris/journals/`;
  until 2026-10-10 `.polaris/journal.json` on the Drive mount - there the
  deletion got lost and a leftover locked the project; the old location is
  no longer read since 2026-11-05): target state of all files and the state
  change before writing; an interrupted step is completed on the next run.
  If a file no longer matches (someone changed it differently) or the
  journal is damaged, the project is locked and shown red in the health
  check ("Curation steps"; German UI: „Kurationsschritte“).
  `polaris-curator journal <project>` shows the status, `--discard` discards
  it (backup; the sources are curated again). compact/reclassify/retract
  refuse while a journal is open.
- **Queue:** the first unit of a run may be larger than the budget;
  repeatedly failing units move back 24 h (warning from 2); errors in one
  project do not stop run-all (mount error: exit 75).

## Entry IDs, supersession, provenance per statement (since 2026-09-29)

Three proven concepts from LLM memory systems, implemented in the existing
Markdown without a new dependency:

1. **IDs instead of text markers.** Every entry carries a visible, stable
   ID: `ID: K12` (knowledge.md, archive), `**ID** D3` (decisions.md),
   `ID: L7` (open-loops.md). The model changes entries via the ID
   (`replaces_id`, `decision_id`, `loop_id`) instead of via a text excerpt it
   would have to find again. Unknown ID: nothing is guessed (entry appended
   or change skipped, warning). IDs are never reused (highest ever seen + 1,
   incl. references and the counter line `<!-- polaris-ids: K=.. -->` in the
   file header); merged entries keep the first ID and record the others
   (`Zusammengeführt: K7`, "merged"). Only the dedicated sub-line
   `  - ID: K12` counts as an ID, never running text or code. Entries
   without an ID are numbered on every run after the integrity check - only
   lines inserted, via the journal, backup `*-before-ids`; duplicate
   headings in decisions.md become "… (2)".
2. **Valid since / superseded by.** New entries carry `Gültig seit` (valid
   since). If an entry replaces another, the old one moves to
   `knowledge-archiv.md` with „Abgelöst durch K40 am …“ (superseded by K40
   on …) (not overwritten); the new one records `Ersetzt: K12` (replaces)
   and keeps its provenance. An already superseded ID leads via the
   `Ersetzt:` chain to the current version. Decisions get
   `**Ersetzt durch**` (replaced by), closed items „erledigt am …“ (done
   on …).
3. **Provenance per statement.** Every entry names `source_message_ids` -
   the messages it relies on. Only IDs from the current batch go into the
   provenance; if the field is missing or none matches, the whole batch
   applies as before (never an entry without provenance). If the entry names
   only part of it, `batch_ids=` (whole batch) is added. For client
   separation the whole batch always counts: without `--rebuild`, `retract`
   removes only fully retracted batches and shows the model's field only as
   a hint; `--rebuild` removes everything that saw the batch and rebuilds the
   clean part.

## Compaction of knowledge.md (since 2026-09-25)

```bash
polaris-curator compact <project> --dry-run --show-plan   # view plan
polaris-curator compact <project>                          # apply
```

The model receives the numbered entries (without provenance) and returns
only a plan: true duplicates with a merged version, plus entries made
obsolete by newer entries. The plan is checked locally and applied
deterministically; provenance is fully preserved, classifications are never
upgraded, obsolete entries move to `knowledge-archiv.md` (nothing is
deleted), backup beforehand under `.polaris/backups/`. Emergency brake: if
the file would shrink by more than half, the plan is discarded. Automatic in
the timer run from `compaction.threshold_chars` (default 100000, 0 = never),
at most every `compaction.min_interval_days` (default 7) days.

**Back-off after runs without result (since 2026-10-17):** If a compaction
finds nothing (no merge, nothing obsolete) or the weekly review of open
loops (`compaction.loops_review_interval_days`) closes no item, the interval
doubles up to the factor `compaction.idle_backoff_max` (default 4: 7 → 14 →
28 days; 1 = off). A run with a result resets it; if `knowledge.md` has grown
by 10 % since the last compaction, the base interval applies to it again. A
failed run does not change the counter. Counter `idle_streak` in
`.polaris/compact-state.json` or `loops-review.json`. Background: audit
2026-10-17, the last runs of all projects closed 0 items and found almost
no duplicates (80–350k characters of input per call).

## Protection against loss and mixing (since 2026-09-29, architecture review)

- **Only mapped messages:** only what `projects.yaml` (status
  `ok`/`missing_target`) maps to exactly this folder is curated. Messages
  with a foreign or unknown `project.id` (e.g. after `polaris unmap`) stay
  unprocessed; the run warns, the health check shows them. Without any
  mapping (fresh installation, tests) nothing is filtered.
- **Late additions:** a new version of an already curated message is only
  adopted silently if no new paragraph with >= 20 characters is added and
  everything new together is < 100 characters.
- **Compaction:** originals of merged entries move verbatim to the archive;
  a merge whose version loses a number from the originals is discarded
  (output "verworfen …", discarded). Writing goes via the journal. Due at
  the latest at 80 % of `max_curated_context_chars`.
- **Truncated/context limit:** if a document is truncated or a curated file
  is larger than the context the model sees, the run reports it ("gekuerzt
  kuratiert", curated truncated; "Kontextgrenze", context limit).
- **Drive mount:** the curator never creates a project folder under
  `project_roots` (`~/.config/polaris/config.yaml`); if it is missing, the
  run ends with exit 75 (retry later) instead of creating shadow folders on
  the local disk.
- **Run result:** `run`/`run-all` write `.polaris/last-run.json` (errors,
  important warnings, backlog). The widget shows it under Curator > Curation
  (German UI: Curator > Kuration) (yellow on errors, important warnings,
  repeatedly failing units, backlog > 7 days).
- **Codex errors:** the error text contains only codex's `ERROR` lines (no
  prompt echo with client content); a usage limit is named as such. Retries
  every 20 min for up to ~8 h (unit: 12 h / 25 starts).

## Claude: fallback model and independent review (since 2026-09-30)

- `claude_fallback_model` (e.g. `opus`): if Codex is unreachable (limit,
  outage), Claude curates directly via `claude -p` (sealed off: no tools, no
  settings/CLAUDE.md, no session). Only for prompts with images does the
  second Codex model (`fallback_model`) remain.
- `reviewer_model` (e.g. `opus`): Claude checks every new entry against the
  whole source content (for supersessions together with the old entry).
  Nothing is discarded; serious objections appear as a "Prüfhinweis" (review
  note) on the entry and in the run result, all findings in
  `.polaris/review-findings.json`. Not reviewed: documents with images,
  batches curated by Claude itself, and, after a reviewer outage, the rest
  of the run (reported).

## Large documents and duplicate attachments (since 2026-10-07)

- Limit per document = `max_input_chars_per_batch` (at most the run budget).
- Up to `document_oversize_factor` (default 2) times the limit, a document
  exceptionally goes through in **one** call: cheaper than parts, because
  the project knowledge is sent only once.
- Above that it is split into **parts** the size of the limit (at line
  ends), curated part by part; each part sees the knowledge from the
  previous ones. The per-run budget still applies, remaining parts come in
  the next run. Progress: `document_parts` in the state; archiving happens
  only after the last part. At most `max_parts_per_document` (default 5)
  parts, the rest is truncated and reported as "gekuerzt kuratiert" (curated
  truncated) - this notice now appears only for documents that were actually
  curated.
- Mail attachments that are byte-identical to a document of their own in
  `inbox/documents` or `inbox/notes`, or already curated, are only filed and
  referenced ("identisch mit …, dort ausgewertet", identical to …, evaluated
  there) instead of being curated twice.

```yaml
budget:
  max_parts_per_document: 5        # 1 = never split
  document_oversize_factor: 2.0    # 1.0 = never allow a one-off larger call
```

## Budget protection

Hard limits per run (see config above). When a limit is reached, the run
ends cleanly; remaining batches/documents stay open and are processed in the
next run (next timer tick or manual call) - oldest open daily batch first.
No batch is marked as processed unless the corresponding LLM call or merge
was fully successful.

If the primary model is unreachable, the fallback model is tried exactly
once (with `claude_fallback_model` set, Claude takes that place except for
prompts with images; see "Claude: fallback model and independent review"); if that fails too, the whole run aborts cleanly (nothing is marked as
processed, the next run retries automatically). An invalid model answer
(format/schema error), by contrast, only affects the individual batch - the
run continues with the remaining units.

## Daily batching

New chat messages (ChatGPT and Claude) are grouped per project and local
calendar day (time anchor: `source_timestamp` from the provider data where
present, otherwise `captured_at`). Days that are too large are split into
sub-batches (`2026-09-12#1`, `2026-09-12#2`, ...), keeping related
conversation blocks together where possible. A day is never finally
"closed" - new messages from the same day are automatically recognised as a
late addition on the next run (state is based on message IDs, not on the
date alone).

## Catch-up after a pause of several days

On the next run, all daily batches open since the last success are detected
and worked through chronologically (oldest first) within the budget. If the
budget does not suffice for all open days, the next run processes the rest
- the budget is never exceeded just because of a backlog.

## Quality logic (v0.2)

`change_schema.py` enforces a classification per `knowledge_updates` entry
instead of leaving it to the model (`prompts.py` justifies and illustrates
each rule in detail):

- `entry_type`: `fact` (evidenced observation) / `stakeholder_claim`
  (perception/statement of a person - not a confirmed fact) /
  `hypothesis` (analytical inference, must be marked as an assumption)
  / `implication` (meaning for operating model, leadership, scaling,
  customer retention, profitability). Real decisions belong separately in
  `decisions_add`.
- `scope` (`local`/`functional`/`cross_functional`/`company_wide`) +
  `evidence_strength` (`single_source`/`multiple_sources`/`corroborated`)
  + `confidence` prevent a single case ("it's like this everywhere") from
  being stored directly as a company-wide pattern - upgrading only with
  actually several independent sources.
- `causal_chain` (only for `hypothesis`) records presumed cause-effect
  chains (e.g. missing internal handling -> personal compensation ->
  strain -> key-person risk -> mandate risk) explicitly as a hypothesis,
  never as a fact.
- `key_person_dependency` specifically records compensation patterns
  (clients stay because of one person, a process only works through
  personal follow-up, escalations repeatedly go through the same person).
- Founder/management bottlenecks: an escalation to a single leader is
  recorded as a short-term intervention (`decisions_add`, usually
  `decision_scope=local`/`provisional`) AND separately as `open_loops_add`
  with `loop_type=leadership_question` (what would the permanent, scalable
  mechanism look like?) - never as an already solved process question.
- `decisions_add.validated` must be `false` for a new decision
  (structurally enforced, see `change_schema.py`) - an introduced measure is
  not automatically considered effective. `decisions_update` can set
  `validated`/`validation_note` later when a follow-up source actually
  proves it.
- `open_loops_add.loop_type` categorises open items (data need, leadership
  question, effectiveness check, process/responsibility gap, economic
  question) instead of a mere to-do archive.
- Reconciliation with existing knowledge: the prompt receives the current
  state of all three files as context and is instructed to condense a
  confirming/refining new source into the existing entry via `mode=replace`
  + `replaces_id` (the entry's ID, plus `related_existing_insight`) (e.g.
  upgrading the evidence strength) instead of appending a new, almost
  identical entry. `merge.py` moves the WHOLE old entry block
  (classification, meta lines, provenance) to `knowledge-archiv.md` as
  superseded and writes the new entry with `Ersetzt: K..`.
- `self_review` (mandatory field at the end of the model answer): 9 boolean
  fields that map exactly the critique checklist from the task specification
  (stakeholder statement wrongly presented as fact? single case
  overgeneralised? intervention presented as proven? systemic implication
  overlooked? key-person dependency overlooked? client/economic impact
  overlooked? leader treated as a permanent process substitute? relevant in
  the long term/not redundant? statement does not go beyond the source?).
  `pipeline.py` discards the ENTIRE batch locally (no merge, batch counts as
  unprocessed, is retried on the next run) if even one field is `false` -
  the prompt tells the model this explicitly, to create an incentive to
  actually correct before answering rather than merely claim to.

**Important limitation**: `self_review` is a self-report from the same model
call, not an independent second look. It forces the model to explicitly
"think through" the critique criteria as mandatory fields (more enforced
intermediate steps before the final answer), but does not replace a real
second review independent of the producer. Whether this suffices or a real
second, independent critique call is needed should be reassessed on the
basis of further reproduced cases (not just the one real test run) - see
"Model strategy". Since 2026-09-30 an optional independent review by Claude
exists (`reviewer_model`, see "Claude: fallback model and independent
review").

## Model strategy

**Current state (since 2026-09-24):** main model `gpt-6-astra` with
`reasoning_effort: medium`, fallback `gpt-5.6-sol` (Codex template). A live
A/B test on a real mail with attachments showed `gpt-6-astra` clearly better
than `gpt-5.6-luna` (condensing instead of duplicating, use of spreadsheet
content, cross-source implications) at roughly the same token usage but more
than twice the run time; hence the higher timeout. Still one call per
batch/document. The history below explains the v0.2 decision.

Deliberately NOT changed in v0.2: still `gpt-5.6-luna` (cheap, according to
the Codex catalogue for agentic coding, not specifically optimised for deep
analytical reasoning) in a single `codex exec` call per batch/document that
handles extraction AND classification AND the merge decision in one step.

Rationale: the original quality loss in the real test run was
predominantly WORKFLOW/SCHEMA-related (no enforced classification, no
scope/evidence strength, no self-review, no guidance on causal
chains/key-person patterns), not primarily model-related - the same task
specification therefore explicitly demands improving prompting/workflow/data
model first and only then checking whether remaining problems are actually
due to the model. An unvetted larger/more expensive model would have masked
this risk instead of fixing it.

If the regression test (below) still shows systematic weaknesses after this
change that look more like a reasoning limit than a prompt/schema gap (e.g.
repeatedly overlooked causal chains despite explicit guidance), the
two-stage architecture proposed in the brief is the obvious next escalation
step: a cheap model for pure parsing/extraction steps, a stronger reasoning
model ONLY for the synthesis/assessment/context-reconciliation step (second
`codex exec` call with the extracted raw material + current knowledge state
as input). That would double the number of LLM calls per unit (the budget
configuration would have to be adjusted accordingly) and is THEREFORE
deliberately not yet implemented here, but documented as an option.

## Document sources

Supported: `.eml` (headers + plain-text/HTML body + attachments, see below),
`.pdf` (via `pdftotext`, already present as a system package), `.docx`,
`.xlsx`/`.xlsm`, `.pptx` (Python standard library only, see
`office_extract.py` - these formats are ZIP archives with XML), `.csv`,
`.md`, `.txt`. Old binary formats (`.doc`, `.xls`, `.ppt`) and `.msg` are
not supported; such files in the inbox are written to `curator.log` as a
warning on every run instead of being skipped silently. Change detection via
the SHA-256 hash of the file - an unchanged file is never analysed again.
After a successful LLM call, validated merge and local processing, source
files are moved to `inbox/<type>/archive/processed/`. Unreadable files as
well as sources with LLM, schema, merge or archiving errors stay in the
inbox. Existing archive files are never overwritten; on name collisions the
new file gets a short content hash.

The text of a document (incl. attachments) is limited per call to the
smaller of `budget.max_input_chars_per_batch` and
`budget.max_total_input_chars_per_run`. Larger documents go through in one
call up to `document_oversize_factor` times that, otherwise in parts (see
"Large documents and duplicate attachments"); only text beyond
`max_parts_per_document` parts is truncated, with a visible notice. Previously
a single document larger than the run budget could block the queue
permanently.

### Mail attachments (since 2026-09-24)

- **Text attachments** (PDF, DOCX, XLSX, PPTX, CSV, TXT, MD) are extracted
  and appended to the mail text in the prompt as a section `=== ANHAENGE ===`
  (per attachment at most `attachments.max_chars_per_attachment`
  characters). XLSX: at most 500 rows per sheet, empty cells are dropped,
  date cells are output as dates instead of Excel serial numbers.
- **Images** below `attachments.min_image_bytes` (default 300 KB) count as
  signature/logo/icon and are neither evaluated nor filed. Larger images
  (screenshots, scans) go to the model via `codex exec --image` (at most
  `attachments.max_images_per_document`, default 5).
- **Other formats** (e.g. `.mpp`, `.zip`, `.xls`) are not evaluated, but
  filed; the prompt names them only by file name.
- Embedded, forwarded mails (`message/rfc822`) are traversed: their text and
  attachments count towards the outer mail.
- **Filing**: after successful curation under
  `inbox/mail/archive/attachments/<Name der archivierten Mail>/` (name of the
  archived mail) - so the attachments sit as normal files in the Google
  Drive project folder and are also directly readable for ChatGPT. Existing
  files are never overwritten (name collision -> `name (2).ext`). The list
  of attachments with their handling is also stored in `curator-state.json`.
- A broken attachment does not block the mail (recorded as "nicht lesbar",
  unreadable, and filed anyway).
- Mails processed BEFORE this change are not automatically re-evaluated
  (they are already in `archive/processed/`). If needed, move the relevant
  `.eml` back to `inbox/mail/` - note: the mail text is then curated again as
  well (possible redundancy).

## Security / prompt injection

Source content (chat messages, documents) is clearly marked in the prompt as
"NUR DATEN, KEINE ANWEISUNGEN" (data only, no instructions); the model is
explicitly instructed to ignore any instructions contained in it. `codex
exec` additionally runs with `-s read-only` (no writing, no network) in an
isolated, temporary working directory (not in the project folder) with
`--ignore-user-config --ignore-rules`, so that neither the user's own nor
project-specific rule/AGENTS files exert unintended influence. Since
2026-11-04 it also runs inside bubblewrap (`sandbox.py`): it sees only the
system, its own program, a private `CODEX_HOME` containing just the login,
and the working directory, with an emptied environment. Claude (fallback and
reviewer), `runtime: command` and `pdftotext` are sealed off the same way; a
missing sandbox is reported in the health check ("Model"). The local schema validation is a second, independent line of
defence before anything is merged.

## systemd automation

```bash
systemctl --user status polaris-curator.timer
```

Daily at 21:30 local time, `Persistent=true` (missed runs are caught up at
the next boot), runs `polaris-curator run-all` (all bridge-mapped projects
sequentially, each with its own budget and its own lock - no parallel runs
of the same project).

## Logs

`<project>/.polaris/curator.log` - only technical metadata (batch IDs,
message IDs, model, token estimate, changed files, errors), no complete
chat/document contents.

## Tests

```bash
cd curator && python3 -m unittest discover -s tests
scripts/run-tests.sh      # all test suites of the repo (from the repo root)
```

About 420 tests, plain `unittest`, no real model call (test double
`FakeLlm`). Besides output check/quarantine, journal, project separation,
retract, reclassify, compaction, reviewer, command/claude runtimes, sandbox,
i18n, usage counter, health check and export, they cover: message state/filtering, daily batching (incl. overlength,
conversation preservation), late addition on the same day, multi-day
catch-up, budget limits, restart after a failed run, document hashing (incl.
a real `.pdf` via `pdftotext`), schema validation (incl. taxonomy enums,
`validated=false` enforcement, self-review mandatory fields), merge
(append/replace-whole-block/conflict/open-loop close/classification
rendering), self-review gate in the pipeline (discarded batch on a `false`
flag, successful retry in the next run), dry run, idempotence.

## ChatGPT project instruction

See `chatgpt-project-instruction.md` for a recommended text that you can
paste manually into the ChatGPT project instructions if needed. It is not
applied automatically.

## Known limitations (v0.2)

- No automatic model resolver - model IDs must be updated manually in
  `curator.yaml` when needed if Codex's catalogue changes.
- `min_messages_for_early_run`/`min_chars_for_early_run` are currently
  without effect (see configuration section above).
- Condensing (`replaces_id`, see "Quality logic") depends entirely on the
  model recognising a matching existing entry - there is no semantic
  duplicate detection (no embedding comparison). Large files are sent as an
  index plus the full text of the relevant entries (`full_context_chars`,
  `index_cap`); entries shown only in the index cannot be replaced (possible
  duplicates, cleaned up by compaction). Only if the result still exceeds
  `max_curated_context_chars` is it cut from the back, with a
  "Kontextgrenze" (context limit) warning.
- `self_review` is a self-report from the same model call, not an
  independent second look - unless `reviewer_model` is set (independent
  Claude review since 2026-09-30, see that section).
- The new classification/self-review raises the demands on the model per
  call (more mandatory fields, more conditions) without changing the
  token/cost structure (still 1 call per batch/document) - whether
  `gpt-5.6-luna` does this reliably enough or a stronger model is needed for
  the synthesis part can only really be judged after several real runs (not
  just the one regression test); since 2026-09-24 the template uses the
  stronger `gpt-6-astra` (see "Model strategy").
- Compaction (see "Compaction of knowledge.md") finds only duplicates and
  obsolete entries that the model recognises; it runs automatically from
  `compaction.threshold_chars`.
