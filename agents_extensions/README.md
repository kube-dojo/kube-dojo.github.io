# Agent extensions for KubeDojo

The release pinned by `requirements-machinery.lock` supplies the fleet skills,
rules, and hooks. `deployment.v1.json` enrolls Claude and Codex and selects the
KubeDojo sources in `shared/`, `claude/`, and `codex/`.

## Apply and verify

Use a virtual environment containing the hash-locked machinery release. See
the [machinery consumer installation procedure](https://github.com/learn-ukrainian/machinery/blob/v0.1.43/docs/release.md#consumers).
Set `LEARN_UKRAINIAN_PRIMARY_REPO_ROOT` to your configured machinery
shared-state checkout. Set `LEARN_UKRAINIAN_PYTHON` to the absolute executable
in the virtual environment where you installed the locked release.

From the KubeDojo checkout you want to configure:

```bash
npm run agents:deploy
bash agents_extensions/deploy.sh --check
```

The wrapper selects this checkout explicitly and runs
`lu_machinery.agent_deploy`. Apply generates `.claude/`, `.codex/` and the
shared `.agents/skills/` tree. Check verifies the bytes, modes and ownership
manifest. It needs a successful apply first. The Claude launcher applies the
plan on a fresh checkout and verifies existing deployments before starting
Claude. For Codex, apply before starting an enrolled
checkout and set `LU_PRODUCT_ROOT` to that checkout's absolute path for the
session. The configured primary supplies Codex's lifecycle hook entry points.

Edit the product source and rerun apply and check. Commit the source files.
Keep each developer's Claude overrides in `.claude/settings.local.json`.
Apply before running the existing hook tests. They exercise the installed
scripts through their generated paths in `.claude/`.

## Existing checkouts

Record any local edits to legacy extension copies before switching to the
enrollment revision. Git removes the tracked copies during the update.
Reconcile any remaining unowned files named by the deployer with the product
sources or personal settings. A fresh checkout is also suitable. The
deployer refuses unexpected files and differing unowned outputs, including a
custom `.codex/config.toml`. Save any local Codex preferences in your personal
configuration before setting aside that conflicting copy and running apply.

## Product guidance

- The release supplies every fleet hook, rule, skill and guard: session
  start, context monitoring, post-compaction, branch and primary-checkout
  guards, dispatch, review, landing and handoff. Do not copy or fork them
  here; a product file with the same purpose fires twice.
- `claude/hooks/` keeps only the shared hook library and the KubeDojo Python
  autoformat hook. Interactive KubeDojo `PreToolUse` scripts deploy
  from `claude/kubedojo-hooks/` to `.claude/kubedojo-hooks/`: the content
  hooks, and `block-direct-commit-on-main.sh`, kept because the release's
  guards do not refuse a `git commit` on the primary checkout's `main`. The headless
  Claude adapter reserves `.claude/hooks/` in `PreToolUse` for release
  guards. The release's Python guard blocks a bare interpreter and suggests
  the configured command.
- `claude/rules/` holds the KubeDojo content rules (module quality,
  translation, Kubernetes release tracks, new-content checklist, durable
  vendor content, GitHub Actions security, fresh session after interview).
- `shared/skills/kubedojo-drive-epic/` is a KubeDojo overlay on the release
  `drive-epic` skill: the site and labs workflow, with local delivery and
  review requirements in its companion documentation. The other KubeDojo
  skills are curriculum skills.
