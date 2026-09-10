# Agent Extensions for KubeDojo

Git-tracked source for agent skills, hooks, and statusline assets. Extensions are
**agent-agnostic by default** (`shared/`) with per-agent overlays (`claude/`,
`codex/`, `cursor/`, `gemini/`).

## Structure

```
agents_extensions/
├── README.md
├── deploy.sh
├── shared/
│   └── skills/                    # Used by ALL agents (also at dispatch time)
│       ├── curriculum-writer/
│       ├── cross-family-reviewer/
│       ├── drive-epic/                 # epic-driver playbook (site + labs)
│       ├── module-quality-reviewer/
│       ├── session-handoff-writer/
│       ├── k8s-cert-expert/
│       └── platform-expert/
├── claude/                        # Claude Code–specific
│   ├── skills/
│   │   ├── curriculum-orchestrator/
│   │   ├── dispatch-router/
│   │   └── cold-start/
│   ├── hooks/
│   │   ├── session-setup.sh
│   │   └── context-monitor.sh
│   └── statusline/
│       └── statusline.sh
├── codex/                         # Placeholder for future Codex extensions
├── cursor/                        # Placeholder for future Cursor extensions
└── gemini/                        # Placeholder for future Gemini extensions
```

Slash commands (`/review-module`, etc.) were retired 2026-05-21; production review
runs through `scripts/dispatch_smart.py` and `docs/review-protocol.md`. Skills
below remain the durable role contracts.

## Deployment

From the repo root:

```bash
# Deploy all agents (default): merges shared/ + per-agent/ into each hidden dir
./agents_extensions/deploy.sh

# Deploy one agent only
./agents_extensions/deploy.sh --target claude

# Quiet mode (for scripts)
./agents_extensions/deploy.sh --quiet
```

For Claude, `deploy.sh` merges `shared/skills/*` and `claude/skills/*` into
`.claude/skills/`, copies `claude/hooks/*` → `.claude/hooks/`, and
`claude/statusline/*` → `.claude/statusline/`. The script is idempotent (`cmp -s`
change detection).

`start-claude.sh` may invoke deploy via `npm run claude:deploy` when configured.

## Development workflow

1. **Edit** extensions under `agents_extensions/` (tracked in git)
2. **Deploy** with `./agents_extensions/deploy.sh`
3. **Test** against the materialized `.claude/` (or `.codex/`, etc.)
4. **Commit** changes to `agents_extensions/` only — not the materialized dirs,
   except where `.claude/` paths are intentionally tracked (skills mirror, hooks)

## Creating new skills

1. Choose **shared** (any agent) vs **`<agent>/`** (orchestrator-only, etc.) from
   the skill frontmatter `description:` field.
2. Create `agents_extensions/<shared|claude|...>/skills/your-skill/SKILL.md`
3. Run `./agents_extensions/deploy.sh --target <agent>`
4. Agents auto-invoke skills when the description matches the task.

## Quality standards reference

Module quality rubric: `docs/quality-rubric.md`. Target 8+/10 per dimension for
production modules.
