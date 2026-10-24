# Codex extensions

Per-agent overlay directory for OpenAI Codex. Shared skills live in
`agents_extensions/shared/skills/`. Add Codex-specific skills, hooks, or config
here; `agents_extensions/deploy.sh --target codex` will materialize into `.codex/`.

`config.toml` is the portable project config. It enables multi-agent v2 in the
`agents` namespace without changing home models, permissions, or MCP servers.
Run `bash agents_extensions/deploy.sh --target codex`, then the same command
with `--check` to verify deployment. A differing local config is preserved and
deployment fails. Inspect its diff first; `--force-config` explicitly backs up
the local file before replacing it. Keep host-specific settings in home config.

`start-codex.sh` also enables v2 explicitly. Set `CODEX_ENABLE_MULTI_AGENT=0`
to disable both multi-agent and v2 for that launch, even if project config
enables them. Explicit Codex arguments forwarded by the launcher take precedence.
