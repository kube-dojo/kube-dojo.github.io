#!/usr/bin/env python3
"""Generate web-grounded knowledge cards for KubeDojo modules."""

from __future__ import annotations

import argparse
import re
import sys
from datetime import UTC, date, datetime, timedelta
from pathlib import Path

import yaml

def _legacy_dispatcher_removed(*_args, **_kwargs):
    raise RuntimeError("legacy dispatcher removed")


def _is_rate_limited(*_args, **_kwargs):
    return False


dispatch_codex = _legacy_dispatcher_removed

REPO_ROOT = Path(__file__).parent.parent
KNOWLEDGE_CARD_DIR = REPO_ROOT / ".pipeline" / "knowledge-cards"

REQUIRED_FRONTMATTER_KEYS = {
    "topic",
    "module_key",
    "generated_by",
    "generated_at",
    "expires",
}


def sanitize_module_key(module_key: str) -> str:
    """Convert a module key into a stable knowledge-card filename."""
    return module_key.replace("/", "__")


def knowledge_card_path(module_key: str) -> Path:
    """Return the cached knowledge-card path for a module key."""
    return KNOWLEDGE_CARD_DIR / f"{sanitize_module_key(module_key)}.md"


def strip_markdown_fences(text: str) -> str:
    """Strip optional ```markdown fences from Codex output."""
    text = text.strip()
    if text.startswith("```markdown"):
        text = text[len("```markdown"):].strip()
    elif text.startswith("```md"):
        text = text[len("```md"):].strip()
    elif text.startswith("```"):
        text = text[3:].strip()
    if text.endswith("```"):
        text = text[:-3].strip()
    return text


def extract_frontmatter(content: str) -> dict:
    """Parse YAML frontmatter from markdown content."""
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


def extract_topic_line(content: str) -> str | None:
    """Extract the scaffolded Topic blockquote, if present."""
    match = re.search(r"^>\s*\*\*Topic\*\*:\s*(.+)$", content, re.MULTILINE)
    if not match:
        return None
    return match.group(1).strip()


def extract_learning_outcomes(content: str) -> str:
    """Extract the Learning Outcomes section as prompt context."""
    match = re.search(
        r"^## Learning Outcomes\s*\n(?P<body>[\s\S]*?)(?=^##\s|\Z)",
        content,
        re.MULTILINE,
    )
    if not match:
        return "(No Learning Outcomes section found.)"
    return match.group("body").strip()


def is_expired(card_content: str, today: datetime | None = None) -> bool:
    """Return True if the card is expired or malformed."""
    data = extract_frontmatter(card_content)
    expires = data.get("expires")
    if isinstance(expires, datetime):
        expires_at = expires.date()
    elif isinstance(expires, date):
        expires_at = expires
    elif isinstance(expires, str):
        try:
            expires_at = datetime.fromisoformat(expires).date()
        except ValueError:
            return True
    else:
        return True
    if not isinstance(expires_at, date):
        return True
    check_date = (today or datetime.now(UTC)).date()
    return expires_at < check_date


def build_prompt(module_key: str, title: str, topic_hint: str,
                 learning_outcomes: str, generated_at: str,
                 expires: str) -> str:
    """Build the Codex prompt for a knowledge card."""
    return f"""You are generating a KubeDojo knowledge card that will be injected into a WRITE prompt before another model drafts course content.

Use CURRENT web research before answering. Prefer authoritative primary sources:
- kubernetes.io docs
- CNCF project pages / announcements
- official project docs
- official GitHub repos / release notes
- official vendor docs only when the topic is vendor-specific

Goal: produce a concise but opinionated grounding card that helps the writer avoid factual drift and stale-cutoff mistakes. The most valuable section is `## Do not`, which should explicitly forbid common hallucinations, deprecated APIs, and outdated project status claims.

Return ONLY markdown. Do not wrap the answer in fences. Follow this exact shape:

```markdown
---
topic: "On-prem FinOps and chargeback with OpenCost, Kubecost, and VPA"
module_key: "on-premises/planning/module-1.5-onprem-finops-chargeback"
generated_by: "codex"
generated_at: "{generated_at}"
expires: "{expires}"
---

## Current status (as of generated_at)
- Bullet points with current, source-grounded facts

## Authoritative sources
- https://example.com/path — short note on what this source confirms

## Do not
- Hard blocks against known bad claims or stale examples
```

Requirements:
- Keep the card roughly 1-3k tokens
- Frontmatter values must use:
  - module_key: "{module_key}"
  - generated_by: "codex"
  - generated_at: "{generated_at}"
  - expires: "{expires}"
- Include at least 3 bullets in `## Current status`
- Include at least 3 sources in `## Authoritative sources`
- Include at least 3 bullets in `## Do not`
- The `topic` should be specific to this module, not generic Kubernetes
- If a fact is uncertain or version-sensitive, phrase it conservatively and push verification into `## Do not`

Module context:
- Module key: {module_key}
- Title: {title}
- Topic hint: {topic_hint}

Learning Outcomes:
{learning_outcomes}
"""


def validate_card(card_content: str, module_key: str) -> None:
    """Validate the returned card shape."""
    data = extract_frontmatter(card_content)
    missing = REQUIRED_FRONTMATTER_KEYS - set(data.keys())
    if missing:
        raise ValueError(f"Knowledge card missing frontmatter keys: {sorted(missing)}")
    if data.get("module_key") != module_key:
        raise ValueError(
            f"Knowledge card module_key mismatch: expected {module_key!r}, "
            f"got {data.get('module_key')!r}"
        )
    if data.get("generated_by") != "codex":
        raise ValueError("Knowledge card generated_by must be 'codex'")
    do_not = re.search(
        r"^## Do not\s*\n(?P<body>[\s\S]*?)(?=^##\s|\Z)",
        card_content,
        re.MULTILINE,
    )
    if not do_not:
        raise ValueError("Knowledge card missing '## Do not' section")
    bullets = re.findall(r"^- ", do_not.group("body"), re.MULTILINE)
    if not bullets:
        raise ValueError("Knowledge card must include at least one '## Do not' bullet")


def generate(module_key: str, *, if_missing: bool = False, force: bool = False,
             model: str = "codex", timeout: int = 900) -> str | None:
    """Generate a knowledge card for a single module key."""
    card_path = knowledge_card_path(module_key)
    if if_missing and not force and card_path.exists():
        existing = card_path.read_text()
        if not is_expired(existing):
            return existing

    from v1_pipeline import find_module_path

    module_path = find_module_path(module_key)
    if module_path is None:
        print(f"  ⚠ Knowledge card skipped — module not found: {module_key}")
        return None

    module_content = module_path.read_text()
    frontmatter = extract_frontmatter(module_content)
    title = str(frontmatter.get("title", module_key)).strip()
    topic_hint = extract_topic_line(module_content) or title
    learning_outcomes = extract_learning_outcomes(module_content)

    today = datetime.now(UTC).date()
    generated_at = today.isoformat()
    expires = (today + timedelta(days=90)).isoformat()
    prompt = build_prompt(
        module_key=module_key,
        title=title,
        topic_hint=topic_hint,
        learning_outcomes=learning_outcomes,
        generated_at=generated_at,
        expires=expires,
    )

    ok, output = dispatch_codex(prompt, model=model, timeout=timeout)
    if not ok:
        reason = "rate-limited" if _is_rate_limited(output) else "unavailable"
        summary = (output or "").strip().splitlines()
        hint = f": {summary[0][:160]}" if summary else ""
        print(f"  ⚠ Knowledge card generation {reason}{hint}")
        return None

    card = strip_markdown_fences(output)
    try:
        validate_card(card, module_key)
    except ValueError as exc:
        print(f"  ⚠ Knowledge card validation failed: {exc}")
        return None

    card_path.parent.mkdir(parents=True, exist_ok=True)
    card_path.write_text(card)
    print(f"  ✓ Knowledge card written: {card_path}")
    return card


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate a knowledge card for one module")
    parser.add_argument("module_key", help="Module key, e.g. on-premises/planning/module-1.5-foo")
    parser.add_argument("--if-missing", action="store_true",
                        help="Only generate when the cached card is missing or expired")
    parser.add_argument("--force", action="store_true",
                        help="Regenerate even if a fresh cached card already exists")
    args = parser.parse_args()

    card = generate(
        args.module_key,
        if_missing=args.if_missing,
        force=args.force,
    )
    if card is None:
        return 1

    sys.stdout.write(card)
    if not card.endswith("\n"):
        sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
