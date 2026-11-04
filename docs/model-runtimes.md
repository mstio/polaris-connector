# Model runtimes

The curator does not talk to a model API itself; it calls an agent CLI that
is already logged in: `runtime: codex`, `runtime: claude`, or
`runtime: command` with any CLI (template `curator/curator.example-command.yaml`).
`polaris-curator llm-check` shows whether the runtime works. The evaluation
of an exchangeable agent runtime is in
[`docs/agent-runtime-evaluation.md`](agent-runtime-evaluation.md), the
decision in [`docs/adr/001-agent-runtime.md`](adr/001-agent-runtime.md),
an isolated proof of concept in
[`experiments/agent-runtime-poc/`](../experiments/agent-runtime-poc/README.md)
(German).

---

[Back to the README](../README.md)
