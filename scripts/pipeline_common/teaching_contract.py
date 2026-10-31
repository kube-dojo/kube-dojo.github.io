"""Validate recorded teaching-review evidence, not source truth or acceptance."""

from __future__ import annotations

DIMENSIONS = {f"D{n}" for n in range(1, 9)}


def _text(value: object) -> bool:
    return isinstance(value, str) and bool(value.strip())


def validate_teaching_review(payload: object, module_text: object, coverage_plan: object) -> list[str]:
    """Return errors for an incomplete passing review, without I/O or state changes.

    A plan is author research input; matching a quote does not verify its meaning,
    source authority, actual execution, independent identity, or page acceptance.
    """
    errors: list[str] = []
    if not _text(module_text):
        errors.append("module_text must be nonempty")
    if not isinstance(payload, dict):
        return [*errors, "payload must be an object"]
    if not isinstance(coverage_plan, dict):
        return [*errors, "coverage_plan must be an object"]

    def quote(value: object, location: str) -> None:
        if not _text(value) or not isinstance(module_text, str) or value not in module_text:
            errors.append(f"{location} must quote the candidate text")

    if coverage_plan.get("module_kind") != "module":
        errors.append("coverage_plan.module_kind must be module")
    expected: dict[str, list[str]] = {}
    for key in ("outcomes", "essential_topics"):
        value = coverage_plan.get(key)
        if (not isinstance(value, list) or not value or any(not _text(item) for item in value)
                or len({item.strip() for item in value if isinstance(item, str)}) != len(value)):
            errors.append(f"coverage_plan.{key} must be a nonempty list of unique strings")
            expected[key] = []
        else:
            expected[key] = value
    sources = coverage_plan.get("source_basis")
    if (not isinstance(sources, list) or not sources or any(
        not isinstance(source, dict) or any(not _text(source.get(key)) for key in ("uri", "locator", "excerpt"))
        for source in sources
    )):
        errors.append("coverage_plan.source_basis must contain uri, locator and excerpt")

    dimensions = payload.get("dimensions")
    if (not isinstance(dimensions, dict) or set(dimensions) != DIMENSIONS
            or any(type(score) is not int or not 1 <= score <= 5 for score in dimensions.values())):
        errors.append("dimensions must contain exactly D1..D8 integer scores from 1 to 5")
    elif min(dimensions.values()) < 4 or sum(dimensions.values()) < 33:
        errors.append("dimensions require every score >= 4 and total >= 33")
    evidence = payload.get("dimension_evidence")
    if not isinstance(evidence, dict) or set(evidence) != DIMENSIONS:
        errors.append("dimension_evidence must contain exactly D1..D8")
    else:
        for key, value in evidence.items():
            quote(value, f"dimension_evidence.{key}")
    if payload.get("must_fix") != [] or not isinstance(payload.get("must_fix"), list):
        errors.append("must_fix must be an empty list")

    coverage = payload.get("coverage")
    if not isinstance(coverage, dict):
        errors.append("coverage must be an object")
        coverage = {}
    for rows_key, plan_key, id_key, quote_keys in (
        ("outcomes", "outcomes", "outcome", ("teaching", "practice", "assessment")),
        ("topics", "essential_topics", "topic", ("teaching",)),
    ):
        rows = coverage.get(rows_key)
        if not isinstance(rows, list):
            errors.append(f"coverage.{rows_key} must be a list")
            continue
        names = [row.get(id_key) if isinstance(row, dict) else None for row in rows]
        if (any(not _text(name) for name in names) or len(names) != len({name for name in names if _text(name)})
                or {name for name in names if _text(name)} != set(expected[plan_key])):
            errors.append(f"coverage.{rows_key} must cover each planned item exactly once")
        for i, row in enumerate(rows):
            if not isinstance(row, dict):
                errors.append(f"coverage.{rows_key}[{i}] must be an object")
                continue
            for key in quote_keys:
                quote(row.get(key), f"coverage.{rows_key}[{i}].{key}")

    scope = payload.get("scope_assessment")
    if (not isinstance(scope, dict) or scope.get("basis_checked") is not True
            or not isinstance(scope.get("unjustified_omissions"), list) or scope["unjustified_omissions"]
            or not _text(scope.get("rationale"))):
        errors.append("scope_assessment requires basis_checked, no unjustified omissions and a rationale")
    return errors
