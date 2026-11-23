#!/usr/bin/env python3
"""Teaching-quality audit dispatcher for KubeDojo modules.

Sends each specified module to Gemini with a pedagogical-framework-grounded
prompt and expects a strict JSON audit back. Results go to
.pipeline/teaching-audit/<module-slug>.json

Pilot usage (one module):
  .venv/bin/python scripts/audit_teaching_quality.py \\
      --module src/content/docs/ai-ml-engineering/ai-native-development/module-1.9-building-with-ai-coding-assistants.md

Batch usage (all 648 .md under src/content/docs, excluding uk/):
  .venv/bin/python scripts/audit_teaching_quality.py --all --workers 3

Idempotent: skips modules whose audit file already exists unless --force.
"""

from __future__ import annotations

import argparse
import concurrent.futures as cf
import json
import sys
import time
from pathlib import Path

from lu_machinery.agent_runtime.errors import (
    AgentRuntimeError,
    AgentTimeoutError,
)
from lu_machinery.agent_runtime.runner import invoke

REPO_ROOT = Path(__file__).resolve().parents[1]
CONTENT_ROOT = REPO_ROOT / "src" / "content" / "docs"
AUDIT_DIR = REPO_ROOT / ".pipeline" / "teaching-audit"
PROMPT_TEMPLATE = REPO_ROOT / "scripts" / "prompts" / "audit_teaching.md"


def slug_for(path: Path) -> str:
    rel = path.relative_to(CONTENT_ROOT)
    return str(rel).replace("/", "-").removesuffix(".md")


def audit_path_for(path: Path) -> Path:
    return AUDIT_DIR / f"{slug_for(path)}.json"


def build_prompt(module_path: Path) -> str:
    template = PROMPT_TEMPLATE.read_text(encoding="utf-8")
    content = module_path.read_text(encoding="utf-8")
    line_count = len(content.splitlines())
    rel = module_path.relative_to(REPO_ROOT).as_posix()
    return (
        template
        .replace("{{MODULE_PATH}}", rel)
        .replace("{{LINE_COUNT}}", str(line_count))
        .replace("{{MODULE_CONTENT}}", content)
    )


def extract_json(stdout: str) -> dict | None:
    """Gemini sometimes wraps JSON in prose / code fences. Extract greedily."""
    stripped = stdout.strip()
    if stripped.startswith("```"):
        stripped = stripped.split("\n", 1)[1] if "\n" in stripped else stripped
        if stripped.endswith("```"):
            stripped = stripped.rsplit("```", 1)[0]
        if stripped.startswith("json"):
            stripped = stripped[4:].lstrip("\n")
    try:
        return json.loads(stripped)
    except json.JSONDecodeError:
        pass
    # Try bracket-balance scan.
    depth = 0
    start = -1
    for i, ch in enumerate(stdout):
        if ch == "{":
            if depth == 0:
                start = i
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0 and start >= 0:
                try:
                    return json.loads(stdout[start:i + 1])
                except json.JSONDecodeError:
                    start = -1
    return None


def audit_one(module_path: Path, model: str, timeout: int, force: bool) -> tuple[Path, str, dict | str]:
    out = audit_path_for(module_path)
    if out.exists() and not force:
        return module_path, "skipped_exists", json.loads(out.read_text())
    prompt = build_prompt(module_path)
    t0 = time.time()
    try:
        result = invoke(
            "agy",
            prompt,
            mode="read-only",
            cwd=REPO_ROOT,
            model=model,
            entrypoint="audit_teaching_quality",
            hard_timeout=timeout,
        )
    except AgentTimeoutError:
        return module_path, "timeout", f"timed out after {timeout}s"
    except AgentRuntimeError as exc:
        return module_path, "dispatch_error", str(exc)[:2000]
    elapsed = time.time() - t0
    if not result.ok:
        return module_path, "dispatch_error", (result.stderr_excerpt or result.response or "")[:2000]
    stdout = result.response or ""
    parsed = extract_json(stdout)
    if parsed is None:
        return module_path, "parse_error", stdout[:2000]
    parsed["_meta"] = {
        "module_path": module_path.relative_to(REPO_ROOT).as_posix(),
        "model": model,
        "elapsed_seconds": round(elapsed, 1),
        "audited_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(parsed, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return module_path, "ok", parsed


def iter_all_modules() -> list[Path]:
    # All .md under src/content/docs, excluding uk/ translations and indexes.
    all_paths = sorted(CONTENT_ROOT.glob("**/*.md"))
    return [p for p in all_paths if "/uk/" not in p.as_posix() and p.name != "index.md"]


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--module", action="append", default=[], help="Specific module path (may repeat)")
    ap.add_argument("--all", action="store_true", help="Audit all English content modules")
    ap.add_argument("--workers", type=int, default=1, help="Parallel workers (cap 3)")
    ap.add_argument("--model", default="gemini-3-flash-preview", help="Gemini model")
    ap.add_argument("--timeout", type=int, default=300, help="Per-module timeout seconds")
    ap.add_argument("--force", action="store_true", help="Re-audit even if output exists")
    args = ap.parse_args()

    if args.workers > 3:
        print(f"workers capped 3 (requested {args.workers})", file=sys.stderr)
        args.workers = 3

    if not PROMPT_TEMPLATE.exists():
        print(f"ERROR: prompt template missing at {PROMPT_TEMPLATE}", file=sys.stderr)
        return 2

    if args.all:
        modules = iter_all_modules()
    elif args.module:
        modules = [Path(m).resolve() for m in args.module]
    else:
        print("ERROR: pass --module <path> or --all", file=sys.stderr)
        return 2

    print(f"# Auditing {len(modules)} module(s), workers={args.workers}, model={args.model}")

    done = 0
    stats = {"ok": 0, "skipped_exists": 0, "timeout": 0, "parse_error": 0, "dispatch_error": 0}
    with cf.ThreadPoolExecutor(max_workers=args.workers) as ex:
        futures = {
            ex.submit(audit_one, m, args.model, args.timeout, args.force): m
            for m in modules
        }
        for fut in cf.as_completed(futures):
            m, status, payload = fut.result()
            done += 1
            stats[status] = stats.get(status, 0) + 1
            if status == "ok" and isinstance(payload, dict):
                v = payload.get("verdict", "?")
                s = payload.get("teaching_score", "?")
                print(f"[{done}/{len(modules)}] ok    {slug_for(m)} → verdict={v} score={s}")
            elif status == "skipped_exists" and isinstance(payload, dict):
                v = payload.get("verdict", "?")
                print(f"[{done}/{len(modules)}] skip  {slug_for(m)} (audit exists, verdict={v})")
            else:
                print(f"[{done}/{len(modules)}] FAIL  {slug_for(m)} → {status}")
                if isinstance(payload, str):
                    print(f"    {payload[:300]}")

    print()
    print(f"# Done: {stats}")
    return 0 if stats.get("dispatch_error", 0) == 0 and stats.get("parse_error", 0) == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
