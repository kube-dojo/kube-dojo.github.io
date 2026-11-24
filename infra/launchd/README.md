# UK Pipeline LaunchAgents

## Purpose

This local launchd wiring runs the Ukrainian pipeline maintenance jobs daily on a developer machine. It detects stale UK translations at 03:00, then runs the translation worker loop at 03:30 to drain a small capped batch from the local queue. The jobs are local-only and write logs under `.pipeline/launchd-logs/`.

## Why launchd, not GitHub Actions

Both target scripts depend on **local state** that GH Actions runners cannot share:

1. `scripts/translation_v2.py worker loop` reads/writes `.pipeline/translation_v2.db` (local SQLite via ControlPlane) and uses **Gemini OAuth** via `dispatch_gemini_with_retry` (per-account creds, not a shared API key -- see `KUBEDOJO_GEMINI_SUBSCRIPTION=1` in `.envrc`).
2. `scripts/detect_uk_divergence.py` enqueues into the **same** local SQLite DB.
3. Neither script auto-commits or pushes; UK files written under `src/content/docs/uk/` are reviewed locally before manual commit.

## Schedule

| Job | Time | Cap |
|---|---|---|
| uk-divergence-detect | 03:00 daily | (full scan; no enqueue cap) |
| translation-worker-loop | 03:30 daily | `--max-calls 3 --sleep-seconds 30` |

## Install

```bash
./infra/launchd/install.sh
```

## Verify

```bash
launchctl list | grep kubedojo
ls -la .pipeline/launchd-logs/
```

## Uninstall

```bash
./infra/launchd/uninstall.sh
```

## Troubleshooting

- `.venv/bin/python` must exist (run `uv sync --locked` from the repository root if missing; it installs the Python in `.python-version` and the hash-pinned `uv.lock`).
- Gemini OAuth creds must be live (`~/.gemini/oauth_creds.json` or whatever `dispatch_gemini_with_retry` uses).
- launchd jobs run with a stripped environment -- anything not in `EnvironmentVariables` is unavailable.
- To trigger a job manually for testing: `launchctl start com.kubedojo.uk-divergence-detect`.
- To check next fire time: `launchctl list <label>` (look at `LastExitStatus`, `PID`).
