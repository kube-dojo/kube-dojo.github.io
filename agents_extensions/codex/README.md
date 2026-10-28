# Codex extensions

Per-agent overlay directory for OpenAI Codex. Shared skills live in
`agents_extensions/shared/skills/`. Add Codex-specific skills, hooks, or config
here; `agents_extensions/deploy.sh --target codex` will materialize into `.codex/`.

`config.toml` is the portable project config. It enables multi-agent v2 in the
`agents` namespace, with Terra 6.1 as the default subagent model. The lead stays
Sol 6.1; coding, writing, computer use and QA default to Terra 6.1, while hard
problems and review use Sol 6.1. Personal named roles live in `~/.codex/agents/`.
The project overlay does not change home permissions or MCP servers.
Headless Codex uses Terra 6.1 for `edit`/`draft`, Sol 6.1 for `review`/`architect`, and GPT-6 Luna for `search`.
Unclassified bridge calls default to Terra 6.1; explicit per-call and `AB_CODEX_MODEL` overrides take precedence.
Run `bash agents_extensions/deploy.sh --target codex`, then the same command
with `--check` to verify deployment. A differing local config is preserved and
deployment fails. Inspect its diff first; `--force-config` explicitly backs up
the local file before replacing it. Keep host-specific settings in home config.

`start-codex.sh` also enables v2 explicitly. Set `CODEX_ENABLE_MULTI_AGENT=0`
to disable both multi-agent and v2 for that launch, even if project config
enables them. Other Codex arguments are forwarded unchanged; avoid conflicting
feature flags and use the wrapper opt-out for a single-agent launch.

The runtime reads final answers only from each invocation's unique `-o` file.
It does not recover answers or terminate a process based on shared rollout
files. A CLI hang therefore waits for the configured hard timeout; missing
final output is reported as a failure rather than borrowing another session.
