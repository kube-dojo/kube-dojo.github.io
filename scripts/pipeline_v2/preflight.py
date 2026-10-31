from __future__ import annotations

import re
import subprocess
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

import yaml

from scripts import v1_pipeline
from scripts.checks.structural import check_k8s_versions, check_leaked_secrets

REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_LINK_CACHE_PATH = REPO_ROOT / ".pipeline" / "link-cache.json"
YAMLLINT_RELAXED_CONFIG = """\
extends: default
rules:
  document-start: disable
  line-length: disable
  indentation:
    spaces: 2
    indent-sequences: consistent
  truthy: disable
"""


@dataclass(frozen=True)
class PreflightFinding:
    id: str
    passed: bool
    severity: str
    evidence: str
    fix_hint: str
    line_range: tuple[int, int] | None = None

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        if self.line_range is not None:
            payload["line_range"] = list(self.line_range)
        return payload


@dataclass(frozen=True)
class PreflightResult:
    module_path: Path
    findings: list[PreflightFinding]

    @property
    def passed(self) -> bool:
        return not any(
            not finding.passed and finding.severity == "ERROR"
            for finding in self.findings
        )

    def failed_findings(self, *, severity: str | None = None) -> list[PreflightFinding]:
        return [
            finding
            for finding in self.findings
            if not finding.passed and (severity is None or finding.severity == severity)
        ]

    def to_dict(self) -> dict[str, Any]:
        return {
            "module_path": str(self.module_path),
            "passed": self.passed,
            "findings": [finding.to_dict() for finding in self.findings],
        }


def run_preflight(
    module_path: Path | str,
    *,
    repo_root: Path | None = None,
    link_cache_path: Path = DEFAULT_LINK_CACHE_PATH,
    content: str | None = None,
) -> PreflightResult:
    module = Path(module_path)
    root = repo_root or REPO_ROOT
    snapshot = content
    if content is None:
        content = module.read_text(encoding="utf-8")

    findings: list[PreflightFinding] = []
    findings.extend(_run_markdownlint(module, cwd=root, content=snapshot))
    findings.extend(_run_yamllint(content, cwd=root))
    findings.extend(_validate_frontmatter_schema(content, module))
    findings.extend(_structural_regex_findings(content))
    findings.extend(_run_link_check(content, link_cache_path=link_cache_path))
    return PreflightResult(module_path=module, findings=findings)


def _run_markdownlint(module_path: Path, *, cwd: Path, content: str | None = None) -> list[PreflightFinding]:
    try:
        result = subprocess.run(
            ["npx", "markdownlint-cli2", str(module_path) if content is None else "-"],
            input=content,
            capture_output=True,
            text=True,
            cwd=cwd,
            check=False,
        )
    except FileNotFoundError as exc:
        return [
            PreflightFinding(
                id="MARKDOWNLINT",
                passed=False,
                severity="ERROR",
                evidence=str(exc),
                fix_hint="Install Node.js and markdownlint-cli2 or make npx available.",
            )
        ]

    if result.returncode == 0:
        return [
            PreflightFinding(
                id="MARKDOWNLINT",
                passed=True,
                severity="INFO",
                evidence="markdownlint passed",
                fix_hint="",
            )
        ]

    output = "\n".join(part for part in (result.stdout, result.stderr) if part).strip() or "markdownlint failed"
    lines = [line for line in output.splitlines() if line.strip()]
    detail_lines = [
        line for line in lines
        if not line.startswith("markdownlint-cli2 ")
        and not line.startswith("Finding:")
        and not line.startswith("Linting:")
        and not line.startswith("Summary:")
    ]
    lines = detail_lines or lines or [output]
    return [
        PreflightFinding(
            id="MARKDOWNLINT",
            passed=False,
            severity="ERROR",
            evidence=line.strip(),
            fix_hint="Fix Markdown formatting issues reported by markdownlint-cli2.",
            line_range=_extract_line_range(line),
        )
        for line in lines
    ]


def _run_yamllint(content: str, *, cwd: Path) -> list[PreflightFinding]:
    yaml_blocks = re.findall(r"```yaml\s*\n([\s\S]*?)```", content, re.IGNORECASE)
    if not yaml_blocks:
        return [
            PreflightFinding(
                id="YAMLLINT",
                passed=True,
                severity="INFO",
                evidence="no fenced yaml blocks found",
                fix_hint="",
            )
        ]

    payload = "\n---\n".join(block.strip("\n") for block in yaml_blocks if block.strip())
    try:
        result = subprocess.run(
            ["yamllint", "-d", YAMLLINT_RELAXED_CONFIG, "-"],
            input=payload,
            capture_output=True,
            text=True,
            cwd=cwd,
            check=False,
        )
    except FileNotFoundError as exc:
        return [
            PreflightFinding(
                id="YAMLLINT",
                passed=False,
                severity="WARNING",
                evidence=str(exc),
                fix_hint="Install yamllint so YAML snippets can be linted before review.",
            )
        ]

    if result.returncode == 0:
        return [
            PreflightFinding(
                id="YAMLLINT",
                passed=True,
                severity="INFO",
                evidence=f"yamllint passed for {len(yaml_blocks)} yaml block(s)",
                fix_hint="",
            )
        ]

    output = (result.stdout or result.stderr or "yamllint failed").strip()
    lines = [line for line in output.splitlines() if line.strip()] or [output]
    return [
        PreflightFinding(
            id="YAMLLINT",
            passed=False,
            severity="ERROR",
            evidence=line.strip(),
            fix_hint="Fix malformed or badly indented YAML in fenced yaml blocks.",
            line_range=_extract_line_range(line),
        )
        for line in lines
    ]


def _validate_frontmatter_schema(content: str, module_path: Path) -> list[PreflightFinding]:
    findings: list[PreflightFinding] = []
    match = re.match(r"^---\s*\n(.*?)\n---\s*(?:\n|$)", content, re.DOTALL)
    if match is None:
        return [
            PreflightFinding(
                id="FRONTMATTER",
                passed=False,
                severity="ERROR",
                evidence="Missing or malformed frontmatter block at top of file.",
                fix_hint="Add a valid YAML frontmatter block starting at line 1.",
                line_range=(1, 1),
            )
        ]

    fm_text = match.group(1)
    try:
        frontmatter = yaml.safe_load(fm_text) or {}
    except yaml.YAMLError as exc:
        line_no = 1
        if getattr(exc, "problem_mark", None) is not None:
            line_no = int(exc.problem_mark.line) + 2
        return [
            PreflightFinding(
                id="FRONTMATTER",
                passed=False,
                severity="ERROR",
                evidence=f"Invalid YAML frontmatter: {exc}",
                fix_hint="Fix the YAML syntax in the frontmatter block.",
                line_range=(line_no, line_no),
            )
        ]

    title = frontmatter.get("title")
    if not isinstance(title, str) or not title.strip():
        findings.append(
            PreflightFinding(
                id="FRONTMATTER",
                passed=False,
                severity="ERROR",
                evidence="Frontmatter must include a non-empty title field.",
                fix_hint="Set title: to the module's display name.",
                line_range=(1, match.group(0).count("\n") + 1),
            )
        )

    sidebar = frontmatter.get("sidebar")
    order = sidebar.get("order") if isinstance(sidebar, dict) else None
    if not _is_valid_sidebar_order(order):
        findings.append(
            PreflightFinding(
                id="FRONTMATTER",
                passed=False,
                severity="ERROR",
                evidence="Frontmatter sidebar.order must be an integer.",
                fix_hint="Set sidebar.order to the numeric position for this page.",
                line_range=(1, match.group(0).count("\n") + 1),
            )
        )

    if "." in module_path.stem and not _has_non_empty_string(frontmatter.get("slug")):
        findings.append(
            PreflightFinding(
                id="FRONTMATTER",
                passed=False,
                severity="ERROR",
                evidence=f"{module_path.name} contains dots in the filename but has no slug field.",
                fix_hint="Add slug: so the generated route remains stable for dotted filenames.",
                line_range=(1, match.group(0).count("\n") + 1),
            )
        )

    if not findings:
        findings.append(
            PreflightFinding(
                id="FRONTMATTER",
                passed=True,
                severity="INFO",
                evidence="frontmatter schema valid",
                fix_hint="",
            )
        )
    return findings


def _structural_regex_findings(content: str) -> list[PreflightFinding]:
    findings: list[PreflightFinding] = []
    for result in check_leaked_secrets(content):
        findings.append(
            PreflightFinding(
                id=result.check,
                passed=result.passed,
                severity=result.severity,
                evidence=result.message,
                fix_hint="Replace realistic secrets with safe placeholders.",
            )
        )
    for result in check_k8s_versions(content):
        findings.append(
            PreflightFinding(
                id=result.check,
                passed=result.passed,
                severity=result.severity,
                evidence=result.message,
                fix_hint="Update deprecated Kubernetes API versions to currently supported APIs.",
            )
        )
    return findings


def _run_link_check(content: str, *, link_cache_path: Path) -> list[PreflightFinding]:
    raw_urls = re.findall(r"https?://[^\s)>\]\"']+", content)
    urls = sorted({url for url in (_normalize_external_url(item) for item in raw_urls) if url})
    if not urls:
        return [
            PreflightFinding(
                id="LINK_CHECK",
                passed=True,
                severity="INFO",
                evidence="no external links found",
                fix_hint="",
            )
        ]

    statuses = _resolve_link_statuses(urls, link_cache_path=link_cache_path)
    failed = [
        PreflightFinding(
            id="LINK_CHECK",
            passed=False,
            severity="WARNING",
            evidence=f"{url} returned {status if status is not None else 'ERROR'}",
            fix_hint="Check whether the URL is still valid or replace it with a working reference.",
        )
        for url, status in statuses.items()
        if status is None or status >= 400
    ]
    if failed:
        return failed
    return [
        PreflightFinding(
            id="LINK_CHECK",
            passed=True,
            severity="INFO",
            evidence=f"{len(urls)} external link(s) resolved via shared cache",
            fix_hint="",
        )
    ]


def _resolve_link_statuses(
    urls: list[str],
    *,
    link_cache_path: Path,
) -> dict[str, int | None]:
    original = v1_pipeline.LINK_CACHE_FILE
    v1_pipeline.LINK_CACHE_FILE = link_cache_path
    try:
        return v1_pipeline._resolve_url_statuses(urls)
    finally:
        v1_pipeline.LINK_CACHE_FILE = original


def _normalize_external_url(raw_url: str) -> str | None:
    url = raw_url.rstrip("`.,:;!?")
    if not url:
        return None

    match = re.match(r"^https?://([^/]+)", url, re.IGNORECASE)
    if match is None:
        return url

    host = match.group(1).split(":", 1)[0].lower()
    if host in {"localhost", "127.0.0.1", "0.0.0.0"}:
        return None
    if "your_public_ip" in host:
        return None
    return url


def _is_valid_sidebar_order(value: Any) -> bool:
    if isinstance(value, bool):
        return False
    if isinstance(value, int):
        return True
    return isinstance(value, str) and re.fullmatch(r"-?\d+", value.strip()) is not None


def _has_non_empty_string(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip())


def _extract_line_range(text: str) -> tuple[int, int] | None:
    match = re.search(r":(\d+)(?::\d+)?", text)
    if match is None:
        return None
    line_no = int(match.group(1))
    return (line_no, line_no)
