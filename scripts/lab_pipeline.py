#!/usr/bin/env python3
"""Decoupled lab review pipeline for KubeDojo labs."""

from __future__ import annotations

import argparse
import fcntl
import json
import os
import re
import subprocess
import sys
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(REPO_ROOT / "scripts"))

def _legacy_dispatcher_removed(*_args, **_kwargs):
    raise RuntimeError("legacy dispatcher removed")


GEMINI_WRITER_MODEL = "gemini-3.1-pro-high"


def _is_rate_limited(*_args, **_kwargs):
    return False


dispatch_agy = _legacy_dispatcher_removed
dispatch_claude = _legacy_dispatcher_removed
dispatch_codex = _legacy_dispatcher_removed

CONTENT_ROOT = REPO_ROOT / "src" / "content" / "docs"
KUBEDOJO_LABS_DIR = Path(
    os.environ.get("KUBEDOJO_LABS_DIR", "~/projects/kubedojo-labs")
).expanduser()
LAB_STATE_FILE = REPO_ROOT / ".pipeline" / "lab-state.yaml"
LAB_REVIEW_DIR = REPO_ROOT / ".pipeline" / "lab-reviews"
LAB_CHECK_IDS = [
    "STRUCTURE",
    "DOCS",
    "COVERAGE",
    "CALIBRATION",
    "VERIFY",
    "EXEC",
    "DETERM",
]
STATIC_CHECK_IDS = LAB_CHECK_IDS[:5]
MODELS = {
    "review": GEMINI_WRITER_MODEL,
}

LAB_REVIEW_PROMPT_TEMPLATE = """You are reviewing a hands-on lab for KubeDojo.

The lab practices concepts taught in this module:
- Learning outcomes:
{module_outcomes}
- Topics covered:
{module_topics}
- Existing inline summary:
{inline_summary}

Your job is to grade the LAB ONLY on these dimensions:

1. COVERAGE — Do the lab steps practice every Learning Outcome from the module?
   A FAIL must list specific outcomes the lab doesn't exercise. If module
   metadata is unavailable, judge whether the lab still practices a coherent,
   end-to-end skill progression implied by its title and steps.

2. CALIBRATION — Does the declared difficulty and time match the actual lab?
   Consider step count, scaffolding density, hint quantity, state complexity,
   and the declared time budget together.

3. STRUCTURE — Are required files present and is index.json coherent?

4. VERIFY — Are verify.sh scripts deterministic? They must check exact state,
   not stdout patterns. Flag uses of grep, wc -l, sleep, brittle output
   formatting checks, or anything likely to be flaky.

5. DOCS — Are intro, steps, and finish clear and usable for a student?

Return JSON only:
{{
  "verdict": "APPROVE" or "REJECT",
  "checks": [
    {{"id": "STRUCTURE", "passed": true, "evidence": "..."}},
    {{"id": "DOCS", "passed": true, "evidence": "..."}},
    {{"id": "COVERAGE", "passed": true, "evidence": "..."}},
    {{"id": "CALIBRATION", "passed": true, "evidence": "..."}},
    {{"id": "VERIFY", "passed": true, "evidence": "..."}}
  ],
  "feedback": "optional prose summary"
}}

Every one of STRUCTURE, DOCS, COVERAGE, CALIBRATION, VERIFY must appear.

LAB INDEX.JSON:
{index_json}

LAB INTRO:
{intro_text}

LAB FINISH:
{finish_text}

LAB STEPS:
{steps_text}
"""


@dataclass
class ModuleResolution:
    module_path: Path | None
    module_key: str | None
    warnings: list[str]
    errors: list[str]


def dispatch_auto(prompt: str, model: str, timeout: int = 900) -> tuple[bool, str]:
    # gemini-* slugs are agy (Antigravity) display models; gemini-cli retired (#2125).
    if model.startswith("gemini"):
        return dispatch_agy(prompt, model=model, timeout=timeout)
    if model.startswith("claude"):
        return dispatch_claude(prompt, model=model, timeout=timeout)
    if model.startswith("codex") or "codex" in model or model.startswith("gpt-"):
        return dispatch_codex(prompt, model=model, timeout=timeout)
    raise ValueError(f"Unknown model family: {model!r}")


def _atomic_write_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    unique = f".{os.getpid()}.{datetime.now(UTC).strftime('%H%M%S%f')}.tmp"
    tmp = path.with_suffix(path.suffix + unique)
    try:
        tmp.write_text(content)
        os.replace(tmp, path)
    except Exception:
        if tmp.exists():
            try:
                tmp.unlink()
            except OSError:
                pass
        raise


def _format_timestamp(value: datetime | str | None = None) -> str:
    if value is None:
        current = datetime.now(UTC)
    elif isinstance(value, datetime):
        current = value
    elif isinstance(value, str):
        try:
            current = datetime.fromisoformat(value)
        except ValueError:
            return value
    else:
        return str(value)
    if current.tzinfo is None:
        current = current.replace(tzinfo=UTC)
    else:
        current = current.astimezone(UTC)
    return current.strftime("%Y-%m-%dT%H:%M:%SZ")


def _format_duration(seconds: float | int | None) -> str:
    if seconds is None:
        return "unknown"
    try:
        total = max(0.0, float(seconds))
    except (TypeError, ValueError):
        return str(seconds)
    if total >= 60:
        minutes = int(total // 60)
        remainder = int(round(total - (minutes * 60)))
        return f"{minutes}m {remainder}s"
    if total >= 10:
        return f"{int(round(total))}s"
    if total >= 1:
        return f"{total:.1f}s"
    return f"{int(round(total * 1000))}ms"


def _quote_block(text: str) -> str:
    lines = text.splitlines() or [text]
    return "\n".join(f"> {line}" if line else ">" for line in lines)


def _extract_entry_timestamps(content: str) -> list[str]:
    return re.findall(r"^## ([0-9TZ:\-]+) — ", content, re.MULTILINE)


def _split_header_body(content: str) -> tuple[str, str]:
    marker = "\n---\n"
    if marker in content:
        header, body = content.split(marker, 1)
        return header, body.lstrip("\n")
    return content, ""


def _extract_json(output: str, required_keys: tuple[str, ...] = ("verdict", "checks")) -> dict | None:
    text = output.strip()
    if text.startswith("```"):
        parts = text.split("```")
        if len(parts) >= 2:
            candidate = parts[1]
            if candidate.startswith("json"):
                candidate = candidate[4:]
            try:
                obj = json.loads(candidate.strip())
                if isinstance(obj, dict) and all(k in obj for k in required_keys):
                    return obj
            except json.JSONDecodeError:
                pass
    try:
        obj = json.loads(text)
        if isinstance(obj, dict) and all(k in obj for k in required_keys):
            return obj
    except json.JSONDecodeError:
        pass

    depth = 0
    end = -1
    for i in range(len(text) - 1, -1, -1):
        ch = text[i]
        if ch == "}":
            if depth == 0:
                end = i
            depth += 1
        elif ch == "{":
            if depth > 0:
                depth -= 1
                if depth == 0 and end != -1:
                    candidate = text[i:end + 1]
                    try:
                        obj = json.loads(candidate)
                        if isinstance(obj, dict) and all(k in obj for k in required_keys):
                            return obj
                    except json.JSONDecodeError:
                        pass
                    end = -1
    return None


def load_lab_state() -> dict:
    if LAB_STATE_FILE.exists():
        return yaml.safe_load(LAB_STATE_FILE.read_text()) or {"labs": {}}
    return {"labs": {}}


def save_lab_state(state: dict) -> None:
    LAB_STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    lock_file = LAB_STATE_FILE.with_suffix(".lock")
    with open(lock_file, "w", encoding="utf-8") as lf:
        fcntl.flock(lf, fcntl.LOCK_EX)
        try:
            _atomic_write_text(
                LAB_STATE_FILE,
                yaml.dump(state, allow_unicode=True, sort_keys=False),
            )
        finally:
            fcntl.flock(lf, fcntl.LOCK_UN)


def get_lab_state(state: dict, lab_key: str) -> dict:
    return state.setdefault("labs", {}).setdefault(
        lab_key,
        {
            "phase": "pending",
            "last_run": None,
            "severity": "clean",
            "reviewer": None,
            "module": None,
            "checks_failed": [],
            "errors": [],
        },
    )


def discover_labs(labs_dir: Path = KUBEDOJO_LABS_DIR) -> dict[str, Path]:
    if not labs_dir.exists():
        return {}
    labs: dict[str, Path] = {}
    for path in sorted(labs_dir.iterdir()):
        if path.is_dir() and (path / "index.json").exists():
            labs[path.name] = path
    return labs


def lab_key_from_path(lab_dir: Path) -> str:
    return lab_dir.name


def lab_audit_path_for_key(lab_key: str) -> Path:
    return LAB_REVIEW_DIR / f"{lab_key}.md"


def module_key_from_path(module_path: Path, content_root: Path = CONTENT_ROOT) -> str:
    rel = module_path.resolve().relative_to(content_root.resolve())
    return str(rel).replace(".md", "")


def find_module_path(module_ref: str, content_root: Path = CONTENT_ROOT) -> Path | None:
    cleaned = str(module_ref).strip().replace("\\", "/")
    if not cleaned:
        return None
    cleaned = cleaned[:-3] if cleaned.endswith(".md") else cleaned
    if cleaned.startswith("/"):
        candidate = Path(cleaned)
        return candidate if candidate.exists() else None
    candidate = content_root / f"{cleaned}.md"
    if candidate.exists():
        return candidate
    matches = list(content_root.glob(f"**/{Path(cleaned).name}.md"))
    return matches[0] if matches else None


def _extract_frontmatter(content: str) -> dict:
    if not content.startswith("---\n"):
        return {}
    parts = content.split("---", 2)
    if len(parts) < 3:
        return {}
    try:
        data = yaml.safe_load(parts[1]) or {}
    except yaml.YAMLError:
        return {}
    return data if isinstance(data, dict) else {}


def _module_lab_id(frontmatter: dict) -> str | None:
    lab = frontmatter.get("lab")
    if isinstance(lab, str) and lab.strip():
        return lab.strip()
    if isinstance(lab, dict):
        for key in ("id", "name", "slug"):
            value = lab.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip()
    return None


def find_module_for_lab(
    lab_dir: Path,
    *,
    content_root: Path = CONTENT_ROOT,
    require_lab_meta: bool = False,
) -> ModuleResolution:
    lab_key = lab_key_from_path(lab_dir)
    warnings: list[str] = []
    errors: list[str] = []

    try:
        index_data = json.loads((lab_dir / "index.json").read_text())
    except (OSError, json.JSONDecodeError) as exc:
        errors.append(f"invalid index.json: {exc}")
        return ModuleResolution(None, None, warnings, errors)

    module_ref = index_data.get("module")
    module_path = None
    metadata_used = False
    if isinstance(module_ref, str) and module_ref.strip():
        module_path = find_module_path(module_ref, content_root=content_root)
        metadata_used = True
        if module_path is None:
            errors.append(f"module metadata points to missing module: {module_ref}")

    if module_path is None:
        match = re.match(r"^(?P<track>[a-z0-9]+)-(?P<num>\d+\.\d+)-(?P<slug>.+)$", lab_key)
        if match:
            module_name = f"module-{match.group('num')}-{match.group('slug')}.md"
            track = match.group("track")
            candidates = sorted(
                p for p in content_root.glob(f"**/{module_name}")
                if f"/{track}/" in str(p).replace("\\", "/")
                and "/uk/" not in str(p).replace("\\", "/")
            )
            if candidates:
                module_path = candidates[0]
                if not metadata_used:
                    warnings.append("lab missing index.json module metadata; used filename fallback")
            else:
                warnings.append(f"no module found via fallback pattern for {lab_key}")
        else:
            warnings.append(f"lab key does not match fallback naming convention: {lab_key}")

    if module_path is None:
        if require_lab_meta:
            errors.append("lab metadata is required but no module link could be resolved")
        return ModuleResolution(None, None, warnings, errors)

    module_content = module_path.read_text()
    module_fm = _extract_frontmatter(module_content)
    module_lab = _module_lab_id(module_fm)
    if module_lab != lab_key:
        if module_lab:
            msg = f"module frontmatter lab mismatch: expected {lab_key}, found {module_lab}"
        else:
            msg = "module missing lab metadata"
        if require_lab_meta:
            errors.append(msg)
        else:
            warnings.append(msg)

    if require_lab_meta and not (isinstance(module_ref, str) and module_ref.strip()):
        errors.append("lab missing index.json module metadata")

    return ModuleResolution(
        module_path=module_path,
        module_key=module_key_from_path(module_path, content_root=content_root),
        warnings=warnings,
        errors=errors,
    )


def _extract_section(content: str, heading_pattern: str) -> str:
    match = re.search(
        rf"(?ms)^## +{heading_pattern}\n(.*?)(?=^## +|\Z)",
        content,
    )
    if not match:
        return ""
    return match.group(1).strip()


def _extract_learning_outcomes(content: str) -> list[str]:
    for heading in (
        r"What You'll Be Able to Do",
        r"Learning Outcomes",
        r"What You'll Learn",
    ):
        section = _extract_section(content, heading)
        if not section:
            continue
        bullets = [
            line.strip()[2:].strip()
            for line in section.splitlines()
            if line.strip().startswith("- ")
        ]
        if bullets:
            return bullets
    return []


def _extract_topics(content: str) -> list[str]:
    topics = re.findall(r"(?m)^## +(.+)$", content)
    return [topic.strip() for topic in topics[:8]]


def _extract_hands_on_summary(content: str) -> str:
    section = _extract_section(content, r"Hands-On Exercise")
    if not section:
        return ""
    return section[:2000].strip()


def _read_json(path: Path) -> dict:
    return json.loads(path.read_text())


def _lab_step_records(index_data: dict) -> list[dict]:
    details = index_data.get("details")
    if not isinstance(details, dict):
        return []
    steps = details.get("steps")
    return steps if isinstance(steps, list) else []


def run_structure_check(lab_dir: Path, index_data: dict) -> dict:
    failures: list[str] = []
    for field in ("title", "description", "difficulty", "time"):
        value = index_data.get(field)
        if not isinstance(value, str) or not value.strip():
            failures.append(f"index.json missing string field `{field}`")

    details = index_data.get("details")
    if not isinstance(details, dict):
        failures.append("index.json missing object field `details`")
        details = {}
    backend = index_data.get("backend")
    if not isinstance(backend, dict) or not str(backend.get("imageid", "")).strip():
        failures.append("index.json missing backend.imageid")

    intro = details.get("intro") if isinstance(details, dict) else None
    finish = details.get("finish") if isinstance(details, dict) else None
    steps = _lab_step_records(index_data)

    intro_path = lab_dir / str((intro or {}).get("text", ""))
    setup_path = lab_dir / str((intro or {}).get("background", "setup.sh"))
    finish_path = lab_dir / str((finish or {}).get("text", ""))
    if not intro_path.exists():
        failures.append(f"missing intro file: {intro_path.relative_to(lab_dir)}")
    if not setup_path.exists():
        failures.append(f"missing setup file: {setup_path.relative_to(lab_dir)}")
    if not finish_path.exists():
        failures.append(f"missing finish file: {finish_path.relative_to(lab_dir)}")
    if not steps:
        failures.append("index.json has no steps")

    for idx, step in enumerate(steps, 1):
        if not isinstance(step, dict):
            failures.append(f"step {idx} is not an object")
            continue
        for field in ("text", "verify", "solution"):
            value = step.get(field)
            if not isinstance(value, str) or not value.strip():
                failures.append(f"step {idx} missing `{field}`")
                continue
            step_path = lab_dir / value
            if not step_path.exists():
                failures.append(f"step {idx} missing file: {value}")

    return {
        "id": "STRUCTURE",
        "passed": not failures,
        "evidence": "; ".join(failures) if failures else "required files and schema present",
    }


def run_verify_check(lab_dir: Path, index_data: dict) -> dict:
    failures: list[str] = []
    anti_patterns = [
        (re.compile(r"\bgrep\b"), "uses grep"),
        (re.compile(r"\bwc\s+-l\b"), "uses wc -l"),
        (re.compile(r"\bsleep\b"), "uses sleep"),
    ]
    for idx, step in enumerate(_lab_step_records(index_data), 1):
        verify_ref = step.get("verify")
        if not isinstance(verify_ref, str) or not verify_ref.strip():
            failures.append(f"step {idx} missing verify.sh")
            continue
        verify_path = lab_dir / verify_ref
        if not verify_path.exists():
            failures.append(f"step {idx} missing file: {verify_ref}")
            continue
        text = verify_path.read_text()
        for pattern, reason in anti_patterns:
            if pattern.search(text):
                failures.append(f"step {idx} {reason} in {verify_ref}")
    return {
        "id": "VERIFY",
        "passed": not failures,
        "evidence": "; ".join(failures) if failures else "verify scripts avoid obvious anti-patterns",
    }


def _load_lab_bundle(lab_dir: Path, index_data: dict) -> tuple[str, str, str]:
    details = index_data.get("details", {})
    intro_text = ""
    finish_text = ""
    steps_text: list[str] = []

    intro_ref = ((details.get("intro") or {}).get("text")) if isinstance(details, dict) else None
    finish_ref = ((details.get("finish") or {}).get("text")) if isinstance(details, dict) else None
    if isinstance(intro_ref, str) and (lab_dir / intro_ref).exists():
        intro_text = (lab_dir / intro_ref).read_text()
    if isinstance(finish_ref, str) and (lab_dir / finish_ref).exists():
        finish_text = (lab_dir / finish_ref).read_text()

    for idx, step in enumerate(_lab_step_records(index_data), 1):
        block = [f"STEP {idx}: {step.get('title', f'Step {idx}')}".strip()]
        for field in ("text", "verify"):
            ref = step.get(field)
            if isinstance(ref, str) and (lab_dir / ref).exists():
                block.append(f"{field.upper()} ({ref}):")
                block.append((lab_dir / ref).read_text())
        steps_text.append("\n".join(block))
    return intro_text, finish_text, "\n\n".join(steps_text)


def _normalize_review_checks(checks: list[dict], required_ids: list[str]) -> dict[str, dict]:
    result: dict[str, dict] = {}
    for check in checks:
        if not isinstance(check, dict):
            continue
        check_id = str(check.get("id", "")).strip().upper()
        if check_id:
            result[check_id] = {
                "id": check_id,
                "passed": bool(check.get("passed")),
                "evidence": str(check.get("evidence", "")).strip(),
            }
    for check_id in required_ids:
        result.setdefault(
            check_id,
            {"id": check_id, "passed": False, "evidence": "reviewer omitted required check"},
        )
    return result


def review_static_checks_with_model(
    lab_dir: Path,
    index_data: dict,
    resolution: ModuleResolution,
    *,
    model: str,
) -> dict:
    module_outcomes = ["Generic lab outcomes inferred from title and steps."]
    module_topics = ["No linked module topics available."]
    inline_summary = "No linked module summary available."
    if resolution.module_path is not None and resolution.module_path.exists():
        module_content = resolution.module_path.read_text()
        outcomes = _extract_learning_outcomes(module_content)
        topics = _extract_topics(module_content)
        summary = _extract_hands_on_summary(module_content)
        if outcomes:
            module_outcomes = outcomes
        if topics:
            module_topics = topics
        if summary:
            inline_summary = summary

    intro_text, finish_text, steps_text = _load_lab_bundle(lab_dir, index_data)
    prompt = LAB_REVIEW_PROMPT_TEMPLATE.format(
        module_outcomes="\n".join(f"  - {item}" for item in module_outcomes),
        module_topics="\n".join(f"  - {item}" for item in module_topics),
        inline_summary=inline_summary,
        index_json=json.dumps(index_data, indent=2),
        intro_text=intro_text,
        finish_text=finish_text,
        steps_text=steps_text,
    )
    ok, output = dispatch_auto(prompt, model=model, timeout=900)
    if not ok:
        if output and _is_rate_limited(output):
            raise RuntimeError(f"reviewer rate-limited: {output}")
        raise RuntimeError(output or "reviewer failed")

    payload = _extract_json(output)
    if not isinstance(payload, dict):
        raise RuntimeError("failed to parse reviewer JSON")
    checks = payload.get("checks")
    if not isinstance(checks, list):
        raise RuntimeError("reviewer returned malformed checks")
    return {
        "verdict": str(payload.get("verdict", "REJECT")).upper(),
        "feedback": str(payload.get("feedback", "")).strip(),
        "checks": _normalize_review_checks(checks, STATIC_CHECK_IDS),
    }


def compute_lab_severity(checks: list[dict], errors: list[str]) -> str:
    if errors:
        return "severe"
    failed = sum(1 for check in checks if not check.get("passed") and not check.get("not_run"))
    if failed == 0:
        return "clean"
    if failed <= 2:
        return "targeted"
    return "severe"


def _render_check_summary(checks: list[dict]) -> str:
    passed = [c["id"] for c in checks if c.get("passed")]
    failed = [c["id"] for c in checks if not c.get("passed") and not c.get("not_run")]
    skipped = [c["id"] for c in checks if c.get("not_run")]
    parts = [f"**Checks**: {len(passed)}/{len(checks)} passed"]
    if passed:
        parts.append(f"passed={' '.join(passed)}")
    if failed:
        parts.append(f"failed={' '.join(failed)}")
    if skipped:
        parts.append(f"not-run={' '.join(skipped)}")
    return " | ".join(parts)


def _render_failed_evidence(checks: list[dict]) -> str:
    lines = []
    for check in checks:
        if check.get("passed") or check.get("not_run"):
            continue
        evidence = str(check.get("evidence", "")).strip()
        if evidence:
            lines.append(f"- **{check['id']}**: {evidence}")
    return "**Failed check evidence**:\n" + "\n".join(lines) if lines else ""


def _render_lab_audit_entry(event: str, timestamp: str, fields: dict) -> str:
    heading = f"## {timestamp} — `{event}`"
    if event == "LAB_REVIEW":
        heading += f" — `{fields.get('verdict', 'UNKNOWN')}`"
    lines = [heading, ""]

    if event == "LAB_REVIEW":
        checks = fields.get("checks") if isinstance(fields.get("checks"), list) else []
        lines.extend(
            [
                f"**Reviewer**: {fields.get('reviewer', 'unknown')}",
                f"**Module**: {fields.get('module', '-')}",
                f"**Severity**: {fields.get('severity', 'unknown')}",
                _render_check_summary(checks),
            ]
        )
        warnings = fields.get("warnings") if isinstance(fields.get("warnings"), list) else []
        if warnings:
            lines.extend(["", "**Warnings**:"])
            lines.extend(f"- {item}" for item in warnings)
        failed = _render_failed_evidence(checks)
        if failed:
            lines.extend(["", failed])
        feedback = str(fields.get("feedback", "")).strip()
        if feedback:
            lines.extend(["", "**Feedback**:", _quote_block(feedback)])
    elif event == "LAB_EXEC":
        lines.extend(
            [
                f"**Duration**: {_format_duration(fields.get('duration'))}",
                f"**Status**: {fields.get('status', 'unknown')}",
            ]
        )
        step_results = fields.get("step_results") if isinstance(fields.get("step_results"), list) else []
        if step_results:
            lines.extend(["", "**Step results**:"])
            lines.extend(f"- {item}" for item in step_results)
        stderr = str(fields.get("stderr", "")).strip()
        if stderr:
            lines.extend(["", "**Captured stderr**:", _quote_block(stderr)])
    elif event == "LAB_DONE":
        lines.extend(
            [
                f"**Reviewer**: {fields.get('reviewer', 'unknown')}",
                f"**Module**: {fields.get('module', '-')}",
            ]
        )
    elif event == "LAB_RESET":
        lines.extend(
            [
                f"**New phase**: {fields.get('new_phase', 'pending')}",
                "**Cleared errors**:",
            ]
        )
        cleared = fields.get("cleared_errors") if isinstance(fields.get("cleared_errors"), list) else []
        lines.extend(f"- {item}" for item in cleared)
    else:
        for key, value in fields.items():
            lines.append(f"**{key}**: {value}")

    return "\n".join(lines).rstrip()


def append_lab_review_audit(lab_key: str, event: str, **fields) -> Path:
    target = lab_audit_path_for_key(lab_key)
    lock_file = target.with_suffix(".lock")
    timestamp = _format_timestamp(fields.pop("timestamp", None))

    target.parent.mkdir(parents=True, exist_ok=True)
    with open(lock_file, "w", encoding="utf-8") as lf:
        fcntl.flock(lf, fcntl.LOCK_EX)
        try:
            existing = target.read_text() if target.exists() else ""
            _, existing_body = _split_header_body(existing)
            existing_timestamps = _extract_entry_timestamps(existing)
            all_timestamps = existing_timestamps + [timestamp]
            state = load_lab_state()
            lab_state = state.get("labs", {}).get(lab_key, {})
            new_entry = _render_lab_audit_entry(event, timestamp, fields)
            new_body = new_entry
            existing_body = existing_body.strip()
            if existing_body:
                new_body += f"\n\n---\n\n{existing_body}"
            header_lines = [
                f"# Lab Review Audit: {lab_key}",
                "",
                f"**Lab**: `{lab_key}`",
                f"**First pass**: {min(all_timestamps) if all_timestamps else timestamp}",
                f"**Last pass**: {max(all_timestamps) if all_timestamps else timestamp}",
                f"**Total passes**: {len(existing_timestamps) + 1}",
                f"**Current phase**: {lab_state.get('phase', 'pending')}",
                f"**Current reviewer**: {lab_state.get('reviewer', '-')}",
                f"**Current severity**: {lab_state.get('severity', '-')}",
                f"**Linked module**: {lab_state.get('module', '-')}",
            ]
            _atomic_write_text(target, "\n".join(header_lines) + f"\n\n---\n\n{new_body}\n")
        finally:
            fcntl.flock(lf, fcntl.LOCK_UN)
    return target


def check_docker_daemon() -> tuple[bool, str]:
    try:
        result = subprocess.run(
            ["docker", "info"],
            capture_output=True,
            text=True,
            timeout=30,
        )
    except FileNotFoundError:
        return False, "Docker CLI not installed"
    except subprocess.SubprocessError as exc:
        return False, f"Docker check failed: {exc}"
    if result.returncode != 0:
        stderr = (result.stderr or result.stdout or "").strip()
        return False, stderr or "docker info failed"
    return True, "Docker available"


def _docker_name(lab_key: str) -> str:
    suffix = uuid.uuid4().hex[:8]
    return f"kubedojo-lab-{re.sub(r'[^a-z0-9-]+', '-', lab_key.lower())}-{suffix}"


def _docker_run(args: list[str], *, check: bool = True) -> subprocess.CompletedProcess:
    result = subprocess.run(args, capture_output=True, text=True)
    if check and result.returncode != 0:
        raise RuntimeError(result.stderr.strip() or result.stdout.strip() or "docker command failed")
    return result


def _start_lab_container(image_id: str, lab_key: str) -> str:
    name = _docker_name(lab_key)
    _docker_run(["docker", "run", "-d", "--name", name, image_id, "bash", "-lc", "sleep infinity"])
    return name


def _docker_exec(container: str, command: str, *, check: bool = True) -> subprocess.CompletedProcess:
    return _docker_run(["docker", "exec", container, "bash", "-lc", command], check=check)


def _copy_lab_into_container(container: str, lab_dir: Path) -> None:
    _docker_exec(container, "mkdir -p /lab")
    _docker_run(["docker", "cp", f"{lab_dir}{os.sep}.", f"{container}:/lab"])


def _teardown_container(container: str) -> None:
    subprocess.run(["docker", "rm", "-f", container], capture_output=True, text=True)


def run_exec_checks(lab_dir: Path, index_data: dict) -> tuple[list[dict], dict]:
    image_id = str(((index_data.get("backend") or {}).get("imageid", ""))).strip()
    if not image_id:
        failed = {
            "id": "EXEC",
            "passed": False,
            "evidence": "backend.imageid missing",
        }
        determ = {
            "id": "DETERM",
            "passed": False,
            "evidence": "backend.imageid missing",
        }
        return [failed, determ], {"status": "failed", "step_results": [], "stderr": ""}

    step_results: list[str] = []
    stderr_chunks: list[str] = []
    try:
        container = _start_lab_container(image_id, lab_key_from_path(lab_dir))
    except RuntimeError as exc:
        failed = {"id": "EXEC", "passed": False, "evidence": str(exc)}
        determ = {"id": "DETERM", "passed": False, "evidence": "exec tier did not start"}
        return [failed, determ], {"status": "failed", "step_results": [], "stderr": str(exc)}

    exec_passed = True
    determ_passed = True
    determ_failures: list[str] = []
    try:
        _copy_lab_into_container(container, lab_dir)
        setup_result = _docker_exec(container, "cd /lab && chmod +x setup.sh && ./setup.sh", check=False)
        if setup_result.returncode != 0:
            exec_passed = False
            stderr_chunks.append(setup_result.stderr)
            step_results.append("setup.sh failed")
        else:
            step_results.append("setup.sh passed")
            for idx, step in enumerate(_lab_step_records(index_data), 1):
                solution = step.get("solution")
                verify = step.get("verify")
                if not isinstance(solution, str) or not isinstance(verify, str):
                    exec_passed = False
                    step_results.append(f"step {idx}: missing solution or verify reference")
                    continue
                sol_result = _docker_exec(container, f"cd /lab && chmod +x {solution} {verify} && ./{solution}", check=False)
                if sol_result.returncode != 0:
                    exec_passed = False
                    stderr_chunks.append(sol_result.stderr)
                    step_results.append(f"step {idx}: solution failed")
                    continue
                verify_result = _docker_exec(container, f"cd /lab && ./{verify}", check=False)
                if verify_result.returncode != 0:
                    determ_passed = False
                    determ_failures.append(f"step {idx} verify after solution exited {verify_result.returncode}")
                    stderr_chunks.append(verify_result.stderr)
                    step_results.append(f"step {idx}: verify after solution failed")
                else:
                    step_results.append(f"step {idx}: solution+verify passed")
    finally:
        _teardown_container(container)

    negative_container = None
    try:
        negative_container = _start_lab_container(image_id, f"{lab_key_from_path(lab_dir)}-negative")
        _copy_lab_into_container(negative_container, lab_dir)
        setup_result = _docker_exec(negative_container, "cd /lab && chmod +x setup.sh && ./setup.sh", check=False)
        if setup_result.returncode != 0:
            exec_passed = False
            stderr_chunks.append(setup_result.stderr)
            step_results.append("negative setup.sh failed")
        else:
            for idx, step in enumerate(_lab_step_records(index_data), 1):
                verify = step.get("verify")
                if not isinstance(verify, str):
                    determ_passed = False
                    determ_failures.append(f"step {idx} missing verify reference for negative test")
                    continue
                verify_result = _docker_exec(negative_container, f"cd /lab && chmod +x {verify} && ./{verify}", check=False)
                if verify_result.returncode == 0:
                    determ_passed = False
                    determ_failures.append(f"step {idx} negative verify unexpectedly passed")
                    stderr_chunks.append(verify_result.stderr)
                    step_results.append(f"step {idx}: negative verify unexpectedly passed")
                else:
                    step_results.append(f"step {idx}: negative verify failed as expected")
    finally:
        if negative_container is not None:
            _teardown_container(negative_container)

    exec_check = {
        "id": "EXEC",
        "passed": exec_passed,
        "evidence": "setup and solutions executed cleanly" if exec_passed else "one or more setup/solution steps failed",
    }
    determ_check = {
        "id": "DETERM",
        "passed": determ_passed,
        "evidence": "verifiers passed after solution and failed before solution"
        if determ_passed else "; ".join(determ_failures),
    }
    return [exec_check, determ_check], {
        "status": "passed" if exec_passed and determ_passed else "failed",
        "step_results": step_results,
        "stderr": "\n".join(chunk.strip() for chunk in stderr_chunks if chunk.strip()),
    }


def _merged_checks(
    reviewer_checks: dict[str, dict],
    deterministic_checks: list[dict],
) -> list[dict]:
    checks = dict(reviewer_checks)
    for check in deterministic_checks:
        checks[check["id"]] = check
    return [checks[check_id] for check_id in STATIC_CHECK_IDS]


def review_lab(
    lab_dir: Path,
    *,
    run_exec: bool = False,
    require_lab_meta: bool = False,
    review_model: str = MODELS["review"],
    state: dict | None = None,
    docker_status: tuple[bool, str] | None = None,
) -> dict:
    lab_key = lab_key_from_path(lab_dir)
    index_data = _read_json(lab_dir / "index.json")
    state = state or load_lab_state()
    lab_state = get_lab_state(state, lab_key)
    lab_state["phase"] = "review"
    lab_state["reviewer"] = review_model
    lab_state["last_run"] = _format_timestamp()
    save_lab_state(state)

    resolution = find_module_for_lab(
        lab_dir,
        content_root=CONTENT_ROOT,
        require_lab_meta=require_lab_meta,
    )
    warnings = list(resolution.warnings)
    errors = list(resolution.errors)
    lab_state["module"] = resolution.module_key

    deterministic = [
        run_structure_check(lab_dir, index_data),
        run_verify_check(lab_dir, index_data),
    ]

    feedback = ""
    reviewer_checks: dict[str, dict] = {}
    verdict = "REJECT"
    if not errors:
        reviewed = review_static_checks_with_model(
            lab_dir,
            index_data,
            resolution,
            model=review_model,
        )
        reviewer_checks = reviewed["checks"]
        verdict = reviewed["verdict"]
        feedback = reviewed["feedback"]
    else:
        reviewer_checks = {
            check_id: {"id": check_id, "passed": False, "evidence": "metadata resolution failed"}
            for check_id in STATIC_CHECK_IDS
        }
        feedback = "; ".join(errors)

    checks = _merged_checks(reviewer_checks, deterministic)
    exec_summary = None
    if run_exec:
        lab_state["phase"] = "check"
        save_lab_state(state)
        docker_ok, docker_message = docker_status if docker_status is not None else check_docker_daemon()
        if not docker_ok:
            if os.environ.get("CI", "").lower() == "true":
                errors.append(f"EXEC tier required in CI but Docker unavailable: {docker_message}")
                checks.extend(
                    [
                        {"id": "EXEC", "passed": False, "evidence": docker_message},
                        {"id": "DETERM", "passed": False, "evidence": docker_message},
                    ]
                )
                exec_summary = {"status": "failed", "step_results": [], "stderr": docker_message}
            else:
                warnings.append(f"EXEC tier skipped — Docker not available: {docker_message}")
                checks.extend(
                    [
                        {"id": "EXEC", "passed": False, "not_run": True, "evidence": docker_message},
                        {"id": "DETERM", "passed": False, "not_run": True, "evidence": docker_message},
                    ]
                )
                exec_summary = {"status": "skipped", "step_results": [], "stderr": docker_message}
        else:
            exec_checks, exec_summary = run_exec_checks(lab_dir, index_data)
            checks.extend(exec_checks)
    else:
        checks.extend(
            [
                {"id": "EXEC", "passed": False, "not_run": True, "evidence": "exec tier not requested"},
                {"id": "DETERM", "passed": False, "not_run": True, "evidence": "exec tier not requested"},
            ]
        )

    failed_checks = [check["id"] for check in checks if not check.get("passed") and not check.get("not_run")]
    if not failed_checks and not errors:
        verdict = "APPROVE"
    else:
        verdict = "REJECT"
    severity = compute_lab_severity(checks, errors)

    lab_state["phase"] = "done"
    lab_state["severity"] = severity
    lab_state["module"] = resolution.module_key
    lab_state["checks_failed"] = failed_checks
    lab_state["errors"] = errors
    save_lab_state(state)

    append_lab_review_audit(
        lab_key,
        "LAB_REVIEW",
        verdict=verdict,
        reviewer=review_model,
        severity=severity,
        module=resolution.module_key,
        checks=checks,
        feedback=feedback,
        warnings=warnings,
    )
    if exec_summary is not None:
        append_lab_review_audit(
            lab_key,
            "LAB_EXEC",
            duration=None,
            status=exec_summary.get("status", "unknown"),
            step_results=exec_summary.get("step_results", []),
            stderr=exec_summary.get("stderr", ""),
        )
    if verdict == "APPROVE":
        append_lab_review_audit(
            lab_key,
            "LAB_DONE",
            reviewer=review_model,
            module=resolution.module_key,
        )

    return {
        "lab_key": lab_key,
        "verdict": verdict,
        "severity": severity,
        "module": resolution.module_key,
        "warnings": warnings,
        "errors": errors,
        "checks": checks,
        "feedback": feedback,
        "audit_path": str(lab_audit_path_for_key(lab_key)),
    }


def _print_review_result(result: dict) -> None:
    print(f"{result['lab_key']}: {result['verdict']} ({result['severity']})")
    if result.get("module"):
        print(f"  module: {result['module']}")
    for warning in result.get("warnings", []):
        print(f"  WARNING: {warning}")
    for error in result.get("errors", []):
        print(f"  ERROR: {error}")
    passed = [check["id"] for check in result["checks"] if check.get("passed")]
    failed = [check["id"] for check in result["checks"] if not check.get("passed") and not check.get("not_run")]
    skipped = [check["id"] for check in result["checks"] if check.get("not_run")]
    print(f"  passed: {' '.join(passed) if passed else '-'}")
    if failed:
        print(f"  failed: {' '.join(failed)}")
    if skipped:
        print(f"  not run: {' '.join(skipped)}")
    print(f"  audit: {result['audit_path']}")


def cmd_status(_args) -> int:
    labs = discover_labs()
    state = load_lab_state()
    print(f"Labs discovered: {len(labs)}")
    phase_counts: dict[str, int] = {}
    for lab_key in labs:
        phase = state.get("labs", {}).get(lab_key, {}).get("phase", "pending")
        phase_counts[phase] = phase_counts.get(phase, 0) + 1
    for phase in ("pending", "review", "check", "done"):
        print(f"  {phase}: {phase_counts.get(phase, 0)}")
    for lab_key in sorted(labs):
        lab_state = state.get("labs", {}).get(lab_key, {})
        print(
            f"- {lab_key}: phase={lab_state.get('phase', 'pending')}"
            f" severity={lab_state.get('severity', '-')}"
            f" module={lab_state.get('module', '-')}"
        )
    return 0


def cmd_review(args) -> int:
    labs = discover_labs()
    lab_dir = labs.get(args.lab_key)
    if lab_dir is None:
        print(f"Lab not found: {args.lab_key}", file=sys.stderr)
        return 1

    docker_status = None
    if args.run_exec:
        docker_status = check_docker_daemon()
        if not docker_status[0] and os.environ.get("CI", "").lower() == "true":
            print(f"ERROR: EXEC tier required in CI but Docker unavailable: {docker_status[1]}", file=sys.stderr)
            return 1

    result = review_lab(
        lab_dir,
        run_exec=args.run_exec,
        require_lab_meta=args.require_lab_meta,
        review_model=args.review_model,
        docker_status=docker_status,
    )
    _print_review_result(result)
    return 1 if result["errors"] else 0


def cmd_e2e(args) -> int:
    all_labs = discover_labs()
    selected = all_labs
    if args.tracks:
        selected = {
            key: path for key, path in all_labs.items()
            if any(key == track or key.startswith(f"{track}-") for track in args.tracks)
        }
    docker_status = None
    if args.run_exec:
        docker_status = check_docker_daemon()
        if not docker_status[0] and os.environ.get("CI", "").lower() == "true":
            print(f"ERROR: EXEC tier required in CI but Docker unavailable: {docker_status[1]}", file=sys.stderr)
            return 1

    exit_code = 0
    state = load_lab_state()
    for lab_key, lab_dir in selected.items():
        try:
            result = review_lab(
                lab_dir,
                run_exec=args.run_exec,
                require_lab_meta=args.require_lab_meta,
                review_model=args.review_model,
                state=state,
                docker_status=docker_status,
            )
            _print_review_result(result)
            if result["errors"]:
                exit_code = 1
        except Exception as exc:
            exit_code = 1
            print(f"{lab_key}: ERROR {exc}", file=sys.stderr)
    return exit_code


def cmd_reset_stuck(_args) -> int:
    state = load_lab_state()
    reset = 0
    for lab_key, lab_state in sorted(state.get("labs", {}).items()):
        if lab_state.get("phase") not in ("review", "check"):
            continue
        cleared = [str(item) for item in lab_state.get("errors", [])]
        lab_state["phase"] = "pending"
        lab_state["errors"] = []
        lab_state["checks_failed"] = []
        append_lab_review_audit(
            lab_key,
            "LAB_RESET",
            new_phase="pending",
            cleared_errors=cleared,
        )
        reset += 1
        print(f"reset {lab_key}")
    if reset:
        save_lab_state(state)
    else:
        print("No stuck labs found.")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Review KubeDojo labs")
    parser.add_argument("--review-model", default=MODELS["review"])
    subparsers = parser.add_subparsers(dest="command", required=True)

    sp = subparsers.add_parser("status", help="Show lab status")
    sp.set_defaults(func=cmd_status)

    rp = subparsers.add_parser("review", help="Review one lab")
    rp.add_argument("lab_key")
    rp.add_argument("--static", action="store_false", dest="run_exec", default=False)
    rp.add_argument("--exec", action="store_true", dest="run_exec")
    rp.add_argument("--require-lab-meta", action="store_true")
    rp.set_defaults(func=cmd_review)

    ep = subparsers.add_parser("e2e", help="Review all or selected labs")
    ep.add_argument("tracks", nargs="*")
    ep.add_argument("--static", action="store_false", dest="run_exec", default=False)
    ep.add_argument("--exec", action="store_true", dest="run_exec")
    ep.add_argument("--require-lab-meta", action="store_true")
    ep.set_defaults(func=cmd_e2e)

    rsp = subparsers.add_parser("reset-stuck", help="Reset labs stuck mid-run")
    rsp.set_defaults(func=cmd_reset_stuck)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
