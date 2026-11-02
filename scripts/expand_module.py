#!/usr/bin/env python3
"""Stage 2 module expansion for pipeline v4."""

from __future__ import annotations

import argparse
import difflib
import json
import sys
from dataclasses import asdict, dataclass
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
SCRIPTS_DIR = REPO_ROOT / "scripts"
for candidate in (REPO_ROOT, SCRIPTS_DIR):
    candidate_str = str(candidate)
    if candidate_str not in sys.path:
        sys.path.insert(0, candidate_str)

import module_sections  # noqa: E402
import rubric_gaps  # noqa: E402
from dispatch import dispatch_agy, dispatch_codex_patch  # noqa: E402

DOCS_ROOT = REPO_ROOT / "src" / "content" / "docs"
PROVENANCE_PREFIX = "<!-- v4:generated"
PROVENANCE_SUFFIX = "<!-- /v4:generated -->"
_THIN_CLEAR_LOC = 220
_OUTPUT_ONLY_CONTRACT = (
    "Return only the markdown fragment requested. "
    "Do not describe your plan. "
    "Do not say 'I will', 'I have', or similar process narration. "
    "Do not inspect other files, run validation, or mention tests. "
    "Do not wrap the whole answer in code fences unless the content itself includes a code block."
)

_SKIP_REASONS = {
    "no_diagram": "skipped: diagram gap requires human judgment",
    "no_citations": "handled by Stage 4 (citation_v3), not expand stage",
}


@dataclass
class ExpandResult:
    module_key: str
    gaps_processed: list[str]
    gaps_filled: list[str]
    gaps_failed: list[tuple[str, str]]
    loc_before: int
    loc_after: int
    diff: str
    provenance_blocks_added: int


@dataclass
class HandlerResult:
    ok: bool
    doc: module_sections.ModuleDocument
    text: str
    reason: str | None = None
    provenance_blocks_added: int = 0
    llm_calls: int = 0


def _module_path(module_key: str) -> Path:
    normalized = module_key[:-3] if module_key.endswith(".md") else module_key
    return DOCS_ROOT / f"{normalized}.md"


def _count_loc(text: str) -> int:
    return len(text.splitlines())


def _log(message: str) -> None:
    print(message, file=sys.stderr)


def _module_text(doc: module_sections.ModuleDocument) -> str:
    return module_sections.assemble_module(doc)


def _strip_code_fence(text: str) -> str:
    stripped = text.strip()
    if not stripped.startswith("```"):
        return text

    lines = stripped.splitlines()
    if len(lines) >= 2 and lines[0].startswith("```") and lines[-1].startswith("```"):
        return "\n".join(lines[1:-1]).strip()
    return text


def _strip_heading_prefix(text: str, heading: str) -> str:
    lines = text.splitlines()
    while lines and not lines[0].strip():
        lines.pop(0)
    if not lines:
        return ""

    first = lines[0].strip()
    heading_lower = heading.strip().lower()
    if first.lstrip("#").strip().lower() == heading_lower:
        lines.pop(0)
    elif first.lower() == heading_lower:
        lines.pop(0)
    return "\n".join(lines).strip()


def _normalize_generated_body(raw_output: str, heading: str) -> str:
    text = _strip_code_fence(raw_output)
    text = _strip_heading_prefix(text, heading)
    text = text.strip()
    if not text:
        return "\n\n"
    return f"\n\n{text}\n"


def _subsequence_index(old_lines: list[str], new_lines: list[str]) -> tuple[bool, str]:
    new_cursor = 0
    for old_line in old_lines:
        found = False
        while new_cursor < len(new_lines):
            if new_lines[new_cursor] == old_line:
                found = True
                new_cursor += 1
                break
            new_cursor += 1
        if not found:
            preview = old_line.strip() or "<blank>"
            return False, f"original line missing after expansion: {preview}"
    return True, ""


def _is_generated_new_section(section: module_sections.Section) -> bool:
    if PROVENANCE_PREFIX in section.body:
        return True
    return section.heading == "Practitioner Notes"


def _diff_lint_additive_only(old_text: str, new_text: str) -> tuple[bool, str]:
    """Check that expansion preserved existing content and only added material."""
    if old_text == new_text:
        return True, "no changes"

    old_doc = module_sections.parse_module(old_text)
    new_doc = module_sections.parse_module(new_text)
    new_index = 0

    for old_section in old_doc.sections:
        matched_index: int | None = None
        while new_index < len(new_doc.sections):
            candidate = new_doc.sections[new_index]
            if candidate.heading == old_section.heading and candidate.level == old_section.level:
                matched_index = new_index
                break
            if not _is_generated_new_section(candidate) and candidate.slot not in module_sections._CANONICAL_SLOT_ORDER:
                return False, f"unexpected inserted section before {old_section.heading}: {candidate.heading}"
            new_index += 1

        if matched_index is None:
            return False, f"missing original section after expansion: {old_section.heading}"

        candidate = new_doc.sections[matched_index]
        ok, reason = _subsequence_index(
            old_section.body.splitlines(),
            candidate.body.splitlines(),
        )
        if not ok:
            return False, f"{old_section.heading}: {reason}"
        new_index = matched_index + 1

    for candidate in new_doc.sections[new_index:]:
        if _is_generated_new_section(candidate):
            continue
        if candidate.slot in module_sections._CANONICAL_SLOT_ORDER:
            continue
        return False, f"unexpected trailing section after expansion: {candidate.heading}"

    return True, "additive-only"


def _wrap_full_section(section_text: str, gap_type: str, model: str, turn: int) -> str:
    wrapped = section_text
    if not wrapped.endswith("\n"):
        wrapped += "\n"
    return (
        f"<!-- v4:generated type={gap_type} model={model} turn={turn} -->\n"
        f"{wrapped}\n"
        f"{PROVENANCE_SUFFIX}\n"
    )


def _wrap_inline_block(content: str, gap_type: str, model: str, turn: int) -> str:
    stripped = content.strip("\n")
    if not stripped:
        return ""
    return (
        f"\n<!-- v4:generated type={gap_type} model={model} turn={turn} -->\n\n"
        f"{stripped}\n\n"
        f"{PROVENANCE_SUFFIX}\n"
    )


def _replace_once(text: str, needle: str, replacement: str) -> str:
    if needle not in text:
        raise ValueError("could not locate generated section in assembled module")
    return text.replace(needle, replacement, 1)


def _inject_generated_section(
    doc: module_sections.ModuleDocument,
    *,
    slot: str,
    heading: str,
    generated_body: str,
    gap_type: str,
    model: str,
    turn: int,
) -> HandlerResult:
    old_text = _module_text(doc)
    try:
        inserted = module_sections.insert_section(doc, slot, heading, generated_body)
    except ValueError as exc:
        return HandlerResult(False, doc, old_text, reason=str(exc))
    section_text = f"## {heading}\n{generated_body}"
    candidate_text = _replace_once(
        _module_text(inserted),
        section_text,
        _wrap_full_section(section_text, gap_type, model, turn),
    )
    ok, reason = _diff_lint_additive_only(old_text, candidate_text)
    if not ok:
        return HandlerResult(False, doc, old_text, reason=reason)
    updated_doc = module_sections.parse_module(candidate_text)
    return HandlerResult(True, updated_doc, candidate_text, provenance_blocks_added=1, llm_calls=1)


def _append_generated_to_section(
    doc: module_sections.ModuleDocument,
    section_heading: str,
    generated_body: str,
    *,
    gap_type: str,
    model: str,
    turn: int,
) -> HandlerResult:
    old_text = _module_text(doc)
    updated = module_sections.parse_module(old_text)
    target = next((section for section in updated.sections if section.heading == section_heading), None)
    if target is None:
        return HandlerResult(False, doc, old_text, reason=f"section not found: {section_heading}")

    target.body = target.body.rstrip() + _wrap_inline_block(generated_body, gap_type, model, turn)
    if not target.body.endswith("\n"):
        target.body += "\n"
    candidate_text = _module_text(updated)
    ok, reason = _diff_lint_additive_only(old_text, candidate_text)
    if not ok:
        return HandlerResult(False, doc, old_text, reason=reason)
    return HandlerResult(True, updated, candidate_text, provenance_blocks_added=1, llm_calls=1)


def _insert_practitioner_notes(
    doc: module_sections.ModuleDocument,
    generated_body: str,
    *,
    turn: int,
    model: str = "gemini",
) -> HandlerResult:
    old_text = _module_text(doc)
    updated = module_sections.parse_module(old_text)
    insert_at = next(
        (
            idx
            for idx, section in enumerate(updated.sections)
            if section.slot in {"did_you_know", "common_mistakes", "quiz", "hands_on", "next_module"}
        ),
        len(updated.sections),
    )
    body = _wrap_inline_block(generated_body, "thin", model, turn)
    if not body.endswith("\n"):
        body += "\n"
    section = module_sections.Section(
        slot="core_subsection",
        heading="Practitioner Notes",
        body=body,
        level=2,
    )
    section._heading_line_raw = "## Practitioner Notes\n"
    updated.sections.insert(insert_at, section)
    candidate_text = _module_text(updated)
    ok, reason = _diff_lint_additive_only(old_text, candidate_text)
    if not ok:
        return HandlerResult(False, doc, old_text, reason=reason)
    return HandlerResult(True, updated, candidate_text, provenance_blocks_added=1, llm_calls=1)


def _dispatch_codex_section(prompt: str) -> tuple[bool, str]:
    return dispatch_codex_patch(prompt, timeout=1200)


def _dispatch_gemini_section(prompt: str) -> tuple[bool, str]:
    return dispatch_agy(prompt, timeout=900)


def handler_quiz(doc: module_sections.ModuleDocument, module_key: str) -> HandlerResult:
    existing_quiz = module_sections.find_section(doc, "quiz")
    if existing_quiz is not None:
        return HandlerResult(True, doc, _module_text(doc))

    prompt = (
        "Write scenario-based quiz questions that test each learning outcome of the following KubeDojo module (no filler questions).\n"
        "Each question must be:\n"
        "- scenario-based (not recall; something like 'Your team deployed X...')\n"
        "- answerable using the module's content\n"
        "- formatted as: **Q1.** [question]\\n\\n<details>\\n<summary>Answer</summary>\\n"
        "[answer + explanation]\\n</details>\n"
        "- concrete enough that this clearly reads as a real quiz section\n"
        "The section heading will be inserted automatically as `## Quiz`, so do not include any heading.\n"
        f"{_OUTPUT_ONLY_CONTRACT}\n\n"
        f"Module key: {module_key}\n\n"
        f"{_module_text(doc)}"
    )
    ok, output = _dispatch_codex_section(prompt)
    if not ok:
        return HandlerResult(False, doc, _module_text(doc), reason=f"codex quiz generation failed: {output or 'no output'}")
    return _inject_generated_section(
        doc,
        slot="quiz",
        heading="Quiz",
        generated_body=_normalize_generated_body(output, "Quiz"),
        gap_type="no_quiz",
        model="codex",
        turn=1,
    )


def handler_mistakes(doc: module_sections.ModuleDocument, module_key: str) -> HandlerResult:
    prompt = (
        "Write a 'Common Mistakes' markdown table for the following module.\n"
        "One row per mistake learners actually make; no filler rows. Columns: Mistake | Why it's wrong | Fix.\n"
        "Do not include a heading; the section heading is inserted automatically.\n"
        f"{_OUTPUT_ONLY_CONTRACT}\n\n"
        f"Module key: {module_key}\n\n"
        f"{_module_text(doc)}"
    )
    ok, output = _dispatch_codex_section(prompt)
    if not ok:
        return HandlerResult(False, doc, _module_text(doc), reason=f"codex mistakes generation failed: {output or 'no output'}")
    return _inject_generated_section(
        doc,
        slot="common_mistakes",
        heading="Common Mistakes",
        generated_body=_normalize_generated_body(output, "Common Mistakes"),
        gap_type="no_mistakes",
        model="codex",
        turn=1,
    )


def handler_exercise(doc: module_sections.ModuleDocument, module_key: str) -> HandlerResult:
    prompt = (
        "Write a multi-step Hands-On Exercise for the following module.\n"
        "Start with a goal. Then checklist of steps: - [ ] step.\n"
        "Include verification commands. End with 'Success criteria:' bullet list.\n"
        "Do not include a heading; the section heading is inserted automatically.\n"
        f"{_OUTPUT_ONLY_CONTRACT}\n\n"
        f"Module key: {module_key}\n\n"
        f"{_module_text(doc)}"
    )
    ok, output = _dispatch_codex_section(prompt)
    if not ok:
        return HandlerResult(False, doc, _module_text(doc), reason=f"codex exercise generation failed: {output or 'no output'}")
    return _inject_generated_section(
        doc,
        slot="hands_on",
        heading="Hands-On Exercise",
        generated_body=_normalize_generated_body(output, "Hands-On Exercise"),
        gap_type="no_exercise",
        model="codex",
        turn=1,
    )


def handler_outcomes(doc: module_sections.ModuleDocument, module_key: str) -> HandlerResult:
    prompt = (
        "Write 3-5 Bloom-L3+ Learning Outcomes bullets for the following KubeDojo module.\n"
        "Keep them concrete, observable, and specific to the module.\n"
        "Do not include a heading; the section heading is inserted automatically.\n"
        f"{_OUTPUT_ONLY_CONTRACT}\n\n"
        f"Module key: {module_key}\n\n"
        f"{_module_text(doc)}"
    )
    ok, output = _dispatch_codex_section(prompt)
    if not ok:
        return HandlerResult(False, doc, _module_text(doc), reason=f"codex outcomes generation failed: {output or 'no output'}")
    return _inject_generated_section(
        doc,
        slot="learning_outcomes",
        heading="Learning Outcomes",
        generated_body=_normalize_generated_body(output, "Learning Outcomes"),
        gap_type="no_outcomes",
        model="codex",
        turn=1,
    )


def _thin_prompt(
    module_key: str,
    section: module_sections.Section,
    *,
    current_loc: int,
    clear_loc: int,
    target_loc: int,
) -> str:
    return (
        "Expand the following section of a KubeDojo module. Keep the existing prose intact. "
        "Add substantial new material that goes deeper on the technical content. "
        "Do not repeat what the section already says.\n"
        f"The module currently has about {current_loc} lines. "
        f"The scorer stops flagging `thin` once the module reaches at least {clear_loc} lines. "
        f"The long-form curriculum target is {target_loc} lines.\n"
        "In this single reply, add roughly 18-35 nonblank lines of substantive markdown by using:\n"
        "- 2-4 dense paragraphs with practitioner-depth detail\n"
        "- one concrete example, command block, or configuration fragment when helpful\n"
        "- explicit 'why this matters in practice' commentary\n"
        "Return markdown to append INSIDE the existing section only. Do not include a heading.\n"
        f"{_OUTPUT_ONLY_CONTRACT}\n\n"
        f"Module key: {module_key}\n"
        f"Section heading: {section.heading}\n\n"
        f"{section.body}"
    )


def _practitioner_notes_prompt(
    module_key: str,
    doc: module_sections.ModuleDocument,
    *,
    current_loc: int,
    clear_loc: int,
    target_loc: int,
) -> str:
    return (
        "Write a new H2 section titled 'Practitioner Notes' for the following KubeDojo module.\n"
        "Add 3-5 short paragraphs or bullet-backed notes that deepen the operational tradeoffs, "
        "failure modes, and real-world usage. Keep it additive and technically concrete.\n"
        f"The module currently has about {current_loc} lines. "
        f"The scorer stops flagging `thin` once the module reaches at least {clear_loc} lines. "
        f"The long-form curriculum target is {target_loc} lines.\n"
        "Aim for roughly 20-35 nonblank lines of substantive content so this pass materially changes the score.\n"
        "Return only the body for the new section; do not include the `## Practitioner Notes` heading.\n"
        f"{_OUTPUT_ONLY_CONTRACT}\n\n"
        f"Module key: {module_key}\n\n"
        f"{_module_text(doc)}"
    )


def handler_thin(
    doc: module_sections.ModuleDocument,
    module_key: str,
    target_loc: int = 600,
    max_thin_passes: int = 5,
) -> HandlerResult:
    current = module_sections.parse_module(_module_text(doc))
    turns_used = 0
    provenance_blocks = 0
    clear_loc = min(target_loc, _THIN_CLEAR_LOC)

    while _count_loc(_module_text(current)) < clear_loc and turns_used < max_thin_passes:
        progressed = False
        core_sections = [section for section in current.sections if section.slot == "core_subsection"]
        if not core_sections:
            break

        for section in core_sections:
            current_loc = _count_loc(_module_text(current))
            if current_loc >= clear_loc or turns_used >= max_thin_passes:
                break

            ok, output = _dispatch_gemini_section(
                _thin_prompt(
                    module_key,
                    section,
                    current_loc=current_loc,
                    clear_loc=clear_loc,
                    target_loc=target_loc,
                )
            )
            turns_used += 1
            if not ok:
                return HandlerResult(
                    False,
                    current,
                    _module_text(current),
                    reason=f"thin: gemini generation failed for '{section.heading}': {output or 'no output'}",
                    provenance_blocks_added=provenance_blocks,
                    llm_calls=turns_used,
                )

            append_result = _append_generated_to_section(
                current,
                section.heading,
                _normalize_generated_body(output, section.heading),
                gap_type="thin",
                model="gemini",
                turn=turns_used,
            )
            if not append_result.ok:
                return HandlerResult(
                    False,
                    current,
                    _module_text(current),
                    reason=append_result.reason,
                    provenance_blocks_added=provenance_blocks,
                    llm_calls=turns_used,
                )

            current = append_result.doc
            provenance_blocks += append_result.provenance_blocks_added
            progressed = True

        if not progressed:
            break

    if _count_loc(_module_text(current)) < clear_loc and turns_used < max_thin_passes:
        ok, output = _dispatch_gemini_section(
            _practitioner_notes_prompt(
                module_key,
                current,
                current_loc=_count_loc(_module_text(current)),
                clear_loc=clear_loc,
                target_loc=target_loc,
            )
        )
        turns_used += 1
        if not ok:
            return HandlerResult(
                False,
                current,
                _module_text(current),
                reason=f"thin: practitioner notes generation failed: {output or 'no output'}",
                provenance_blocks_added=provenance_blocks,
                llm_calls=turns_used,
            )

        insert_result = _insert_practitioner_notes(
            current,
            _normalize_generated_body(output, "Practitioner Notes"),
            turn=turns_used,
        )
        if not insert_result.ok:
            return HandlerResult(
                False,
                current,
                _module_text(current),
                reason=insert_result.reason,
                provenance_blocks_added=provenance_blocks,
                llm_calls=turns_used,
            )
        current = insert_result.doc
        provenance_blocks += insert_result.provenance_blocks_added

    if _count_loc(_module_text(current)) < clear_loc:
        return HandlerResult(
            False,
            current,
            _module_text(current),
            reason=(
                f"thin: max_passes reached, actual_loc={_count_loc(_module_text(current))} "
                f"target={clear_loc}"
            ),
            provenance_blocks_added=provenance_blocks,
            llm_calls=turns_used,
        )

    return HandlerResult(
        True,
        current,
        _module_text(current),
        provenance_blocks_added=provenance_blocks,
        llm_calls=turns_used,
    )


_HANDLERS = {
    "no_quiz": handler_quiz,
    "no_mistakes": handler_mistakes,
    "no_exercise": handler_exercise,
    "thin": handler_thin,
    "no_outcomes": handler_outcomes,
}


def can_expand(gaps: list[str]) -> bool:
    """True if at least one gap is handled by Stage 2 expansion.

    False means the pipeline should skip Stage 2 and proceed to Stage 4 —
    e.g. only no_citations or no_diagram gaps remain. Used by pipeline_v4
    to avoid burning retry budget on guaranteed-no-op expansions."""
    return any(gap in _HANDLERS for gap in gaps)


def expand_module(
    module_key: str,
    gaps: list[str],
    target_loc: int = 600,
    max_thin_passes: int = 5,
    *,
    dry_run: bool = False,
) -> ExpandResult:
    """Run Stage 2 on a single module."""
    path = _module_path(module_key)
    old_text = path.read_text(encoding="utf-8")
    current_doc = module_sections.parse_module(old_text)
    current_text = _module_text(current_doc)
    gaps_processed: list[str] = []
    gaps_filled: list[str] = []
    gaps_failed: list[tuple[str, str]] = []
    provenance_blocks_added = 0

    for gap in gaps:
        gaps_processed.append(gap)
        if gap in _SKIP_REASONS:
            gaps_failed.append((gap, _SKIP_REASONS[gap]))
            _log(f"{module_key}: {gap} skipped: {_SKIP_REASONS[gap]}")
            continue

        handler = _HANDLERS.get(gap)
        if handler is None:
            gaps_failed.append((gap, "unsupported gap type"))
            _log(f"{module_key}: {gap} failed: unsupported gap type")
            continue

        _log(f"{module_key}: handling {gap}")
        if gap == "thin":
            result = handler(current_doc, module_key, target_loc=target_loc, max_thin_passes=max_thin_passes)
        else:
            result = handler(current_doc, module_key)

        if not result.ok:
            gaps_failed.append((gap, result.reason or "unknown failure"))
            _log(f"{module_key}: {gap} failed: {result.reason or 'unknown failure'}")
            continue

        current_doc = result.doc
        current_text = result.text
        gaps_filled.append(gap)
        provenance_blocks_added += result.provenance_blocks_added
        _log(f"{module_key}: {gap} filled")

    if not dry_run and current_text != old_text:
        path.write_text(current_text, encoding="utf-8")

    diff = "".join(
        difflib.unified_diff(
            old_text.splitlines(keepends=True),
            current_text.splitlines(keepends=True),
            fromfile=str(path),
            tofile=str(path),
        )
    )
    return ExpandResult(
        module_key=module_key[:-3] if module_key.endswith(".md") else module_key,
        gaps_processed=gaps_processed,
        gaps_filled=gaps_filled,
        gaps_failed=gaps_failed,
        loc_before=_count_loc(old_text),
        loc_after=_count_loc(current_text),
        diff=diff,
        provenance_blocks_added=provenance_blocks_added,
    )


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("module_key", help="Module key without .md suffix.")
    parser.add_argument("--gap", action="append", default=[], help="Gap to address; repeat for ordered gaps.")
    parser.add_argument("--dry-run", action="store_true", help="Generate and diff-lint without writing to disk.")
    parser.add_argument("--target-loc", type=int, default=600, help="Target line count for thin modules.")
    parser.add_argument(
        "--max-thin-passes",
        type=int,
        default=5,
        help="Maximum total LLM calls allowed for the thin-gap handler.",
    )
    return parser


def _resolve_gap_list(module_key: str, explicit_gaps: list[str]) -> list[str]:
    if explicit_gaps:
        return explicit_gaps
    item = rubric_gaps.gaps_for_module(module_key)
    if item is None:
        raise ValueError(f"module not found in rubric gaps: {module_key}")
    return list(item.get("gaps", []))


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    try:
        gaps = _resolve_gap_list(args.module_key, args.gap)
        result = expand_module(
            args.module_key,
            gaps,
            target_loc=args.target_loc,
            max_thin_passes=args.max_thin_passes,
            dry_run=args.dry_run,
        )
    except (FileNotFoundError, rubric_gaps.QualityScoresError, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1

    print(json.dumps(asdict(result), ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
