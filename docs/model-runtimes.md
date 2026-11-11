# Model runtimes

The curator does not talk to a model API itself; it calls an agent CLI that
is already logged in: `runtime: default` (Omarchy's selected agent),
`runtime: codex`, `runtime: claude`, or
`runtime: command` with any CLI (template `curator/curator.example-command.yaml`).
The default resolves at each run; it currently supports Claude and Codex.
Older configuration files without a `runtime` key retain the previous Codex
choice across updates. Set `runtime: default` explicitly to follow Omarchy.
If Omarchy has no default or selects another agent, the Curator reports a
configuration error rather than choosing one silently. A local `runtime`
setting overrides the Omarchy choice; `runtime: command` also needs its
explicit command and sandbox configuration. An explicit model requires an
explicit runtime when using the Omarchy default, so a later desktop switch
cannot silently pass a model name to the wrong provider.
When the default changes to Claude, image attachments are omitted from
curation; document text is still processed. A `fallback_model: null` disables
the fallback without fixing the runtime.
`polaris-curator llm-check` shows whether the runtime works.

Every runtime runs in a bubblewrap sandbox, because chats, mails and
attachments are foreign content that may carry injected instructions: the CLI
sees the system (`/usr`, `/etc`, read-only), its own program folder, a
temporary working directory and a private config folder holding only a copy
of its login (`auth.json` for codex, `.credentials.json` for claude; a renewed
login is written back). It does not see your home, and inherits no
environment variables beyond a short allow-list. For `runtime: command`, add
the paths your CLI needs (e.g. its login folder) to the local `curator.yaml`
as `command_sandbox_ro: [...]` / `command_sandbox_rw: [...]`; project
overrides cannot set them. A CLI living directly in your home or in
`~/.local/bin` gets only its own file, not the folder. Node-based CLIs need
their node runtime listed in `command_sandbox_ro` (it usually lives outside
`/usr`). Without bubblewrap the CLI runs unsandboxed and the
health check says so (line "Model"). The evaluation
of an exchangeable agent runtime is in
[`docs/agent-runtime-evaluation.md`](agent-runtime-evaluation.md), the
decision in [`docs/adr/001-agent-runtime.md`](adr/001-agent-runtime.md),
an isolated proof of concept was archived on 2026-11-05 in the private
repo's git tag `archiv/agent-runtime-poc-20261105` (German).

---

[Back to the README](../README.md)
