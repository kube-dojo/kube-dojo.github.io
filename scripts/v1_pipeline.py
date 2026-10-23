"""KubeDojo Module Quality Pipeline — v1.

Processes each module through 8 quality dimensions to reach 33/40.
Uses Gemini for writing/translating, deterministic Python checks as gates.

Pipeline per module: WRITE/REWRITE → CITATION CHECK → REVIEW → CHECK → SCORE → COMMIT
Pipeline per section: modules + INDEX rewrite (EN) + INDEX translate (UK)

Features:
- Knowledge packet extraction: preserves code blocks, tables, diagrams, quiz
  blocks, inline prompts, and links during rewrites
- ASCII→Mermaid conversion instruction in WRITE/REWRITE prompts
- Deterministic checks: frontmatter, sections, inline prompts, quiz format,
  emojis, K8s API versions (WARNING only, strips code blocks + inline code)
- Section index.md: Gemini rewrite after section completes, auto-translates UK
- Safety: truncation guard, frontmatter validation, thinking leak detection,
  circuit breaker (5 consecutive failures), atomic state writes

Usage:
    python scripts/v1_pipeline.py status
    python scripts/v1_pipeline.py e2e ztt              # single section (EN + UK + index)
    python scripts/v1_pipeline.py e2e prereqs           # track (all sections)
    python scripts/v1_pipeline.py e2e k8s/cka           # auto-discovers parts
    python scripts/v1_pipeline.py e2e certs linux cloud  # multiple tracks
    python scripts/v1_pipeline.py e2e ztt --no-translate # EN only, skip UK
    python scripts/v1_pipeline.py run <module-path>      # single module
    python scripts/v1_pipeline.py run-section <path>     # section without index
    python scripts/v1_pipeline.py resume                 # retry stuck modules
    python scripts/v1_pipeline.py audit <module-path>    # deprecated no-op
    python scripts/v1_pipeline.py audit-all              # deterministic checks only

Section aliases: ztt, git, cn101, k8sbasics, philosophy, devops,
    cka, ckad, cks, kcna, kcsa, extending, aws, gcp, azure, eks, gke, aks
Track aliases: prereqs, certs, specialty, cloud, platform, on-prem, linux
Any directory path also works: e2e on-premises, e2e platform/foundations
"""

from __future__ import annotations

import argparse
import builtins
import copy
import fcntl
import html as html_lib
import http.client
import json
import logging
import os
import random
import re
import shutil
import subprocess
import sys
import threading
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import UTC, date, datetime, timedelta
from functools import cache
from pathlib import Path

import yaml

logger = logging.getLogger(__name__)

REPO_ROOT = Path(__file__).parent.parent
CONTENT_ROOT = REPO_ROOT / "src" / "content" / "docs"
STATE_FILE = REPO_ROOT / ".pipeline" / "state.yaml"
REPORT_FILE = REPO_ROOT / ".pipeline" / "audit-report.json"
SCORE_SCRIPT = REPO_ROOT / "scripts" / "score_module.py"
KNOWLEDGE_CARD_DIR = REPO_ROOT / ".pipeline" / "knowledge-cards"
FACT_LEDGER_DIR = REPO_ROOT / ".pipeline" / "fact-ledgers"
REVIEW_AUDIT_DIR = REPO_ROOT / ".pipeline" / "reviews"
FACT_LEDGER_TTL = timedelta(days=7)
LINK_CACHE_FILE = REPO_ROOT / ".pipeline" / "link-cache.json"
LINK_CACHE_TTL = timedelta(hours=24)
DASHBOARD_FILE = REPO_ROOT / ".pipeline" / "dashboard.html"
RUBRIC_PROFILE_DIR = REPO_ROOT / "docs" / "rubric-profiles"
REVIEW_SAMPLES_FILE = REPO_ROOT / ".cache" / "review_samples.jsonl"
REVIEWER_DRIFT_FLAGGED_FILE = REPO_ROOT / ".cache" / "reviewer_drift_flagged.json"
LINK_HEALTH_TIMEOUT_SEC = 5
K8S_MIN_SUPPORTED_MINOR = 35
K8S_VERSION_RE = re.compile(r"\bv?1\.(\d{1,2})\b")
CLAIM_MATCH_TOLERANCE_CHARS = 10
DATA_CONFLICT_CONFLICT_THRESHOLD = 3
DATA_CONFLICT_UNVERIFIED_THRESHOLD = 5
LEGACY_SCORE_PASS_THRESHOLD = 4
CONTENT_AWARE_FACT_LEDGER_MAX_CHARS = 40_000
CONTENT_AWARE_FACT_LEDGER_OVERLAP_CHARS = 4_000
MAX_RETRIES = 4
REVIEW_REJECTED_ERROR_RE = re.compile(r"^Review rejected (\d+) times$")
SECOND_REVIEWER_SAMPLE_RATE = 0.15
SECOND_REVIEWER_MODEL = "claude-opus-4-8"
REVIEW_SAMPLES_SCHEMA_COMMENT = (
    "# schema: "
    '{"module_key":"str","codex_review":"object","opus_review":"object",'
    '"delta_sum":"int","delta_dims":"list[int] aligned to [COV, QUIZ, EXAM, DEPTH, WHY, PRES]"}'
)
_LINK_CACHE_LOCK = threading.Lock()
_PARALLEL_RUN_SECTION_STATE_LOCK = None
_PARALLEL_RUN_SECTION_GIT_LOCK = None
_PARALLEL_RUN_SECTION_CONTEXT = threading.local()
INTEGRITY_WARNING_PREFIXES = (
    "LINK_DEAD:",
    "STALE_K8S_VERSION:",
    "VERSION_MISMATCH_WARNING:",
    "MISSING_SUPPORTED_CLAIM:",
    "UNMAPPED_CLAIM:",
)

# ---------------------------------------------------------------------------
# Timestamped logging — tee all print() to a log file
# ---------------------------------------------------------------------------

LOG_DIR = REPO_ROOT / ".pipeline" / "logs"
LOG_DIR.mkdir(parents=True, exist_ok=True)
LOG_FILE = LOG_DIR / f"run_{datetime.now(UTC).strftime('%Y%m%dT%H%M%S')}.log"

_original_print = builtins.print
_quiet = False  # set by e2e command
os.environ["KUBEDOJO_QUIET"] = "1"  # suppress Gemini streaming to stdout


def _logged_print(*args, **kwargs):
    msg = " ".join(str(a) for a in args)
    # Always write to log file
    with open(LOG_FILE, "a", encoding="utf-8") as f:
        f.write(f"[{datetime.now(UTC).strftime('%H:%M:%S')}] {msg}\n")
    # Only print to stdout if not in quiet mode, or if it's a summary/error line
    if not _quiet:
        _original_print(*args, **kwargs)
    elif any(k in msg for k in (
        # Progress milestones
        "PASS", "FAIL", "CIRCUIT", "E2E COMPLETE", "SECTION:", "PHASE 1",
        "SKIP:", "Resumed:", "passed,", "BREAKER",
        # Pipeline steps — so user sees what's happening
        "PIPELINE:", "AUDIT:", "WRITE:", "REWRITE:", "CITATION:", "REVIEW:", "CHECK:", "INDEX:",
        "FACT LEDGER:", "TRANSLATE:",
        # Key decisions and results
        "Verdict:", "Scores:", "REWRITE mode", "already passes",
        "Rejected", "produced", "file written", "Committed",
        # Errors and operational issues
        "❌", "rate-limited", "falling back", "unavailable",
        "Exception", "DONE:",
    )):
        _original_print(f"[{datetime.now(UTC).strftime('%H:%M:%S')}] {msg}")


builtins.print = _logged_print

# Add scripts to path for imports
sys.path.insert(0, str(REPO_ROOT / "scripts"))

from checks import gaps, structural, ukrainian
from dispatch import (
    GEMINI_WRITER_MODEL,
    ClaudeUnavailableError,
    _is_rate_limited,
    dispatch_agy,
    dispatch_claude,
    dispatch_codex,
)
from uk_sync import (
    CONTENT_ROOT as UK_CONTENT_ROOT,
)
from uk_sync import (
    UK_ROOT,
)
from uk_sync import (
    _find_content_files as uk_find_content_files,
)
from uk_sync import (
    fix_module as uk_fix,
)
from uk_sync import (
    translate_new_module as uk_translate,
)


def dispatch_auto(prompt: str, model: str, timeout: int = 900) -> tuple[bool, str]:
    """Route to agy (Google lane), Claude, or Codex based on model name.

    ``gemini-*`` model slugs are agy (Antigravity) display models and route to
    dispatch_agy — gemini-cli is retired (#2125)."""
    if model.startswith("gemini"):
        return dispatch_agy(prompt, model=model, timeout=timeout)
    if model.startswith("claude"):
        return dispatch_claude(prompt, model=model, timeout=timeout)
    if model.startswith(("codex", "gpt-")) or "codex" in model:
        return dispatch_codex(prompt, model=model, timeout=timeout)
    raise ValueError(f"Unknown model family: {model!r} — must start with 'gemini', 'claude', or 'codex'")


# ---------------------------------------------------------------------------
# Model configuration (overridable via CLI)
# ---------------------------------------------------------------------------

MODELS = {
    "write": GEMINI_WRITER_MODEL,          # Pinned in dispatch.py; re-evaluate monthly and replace when GA is available. See issue #217/#278.
    "write_targeted": "claude-sonnet-4-6", # TARGETED FIX: surgical patches (instruction-following)
    "review": GEMINI_WRITER_MODEL,         # STRUCTURAL REVIEW: calibration-backed choice for split-reviewer flow
    "review_fallback": "claude-sonnet-4-6",  # independent REVIEW fallback when Codex is unavailable
    "knowledge_card": "gpt-5.3-codex-spark",  # WRITE grounding aligned with fact-grounding calibration
    "fact_grounding": "gpt-5.3-codex-spark",  # split-reviewer architecture: factual grounding ledger
    "fact_fallback": "claude-sonnet-4-6",     # cross-family backup for facts
    # "translate" removed — uk_sync.CHUNKED_MODEL owns translation model config
}

# Reviewer families considered "independent" for the deferred re-review path
# and fact-grounding model validation. Claude remains the preferred cross-family
# fallback when the primary structural reviewer is unavailable.
INDEPENDENT_REVIEWER_FAMILIES = {"codex", "claude"}

# Pipeline phases in order.
# "needs_targeted_fix" is a pause state entered when Claude is unavailable
# (peak hours / rate limit / budget) mid retry-loop. On resume, it loads the
# staged content + saved plan and transitions back to "write" to re-enter
# the targeted-fix retry path without re-running the initial write.
PHASES = ["pending", "data_conflict", "write", "review", "needs_targeted_fix",
          "check", "score", "done"]

# ---------------------------------------------------------------------------
# State management
# ---------------------------------------------------------------------------

def load_state() -> dict:
    if STATE_FILE.exists():
        return yaml.safe_load(STATE_FILE.read_text()) or {"modules": {}}
    return {"modules": {}}


def _with_parallel_state_lock(func, /, *args, **kwargs):
    """Serialize shared state merges during parallel run-section mode."""
    lock = _PARALLEL_RUN_SECTION_STATE_LOCK
    if lock is None:
        return func(*args, **kwargs)
    with lock:
        return func(*args, **kwargs)


def _with_parallel_git_lock(func, /, *args, **kwargs):
    """Serialize git add/commit during parallel run-section mode."""
    lock = _PARALLEL_RUN_SECTION_GIT_LOCK
    if lock is None:
        return func(*args, **kwargs)
    with lock:
        return func(*args, **kwargs)


def _write_state_file(state: dict) -> None:
    STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    lock_file = STATE_FILE.with_suffix(".lock")
    tmp_file = STATE_FILE.with_suffix(".tmp")
    with open(lock_file, "w") as lf:
        fcntl.flock(lf, fcntl.LOCK_EX)
        try:
            tmp_file.write_text(yaml.dump(state, allow_unicode=True, sort_keys=False))
            tmp_file.replace(STATE_FILE)  # atomic on POSIX
        finally:
            fcntl.flock(lf, fcntl.LOCK_UN)


def _parallel_worker_state(shared_state: dict, module_key: str) -> dict:
    """Return an isolated per-worker snapshot for one module."""
    worker_state = {"modules": {}}
    modules = shared_state.get("modules") or {}
    if module_key in modules:
        worker_state["modules"][module_key] = copy.deepcopy(modules[module_key])
    return worker_state


def _merge_parallel_worker_state(local_state: dict) -> None:
    """Merge one worker-local module snapshot back into the shared state."""
    ctx = getattr(_PARALLEL_RUN_SECTION_CONTEXT, "value", None)
    if ctx is None or local_state is not ctx["local_state"]:
        _write_state_file(local_state)
        return

    module_key = ctx["module_key"]

    def _merge() -> None:
        shared_modules = ctx["shared_state"].setdefault("modules", {})
        worker_modules = local_state.get("modules", {})
        if module_key in worker_modules:
            shared_modules[module_key] = copy.deepcopy(worker_modules[module_key])
        else:
            shared_modules.pop(module_key, None)
        _write_state_file(ctx["shared_state"])

    _with_parallel_state_lock(_merge)


def save_state(state: dict) -> None:
    """Save state with file locking + atomic write to prevent corruption."""
    ctx = getattr(_PARALLEL_RUN_SECTION_CONTEXT, "value", None)
    if ctx is not None and state is ctx["local_state"]:
        _merge_parallel_worker_state(state)
        return
    _with_parallel_state_lock(_write_state_file, state)


def _git_stage_and_commit(add_paths: list[str], commit_msg: str,
                          timeout: int | None = None) -> tuple[subprocess.CompletedProcess,
                                                               subprocess.CompletedProcess]:
    """Run git add + git commit, serialized in parallel run-section mode."""
    def _run() -> tuple[subprocess.CompletedProcess, subprocess.CompletedProcess]:
        kwargs = {
            "cwd": str(REPO_ROOT),
            "capture_output": True,
            "text": True,
        }
        if timeout is not None:
            kwargs["timeout"] = timeout
        add_result = subprocess.run(["git", "add", *add_paths], check=False, **kwargs)
        commit_result = subprocess.run(["git", "commit", "-m", commit_msg], check=False, **kwargs)
        return add_result, commit_result

    return _with_parallel_git_lock(_run)


def get_module_state(state: dict, module_key: str) -> dict:
    return state["modules"].setdefault(module_key, {
        "phase": "pending",
        "scores": None,
        "sum": None,
        "passes": False,
        "last_run": None,
        "errors": [],
        "fact_ledger": None,
        "fact_ledger_generated_at": None,
    })


def _run_module_in_parallel(module_path: Path, shared_state: dict, max_retries: int | None = None,
                            models: dict | None = None, dry_run: bool = False,
                            refresh_fact_ledger: bool = False,
                            write_only: bool = False) -> bool:
    """Run one module with an isolated worker-local state snapshot.

    Uses the shared retry cap from `_resolve_max_retries` so parallel
    workers follow the same policy as serial/reset-stuck modes (#235).
    """
    module_key = module_key_from_path(module_path)
    local_state = _parallel_worker_state(shared_state, module_key)
    _PARALLEL_RUN_SECTION_CONTEXT.value = {
        "local_state": local_state,
        "module_key": module_key,
        "shared_state": shared_state,
    }
    try:
        ok = run_module(
            module_path,
            local_state,
            max_retries=_resolve_max_retries(max_retries),
            models=models,
            dry_run=dry_run,
            refresh_fact_ledger=refresh_fact_ledger,
            write_only=write_only,
        )
        _merge_parallel_worker_state(local_state)
        return ok
    finally:
        _PARALLEL_RUN_SECTION_CONTEXT.value = None


def module_key_from_path(path: Path) -> str:
    """Convert file path to module key (e.g., 'k8s/cka/part1/module-1.1')."""
    path = path.resolve()
    rel = path.relative_to(CONTENT_ROOT.resolve())
    return str(rel).replace(".md", "")


def find_module_path(key: str) -> Path | None:
    """Find the actual file path from a module key."""
    # Path traversal protection
    if ".." in key or key.startswith("/"):
        print(f"  ❌ Invalid module key (path traversal): {key}")
        return None
    candidate = CONTENT_ROOT / f"{key}.md"
    # Ensure resolved path is still under CONTENT_ROOT
    if not candidate.resolve().is_relative_to(CONTENT_ROOT.resolve()):
        print(f"  ❌ Path escapes content root: {key}")
        return None
    if candidate.exists():
        return candidate
    # Try fuzzy match
    parts = key.split("/")
    pattern = f"**/{parts[-1]}.md"
    matches = list(CONTENT_ROOT.glob(pattern))
    return matches[0] if matches else None


def initial_write_plan(key: str) -> str:
    """Generic first-pass plan for new or legacy pre-write states."""
    return (
        f"Draft or improve the module at {key} per the topic spec in the "
        f"module frontmatter and any TODO comments in the existing stub."
    )


def _clear_resume_metadata(ms: dict, staging_path: Path | None = None) -> None:
    """Drop run-scoped resume state before starting a fresh pipeline attempt."""
    ms.pop("plan", None)
    ms.pop("targeted_fix", None)
    ms.pop("paused_reason", None)
    if staging_path is not None:
        staging_path.unlink(missing_ok=True)


def sanitize_module_key(module_key: str) -> str:
    """Convert a module key into a stable knowledge-card filename."""
    return module_key.replace("/", "__")


def knowledge_card_path_for_key(module_key: str) -> Path:
    """Return the cached knowledge-card path for a module key."""
    return KNOWLEDGE_CARD_DIR / f"{sanitize_module_key(module_key)}.md"


def fact_ledger_path_for_key(module_key: str) -> Path:
    """Return the cached fact-ledger path for a module key."""
    return FACT_LEDGER_DIR / f"{sanitize_module_key(module_key)}.json"


def review_audit_path_for_key(module_key: str) -> Path:
    """Return the audit-log path for a module key."""
    return REVIEW_AUDIT_DIR / f"{sanitize_module_key(module_key)}.md"


def _extract_frontmatter_data(content: str) -> dict:
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


def _knowledge_card_is_expired(card_content: str) -> bool:
    """Return True if a knowledge card is expired or malformed."""
    data = _extract_frontmatter_data(card_content)
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
    return expires_at < datetime.now(UTC).date()


def _cache_is_fresh(path: Path, ttl: timedelta) -> bool:
    """Return True if file mtime is within ttl."""
    if not path.exists():
        return False
    modified_at = datetime.fromtimestamp(path.stat().st_mtime, UTC)
    return datetime.now(UTC) - modified_at < ttl


def _extract_topic_from_module(module_path: Path) -> str:
    """Extract module topic from frontmatter title, falling back to filename."""
    content = module_path.read_text()
    fm = _extract_frontmatter_data(content)
    title = fm.get("title")
    if isinstance(title, str) and title.strip():
        return title.strip()
    return module_path.stem


def _model_family(model: str) -> str:
    """Normalize model name to provider family key."""
    if model.startswith("gemini"):
        return "gemini"
    if model.startswith("claude"):
        return "claude"
    if model.startswith(("codex", "gpt-")) or "codex" in model:
        return "codex"
    return model.split("-", 1)[0]


def ensure_knowledge_card(module_path: Path, ms: dict,
                          model: str = MODELS["knowledge_card"]) -> str | None:
    """Ensure a fresh knowledge card exists for this module. Returns the card
    content for injection into WRITE prompts, or None if unavailable.

    Behavior:
    - If .pipeline/knowledge-cards/<key>.md exists and has not expired → read and return
    - If missing or expired → call generate_knowledge_card.generate()
    - On Codex rate limit: return existing stale card if any (with stale flag),
      else None. Set ms["stale_knowledge_card"] = True when using stale.
    - On success, clear ms["stale_knowledge_card"] if previously set.
    """
    key = module_key_from_path(module_path)
    card_path = knowledge_card_path_for_key(key)
    existing = card_path.read_text() if card_path.exists() else None

    if existing and not _knowledge_card_is_expired(existing):
        ms.pop("stale_knowledge_card", None)
        return existing

    import generate_knowledge_card

    generated = generate_knowledge_card.generate(key, force=True, model=model)
    if generated is not None:
        ms.pop("stale_knowledge_card", None)
        return generated

    if existing:
        ms["stale_knowledge_card"] = True
        return existing

    ms.pop("stale_knowledge_card", None)
    return None


FACT_LEDGER_PROMPT_TEMPLATE = """You are doing a fact-grounding pass for the KubeDojo curriculum module on the topic: {topic}.

As-of date: {as_of_date}

Identify every externally-versioned factual claim that a module on this topic would need to make. For each claim, determine its current truth from authoritative upstream sources (official vendor docs, project sites, CNCF status pages, GitHub release notes).

Return a structured ledger.

Rules:
- Do NOT answer from memory. Use current upstream documentation.
- Prefer official vendor/project docs over blog posts.
- If two authoritative sources disagree, mark CONFLICTING — never synthesize.
- If you cannot find an authoritative source, mark UNVERIFIED — never guess.
- Every SUPPORTED claim needs at least 1 resolvable canonical URL and a source date if available.
- Every CONFLICTING claim needs at least 2 resolvable URLs and a one-sentence conflict summary.
- Saying "I don't know" costs nothing. Confident wrong answers cost a lot.
- Output strict JSON only, no prose preamble.

Required JSON shape:
{{
  "as_of_date": "{as_of_date}",
  "topic": "{topic}",
  "claims": [
    {{
      "id": "C1",
      "claim": "short factual statement",
      "status": "SUPPORTED" | "CONFLICTING" | "UNVERIFIED",
      "current_truth": "what is true now or null",
      "sources": [
        {{"url": "...", "source_date": "YYYY-MM-DD or null"}}
      ],
      "conflict_summary": "one sentence if status is CONFLICTING, else null",
      "unverified_reason": "one sentence if status is UNVERIFIED, else null"
    }}
  ]
}}
"""


def step_fact_ledger(module_path: Path, topic_hint: str | None = None,
                     model: str = MODELS["fact_grounding"],
                     refresh: bool = False) -> dict | None:
    """Generate or load a cached fact ledger for a module.

    This is the split-reviewer architecture's factual source of truth. It
    dispatches exactly one call to the fact-grounding model and stores the
    result in `.pipeline/fact-ledgers/` for 7 days unless refresh is forced.
    """
    key = module_key_from_path(module_path)
    cache_path = fact_ledger_path_for_key(key)
    if cache_path.exists() and not refresh and _cache_is_fresh(cache_path, FACT_LEDGER_TTL):
        try:
            cached = json.loads(cache_path.read_text())
            claims = cached.get("claims") if isinstance(cached, dict) else None
            if isinstance(claims, list) and claims:
                print(f"  ✓ FACT LEDGER cache hit: {cache_path.name}")
                return cached
        except (json.JSONDecodeError, OSError) as e:
            print(f"  ⚠ FACT LEDGER cache unreadable, regenerating: {e}")

    topic = topic_hint or _extract_topic_from_module(module_path)
    as_of_date = datetime.now(UTC).date().isoformat()
    prompt = FACT_LEDGER_PROMPT_TEMPLATE.format(topic=topic, as_of_date=as_of_date)
    key = module_key_from_path(module_path)
    print(f"\n  FACT LEDGER: {key} (using {model})")
    ok, output = dispatch_auto(prompt, model=model, timeout=900)
    if not ok:
        if output and _is_rate_limited(output):
            print("  ⚠ FACT LEDGER rate-limited")
            return {"rate_limited": True}
        print("  ❌ FACT LEDGER dispatch failed")
        return None

    ledger = _extract_review_json(output, required_keys=("claims",))
    if not isinstance(ledger, dict):
        print("  ❌ FACT LEDGER parse failed")
        return None
    claims = ledger.get("claims")
    if not isinstance(claims, list) or not claims:
        print("  ❌ FACT LEDGER invalid: missing non-empty claims[]")
        return None

    ledger_json = json.dumps(ledger, indent=2, ensure_ascii=False)
    _atomic_write_text(cache_path, ledger_json)
    print(f"  ✓ FACT LEDGER cached: {cache_path.name}")
    return ledger


def ensure_fact_ledger(module_path: Path, ms: dict,
                       model: str = MODELS["fact_grounding"],
                       topic_hint: str | None = None,
                       refresh: bool = False) -> dict | None:
    """Ensure a fresh fact ledger is available in module state.

    The on-disk cache is authoritative; state metadata is only a mirror.
    """
    key = module_key_from_path(module_path)
    cache_path = fact_ledger_path_for_key(key)

    if not refresh and cache_path.exists() and _cache_is_fresh(cache_path, FACT_LEDGER_TTL):
        try:
            cached = json.loads(cache_path.read_text())
            claims = cached.get("claims") if isinstance(cached, dict) else None
            if isinstance(claims, list) and claims:
                ms["fact_ledger"] = cached
                return cached
        except (json.JSONDecodeError, OSError):
            pass

    ledger = step_fact_ledger(module_path, topic_hint=topic_hint, model=model, refresh=refresh)
    if isinstance(ledger, dict) and not ledger.get("rate_limited"):
        ms["fact_ledger"] = ledger
        ms["fact_ledger_generated_at"] = datetime.now(UTC).isoformat()
    return ledger


# ---------------------------------------------------------------------------
# Content-aware fact ledger — regenerated AFTER writing to verify actual claims
# ---------------------------------------------------------------------------

CONTENT_AWARE_FACT_LEDGER_PROMPT = """You are verifying the factual claims in a KubeDojo curriculum module.

As-of date: {as_of_date}

Below is module content that was just written. It may be the full module or one
consecutive excerpt from it. Extract every externally-versioned factual claim
(version numbers, release dates, API paths, CLI flags, feature gates, CNCF
status, default values, compatibility ranges) that appears in the content you
were given and verify each against authoritative upstream sources.

Rules:
- Extract claims FROM THE CONTENT BELOW — do not invent claims about the topic.
- Verify each extracted claim against official vendor/project docs.
- If two authoritative sources disagree, mark CONFLICTING.
- If you cannot find an authoritative source, mark UNVERIFIED.
- Every SUPPORTED claim needs at least 1 resolvable canonical URL.
- Output strict JSON only, no prose preamble.

Required JSON shape:
{{
  "as_of_date": "{as_of_date}",
  "topic": "{topic}",
  "content_aware": true,
  "claims": [
    {{
      "id": "C1",
      "claim": "short factual statement extracted from the content",
      "status": "SUPPORTED" | "CONFLICTING" | "UNVERIFIED",
      "current_truth": "what is true now or null",
      "sources": [
        {{"url": "...", "source_date": "YYYY-MM-DD or null"}}
      ],
      "conflict_summary": "one sentence if status is CONFLICTING, else null",
      "unverified_reason": "one sentence if status is UNVERIFIED, else null"
    }}
  ]
}}

--- MODULE CONTENT ---
{content}
"""


def _split_content_aware_ledger_windows(
    content: str,
    max_chars: int = CONTENT_AWARE_FACT_LEDGER_MAX_CHARS,
    overlap_chars: int = CONTENT_AWARE_FACT_LEDGER_OVERLAP_CHARS,
) -> list[str]:
    """Split long modules into overlapping windows for full-content grounding."""
    if len(content) <= max_chars:
        return [content]

    windows: list[str] = []
    start = 0
    content_len = len(content)
    min_split_point = max_chars // 2
    boundary_markers = ("\n## ", "\n### ", "\n\n")

    while start < content_len:
        end = min(start + max_chars, content_len)
        if end < content_len:
            search_start = min(start + min_split_point, end)
            candidates = [
                content.rfind(marker, search_start, end)
                for marker in boundary_markers
            ]
            split_at = max((idx for idx in candidates if idx > start), default=-1)
            if split_at != -1:
                end = split_at

        window = content[start:end].strip()
        if window:
            windows.append(window)

        if end >= content_len:
            break

        next_start = max(0, end - overlap_chars)
        if next_start <= start:
            next_start = end
        start = next_start

    return windows or [content]


def _merge_content_aware_window_ledgers(
    ledgers: list[dict],
    *,
    topic: str,
    as_of_date: str,
) -> dict | None:
    """Merge per-window content-aware ledgers, de-duping overlap claims."""
    merged_claims: list[dict] = []
    seen_claims: set[str] = set()
    merged_topic = topic
    merged_as_of_date = as_of_date

    for ledger in ledgers:
        if not isinstance(ledger, dict):
            continue
        if ledger.get("topic"):
            merged_topic = ledger["topic"]
        if ledger.get("as_of_date"):
            merged_as_of_date = ledger["as_of_date"]

        for claim in ledger.get("claims", []):
            if not isinstance(claim, dict):
                continue
            claim_text = claim.get("claim", "").strip()
            normalized = " ".join(claim_text.lower().split())
            if not normalized or normalized in seen_claims:
                continue
            merged_claims.append(copy.deepcopy(claim))
            seen_claims.add(normalized)

    if not merged_claims:
        return None

    for i, claim in enumerate(merged_claims, 1):
        claim["id"] = f"C{i}"

    return {
        "as_of_date": merged_as_of_date,
        "topic": merged_topic,
        "content_aware": True,
        "claims": merged_claims,
    }


def step_content_aware_fact_ledger(
    module_path: Path,
    content: str,
    model: str = MODELS["fact_grounding"],
) -> dict | None:
    """Generate a fact ledger from the actual written content.

    Unlike step_fact_ledger (topic-based, pre-write), this extracts and
    verifies claims the writer actually made. Used between WRITE and REVIEW
    so the reviewer has precise grounding.

    Cached separately with a '-content' suffix to avoid colliding with
    the pre-write topic-based ledger.
    """
    key = module_key_from_path(module_path)
    cache_path = FACT_LEDGER_DIR / f"{sanitize_module_key(key)}-content.json"

    topic = _extract_topic_from_module(module_path)
    as_of_date = datetime.now(UTC).date().isoformat()

    windows = _split_content_aware_ledger_windows(content)
    total_windows = len(windows)
    window_ledgers: list[dict] = []

    for index, window in enumerate(windows, 1):
        window_label = f" [{index}/{total_windows}]" if total_windows > 1 else ""
        prompt = CONTENT_AWARE_FACT_LEDGER_PROMPT.format(
            topic=topic, as_of_date=as_of_date, content=window
        )
        print(f"\n  FACT LEDGER (content-aware{window_label}): {key} (using {model})")
        ok, output = dispatch_auto(prompt, model=model, timeout=900)
        if not ok:
            if output and _is_rate_limited(output):
                print("  ⚠ Content-aware FACT LEDGER rate-limited — using topic-based ledger")
                return None
            print("  ⚠ Content-aware FACT LEDGER dispatch failed — using topic-based ledger")
            return None

        ledger = _extract_review_json(output, required_keys=("claims",))
        if not isinstance(ledger, dict):
            print("  ⚠ Content-aware FACT LEDGER parse failed — using topic-based ledger")
            return None
        claims = ledger.get("claims")
        if not isinstance(claims, list):
            print("  ⚠ Content-aware FACT LEDGER invalid claims payload — using topic-based ledger")
            return None
        window_ledgers.append(ledger)

    ledger = _merge_content_aware_window_ledgers(
        window_ledgers,
        topic=topic,
        as_of_date=as_of_date,
    )
    if ledger is None:
        print("  ⚠ Content-aware FACT LEDGER empty — using topic-based ledger")
        return None

    ledger_json = json.dumps(ledger, indent=2, ensure_ascii=False)
    _atomic_write_text(cache_path, ledger_json)
    print(f"  ✓ Content-aware FACT LEDGER: {len(ledger['claims'])} claims verified, cached")
    return ledger


def _merge_fact_ledgers(topic_ledger: dict | None, content_ledger: dict | None) -> dict | None:
    """Merge topic-based and content-aware fact ledgers.

    Content-aware claims take precedence (more specific). Topic-based claims
    that don't overlap are kept for broad coverage. Returns a merged ledger
    or the best available single ledger.
    """
    topic_copy = copy.deepcopy(topic_ledger) if isinstance(topic_ledger, dict) else None
    content_copy = copy.deepcopy(content_ledger) if isinstance(content_ledger, dict) else None

    if not content_copy or not content_copy.get("claims"):
        return topic_copy
    if not topic_copy or not topic_copy.get("claims"):
        return content_copy

    # Use content-aware claims as the base
    merged_claims = copy.deepcopy(content_copy["claims"])
    content_texts = {c.get("claim", "").lower().strip() for c in merged_claims if isinstance(c, dict)}

    # Add non-overlapping topic claims
    for claim in topic_copy.get("claims", []):
        if not isinstance(claim, dict):
            continue
        claim_text = claim.get("claim", "").lower().strip()
        if claim_text and claim_text not in content_texts:
            merged_claims.append(copy.deepcopy(claim))

    # Re-number
    for i, claim in enumerate(merged_claims, 1):
        if isinstance(claim, dict):
            claim["id"] = f"C{i}"

    return {
        "as_of_date": content_copy.get("as_of_date", topic_copy.get("as_of_date")),
        "topic": content_copy.get("topic", topic_copy.get("topic")),
        "content_aware": True,
        "claims": merged_claims,
    }


def _count_fact_ledger_issues(ledger: dict | None) -> tuple[int, int]:
    """Return (conflicting, unverified) claim counts for a fact ledger."""
    if not isinstance(ledger, dict):
        return 0, 0

    n_conflict = sum(
        1 for c in ledger.get("claims", [])
        if isinstance(c, dict) and c.get("status") == "CONFLICTING"
    )
    n_unverified = sum(
        1 for c in ledger.get("claims", [])
        if isinstance(c, dict) and c.get("status") == "UNVERIFIED"
    )
    return n_conflict, n_unverified


# ---------------------------------------------------------------------------
# WRITE step — Gemini drafts improvements
# ---------------------------------------------------------------------------

KNOWLEDGE_CARD_UNAVAILABLE = (
    "(No knowledge card available — use general K8s 1.30+ knowledge but flag any "
    "uncertain facts for reviewer verification.)"
)

K8S_LIFECYCLE_BLOCK = """## Kubernetes Version Policy

Current supported versions (as of {as_of_date}):
- v1.35 (current stable release)
- v1.34 (supported)
- v1.33 (supported, nearing EOL)
- v1.32 and below: end-of-life — do NOT recommend for production

Rules:
- All kubectl/YAML examples MUST target v1.35+
- Historical references are OK ("feature X was introduced in v1.28")
- When referencing other tools (containerd, Helm, etc.), use their current stable versions
- Never use version 47 of anything (known LLM pattern)
"""

VERIFIED_FACTS_BLOCK_TEMPLATE = """## Verified Facts (from fact-grounding pass)

The following facts have been verified against upstream sources. Incorporate
them accurately in your content. Do not contradict them.

{claims_block}
"""

AUTHORITATIVE_SOURCES_BLOCK_TEMPLATE = """## Sources — cite these inline

Maintain the module's `## Sources` section and cite these URLs
inline where relevant in the body.

{sources_block}
"""

SEED_SECTION_RE = re.compile(r"^##\s+`([^`]+)`\s*$")
URL_RE = re.compile(r"https?://[^\s)]+")
# Accept both `## Sources` (canonical per docs/citation-upgrade-plan.md) and
# the legacy `## Authoritative Sources` header so older drafts still verify.
AUTHORITATIVE_SOURCES_HEADING_RE = re.compile(
    r"^##\s+(?:Sources|Authoritative Sources)(?:\s+[—-].*)?\s*$",
    re.MULTILINE | re.IGNORECASE,
)


def _format_fact_ledger_for_prompt(fact_ledger: dict | None) -> str:
    """Serialize fact ledger for prompt injection."""
    if not isinstance(fact_ledger, dict):
        return "(No fact ledger available.)"
    try:
        return json.dumps(fact_ledger, indent=2, ensure_ascii=False)
    except (TypeError, ValueError):
        return "(Fact ledger serialization failed.)"


def _format_verified_claims_for_prompt(fact_ledger: dict | None) -> str:
    """Build a compact verified-claims block for writer prompt injection."""
    if not isinstance(fact_ledger, dict):
        return ""

    claims = fact_ledger.get("claims")
    if not isinstance(claims, list) or not claims:
        return ""

    lines: list[str] = []
    for claim in claims:
        if not isinstance(claim, dict):
            continue

        status = str(claim.get("status", "")).upper()
        if status not in {"VERIFIED", "SUPPORTED"}:
            continue

        claim_text = str(claim.get("claim", "")).strip()
        if not claim_text:
            continue

        claim_id = str(claim.get("id") or f"C{len(lines) + 1}")
        source_url = "verified"
        sources = claim.get("sources")
        if isinstance(sources, list):
            for source in sources:
                if not isinstance(source, dict):
                    continue
                url = source.get("url")
                if isinstance(url, str) and url.strip():
                    source_url = url.strip()
                    break

        lines.append(f"- [{claim_id}] {claim_text} (source: {source_url})")

    if not lines:
        return ""
    return VERIFIED_FACTS_BLOCK_TEMPLATE.format(claims_block="\n".join(lines))


def _citation_seed_path(module_key: str) -> Path | None:
    """Return the per-track citation seed file path for a module key."""
    track = "-".join(module_key.split("/")[:-1]).strip("-")
    if not track:
        return None
    return REPO_ROOT / "docs" / f"citation-seeds-{track}.md"


def _matching_seed_lines(seed_path: Path, module_key: str) -> list[str]:
    """Return the URL-bearing seed lines for one module section."""
    current_key: str | None = None
    lines: list[str] = []
    for raw_line in seed_path.read_text(encoding="utf-8").splitlines():
        heading = SEED_SECTION_RE.match(raw_line.strip())
        if heading:
            if current_key == module_key:
                break
            current_key = heading.group(1).strip()
            continue
        if current_key != module_key:
            continue
        line = raw_line.strip()
        if "http" in line and (
            line.startswith(("- ", "http"))
            or re.match(r"^\d+\.\s+", line)
        ):
            lines.append(line)
    return lines


def _format_authoritative_sources_for_prompt(module_key: str) -> str:
    """Build a prompt block from the matching module section in a seed file."""
    seed_path = _citation_seed_path(module_key)
    if seed_path is None or not seed_path.exists():
        return ""
    lines = _matching_seed_lines(seed_path, module_key)

    if not lines:
        return ""
    return AUTHORITATIVE_SOURCES_BLOCK_TEMPLATE.format(
        sources_block="\n".join(lines)
    )


def step_check_citations(
    draft_path: Path, seeds_path: Path, min_citations: int = 3,
) -> dict:
    """Run the deterministic citation checker and enforce seed coverage."""
    result = {
        "passes": False,
        "citation_count": 0,
        "issues": [],
        "missing_seed_urls": [],
        "dead_urls": [],
    }
    key = module_key_from_path(
        draft_path.with_name(draft_path.name.replace(".staging.md", ".md"))
    )
    print(f"\n  CITATION: {key}")
    try:
        proc = subprocess.run(
            [".venv/bin/python", "scripts/check_citations.py", str(draft_path), "--json"],
            cwd=str(REPO_ROOT),
            capture_output=True,
            text=True,
            check=False,
            timeout=60,
        )
        payload = json.loads(proc.stdout or "{}")
    except (OSError, subprocess.SubprocessError, json.JSONDecodeError) as exc:
        result["issues"] = [f"citation_checker_failed: {exc}"]
        return result

    entry = ((payload.get("results") or [{}])[0]
             if isinstance(payload, dict) else {})
    issues = [str(issue) for issue in (entry.get("issues") or [])]
    citation_count = entry.get("sources_count", entry.get("citation_count", 0))
    draft_text = draft_path.read_text(encoding="utf-8")
    seed_urls = []
    if seeds_path.exists():
        for line in _matching_seed_lines(seeds_path, key):
            seed_urls.extend(URL_RE.findall(line))
    missing_seed_urls = [url for url in dict.fromkeys(seed_urls) if url not in draft_text]
    dead_urls = [str(url) for url in (entry.get("dead_urls") or [])]
    dead_urls.extend(
        issue.split(":", 1)[1].strip()
        for issue in issues
        if issue.lower().startswith("dead_url:")
    )

    if citation_count < min_citations:
        issues.append(f"needs_at_least_{min_citations}_citations")
    if missing_seed_urls:
        issues.append("missing_seed_urls")
    if dead_urls:
        issues.append("dead_urls")

    result.update({
        "passes": bool(entry.get("passes")) and citation_count >= min_citations
        and not missing_seed_urls and not dead_urls,
        "citation_count": citation_count,
        "issues": issues,
        "missing_seed_urls": missing_seed_urls,
        "dead_urls": list(dict.fromkeys(dead_urls)),
    })
    return result


def _compute_cite_check(content: str) -> dict:
    """Deterministically validate inline citation usage for authoritative seeds."""
    match = AUTHORITATIVE_SOURCES_HEADING_RE.search(content)
    if match is None:
        return {
            "id": "CITE",
            "passed": False,
            "evidence": "Missing `## Sources` section.",
        }

    after_heading = content[match.end():]
    next_heading = re.search(r"^##\s+", after_heading, re.MULTILINE)
    if next_heading is None:
        sources_block = after_heading
        body = content[:match.start()]
    else:
        sources_block = after_heading[:next_heading.start()]
        body = content[:match.start()] + after_heading[next_heading.start():]

    seed_urls = list(dict.fromkeys(URL_RE.findall(sources_block)))
    missing_urls = [url for url in seed_urls if url not in body]
    dead_urls = [
        url for url, status in _resolve_url_statuses(seed_urls).items()
        if status is None or status >= 400
    ]
    problems: list[str] = []
    if missing_urls:
        problems.append("Missing inline seed URLs:\n- " + "\n- ".join(missing_urls))
    if dead_urls:
        problems.append("Dead authoritative source URLs:\n- " + "\n- ".join(dead_urls))
    return {
        "id": "CITE",
        "passed": not problems,
        "evidence": "\n".join(problems) if problems else "All authoritative seed URLs are cited inline and reachable.",
    }


WRITE_PROMPT_TEMPLATE = """CRITICAL INSTRUCTION: Your response must be ONLY the raw markdown content of the improved module. Start your response with the --- frontmatter delimiter. No preamble, no explanation, no summary, no "I have improved..." — ONLY the markdown file content from first line to last.

You are improving a KubeDojo module. You will receive the current module content and an improvement plan.

RULES:
- Output the COMPLETE improved module (full file replacement)
- Your response IS the file — start with --- and end with the last line of content
- Do NOT remove or rewrite sections that are already good
- Do NOT change code blocks, YAML examples, or diagrams unless they contain errors
- Do NOT add emojis
- Do NOT change frontmatter unless fixing an error
- Add inline prompts as blockquotes: > **Pause and predict**: or > **Stop and think**:
- Quiz questions must be scenario-based (lead with realistic situation, test understanding not recall)
- Every quiz answer must explain WHY (3-5 sentences minimum)
- Keep the module's existing voice and style
- CONVERT any ASCII art diagrams to Mermaid (```mermaid blocks) — Mermaid renders natively in our site

{k8s_lifecycle}

KNOWLEDGE CARD:
{knowledge_card}

FACT LEDGER (authoritative, as-of dated):
{fact_ledger}

Use the fact ledger as the factual source of truth. If a claim is CONFLICTING or
UNVERIFIED in the ledger, hedge explicitly in the module text and cite the
authority context.

{verified_facts_block}

{authoritative_sources_block}

IMPROVEMENT PLAN:
{plan}

---

CURRENT MODULE:
{content}
"""


REWRITE_PROMPT_TEMPLATE = """CRITICAL INSTRUCTION: Your response must be ONLY the raw markdown content. Start with the --- frontmatter delimiter. No preamble, no explanation — ONLY the markdown file.

TASK: Rewrite a KubeDojo educational module. The existing module scored too low — rewrite it while preserving all technical assets listed in the KNOWLEDGE PACKET below.

The file path is: {file_path}
Keep the EXACT same frontmatter (title, slug, sidebar order).

{k8s_lifecycle}

KNOWLEDGE CARD:
{knowledge_card}

FACT LEDGER (authoritative, as-of dated):
{fact_ledger}

Use the fact ledger as the factual source of truth. If a claim is CONFLICTING or
UNVERIFIED in the ledger, hedge explicitly in the module text and cite the
authority context.

{verified_facts_block}

{authoritative_sources_block}

KNOWLEDGE PACKET — MUST PRESERVE:
The following technical assets are extracted from the original module. You MUST include ALL of them in your rewrite, placed in the appropriate sections. Do NOT omit, summarize, or simplify any of these.

{knowledge_packet}

TOPICS TO COVER (from plan):
{plan}

QUALITY REQUIREMENTS:
- 600-800 lines of content minimum (visual aids don't count toward this)
- Learning Outcomes: 3-5 measurable, Bloom's L3+ verbs (debug, design, evaluate, compare, diagnose, implement)
- Why This Module Matters: open with dramatic real-world incident, real company, real financial impact. 2-3 paragraphs.
- Core content (3-6 sections): explanations with analogies, runnable code blocks, Mermaid diagrams (preferred over ASCII), tables, war stories
- At least 2 inline active learning prompts distributed throughout: > **Pause and predict**: or > **Stop and think**:
- Did You Know?: exactly 4 facts with real numbers/dates
- Common Mistakes: table with 6-8 rows (Mistake | Why | Fix)
- Quiz: 6-8 questions in <details> tags, at least 4 scenario-based. Answers 3-5 sentences explaining WHY.
- Hands-On Exercise: 4-6 progressive tasks with solutions in <details> tags, success checklist
- Next Module: link with teaser
- NO emojis, NO recall quiz questions, NO thin outlines, NO number 47
- CONVERT all ASCII art diagrams to Mermaid (```mermaid blocks). Use flowchart for architecture, sequenceDiagram for flows, graph TD for hierarchies. ASCII art is fragile and hard to maintain — Mermaid renders natively in our site.

EXISTING MODULE (rewrite this, preserving all knowledge packet assets):
{content}
"""


# ---------------------------------------------------------------------------
# Knowledge packet extraction — preserves technical assets for rewrites
# ---------------------------------------------------------------------------

def extract_knowledge_packet(content: str) -> str:
    """Extract preservable technical assets from a module.

    Returns a formatted string with labeled code blocks, tables, diagrams,
    quiz questions, inline prompts, and links for the REWRITE prompt.
    """
    sections = []

    # 1. Code blocks — extract all fenced blocks, find nearest heading for context
    raw_blocks = list(re.finditer(r"```[\w]*\n[\s\S]*?```", content))
    if raw_blocks:
        headings = list(re.finditer(r"^#{2,3} .+$", content, re.MULTILINE))
        labeled = []
        for i, match in enumerate(raw_blocks, 1):
            # Find nearest heading before this code block
            heading = "unknown section"
            for h in reversed(headings):
                if h.start() < match.start():
                    heading = h.group().lstrip("# ").strip()
                    break
            labeled.append(f"[CODE-{i}] (from: {heading})\n{match.group()}")
        sections.append("### CODE BLOCKS\n" + "\n\n".join(labeled))

    # 2. Tables
    table_pattern = re.compile(r"(\|.+\|)\n(\|[-| :]+\|)\n((?:\|.+\|\n?)+)", re.MULTILINE)
    tables = table_pattern.findall(content)
    if tables:
        labeled_tables = []
        for i, (header, sep, rows) in enumerate(tables, 1):
            labeled_tables.append(f"[TABLE-{i}]\n{header}\n{sep}\n{rows.strip()}")
        sections.append("### TABLES\n" + "\n\n".join(labeled_tables))

    # 3. Mermaid and ASCII diagrams
    mermaid = re.findall(r"```mermaid\n[\s\S]*?```", content)
    if mermaid:
        labeled = [f"[DIAGRAM-{i}]\n{d}" for i, d in enumerate(mermaid, 1)]
        sections.append("### MERMAID DIAGRAMS\n" + "\n\n".join(labeled))

    # ASCII diagrams (lines with box-drawing chars or +--+)
    ascii_blocks = re.findall(
        r"(?:^[ ]*[+|┌┐└┘├┤┬┴┼─│╔╗╚╝║═].*\n){3,}",
        content, re.MULTILINE
    )
    if ascii_blocks:
        labeled = [f"[ASCII-{i}]\n{b.strip()}" for i, b in enumerate(ascii_blocks, 1)]
        sections.append("### ASCII DIAGRAMS (convert to Mermaid if possible)\n" + "\n\n".join(labeled))

    # 4. Quiz questions — full <details> blocks (questions + answers)
    quiz_blocks = re.findall(r"(<details>[\s\S]*?</details>)", content)
    if quiz_blocks:
        labeled = [f"[QUIZ-{i}]\n{q}" for i, q in enumerate(quiz_blocks, 1)]
        sections.append("### QUIZ BLOCKS (preserve questions AND answers)\n" + "\n\n".join(labeled))

    # 5. Inline prompts — capture full blockquote (may be multi-line)
    prompt_blocks = re.findall(
        r"(>\s*\*\*(?:Pause and predict|Stop and think|What would happen|Try it yourself|Before you look)[\s\S]*?)(?=\n\n|\n[^>]|\Z)",
        content
    )
    if prompt_blocks:
        labeled = [f"[PROMPT-{i}]\n{p.strip()}" for i, p in enumerate(prompt_blocks, 1)]
        sections.append("### INLINE PROMPTS\n" + "\n\n".join(labeled))

    # 6. Links (internal and external)
    links = re.findall(r"\[([^\]]+)\]\(([^)]+)\)", content)
    if links:
        unique_links = list(dict.fromkeys((text, url) for text, url in links))[:20]
        sections.append("### KEY LINKS\n" + "\n".join(f"- [{t}]({u})" for t, u in unique_links))

    if not sections:
        return "(No technical assets extracted — module may be a stub)"

    packet = "\n\n".join(sections)
    if len(packet) > 15000:
        print(f"  ⚠ Knowledge packet is large ({len(packet)} chars) — may cause output truncation")

    return packet


def count_assets(content: str) -> dict:
    """Count technical assets in content for before/after comparison."""
    return {
        "code_blocks": len(re.findall(r"```[\w]*\n[\s\S]*?```", content)),
        "tables": len(re.compile(r"(\|.+\|)\n(\|[-| :]+\|)\n((?:\|.+\|\n?)+)", re.MULTILINE).findall(content)),
        "quiz_blocks": len(re.findall(r"<details>[\s\S]*?</details>", content)),
        "mermaid": len(re.findall(r"```mermaid\n[\s\S]*?```", content)),
        "inline_prompts": len(re.findall(
            r">\s*\*\*(?:Pause and predict|Stop and think|What would happen|Try it yourself|Before you look|Зупиніться|Подумайте)",
            content)),
    }


def step_write(module_path: Path, plan: str, model: str = MODELS["write"],
               rewrite: bool = False,
               previous_output: str | None = None,
               knowledge_card: str | None = None,
               fact_ledger: dict | None = None) -> str | None:
    """Gemini drafts improvements or full rewrite based on the plan.

    If previous_output is provided (e.g. from an earlier attempt in the
    write→review loop), it is used as the content to improve instead of
    re-reading the file from disk. The file on disk is only updated during
    the CHECK phase, so without this the loop would keep operating on stale
    (original) content.
    """
    content = previous_output if previous_output is not None else module_path.read_text()
    key = module_key_from_path(module_path)
    mode = "REWRITE" if rewrite else "WRITE"
    print(f"\n  {mode}: {key} (using {model})")
    knowledge_card_text = knowledge_card or KNOWLEDGE_CARD_UNAVAILABLE
    fact_ledger_text = _format_fact_ledger_for_prompt(fact_ledger)
    k8s_lifecycle = K8S_LIFECYCLE_BLOCK.format(as_of_date=datetime.now(UTC).date().isoformat())
    verified_facts_block = _format_verified_claims_for_prompt(fact_ledger)
    authoritative_sources_block = _format_authoritative_sources_for_prompt(key)

    if rewrite:
        packet = extract_knowledge_packet(content)
        prompt = REWRITE_PROMPT_TEMPLATE.format(
            file_path=key, plan=plan, content=content, knowledge_packet=packet,
            knowledge_card=knowledge_card_text, fact_ledger=fact_ledger_text,
            k8s_lifecycle=k8s_lifecycle, verified_facts_block=verified_facts_block,
            authoritative_sources_block=authoritative_sources_block)
    else:
        prompt = WRITE_PROMPT_TEMPLATE.format(
            plan=plan, content=content, knowledge_card=knowledge_card_text,
            fact_ledger=fact_ledger_text, k8s_lifecycle=k8s_lifecycle,
            verified_facts_block=verified_facts_block,
            authoritative_sources_block=authoritative_sources_block)

    # Must use dispatch_auto (not dispatch_gemini_with_retry directly) so that
    # Claude Sonnet is actually called for targeted-fix mode. Previously this
    # was hardcoded to Gemini, which caused `model="claude-sonnet-4-6"` to be
    # passed to the Gemini CLI, fail with ModelNotFoundError, and silently
    # fall back to Gemini's "auto" model — completely defeating the point of
    # routing precision edits to Claude (PR #212).
    ok, output = dispatch_auto(prompt, model=model, timeout=900)

    if not ok or not output.strip():
        print("  ❌ WRITE failed")
        return None

    # Strip markdown wrapper if present
    if output.startswith("```markdown"):
        output = output[len("```markdown"):].strip()
    if output.startswith("```md"):
        output = output[len("```md"):].strip()
    if output.startswith("```"):
        output = output[3:].strip()
    if output.endswith("```"):
        output = output[:-3].strip()

    # Detect Gemini thinking leaks (chain-of-thought dumped into output)
    thinking_markers = ["CRITICAL INSTRUCTION", "thought\n", "Wait,", "I will ", "I'll just",
                        "the prompt says", "standard behavior"]
    if any(marker in output[:500] for marker in thinking_markers):
        print("  ❌ WRITE failed — Gemini leaked chain-of-thought into output")
        return None

    # Ensure output starts with frontmatter
    if not output.startswith("---"):
        # Try to find frontmatter deeper in the output
        fm_start = output.find("---\n")
        if fm_start > 0 and fm_start < 2000:
            output = output[fm_start:]
            print(f"  ⚠ Stripped {fm_start} chars of preamble before frontmatter")
        else:
            print("  ❌ WRITE failed — output has no frontmatter")
            return None

    # Reject degenerate output — a real module rewrite is thousands of chars.
    # 3000 is well below the expected 15k–40k range but above plausible stubs.
    MIN_WRITE_CHARS = 3000
    if len(output.strip()) < MIN_WRITE_CHARS:
        print(f"  ❌ WRITE failed — output is suspiciously short "
              f"({len(output.strip())} chars, expected ≥ {MIN_WRITE_CHARS})")
        return None

    print(f"  ✓ WRITE produced {len(output)} chars")
    return output


# ---------------------------------------------------------------------------
# REVIEW step — structural binary review
# ---------------------------------------------------------------------------

REVIEW_PROMPT_TEMPLATE = """You are the Lead Content Auditor for KubeDojo — an
independent, strict, BINARY reviewer. You do NOT give partial credit. You do
NOT use a 1-5 scale.

A separate fact-grounding pass has already verified all factual claims in this
module against current upstream documentation. The fact ledger is provided
below as `FACT_LEDGER`. You MUST NOT re-grade factual currency — assume the
ledger is the source of truth. If the module contradicts the ledger, that is a
structural failure (the writer ignored the ledger), not a factual failure.

Your job is to grade the module on STRUCTURE only:
- COV: does it cover every Learning Outcome from the frontmatter?
- QUIZ: do quiz questions require reasoning, not recall?
- EXAM: does the depth match the certification target (skip if no cert in frontmatter)?
- DEPTH: at least one practitioner-grade element (production gotcha, decision framework, war story)?
- WHY: rationale for every major design decision?
- PRES: every distinct concept/lab/diagram/quiz from the original is preserved (compression OK, deletion of unique value not OK)?
- CITE: every URL from `## Sources` is cited inline in the body, with no dead links?
Lab quality is evaluated by the separate `lab_pipeline.py` pipeline — do not
grade hands-on sections here.

DO NOT add a FACT check. DO NOT search the web for factual currency. DO NOT
contradict the fact ledger.

MANDATORY CHECKS — answer PASS or FAIL for each:

1. COV — Does the content cover every Learning Outcome listed in the
   module's frontmatter? A FAIL must list specific outcomes that have no
   corresponding content section.

2. QUIZ — Does every quiz question require reasoning or scenario
   application (not fact recall)? "What port does etcd use?" is recall
   and fails. "Given a CrashLoopBackOff on a pod with a PVC, which of
   these four causes is ruled out by the events log?" is scenario and
   passes. Each question must have exactly one correct answer supported
   by the module's own text.

3. EXAM — If the frontmatter declares a `certification:` target (CKA,
   CKAD, CKS, KCNA, KCSA), does the module depth match the published
   CNCF curriculum for that exam? Skip this check entirely if no
   certification is named in frontmatter. A FAIL must cite the specific
   curriculum domain the module fails to meet.

4. DEPTH — Does the module include at least one practitioner-grade
   element: a production gotcha, a decision framework, a war story, or a
   non-obvious failure mode? This is the anti-"Hello World" guardrail.
   A FAIL means the module reads like a surface tutorial with no
   operational nuance.

5. WHY — Does every major design decision (architecture choice, resource
   selection, flag usage, tradeoff) have at least one sentence of
   rationale? "Do X then Y" with no motivation is a FAIL. You are NOT
   looking for rationale on every individual line — major design
   decisions only.

6. PRES — Every distinct concept, lab, table, diagram, and quiz question
   from the ORIGINAL is present in the IMPROVED version, unless it
   contained a factual error or was explicit duplication. Compression
   and reorganization are ALLOWED. Deletion of unique value is NOT. A
   FAIL must cite the specific missing item from the original. This
   check exists to prevent information loss during rewrites — it does
   NOT forbid tightening prose.

7. CITE — Does every URL listed under `## Sources` appear
   inline in the module body, and are all cited URLs alive? A FAIL must
   name each missing or dead URL.

APPROVE REQUIRES every check `passed: true`. If even one check is
`passed: false`, the verdict is REJECT.

STRUCTURED EDIT FORMAT — for every FAIL, provide an edit OR explain in
`evidence` why an edit is not possible (e.g. "the Hands-on section needs
a ground-up rewrite — not fixable with substring replacement"):

  {{"type": "replace", "find": "<literal substring>", "new": "<replacement>", "reason": "<short>"}}
  {{"type": "insert_after", "find": "<literal anchor>", "new": "<content AFTER>", "reason": "..."}}
  {{"type": "insert_before", "find": "<literal anchor>", "new": "<content BEFORE>", "reason": "..."}}
  {{"type": "delete", "find": "<literal substring to remove>", "reason": "..."}}

HARD RULES for edits:
1. `find` MUST be a literal substring that appears EXACTLY ONCE in the
   IMPROVED module. If the phrase appears multiple times, include
   surrounding context (e.g. the heading above the paragraph) to make
   it unique. Ambiguous anchors FAIL and the edit is dropped.
2. `new` is the exact replacement text — no placeholders, no "...",
   no "TODO", no "rest unchanged". Full verbatim content.
3. Quote Markdown/YAML/code literally. Preserve leading whitespace and
   newlines exactly as they appear in the module. Escape embedded
   quotes for JSON.
4. List every concrete issue as a separate edit. There is no cap — the
   pipeline applies all structured edits in one pass.
5. One edit = one atomic change. Do NOT bundle multiple unrelated
   edits into one patch.

SEVERITY (advisory — code will compute the final value):
- "clean": verdict APPROVE, no failed checks.
- "targeted": verdict REJECT, 1-4 failed checks, ALL addressable via
  structured edits.
- "severe": verdict REJECT, 5+ failed checks OR any failure that
  cannot be fixed with structured edits.

Your `severity` field is ADVISORY. Code will override it based on the
actual number of failed checks and whether each failure has a workable
edit. Be honest — don't under-report to avoid triggering a rewrite.

OUTPUT JSON ONLY — no preamble, no postamble, no markdown fences:

{{
  "verdict": "APPROVE" or "REJECT",
  "severity": "clean" or "targeted" or "severe",
  "checks": [
    {{"id": "COV", "passed": true}},
    {{"id": "QUIZ", "passed": true}},
    {{"id": "EXAM", "passed": true}},
    {{"id": "DEPTH", "passed": true}},
    {{"id": "WHY", "passed": true}},
    {{"id": "PRES", "passed": true}},
    {{"id": "CITE", "passed": true}}
  ],
  "edits": [
    {{"type": "replace", "find": "...", "new": "...", "reason": "..."}}
  ],
  "feedback": "optional prose summary of qualitative notes that don't map to an edit"
}}

Every one of the 7 check IDs MUST appear in `checks`. Skipping EXAM when
there is no `certification:` target is fine — return it as `passed: true`
with evidence `"no certification target in frontmatter"`.

---

FACT_LEDGER:
{fact_ledger}

---

ORIGINAL MODULE:
{original}

---

IMPROVED MODULE:
{improved}
"""

CHECK_IDS = ["COV", "QUIZ", "EXAM", "DEPTH", "WHY", "PRES", "CITE"]
DEFAULT_SEVERE_FAILED_CHECKS = 5


def _default_rubric_profile(name: str = "default") -> dict:
    return {
        "name": name,
        "weights": {check_id: 1 for check_id in CHECK_IDS},
        "severity_gate": {"severe_failed_checks": DEFAULT_SEVERE_FAILED_CHECKS},
    }


def _normalize_rubric_track(track: str | None) -> str | None:
    if track is None:
        return None
    value = str(track).strip().lower().replace("_", "-")
    if not value:
        return None
    aliases = {
        "prereqs": "prerequisites",
        "prerequisites": "prerequisites",
        "cka": "cka",
        "ckad": "ckad",
        "cks": "cks",
        "kcna": "kcna",
        "cloud": "cloud",
        "platform": "platform",
        "ai": "ai",
        "ai-ml-engineering": "ai",
    }
    if value in aliases:
        return aliases[value]
    parts = [part for part in value.split("/") if part]
    if not parts:
        return None
    if parts[0] == "k8s" and len(parts) > 1 and parts[1] in {"cka", "ckad", "cks", "kcna"}:
        return parts[1]
    if parts[0] in {"prerequisites", "cloud", "platform"}:
        return parts[0]
    if parts[0] in {"ai", "ai-ml-engineering"}:
        return "ai"
    return aliases.get(parts[0])


def _rubric_track_from_path(module_path: Path) -> str | None:
    try:
        relative = module_path.resolve().relative_to(CONTENT_ROOT.resolve())
    except ValueError:
        return None
    parts = relative.parts
    if not parts:
        return None
    if parts[0] == "uk" and len(parts) > 1:
        parts = parts[1:]
    if not parts:
        return None
    if parts[0] == "k8s" and len(parts) > 1:
        return _normalize_rubric_track(f"k8s/{parts[1]}")
    return _normalize_rubric_track(parts[0])


def rubric_profile_name_for_module(module_path: Path) -> str:
    frontmatter = _extract_frontmatter_data(module_path.read_text())
    candidates = [
        frontmatter.get("track"),
        frontmatter.get("slug"),
    ]
    try:
        candidates.append(module_key_from_path(module_path))
    except ValueError:
        pass
    candidates.append(_rubric_track_from_path(module_path))
    for candidate in candidates:
        normalized = _normalize_rubric_track(candidate)
        if normalized:
            profile_path = RUBRIC_PROFILE_DIR / f"{normalized}.yaml"
            if profile_path.exists():
                return normalized
    return "default"


@cache
def load_rubric_profile(profile_name: str) -> dict:
    normalized = _normalize_rubric_track(profile_name) or "default"
    profile_path = RUBRIC_PROFILE_DIR / f"{normalized}.yaml"
    profile = _default_rubric_profile(normalized)
    if not profile_path.exists():
        normalized = "default"
        profile_path = RUBRIC_PROFILE_DIR / "default.yaml"
        profile = _default_rubric_profile("default")
    if profile_path.exists():
        raw = yaml.safe_load(profile_path.read_text()) or {}
        if isinstance(raw, dict):
            weights = raw.get("weights") or {}
            if isinstance(weights, dict):
                for check_id in CHECK_IDS:
                    value = weights.get(check_id)
                    if isinstance(value, (int, float)) and not isinstance(value, bool):
                        profile["weights"][check_id] = value
            severity_gate = raw.get("severity_gate") or {}
            if isinstance(severity_gate, dict):
                threshold = severity_gate.get("severe_failed_checks")
                if isinstance(threshold, int) and not isinstance(threshold, bool) and threshold > 0:
                    profile["severity_gate"]["severe_failed_checks"] = threshold
    return profile


def load_rubric_profile_for_module(module_path: Path) -> dict:
    return load_rubric_profile(rubric_profile_name_for_module(module_path))


def _has_valid_review_checks(checks: object) -> bool:
    """Return True when review `checks` has the expected binary-gate shape."""
    return (
        isinstance(checks, list)
        and all(
            isinstance(check, dict) and isinstance(check.get("passed"), bool)
            for check in checks
        )
    )


def compute_severity(
    verdict: str,
    checks: object,
    edits: object,
    profile: dict | None = None,
) -> str:
    """Compute the authoritative severity from reviewer output.

    The reviewer returns an advisory `severity` field but an LLM can
    under-report to avoid triggering a rewrite, or report "targeted" with
    zero edits (which is meaningless). Code is the final arbiter:

    - APPROVE → clean (regardless of what the reviewer said)
    - REJECT with 5+ failed checks → severe
    - REJECT with any failed check that has no corresponding edit → severe
    - REJECT with 1-4 failed checks, all backed by edits → targeted
    - REJECT with no edits at all → severe (nothing to apply)

    Fixes Gemini pair-review critique A from round 2.

    Split-reviewer context: factual model routing is selected from
    `project_fact_grounding_calibration.md`; this function intentionally
    stays FACT-agnostic and only routes structural reviewer output.
    """
    if not _has_valid_review_checks(checks):
        # Fail closed: malformed review payloads must never enter the
        # default-pass path, even if the reviewer claimed APPROVE.
        return "severe"
    if verdict == "APPROVE":
        return "clean"
    failed = [c for c in checks if isinstance(c, dict) and not c.get("passed", True)]
    if not failed:
        # Contradictory: REJECT with no failed checks. Treat as severe —
        # the reviewer's structure is inconsistent, fall back to rewrite.
        return "severe"
    severe_failed_checks = (
        ((profile or {}).get("severity_gate") or {}).get("severe_failed_checks")
        if isinstance(profile, dict)
        else None
    )
    if not isinstance(severe_failed_checks, int) or isinstance(severe_failed_checks, bool) or severe_failed_checks < 1:
        severe_failed_checks = DEFAULT_SEVERE_FAILED_CHECKS
    if len(failed) >= severe_failed_checks:
        return "severe"
    if not edits or not isinstance(edits, list):
        return "severe"
    edits_len = len(edits)
    # A failed check is "covered" iff edit_refs is a list of valid integer
    # indices into the edits array. Anything else — bool, str, out-of-bounds
    # int, non-list — is treated as uncovered and forces severe escalation.
    # Codex PR review flagged this as an arbiter-contract violation: the
    # previous implementation accepted any truthy edit_refs as coverage,
    # which let a malformed review (edit_refs=True, edit_refs="0", or
    # edit_refs=[999]) misroute to targeted.
    uncovered = []
    for c in failed:
        refs = c.get("edit_refs")
        if not isinstance(refs, list) or not refs:
            uncovered.append(c.get("id", "?"))
            continue
        if not all(isinstance(r, int) and not isinstance(r, bool) for r in refs):
            uncovered.append(c.get("id", "?"))
            continue
        if any(r < 0 or r >= edits_len for r in refs):
            uncovered.append(c.get("id", "?"))
            continue
    if uncovered:
        # At least one failure has no valid edit attached → can't patch,
        # need a rewrite for those sections. Escalate to severe.
        return "severe"
    return "targeted"


def compute_review_payload_severity(
    review: dict | None,
    profile: dict | None = None,
) -> str:
    """Compute severity from a possibly malformed review payload."""
    if not isinstance(review, dict):
        return "severe"
    return compute_severity(
        review.get("verdict", "REJECT"),
        review.get("checks"),
        review.get("edits"),
        profile=profile,
    )


def _second_reviewer_sample_rate() -> float:
    """Read SECOND_REVIEWER_SAMPLE_RATE from env, clamped to [0.0, 1.0]."""
    raw = os.environ.get("SECOND_REVIEWER_SAMPLE_RATE", "").strip()
    if not raw:
        return SECOND_REVIEWER_SAMPLE_RATE
    try:
        value = float(raw)
    except ValueError:
        return SECOND_REVIEWER_SAMPLE_RATE
    return max(0.0, min(1.0, value))


def _review_checks_by_id(review: dict) -> dict[str, bool]:
    """Normalize a review's check list to {check_id: passed_bool}."""
    mapping: dict[str, bool] = {}
    for check in review.get("checks") or []:
        if not isinstance(check, dict):
            continue
        cid = str(check.get("id", "")).strip()
        if cid:
            mapping[cid] = bool(check.get("passed"))
    return mapping


def _compute_review_delta(primary_review: dict, secondary_review: dict) -> tuple[int, list[int]]:
    """Compare two binary review payloads using a 2-point disagreement gap.

    The structural gate is binary PASS/FAIL per dimension, not the old 1-5
    rubric. We encode a mismatch as `2` so #278's per-dimension audit
    threshold (`delta_dims[i] >= 2`) still flags a single reviewer disagreement.
    """
    primary_checks = _review_checks_by_id(primary_review)
    secondary_checks = _review_checks_by_id(secondary_review)
    delta_dims = [
        0 if primary_checks.get(check_id) == secondary_checks.get(check_id) else 2
        for check_id in CHECK_IDS
    ]
    return sum(delta_dims), delta_dims


def _append_review_sample(record: dict) -> None:
    """Append one sampled dual-review record to the calibration JSONL."""
    REVIEW_SAMPLES_FILE.parent.mkdir(parents=True, exist_ok=True)
    lock_file = REVIEW_SAMPLES_FILE.with_suffix(REVIEW_SAMPLES_FILE.suffix + ".lock")
    with open(lock_file, "w", encoding="utf-8") as lf:
        fcntl.flock(lf, fcntl.LOCK_EX)
        try:
            write_schema = (
                not REVIEW_SAMPLES_FILE.exists()
                or REVIEW_SAMPLES_FILE.stat().st_size == 0
            )
            with open(REVIEW_SAMPLES_FILE, "a", encoding="utf-8") as fh:
                if write_schema:
                    fh.write(REVIEW_SAMPLES_SCHEMA_COMMENT + "\n")
                fh.write(json.dumps(record, ensure_ascii=False) + "\n")
        finally:
            fcntl.flock(lf, fcntl.LOCK_UN)


def _flag_reviewer_drift(module_key: str) -> None:
    """Track modules that need a human audit due to reviewer drift."""
    REVIEWER_DRIFT_FLAGGED_FILE.parent.mkdir(parents=True, exist_ok=True)
    lock_file = REVIEWER_DRIFT_FLAGGED_FILE.with_suffix(
        REVIEWER_DRIFT_FLAGGED_FILE.suffix + ".lock"
    )
    with open(lock_file, "w", encoding="utf-8") as lf:
        fcntl.flock(lf, fcntl.LOCK_EX)
        try:
            flagged: list[str] = []
            if REVIEWER_DRIFT_FLAGGED_FILE.exists():
                try:
                    loaded = json.loads(REVIEWER_DRIFT_FLAGGED_FILE.read_text())
                    if isinstance(loaded, list):
                        flagged = [str(item) for item in loaded]
                except json.JSONDecodeError:
                    flagged = []
            if module_key not in flagged:
                flagged.append(module_key)
                _atomic_write_text(
                    REVIEWER_DRIFT_FLAGGED_FILE,
                    json.dumps(flagged, indent=2, ensure_ascii=False) + "\n",
                )
        finally:
            fcntl.flock(lf, fcntl.LOCK_UN)


INDEX_PROMPT_TEMPLATE = """CRITICAL INSTRUCTION: Your response must be ONLY the raw markdown content. Start with the --- frontmatter delimiter. No preamble, no explanation — ONLY the markdown file.

You are rewriting the index.md for a KubeDojo section. This page introduces the section and lists its modules.

Keep the EXACT same frontmatter (title, sidebar order, label).

SECTION: {section_path}

MODULE LIST (current titles and filenames):
{module_list}

CURRENT INDEX:
{current_index}

RULES:
- Preserve the overall structure and voice of the current index
- Update the module table to match the current module titles and filenames
- Keep any prose, analogies, learning paths, prerequisites, and "what's next" sections
- Update descriptions in the table if they no longer match the module content
- Links must use relative paths: [Title](module-slug/)
- Ensure sidebar.order: 0 in frontmatter (index always sorts first)
- NO emojis
- If the current index is just a stub (< 10 lines of body), write a proper introduction (2-3 paragraphs) + module table
"""


def step_update_index(section_path: Path, model: str = MODELS["write"]) -> bool:
    """Rewrite section index.md via Gemini based on current module titles."""
    index_path = section_path / "index.md"
    if not index_path.exists():
        return False

    # Gather module info
    modules = sorted(section_path.glob("module-*.md"))
    modules = [m for m in modules if ".staging" not in str(m)]
    if not modules:
        return False

    module_list_lines = []
    for m in modules:
        content = m.read_text()
        fm_text = content.split("---", 2)[1] if content.startswith("---") else ""
        title_match = re.search(r'^title:\s*["\']?(.+?)["\']?\s*$', fm_text, re.MULTILINE)
        title = title_match.group(1).strip() if title_match else m.stem
        module_list_lines.append(f"- {m.stem} → {title}")

    module_list = "\n".join(module_list_lines)
    current_index = index_path.read_text()
    rel_section = str(section_path.relative_to(CONTENT_ROOT))

    prompt = INDEX_PROMPT_TEMPLATE.format(
        section_path=rel_section,
        module_list=module_list,
        current_index=current_index,
    )

    print(f"\n  INDEX: {rel_section} (using {model})")
    ok, output = dispatch_auto(prompt, model=model, timeout=600)

    if not ok or not output.strip():
        print("  ❌ INDEX rewrite failed")
        return False

    # Strip markdown wrapper
    if output.startswith("```markdown"):
        output = output[len("```markdown"):].strip()
    if output.startswith("```md"):
        output = output[len("```md"):].strip()
    if output.startswith("```"):
        output = output[3:].strip()
    if output.endswith("```"):
        output = output[:-3].strip()

    if not output.startswith("---"):
        print("  ❌ INDEX rewrite has no frontmatter")
        return False

    # Validate frontmatter
    parts = output.split("---", 2)
    if len(parts) < 3:
        print("  ❌ INDEX rewrite has malformed frontmatter")
        return False
    try:
        fm = yaml.safe_load(parts[1])
        if not isinstance(fm, dict) or "title" not in fm:
            print("  ❌ INDEX rewrite missing title in frontmatter")
            return False
    except yaml.YAMLError as e:
        print(f"  ❌ INDEX rewrite has broken YAML: {e}")
        return False

    # Ensure sidebar.order: 0 (index always sorts first)
    if "order:" in parts[1] and "order: 0" not in parts[1]:
        output = re.sub(r'(  order: )\d+', r'\g<1>0', output, count=1)

    index_path.write_text(output)
    print(f"  ✓ INDEX written: {rel_section}/index.md ({len(output)} chars)")

    files_to_add = [str(index_path)]

    # Translate UK index if one exists
    uk_index = CONTENT_ROOT / "uk" / rel_section / "index.md"
    if uk_index.exists():
        uk_ok = _translate_index(output, uk_index, rel_section)
        if uk_ok:
            files_to_add.append(str(uk_index))

    # Git add
    subprocess.run(
        ["git", "add"] + files_to_add,
        cwd=str(REPO_ROOT), capture_output=True, text=True, check=False,
    )

    return True


def _translate_index(_en_content: str, uk_path: Path, rel_section: str) -> bool:
    """Translate an EN index.md to Ukrainian. Delegates to uk_sync."""
    print(f"  INDEX-UK: uk/{rel_section} (translating)")
    en_path = UK_CONTENT_ROOT / rel_section / "index.md"
    if uk_path.exists():
        # Re-translate existing UK index
        return uk_fix(uk_path)
    else:
        # New translation
        return uk_translate(en_path)


def _has_required_json_keys(obj: dict, required_keys: tuple[str, ...]) -> bool:
    """Return True if obj has the required keys for a JSON payload."""
    if required_keys == ("verdict", "checks"):
        # Keep legacy `scores` acceptance so step_review can normalize v1/v2
        # reviewer payloads to v3 `checks`.
        if "verdict" not in obj:
            return False
        if "checks" in obj:
            return _has_valid_review_checks(obj.get("checks"))
        return "scores" in obj
    return all(k in obj for k in required_keys)


def _extract_review_json(output: str,
                         required_keys: tuple[str, ...] = ("verdict", "checks")) -> dict | None:
    """Extract the final JSON payload from a raw model response.

    Codex exec output contains tool-use breadcrumbs, search logs, and the final
    answer on a 'codex' banner line followed by the JSON, then 'tokens used N'.
    Gemini output is usually just the JSON, sometimes inside ```json fences.
    Strategy: try a direct JSON parse first, then fall back to regex-matching
    the LAST balanced {...} block in the output (most reviewers emit the
    canonical response last, near 'tokens used' or end-of-stream).
    """
    text = output.strip()

    # Strip fenced-code wrappers first (gemini pattern)
    if text.startswith("```"):
        parts = text.split("```")
        if len(parts) >= 2:
            candidate = parts[1]
            candidate = candidate.removeprefix("json")
            try:
                obj = json.loads(candidate.strip())
                if isinstance(obj, dict) and _has_required_json_keys(obj, required_keys):
                    return obj
            except json.JSONDecodeError:
                pass

    # Direct parse
    try:
        obj = json.loads(text)
        if isinstance(obj, dict) and _has_required_json_keys(obj, required_keys):
            return obj
    except json.JSONDecodeError:
        pass

    # Last-balanced-{...} scan (handles codex-exec noise)
    # Walk from the end; find matching braces.
    candidates: list[str] = []
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
                    candidates.append(text[i:end + 1])
                    end = -1
    for cand in candidates:
        try:
            obj = json.loads(cand)
            if isinstance(obj, dict) and _has_required_json_keys(obj, required_keys):
                return obj
        except json.JSONDecodeError:
            continue
    return None


def _normalize_review_result(output: str) -> dict | None:
    """Parse + normalize a raw reviewer response into the v3 review schema."""
    result = _extract_review_json(output)
    if result is None:
        return None

    if not isinstance(result, dict):
        return None

    verdict = result.get("verdict", "REJECT")
    checks_raw = result.get("checks")
    if (not isinstance(checks_raw, list) or not checks_raw) and "scores" in result:
        legacy_scores = result.get("scores")
        checks_raw = []
        if isinstance(legacy_scores, dict):
            score_items = list(legacy_scores.items())
        elif isinstance(legacy_scores, list):
            score_items = [(f"d{i+1}", score) for i, score in enumerate(legacy_scores)]
        else:
            score_items = []
        for i, (dim, score) in enumerate(score_items):
            check_id = re.sub(r"[^A-Za-z0-9]+", "_", str(dim).strip()).strip("_").upper()
            if not check_id:
                check_id = f"D{i+1}"
            score_value = score if isinstance(score, (int, float)) else None
            passed = bool(score_value is not None and score_value >= LEGACY_SCORE_PASS_THRESHOLD)
            checks_raw.append({
                "id": check_id,
                "passed": passed,
                "evidence": (
                    f"legacy score={score!r} "
                    f"(pass threshold {LEGACY_SCORE_PASS_THRESHOLD})"
                ),
            })
    if (
        not isinstance(checks_raw, list)
        or not all(
            isinstance(check, dict) and isinstance(check.get("passed"), bool)
            for check in checks_raw
        )
    ):
        return None
    checks = []
    for i, check in enumerate(checks_raw, 1):
        normalized = dict(check)
        if not str(normalized.get("id", "")).strip():
            normalized["id"] = f"C{i}"
        checks.append(normalized)
    edits = result.get("edits") or []
    if not isinstance(edits, list):
        edits = []

    result["severity"] = compute_severity(verdict, checks, edits)
    result["checks"] = checks
    result["edits"] = edits
    return result


def maybe_sample_second_reviewer(
    module_key: str,
    module_path: Path,
    improved: str,
    codex_review: dict,
    fact_ledger: dict | None = None,
) -> None:
    """Best-effort Claude Opus calibration sample after the primary review."""
    sample_rate = _second_reviewer_sample_rate()
    if sample_rate <= 0 or random.random() >= sample_rate:
        return

    print(
        f"  CALIBRATION: sampling {SECOND_REVIEWER_MODEL} second review "
        f"(rate={sample_rate:.2f})"
    )
    prompt = REVIEW_PROMPT_TEMPLATE.format(
        original=module_path.read_text(),
        improved=improved,
        fact_ledger=_format_fact_ledger_for_prompt(fact_ledger),
    )
    try:
        ok, output = dispatch_claude(prompt, model=SECOND_REVIEWER_MODEL, timeout=900)
    except ClaudeUnavailableError as exc:
        print(f"  ⚠ Calibration review skipped: {exc}")
        return
    if not ok:
        print("  ⚠ Calibration review failed")
        return

    opus_review = _normalize_review_result(output)
    if opus_review is None:
        print("  ⚠ Calibration review parse failed")
        return

    delta_sum, delta_dims = _compute_review_delta(codex_review, opus_review)
    _append_review_sample({
        "module_key": module_key,
        "codex_review": copy.deepcopy(codex_review),
        "opus_review": opus_review,
        "delta_sum": delta_sum,
        "delta_dims": delta_dims,
    })
    if delta_sum >= 6 or any(delta >= 2 for delta in delta_dims):
        _flag_reviewer_drift(module_key)


# ---------------------------------------------------------------------------
# Structured edit application — deterministic patches from reviewer output
# ---------------------------------------------------------------------------
#
# When the reviewer returns an `edits` array (structured patches with literal
# find/replace/insert/delete anchors), the pipeline can apply them directly
# via Python string operations without involving a writer LLM. This is:
#
#   - Free  (no Claude/Gemini call)
#   - Instant (milliseconds vs seconds of LLM write)
#   - 100% fidelity (no "LLM interpreted the fix" translation loss)
#   - Deterministic (a successful apply always lands the exact content)
#
# The writer LLM (Sonnet) is only invoked for edits whose anchors don't
# match exactly, or for qualitative feedback that can't be expressed as a
# structured patch.

def _collapse_whitespace(s: str) -> str:
    """Collapse runs of whitespace (including newlines) to a single space."""
    return re.sub(r"\s+", " ", s).strip()


def _find_anchor(content: str, anchor: str) -> tuple[int, int] | None:
    """Locate `anchor` in `content`. Returns (start, end) indices of the
    exact substring if a unique match is found, or None otherwise.

    Matching strategy:
    1. Literal exact match — fast path, handles most well-formed anchors
    2. Whitespace-normalized match — handles minor whitespace drift between
       the reviewer's quoted anchor and the actual module content

    If the anchor appears multiple times, returns None (ambiguous — the
    caller should fall back to an LLM writer rather than guess which
    instance to patch).
    """
    if not anchor:
        return None

    # 1. Exact literal match
    count = content.count(anchor)
    if count == 1:
        start = content.index(anchor)
        return start, start + len(anchor)
    if count > 1:
        return None  # ambiguous

    # 2. Whitespace-normalized match: build a normalized copy of content
    # and find the normalized anchor in it. Then map back to the original
    # indices by re-scanning the content.
    norm_anchor = _collapse_whitespace(anchor)
    if len(norm_anchor) < 20:
        return None  # too short to safely fuzzy-match

    # Build a map from normalized index -> original index
    orig_positions: list[int] = []
    norm_chars: list[str] = []
    i = 0
    prev_ws = False
    while i < len(content):
        ch = content[i]
        if ch.isspace():
            if not prev_ws and norm_chars:
                norm_chars.append(" ")
                orig_positions.append(i)
            prev_ws = True
        else:
            norm_chars.append(ch)
            orig_positions.append(i)
            prev_ws = False
        i += 1
    normalized = "".join(norm_chars).strip()

    if normalized.count(norm_anchor) != 1:
        return None

    norm_start = normalized.index(norm_anchor)
    if norm_start >= len(orig_positions):
        return None
    orig_start = orig_positions[norm_start]

    # Find the end: walk forward from orig_start until we've consumed
    # len(norm_anchor) normalized characters
    consumed = 0
    orig_end = orig_start
    in_whitespace_run = False
    while orig_end < len(content) and consumed < len(norm_anchor):
        ch = content[orig_end]
        if ch.isspace():
            if not in_whitespace_run:
                consumed += 1  # one normalized space
                in_whitespace_run = True
        else:
            consumed += 1
            in_whitespace_run = False
        orig_end += 1
    return orig_start, orig_end


def _atomic_write_text(path: Path, content: str) -> None:
    """Write `content` to `path` atomically — stages to a per-process,
    per-call unique tempfile in the same directory and then `os.replace()`
    swaps it into place. Survives SIGKILL mid-write: either the old file
    is intact, or the new file is complete. No partial writes visible to
    a future reader.

    The temp suffix includes PID and a monotonic nanosecond counter so two
    workers (or two serial calls in the same process) never contend on the
    same temp path — Codex PR #224 review flagged the fixed `.tmp` sibling
    as a concurrency race.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    unique = f".{os.getpid()}.{datetime.now(UTC).strftime('%H%M%S%f')}.tmp"
    tmp = path.with_suffix(path.suffix + unique)
    try:
        tmp.write_text(content)
        os.replace(tmp, path)
    except Exception:
        # Best-effort cleanup so a crash between write and replace
        # doesn't leave a stray temp file behind.
        if tmp.exists():
            try:
                tmp.unlink()
            except OSError:
                pass
        raise


def _format_audit_duration(seconds: float | None) -> str:
    """Render a human-readable duration for audit entries."""
    if seconds is None:
        return "unknown"
    try:
        total = max(0.0, float(seconds))
    except (TypeError, ValueError):
        return str(seconds)
    if total >= 60:
        minutes = int(total // 60)
        remainder = round(total - (minutes * 60))
        if remainder == 60:
            minutes += 1
            remainder = 0
        return f"{minutes}m {remainder}s"
    if total >= 10:
        return f"{round(total)}s"
    if total >= 1:
        return f"{total:.1f}s"
    return f"{round(total * 1000)}ms"


def _format_audit_timestamp(value: datetime | str | None = None) -> str:
    """Normalize datetimes to ISO-8601 UTC strings for audit entries."""
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


def _audit_quote_block(text: str) -> str:
    """Format free-form feedback as a markdown blockquote."""
    lines = text.splitlines() or [text]
    return "\n".join(f"> {line}" if line else ">" for line in lines)


def _module_path_for_audit(module_path: Path) -> str:
    """Format a module path for the audit header."""
    try:
        return str(module_path.resolve().relative_to(REPO_ROOT.resolve()))
    except ValueError:
        return str(module_path)


def _extract_audit_entry_timestamps(content: str) -> list[str]:
    """Extract entry timestamps from an existing audit file."""
    return re.findall(r"^## ([0-9TZ:\-]+) — ", content, re.MULTILINE)


def _split_audit_header_body(content: str) -> tuple[str, str]:
    """Split the audit file into header and entry body."""
    marker = "\n---\n"
    if marker in content:
        _header, body = content.split(marker, 1)
        return _header, body.lstrip("\n")
    return content, ""


def _render_review_check_summary(checks: list[dict]) -> str:
    """Summarize passed/failed review checks for markdown output."""
    if not isinstance(checks, list) or not checks:
        return "**Checks**: none"
    passed = [str(c.get("id", "?")) for c in checks if isinstance(c, dict) and c.get("passed")]
    failed = [str(c.get("id", "?")) for c in checks if isinstance(c, dict) and not c.get("passed")]
    summary = f"**Checks**: {len(passed)}/{len(checks)} passed"
    if passed:
        summary += f" ({' '.join(passed)})"
    if failed:
        summary += f" | **Failed**: {' '.join(failed)}"
    return summary


def _render_review_failed_evidence(checks: list[dict]) -> str:
    """Render failed-check evidence bullets for review audit entries."""
    failed_lines = []
    for check in checks:
        if not isinstance(check, dict) or check.get("passed"):
            continue
        evidence = str(check.get("evidence", "")).strip()
        if evidence:
            failed_lines.append(f"- **{check.get('id', '?')}**: {evidence}")
    if not failed_lines:
        return ""
    return "**Failed check evidence**:\n" + "\n".join(failed_lines)


def _render_check_failures(results: list) -> list[str]:
    """Extract failing deterministic check labels/messages from CHECK results."""
    failures: list[str] = []
    if not isinstance(results, list):
        return failures
    for result in results:
        passed = getattr(result, "passed", None)
        if passed is not False:
            continue
        check_name = getattr(result, "check", None)
        message = getattr(result, "message", None)
        if check_name and message:
            failures.append(f"{check_name}: {message}")
        elif check_name:
            failures.append(str(check_name))
        elif message:
            failures.append(str(message))
    return failures


def _render_audit_entry(event: str, timestamp: str, fields: dict) -> str:
    """Render a single markdown audit entry."""
    heading = f"## {timestamp} — `{event}`"
    if event == "REVIEW":
        verdict = str(fields.get("verdict", "")).strip()
        if verdict:
            heading += f" — `{verdict}`"

    lines = [heading, ""]

    if event == "WRITE":
        plan = str(fields.get("plan", "")).rstrip()
        lines.extend([
            f"**Writer**: {fields.get('writer', 'unknown')}",
            f"**Mode**: {fields.get('mode', 'write')}",
            f"**Output**: {fields.get('output_chars', 0)} chars",
            f"**Duration**: {_format_audit_duration(fields.get('duration'))}",
        ])
        if plan:
            lines.extend(["", "**Plan**:", _audit_quote_block(plan)])
    elif event == "REVIEW":
        checks = fields.get("checks") if isinstance(fields.get("checks"), list) else []
        lines.extend([
            f"**Reviewer**: {fields.get('reviewer', 'unknown')}",
            f"**Attempt**: {fields.get('attempt', '?')}",
            f"**Severity**: {fields.get('severity', 'unknown')}",
            f"**Duration**: {_format_audit_duration(fields.get('duration'))}",
            f"{_render_review_check_summary(checks)}",
        ])
        if fields.get("reviewer_fallback_used"):
            lines.append("**Reviewer fallback used**: true")
        failed_evidence = _render_review_failed_evidence(checks)
        if failed_evidence:
            lines.extend(["", failed_evidence])
        feedback = str(fields.get("feedback", "")).strip()
        if feedback:
            lines.extend(["", "**Feedback**:", _audit_quote_block(feedback)])
    elif event == "INTEGRITY_FAIL":
        errors = fields.get("errors") if isinstance(fields.get("errors"), list) else []
        lines.append("**Errors**:")
        lines.extend(f"- {error}" for error in errors)
    elif event == "CHECK_FAIL":
        failed_checks = fields.get("failed_checks") if isinstance(fields.get("failed_checks"), list) else []
        lines.extend([
            f"**Duration**: {_format_audit_duration(fields.get('duration'))}",
            "**Failed checks**:",
        ])
        lines.extend(f"- {item}" for item in failed_checks)
    elif event == "CHECK_PASS":
        lines.extend([
            f"**Duration**: {_format_audit_duration(fields.get('duration'))}",
            f"**Warnings**: {fields.get('warnings_count', 0)}",
        ])
    elif event == "DONE":
        lines.extend([
            f"**Pass sum**: {fields.get('pass_sum', 'all binary checks passed')}",
            f"**Reviewer**: {fields.get('reviewer', 'unknown')}",
        ])
    elif event == "RESET":
        cleared = fields.get("cleared_errors") if isinstance(fields.get("cleared_errors"), list) else []
        lines.extend([
            f"**New phase**: {fields.get('new_phase', 'pending')}",
            "**Cleared errors**:",
        ])
        lines.extend(f"- {item}" for item in cleared)
    else:
        for key, value in fields.items():
            lines.append(f"**{key.replace('_', ' ').title()}**: {value}")

    return "\n".join(lines).rstrip()


def append_review_audit(module_path: Path, event: str, **fields) -> Path:
    """Prepend a per-module markdown audit entry with atomic locked writes."""
    module_key = module_key_from_path(module_path)
    target = review_audit_path_for_key(module_key)
    lock_file = target.with_suffix(".lock")
    timestamp = _format_audit_timestamp(fields.pop("timestamp", None))

    target.parent.mkdir(parents=True, exist_ok=True)
    with open(lock_file, "w", encoding="utf-8") as lf:
        fcntl.flock(lf, fcntl.LOCK_EX)
        try:
            existing = target.read_text() if target.exists() else ""
            _header, existing_body = _split_audit_header_body(existing)
            existing_timestamps = _extract_audit_entry_timestamps(existing)
            all_timestamps = existing_timestamps + [timestamp]
            state = load_state()
            module_state = state.get("modules", {}).get(module_key, {})
            new_entry = _render_audit_entry(event, timestamp, fields)
            new_body = new_entry
            existing_body = existing_body.strip()
            if existing_body:
                new_body += f"\n\n---\n\n{existing_body}"

            first_pass = min(all_timestamps) if all_timestamps else timestamp
            last_pass = max(all_timestamps) if all_timestamps else timestamp
            total_passes = len(existing_timestamps) + 1
            header_lines = [
                f"# Review Audit: {module_key}",
                "",
                f"**Path**: `{_module_path_for_audit(module_path)}`",
                f"**First pass**: {first_pass}",
                f"**Last pass**: {last_pass}",
                f"**Total passes**: {total_passes}",
                f"**Current phase**: {module_state.get('phase', 'pending')}",
                f"**Current reviewer**: {module_state.get('reviewer', '-')}",
                f"**Current severity**: {module_state.get('severity', '-')}",
            ]
            content = "\n".join(header_lines) + f"\n\n---\n\n{new_body}\n"
            _atomic_write_text(target, content)
        finally:
            fcntl.flock(lf, fcntl.LOCK_UN)
    return target


def apply_review_edits(content: str, edits: list) -> tuple[str, list, list]:
    """Apply structured review edits to content via deterministic string ops.

    Returns:
        (patched_content, applied_edits, failed_edits)

    - applied_edits: list of edit dicts that landed successfully
    - failed_edits:  list of {"edit": <original>, "reason": <str>} entries
                     for edits that couldn't be applied mechanically. Caller
                     should route these to an LLM fallback.

    Application strategy: sort edits by anchor position in reverse order,
    apply each in place. Reverse-order application means earlier indices
    aren't invalidated by later inserts/replaces. If two edits touch
    overlapping regions, the later one wins; the conflicting earlier edit
    is reported as failed so the LLM fallback can resolve it.
    """
    if not isinstance(edits, list) or not edits:
        return content, [], []

    # Resolve anchor positions against the CURRENT content for every edit.
    # We do this up-front so we can detect ambiguity and conflict.
    resolved: list[tuple[dict, int, int]] = []  # (edit, start, end)
    failed: list = []

    for edit in edits:
        if not isinstance(edit, dict):
            failed.append({"edit": edit, "reason": "edit is not a JSON object"})
            continue
        etype = edit.get("type")
        if etype not in ("replace", "insert_after", "insert_before", "delete"):
            failed.append({"edit": edit, "reason": f"unknown edit type: {etype!r}"})
            continue
        find = edit.get("find", "")
        if not isinstance(find, str) or not find:
            failed.append({"edit": edit, "reason": "missing or empty 'find' field"})
            continue
        loc = _find_anchor(content, find)
        if loc is None:
            # Distinguish "not found" from "ambiguous" for clearer logs
            count = content.count(find)
            reason = (
                f"anchor appears {count} times (ambiguous)"
                if count > 1
                else "anchor not found in module"
            )
            failed.append({
                "edit": edit,
                "reason": f"{reason}: {find[:100]!r}",
            })
            continue
        resolved.append((edit, loc[0], loc[1]))

    # Detect overlapping edits (conflict). Sort by start, mark any edit
    # whose range starts before the previous edit's end as failed. Non-
    # overlapping adjacent edits (edit A ends at X, edit B starts at X)
    # are allowed since `start < prev_end` is strict.
    resolved.sort(key=lambda t: t[1])
    non_conflicting: list[tuple[dict, int, int]] = []
    prev_end = -1
    for edit, start, end in resolved:
        if start < prev_end:
            failed.append({
                "edit": edit,
                "reason": f"overlaps a previous edit ending at position {prev_end} "
                          f"(this edit starts at {start})",
            })
            continue
        non_conflicting.append((edit, start, end))
        prev_end = end

    # Apply in REVERSE document order so earlier indices aren't shifted
    # by later inserts/replaces.
    patched = content
    applied: list = []
    for edit, start, end in reversed(non_conflicting):
        etype = edit["type"]
        new = edit.get("new", "")
        if not isinstance(new, str):
            failed.append({"edit": edit, "reason": "'new' field is not a string"})
            continue
        if etype == "replace":
            patched = patched[:start] + new + patched[end:]
        elif etype == "insert_after":
            patched = patched[:end] + new + patched[end:]
        elif etype == "insert_before":
            patched = patched[:start] + new + patched[start:]
        elif etype == "delete":
            patched = patched[:start] + patched[end:]
        applied.append(edit)

    return patched, applied, failed


def step_review(module_path: Path, improved: str, model: str = MODELS["review"],
                fact_ledger: dict | None = None,
                rubric_profile: dict | None = None) -> dict | None:
    """Structural reviewer runs the binary quality gate.

    Returns:
        dict with keys {verdict, severity, checks, edits, feedback} on
            success. `severity` is the CODE-COMPUTED value (reviewer's
            advisory value is overwritten by compute_severity).
        {"rate_limited": True} sentinel dict if the reviewer was rate-limited
            (caller should NOT fail the module — keep content, flag for retry).
        None on any other failure.
    """
    original = module_path.read_text()
    key = module_key_from_path(module_path)
    print(f"\n  REVIEW: {key} (using {model})")

    prompt = REVIEW_PROMPT_TEMPLATE.format(
        original=original,
        improved=improved,
        fact_ledger=_format_fact_ledger_for_prompt(fact_ledger),
    )

    ok, output = dispatch_auto(prompt, model=model, timeout=900)

    if not ok:
        # Rate-limit detection so run_module can degrade gracefully
        if output and _is_rate_limited(output):
            print("  ⚠ REVIEW rate-limited — module flagged for later re-review")
            return {"rate_limited": True}
        print("  ❌ REVIEW failed")
        return None

    result = _normalize_review_result(output)
    if result is None:
        print("  ❌ Failed to parse REVIEW output")
        print(f"  Raw: {output[:500]}")
        return None
    cite_check = _compute_cite_check(improved)
    verdict = result.get("verdict", "REJECT")
    checks = [c for c in (result.get("checks") or []) if c.get("id") != "CITE"]
    checks.append(cite_check)
    edits = result.get("edits") or []
    feedback = result.get("feedback", "")
    if verdict == "APPROVE" and not cite_check["passed"]:
        verdict = "REJECT"
    result["verdict"] = verdict

    # Code as arbiter: override the reviewer's self-reported severity with
    # the computed value. Per Gemini pair-review critique A, trusting the
    # LLM to report severity produces inconsistent routing.
    severity = compute_severity(
        verdict,
        checks,
        edits,
        profile=rubric_profile or load_rubric_profile_for_module(module_path),
    )
    result["severity"] = severity
    result["checks"] = checks
    result["edits"] = edits

    # Binary-gate print: check IDs with PASS/FAIL plus the severity badge
    failed = [c for c in checks if not c.get("passed")]
    passed = [c for c in checks if c.get("passed")]
    severity_icon = {"clean": "🟢", "targeted": "🟡", "severe": "🔴"}.get(severity, "?")
    print(f"  Verdict: {verdict}  Severity: {severity_icon} {severity}")
    if checks:
        passed_ids = [c.get("id", "?") for c in passed]
        failed_ids = [c.get("id", "?") for c in failed]
        print(f"  Checks: {len(passed)}/{len(checks)} passed")
        if passed_ids:
            print(f"    ✓ {' '.join(passed_ids)}")
        if failed_ids:
            print(f"    ✗ {' '.join(failed_ids)}")
        for c in failed:
            ev = c.get("evidence", "")
            if ev:
                for line in ev.splitlines():
                    print(f"      {c.get('id')}: {line}")
    if edits:
        by_type: dict[str, int] = {}
        for e in edits:
            if not isinstance(e, dict):
                continue
            by_type[e.get("type", "?")] = by_type.get(e.get("type", "?"), 0) + 1
        type_summary = ", ".join(f"{k}={v}" for k, v in sorted(by_type.items()))
        print(f"  Structured edits: {len(edits)} ({type_summary})")
    if feedback:
        print("  Feedback:")
        print(f"  {'─' * 70}")
        for line in feedback.splitlines() or [feedback]:
            print(f"  {line}")
        print(f"  {'─' * 70}")

    return result


# ---------------------------------------------------------------------------
# CHECK step — deterministic checks on improved content
# ---------------------------------------------------------------------------

def _load_link_cache() -> dict:
    """Load URL health cache from disk."""
    if not LINK_CACHE_FILE.exists():
        return {}
    try:
        data = json.loads(LINK_CACHE_FILE.read_text())
        return data if isinstance(data, dict) else {}
    except (json.JSONDecodeError, OSError):
        return {}


def _save_link_cache(cache: dict) -> None:
    """Persist URL health cache atomically."""
    _atomic_write_text(LINK_CACHE_FILE, json.dumps(cache, indent=2, ensure_ascii=False))


def _read_cached_url_status(cache: dict, url: str) -> tuple[bool, int | None]:
    """Look up a cached URL status. Returns (hit, status): hit is True when the
    cache entry is present AND within TTL. Pure read, no mutation, no network.
    """
    if not isinstance(cache, dict):
        return False, None
    cached = cache.get(url)
    if not isinstance(cached, dict):
        return False, None
    checked_at_raw = cached.get("checked_at")
    status = cached.get("status")
    if not isinstance(checked_at_raw, str):
        return False, None
    try:
        checked_at = datetime.fromisoformat(checked_at_raw)
    except ValueError:
        return False, None
    if checked_at.tzinfo is None:
        checked_at = checked_at.replace(tzinfo=UTC)
    if datetime.now(UTC) - checked_at >= LINK_CACHE_TTL:
        return False, None
    return True, status if isinstance(status, int) else None


def _probe_url(url: str) -> int | None:
    """Fetch current HTTP status for a URL. Pure network I/O — no cache access.

    Split out of the old `_get_url_status` so the link-cache lock can wrap
    ONLY the cache read/write, never this function. Wrapping network calls
    under the lock was the original concurrency bug: it serialized every
    HTTP probe across the ThreadPoolExecutor and defeated parallelism.
    """
    def _call(method: str) -> int | None:
        headers = {"Range": "bytes=0-1023"} if method == "GET" else {}
        req = urllib.request.Request(url, method=method, headers=headers)
        try:
            with urllib.request.urlopen(req, timeout=LINK_HEALTH_TIMEOUT_SEC) as response:
                if method == "GET":
                    try:
                        response.read(1024)
                    except Exception:
                        logger.exception("Link probe body read failed; retaining HTTP status", exc_info=False)
                return int(response.getcode())
        except urllib.error.HTTPError as e:
            return int(e.code)
        except (urllib.error.URLError, TimeoutError, ValueError,
                http.client.InvalidURL, OSError):
            return None

    head_status = _call("HEAD")
    status_code = head_status
    if head_status in (403, 405):
        get_status = _call("GET")
        if get_status is not None:
            status_code = get_status
    return status_code


def _resolve_url_statuses(urls: list[str]) -> dict[str, int | None]:
    """Resolve URL statuses via the shared link cache with minimal lock scope.

    Phase A (lock): snapshot cache hits, list the URLs that need probing.
    Phase B (no lock): probe uncached URLs — the slow network calls run
                       concurrently across threads.
    Phase C (lock): re-load the cache, merge probed results, persist.
    """
    hits: dict[str, int | None] = {}
    to_probe: list[str] = []
    with _LINK_CACHE_LOCK:
        cache = _load_link_cache()
        for url in urls:
            hit, status = _read_cached_url_status(cache, url)
            if hit:
                hits[url] = status
            else:
                to_probe.append(url)

    probed: dict[str, int | None] = {url: _probe_url(url) for url in to_probe}

    if probed:
        with _LINK_CACHE_LOCK:
            cache = _load_link_cache()
            now_iso = datetime.now(UTC).isoformat()
            for url, status in probed.items():
                cache[url] = {"status": status, "checked_at": now_iso}
            _save_link_cache(cache)

    return {**hits, **probed}


def _contains_with_tolerance(haystack: str, needle: str,
                             tolerance: int = CLAIM_MATCH_TOLERANCE_CHARS) -> bool:
    """Return True when needle is found exactly or with end trimming tolerance."""
    if not needle:
        return False
    h = re.sub(r"\s+", " ", haystack).lower()
    n = re.sub(r"\s+", " ", needle).lower().strip()
    if not n:
        return False
    if n in h:
        return True
    if len(n) <= tolerance:
        return False
    for trim in range(1, tolerance + 1):
        if n[trim:] in h:
            return True
        if n[:-trim] in h:
            return True
    return False


def _is_unhedged_claim_assertion(content: str, claim_text: str) -> bool:
    """Heuristic check for claim assertions with no hedge language nearby."""
    if not claim_text:
        return False
    haystack = content.lower()
    needle = claim_text.lower().strip()
    if not needle:
        return False

    hedge_terms = (
        "according to",
        "as of",
        "reportedly",
        "appears to",
        "may",
        "might",
        "could",
        "conflicting",
        "unverified",
    )
    start = 0
    while True:
        idx = haystack.find(needle, start)
        if idx == -1:
            return False
        window_start = max(0, idx - 120)
        window_end = min(len(haystack), idx + len(needle) + 120)
        window = haystack[window_start:window_end]
        if not any(term in window for term in hedge_terms):
            return True
        start = idx + len(needle)


PRODUCT_VERSION_RE = re.compile(
    r"\b(?:kubernetes|k8s|helm|docker|containerd|etcd|cilium|calico|flannel|coredns|istio|argo(?:\s+cd|cd)?)\s+v?\d+\.\d+(?:\.\d+)?\b",
    re.IGNORECASE,
)
API_NAME_RE = re.compile(r"\b[a-z0-9][a-z0-9.-]*/v\d(?:alpha\d+|beta\d+)?\b", re.IGNORECASE)
HELM_KEY_RE = re.compile(r"`([A-Za-z][A-Za-z0-9_.-]*\.[A-Za-z0-9_.-]+)`")
DEPRECATION_STATUS_TERMS = ("deprecated", "deprecation", "removed", "stable", "ga", "beta", "alpha")


_FENCED_CODE_RE = re.compile(r"```[^\n]*\n[\s\S]*?```", re.MULTILINE)


def _strip_fenced_code(content: str) -> str:
    """Remove fenced code blocks. Factual claim extraction runs on prose only:
    tokens inside code fences are illustrative syntax, not claims the writer
    is asserting, and separate YAML/lint passes already validate them.
    """
    return _FENCED_CODE_RE.sub("", content)


def _extract_factual_claim_candidates(content: str) -> list[str]:
    """Extract likely factual claim fragments that require ledger mapping.

    Scans PROSE only (fenced code blocks are stripped first). API tokens and
    version strings that appear solely inside ```yaml / ```bash examples are
    treated as syntax, not as claims, and so they are not required to have a
    corresponding fact-ledger entry.
    """
    prose = _strip_fenced_code(content)
    candidates: set[str] = set()

    for match in K8S_VERSION_RE.finditer(prose):
        minor = match.group(1)
        snippet = prose[max(0, match.start() - 40):min(len(prose), match.end() + 40)]
        compact = " ".join(snippet.split())
        if compact:
            candidates.add(compact)
        candidates.add(f"v1.{minor}")

    for match in PRODUCT_VERSION_RE.finditer(prose):
        candidates.add(" ".join(match.group(0).split()))

    for match in API_NAME_RE.finditer(prose):
        token = match.group(0)
        if token and not token.startswith("http"):
            candidates.add(token)

    for match in HELM_KEY_RE.finditer(prose):
        token = match.group(1).strip()
        if token:
            candidates.add(token)

    for line in prose.splitlines():
        compact = " ".join(line.split())
        lowered = compact.lower()
        if not compact:
            continue
        if any(term in lowered for term in DEPRECATION_STATUS_TERMS):
            candidates.add(compact[:160])

    return sorted(candidates)


def _claim_maps_to_supported_ledger(claim_text: str, supported_ledger_texts: list[str]) -> bool:
    """Return True when the extracted content claim maps to a supported ledger claim."""
    if not claim_text:
        return False
    for ledger_text in supported_ledger_texts:
        if not ledger_text:
            continue
        if _contains_with_tolerance(ledger_text, claim_text):
            return True
        if _contains_with_tolerance(claim_text, ledger_text):
            return True

        claim_versions = {f"v1.{m.group(1)}" for m in K8S_VERSION_RE.finditer(claim_text)}
        ledger_versions = {f"v1.{m.group(1)}" for m in K8S_VERSION_RE.finditer(ledger_text)}
        if claim_versions and claim_versions.intersection(ledger_versions):
            return True
    return False


def step_check_integrity(content: str, fact_ledger: dict) -> tuple[bool, list[str]]:
    """Tier-1 deterministic integrity gate before structural checks."""
    errors: list[str] = []
    warnings: list[str] = []

    # 1) Link health with 24h cache. Cache dict access is protected by
    # `_LINK_CACHE_LOCK` inside `_resolve_url_statuses`; the actual HTTP
    # probes run OUTSIDE the lock so parallel section workers don't
    # serialize on network I/O.
    urls = sorted(set(re.findall(r"https?://[^\s)>\]\"']+", content)))
    statuses = _resolve_url_statuses(urls)
    for url in urls:
        status = statuses.get(url)
        if status is None or status >= 400:
            label = status if status is not None else "ERROR"
            warnings.append(f"LINK_DEAD: {url} ({label})")

    # 2) K8s version consistency + minimum supported version hard-fail
    versions = set()
    for match in K8S_VERSION_RE.finditer(content):
        minor_raw = match.group(1)
        try:
            minor = int(minor_raw)
        except ValueError:
            continue
        if not (0 <= minor <= 99):
            continue
        canonical = f"v1.{minor}"
        versions.add(canonical)
        if minor < K8S_MIN_SUPPORTED_MINOR:
            warnings.append(f"STALE_K8S_VERSION: {canonical}")
    if len(versions) > 1:
        warnings.append(f"VERSION_MISMATCH_WARNING: {', '.join(sorted(versions))}")

    # 3) YAML lint for fenced ```yaml blocks
    # Use safe_load_all to support multi-document YAML (K8s manifests with `---`
    # separators are valid and very common in examples).
    for match in re.finditer(r"```yaml\s*\n([\s\S]*?)```", content, re.IGNORECASE):
        yaml_block = match.group(1)
        try:
            list(yaml.safe_load_all(yaml_block))
        except yaml.YAMLError as e:
            line_offset = content[:match.start(1)].count("\n")
            line_no = line_offset + 1
            if getattr(e, "problem_mark", None) is not None:
                line_no = line_offset + int(e.problem_mark.line) + 1
            errors.append(f"INVALID_YAML: line {line_no}: {e}")

    # 4) Evidence mapping against fact ledger
    claims = fact_ledger.get("claims", []) if isinstance(fact_ledger, dict) else []
    supported_ledger_texts: list[str] = []
    for claim in claims:
        if not isinstance(claim, dict):
            continue
        claim_id = claim.get("id", "?")
        status = str(claim.get("status", "")).upper()
        current_truth = claim.get("current_truth")
        statement = claim.get("claim") or current_truth or ""

        if status in {"SUPPORTED", "VERIFIED"}:
            if isinstance(current_truth, str) and current_truth.strip():
                supported_ledger_texts.append(current_truth.strip())
            if isinstance(claim.get("claim"), str) and claim.get("claim", "").strip():
                supported_ledger_texts.append(claim.get("claim", "").strip())
            if (isinstance(statement, str) and statement.strip()
                    and not _contains_with_tolerance(content, statement)):
                warnings.append(f"MISSING_SUPPORTED_CLAIM: claim {claim_id}")

        if (status == "CONFLICTING" and isinstance(statement, str) and statement.strip()
                and _is_unhedged_claim_assertion(content, statement)):
            errors.append(f"UNHEDGED_CONFLICT: claim {claim_id}")
        if (status == "UNVERIFIED" and isinstance(statement, str) and statement.strip()
                and _is_unhedged_claim_assertion(content, statement)):
            errors.append(f"UNHEDGED_UNVERIFIED: claim {claim_id}")

    # 5) Reverse evidence mapping: content claims should map to supported
    # ledger facts. Downgraded to WARNING because the topic-based ledger
    # can't anticipate all sub-topics the writer covers. A content-aware
    # ledger regeneration pass would make this a hard error again.
    for extracted in _extract_factual_claim_candidates(content):
        if not _claim_maps_to_supported_ledger(extracted, supported_ledger_texts):
            warnings.append(f"UNMAPPED_CLAIM: {extracted}")

    return len(errors) == 0, errors + warnings


def step_check(content: str, path: Path) -> tuple[bool, list]:
    """Run all deterministic checks on the improved content."""
    print("\n  CHECK: running deterministic checks")

    # Safety guard: reject truncated content (Gemini output limit)
    original = path.read_text()
    if len(content) < len(original) * 0.85:
        print(f"  ✗ CHECK: content truncated — {len(content)} chars vs {len(original)} original (< 85%)")
        return False, []

    # Safety guard: validate YAML frontmatter before writing
    if not content.startswith("---"):
        print("  ✗ CHECK: missing YAML frontmatter delimiter")
        return False, []
    parts = content.split("---", 2)
    if len(parts) < 3:
        print("  ✗ CHECK: malformed frontmatter — no closing ---")
        return False, []
    try:
        fm = yaml.safe_load(parts[1])
        if not isinstance(fm, dict) or "title" not in fm:
            print("  ✗ CHECK: frontmatter missing 'title' field")
            return False, []
    except yaml.YAMLError as e:
        print(f"  ✗ CHECK: broken YAML frontmatter — {e}")
        return False, []

    # Language guard: reject Ukrainian content in EN files (and vice versa)
    is_uk = "/uk/" in str(path)
    has_cyrillic_title = bool(re.search(r'^title:.*[а-яіїєґ]', parts[1], re.MULTILINE))
    has_uk_slug = bool(re.search(r'^slug:\s*uk/', parts[1], re.MULTILINE))
    has_en_commit = "en_commit:" in parts[1]
    if not is_uk and (has_cyrillic_title or has_uk_slug or has_en_commit):
        print("  ✗ CHECK: Ukrainian content in EN file (title/slug/en_commit detected)")
        return False, []
    if is_uk and not has_cyrillic_title and not has_en_commit:
        print("  ✗ CHECK: English content in UK file (no Cyrillic title or en_commit)")
        return False, []

    # Asset preservation check: compare original vs improved
    original_assets = count_assets(original)
    new_assets = count_assets(content)
    for asset_type, orig_count in original_assets.items():
        if orig_count > 0:
            new_count = new_assets.get(asset_type, 0)
            loss_pct = (orig_count - new_count) / orig_count * 100
            if loss_pct >= 20:
                print(f"  ✗ CHECK: {asset_type} lost {loss_pct:.0f}% ({orig_count} → {new_count})")
                return False, []

    is_uk = "/uk/" in str(path)
    results = structural.run_all(content, path)
    if is_uk:
        results.extend(ukrainian.run_all(content, path))

    errors = [r for r in results if not r.passed and r.severity == "ERROR"]

    for r in results:
        if not r.passed:
            print(r)

    passed = len(errors) == 0
    print(f"  {'✓' if passed else '✗'} CHECK: {len(errors)} errors, "
          f"{len([r for r in results if not r.passed and r.severity == 'WARNING'])} warnings")

    return passed, results


# ---------------------------------------------------------------------------
# Full pipeline: run one module through all steps
# ---------------------------------------------------------------------------

def run_module(module_path: Path, state: dict, max_retries: int | None = None,
               models: dict | None = None, dry_run: bool = False,
               refresh_fact_ledger: bool = False,
               write_only: bool = False) -> bool:
    """Run a single module through the full pipeline.

    If write_only=True, skip fact-ledger, review, and checks — just draft
    the content and save. Used for bulk content creation before review pass.
    """
    max_retries = _resolve_max_retries(max_retries)
    m = models or MODELS
    key = module_key_from_path(module_path)
    had_pre_run_state = key in (state.get("modules") or {})
    pre_run_ms = copy.deepcopy((state.get("modules") or {}).get(key))
    ms = get_module_state(state, key)
    ms["errors"] = []
    review_fact_ledger = ms.get("fact_ledger")
    rubric_profile = load_rubric_profile_for_module(module_path)
    staging_path = module_path.with_suffix(".staging.md")
    pre_run_staging = staging_path.read_text() if staging_path.exists() else None
    rewrite_baseline = module_path.read_text()
    citation_seed_path = _citation_seed_path(key)
    citation_gate_enabled = bool(
        citation_seed_path
        and citation_seed_path.exists()
        and _matching_seed_lines(citation_seed_path, key)
    )
    citation_retry_limit = min(max_retries, 3)

    def restore_pre_run_state() -> None:
        modules = state.setdefault("modules", {})
        if had_pre_run_state and pre_run_ms is not None:
            modules[key] = copy.deepcopy(pre_run_ms)
        else:
            modules.pop(key, None)
        if pre_run_staging is None:
            staging_path.unlink(missing_ok=True)
        else:
            _atomic_write_text(staging_path, pre_run_staging)
        save_state(state)

    print(f"\n{'='*60}")
    print(f"  PIPELINE: {key}{'  [DRY RUN]' if dry_run else ''}")
    print(f"  Current phase: {ms['phase']}")
    print(f"{'='*60}")

    def emit_audit(event: str, **fields) -> Path | None:
        if dry_run:
            return None
        if write_only and event != "WRITE":
            return None
        return append_review_audit(module_path, event, **fields)

    # Already-done resumption. If the module is flagged for independent
    # re-review (typically a same-family fallback approve when both Codex and
    # Claude were unavailable), reset to review so the current on-disk content
    # gets an independent pass without forcing a rewrite.
    if ms["phase"] == "done":
        if ms.get("needs_independent_review"):
            print("  ↻ Flagged needs_independent_review — resetting to review for independent re-review")
            ms["phase"] = "review"
            save_state(state)
            # fall through to resume block below
        else:
            reviewer = ms.get("reviewer", "unknown")
            total = ms.get("sum", "?")
            print(f"  ✓ Already done: {total}/40 reviewer={reviewer} — skipping")
            return True

    if ms["phase"] == "data_conflict" and not refresh_fact_ledger:
        print("  ✋ Module blocked in data_conflict phase — rerun with --refresh-fact-ledger after manual triage")
        return False
    if ms["phase"] == "data_conflict" and refresh_fact_ledger:
        ms["phase"] = "pending"
        save_state(state)

    # Peak-hours pause resume. A module paused mid-targeted-fix has its
    # staged draft on disk and its plan saved in state. Transition
    # back to phase=write so the resume branch below loads them correctly
    # and re-enters the write→review loop at the targeted-fix step (no
    # re-initial-write, no re-review).
    if ms["phase"] == "needs_targeted_fix":
        if staging_path.exists() and ms.get("plan"):
            print("  ↻ Resuming targeted fix from peak-hours pause")
            ms["phase"] = "write"
            save_state(state)
        else:
            print("  ⚠ needs_targeted_fix phase but staging/plan missing — restarting from initial write")
            ms["phase"] = "pending"
            _clear_resume_metadata(ms, staging_path)
            save_state(state)

    # Phase 0: split-reviewer fact ledger (issue #225).
    # Model selection rationale is pinned by calibration data in:
    # docs/research/fact-grounding-calibration-2026-04-12.md
    if not dry_run and not write_only:
        fact_model = m.get("fact_grounding", MODELS["fact_grounding"])
        fact_family = _model_family(fact_model)
        if fact_family not in INDEPENDENT_REVIEWER_FAMILIES:
            ms["errors"].append(
                f"Configured fact grounding model is not independent: {fact_model}"
            )
            save_state(state)
            return False

        ledger_result = ensure_fact_ledger(
            module_path,
            ms,
            model=fact_model,
            refresh=refresh_fact_ledger,
        )
        if ledger_result is None or (
            isinstance(ledger_result, dict) and ledger_result.get("rate_limited")
        ):
            fallback_model = m.get("fact_fallback", MODELS["fact_fallback"])
            fallback_family = _model_family(fallback_model)
            if fallback_family not in INDEPENDENT_REVIEWER_FAMILIES:
                ms["errors"].append(
                    f"Configured fact fallback model is not independent: {fallback_model}"
                )
                save_state(state)
                return False
            print(f"  ⚠ {fact_model} unavailable for FACT LEDGER — falling back to {fallback_model}")
            ledger_result = ensure_fact_ledger(
                module_path,
                ms,
                model=fallback_model,
                refresh=refresh_fact_ledger,
            )

        if not isinstance(ledger_result, dict) or ledger_result.get("rate_limited"):
            ms["errors"].append("FACT LEDGER generation failed")
            save_state(state)
            return False

        ms["fact_ledger"] = ledger_result
        review_fact_ledger = ledger_result
        save_state(state)

    # Initial write plan. Legacy `phase="audit"` states from older runs are
    # treated the same as fresh `pending` modules: start a normal first-pass
    # write with the generic plan and let REVIEW produce the real follow-up
    # plan if the draft is rejected.
    if ms["phase"] in ("pending", "audit"):
        plan = initial_write_plan(key)
        if dry_run:
            print(f"\n  [DRY RUN] Initial write plan: {plan}")
            return False
        _clear_resume_metadata(ms, staging_path)
        ms["severity"] = None
        ms["checks_failed"] = []
        ms["reviewer_schema_version"] = 3
        ms["passes"] = False
        ms["phase"] = "write"
        ms["last_run"] = datetime.now(UTC).isoformat()
        save_state(state)
        improved = None
        last_good = None
        targeted_fix = False
    else:
        # Resuming. Two flavors:
        # 1. Peak-hours pause resume: state has `plan` + staging file from
        #    the previous run's Gemini draft. Load them and jump straight
        #    back into the retry loop at the targeted-fix step (no re-initial-
        #    write, no re-review — we already have the plan).
        # 2. Direct-review resume: review the current on-disk content.
        # 3. Generic resume (interrupted mid-loop in a non-Claude run):
        #    fall back to a generic "Resume improvement" plan.
        if ms.get("plan") and staging_path.exists():
            plan = ms["plan"]
            improved = staging_path.read_text()
            last_good = improved
            targeted_fix = ms.get("targeted_fix", False)
            mode = "targeted fix" if targeted_fix else "improve"
            print(f"  Loaded staged content ({len(improved)} chars) and saved {mode} plan")
        elif ms["phase"] in ("review", "citation"):
            # On a fresh resume at phase=review, prefer the staging file if
            # present — it holds the most recent patched content from either
            # a deterministic edit apply or an in-memory LLM write that
            # hadn't reached CHECK yet. Only fall back to on-disk module
            # content if no staging file exists (first-time entry at review).
            plan = initial_write_plan(key)
            if staging_path.exists():
                improved = staging_path.read_text()
                print(f"  Loaded staged content ({len(improved)} chars) for review (resume after deterministic apply or pre-CHECK crash)")
            else:
                improved = module_path.read_text()
                print(f"  Loaded on-disk content ({len(improved)} chars) for {ms['phase']}")
            last_good = improved
            targeted_fix = False
        else:
            failed = ms.get("checks_failed") or []
            failed_ids = ", ".join(c.get("id", "?") for c in failed) if failed else "unknown"
            plan = f"Resume improvement. Last failed checks: {failed_ids}."
            improved = None
            last_good = None
            targeted_fix = False

    # WRITE → REVIEW loop (max retries)
    # Auto-detect rewrite mode from the binary gate's severity signal on
    # the previous review. severe → full rewrite; anything else → normal
    # improve/targeted-fix path. `improved`, `last_good`, and
    # `targeted_fix` are initialized above by the initial-write or resume
    # branches; DO NOT re-initialize here or targeted-fix resume state
    # will be lost.
    prior_severity = ms.get("severity")
    needs_rewrite = prior_severity == "severe"
    if needs_rewrite and targeted_fix:
        # Full rewrites must never inherit a stale targeted-fix route from a
        # prior iteration or resume snapshot.
        targeted_fix = False
        ms["targeted_fix"] = False
        save_state(state)
    if needs_rewrite:
        failed_ids = [c.get("id", "?") for c in (ms.get("checks_failed") or [])]
        print(f"  Prior severity=severe (failed: {failed_ids}) — using REWRITE mode")

    for attempt in range(max_retries + 1):
        if ms["phase"] in ("write",):
            # Any resume content needed for this attempt was loaded above.
            # Drop the sibling staging file now so a fresh write attempt
            # cannot inherit or strand an orphaned draft on disk.
            staging_path.unlink(missing_ok=True)
            review_fact_ledger = ms.get("fact_ledger")
            writer_model = m["write_targeted"] if targeted_fix else m["write"]
            # Severe rewrites must preserve assets from the stable on-disk
            # baseline, not from the latest rejected in-memory draft.
            write_source = rewrite_baseline if needs_rewrite else last_good
            write_started = datetime.now(UTC)
            try:
                # knowledge_card is intentionally not passed to the writer:
                # fact_ledger is the sole authoritative grounding source.
                improved = step_write(module_path, plan, model=writer_model,
                                      rewrite=needs_rewrite,
                                      previous_output=write_source,
                                      knowledge_card=None,
                                      fact_ledger=ms.get("fact_ledger"))
            except ClaudeUnavailableError as e:
                # Peak hours / rate limit / budget exhausted on Claude. Pause
                # this module cleanly so it resumes at the targeted-fix step
                # on the next run outside peak hours, WITHOUT re-running
                # audit, initial write, or initial review:
                #
                # - Stage `last_good` (the latest Gemini draft from the
                #   initial write or prior retry) to <module>.staging.md
                # - Save the targeted-fix `plan` to ms["plan"]
                # - Save the `targeted_fix` flag so the resume path routes
                #   the writer to Claude
                # - Set phase=needs_targeted_fix as a pause marker
                # - Return True so the batch runner moves on cleanly
                print(f"\n  ⏸ PAUSED (Claude unavailable): {e}")
                print("  Progress preserved — will resume at targeted-fix step on next run.")
                staging_path = module_path.with_suffix(".staging.md")
                if last_good:
                    _atomic_write_text(staging_path, last_good)
                    print(f"  Staged {len(last_good)} chars to {staging_path.name}")
                else:
                    print("  ⚠ No last_good content to stage — resume will restart from the initial write")
                ms["phase"] = "needs_targeted_fix"
                ms["plan"] = plan
                ms["targeted_fix"] = targeted_fix
                ms["paused_reason"] = str(e)
                ms["last_run"] = datetime.now(UTC).isoformat()
                save_state(state)
                return True
            if improved is None:
                ms["errors"].append(f"Write failed attempt {attempt+1}")
                save_state(state)
                if attempt < max_retries:
                    continue
                return False
            last_good = improved
            if citation_gate_enabled:
                _atomic_write_text(staging_path, improved)

            ms["phase"] = "citation" if citation_gate_enabled else "review"
            save_state(state)
            emit_audit(
                "WRITE",
                writer=writer_model,
                mode=("rewrite" if needs_rewrite else
                      "targeted fix" if targeted_fix else "write"),
                duration=(datetime.now(UTC) - write_started).total_seconds(),
                plan=plan,
                output_chars=len(improved),
            )

            # Write-only mode: save the draft and stop. No fact-ledger,
            # no review, no checks. Used for bulk content creation.
            if write_only:
                _atomic_write_text(module_path, improved)
                ms["phase"] = "review"
                ms["last_run"] = datetime.now(UTC).isoformat()
                save_state(state)
                print(f"  ✓ WRITE-ONLY: {len(improved)} chars written to {module_path.name}")
                # git commit the draft
                try:
                    _git_stage_and_commit(
                        [str(module_path)],
                        f"chore(content): write-only draft [{module_key_from_path(module_path)}]",
                        timeout=30,
                    )
                    print("  Committed draft")
                except Exception:
                    logger.exception("Draft commit failed; continuing with saved draft", exc_info=False)
                return True

        if ms["phase"] == "citation":
            citation = step_check_citations(staging_path, citation_seed_path)
            if citation["passes"]:
                ms["phase"] = "review"
                save_state(state)
            else:
                reasons = []
                if citation["citation_count"] < 3:
                    reasons.append(
                        f"- Add at least 3 inline citations and source links "
                        f"(found {citation['citation_count']})."
                    )
                if citation["missing_seed_urls"]:
                    reasons.append(
                        "- Cite every required seed URL inline and in `## Sources`:\n  - "
                        + "\n  - ".join(citation["missing_seed_urls"])
                    )
                if citation["dead_urls"]:
                    reasons.append(
                        "- Remove or replace dead citation URLs:\n  - "
                        + "\n  - ".join(citation["dead_urls"])
                    )
                other_issues = [
                    issue for issue in citation["issues"]
                    if issue not in {"missing_seed_urls", "dead_urls", "needs_at_least_3_citations"}
                ]
                reasons.extend(f"- Resolve citation checker issue: {issue}" for issue in other_issues)
                plan = (
                    "CITATION GATE FAILED. Improve the current draft so it passes "
                    "the deterministic citation gate before review.\n\n"
                    "Fix all of the following:\n"
                    + "\n".join(reasons)
                )
                needs_rewrite = False
                targeted_fix = False
                ms["plan"] = plan
                ms["targeted_fix"] = False
                ms["severity"] = None
                ms["checks_failed"] = []
                ms["phase"] = "write"
                save_state(state)
                if attempt < citation_retry_limit:
                    print(f"  ↻ Citation gate failed, retrying WRITE ({attempt+1}/{citation_retry_limit})")
                    continue
                print("  ❌ Citation gate failed after 3 retries — restoring pre-run state")
                restore_pre_run_state()
                return False

        if ms["phase"] == "review":
            # Content-aware fact ledger: verify claims actually made in the
            # written content. Regenerated each iteration so rejected-draft
            # claims stay transient — only the APPROVE branch merges them
            # back into ms["fact_ledger"] (persistent). Generated here (not
            # under phase=write) so re-review after a clean deterministic
            # apply picks up the revised content's claims. See #235.
            content_ledger = None
            review_fact_ledger = ms.get("fact_ledger")
            if improved and not dry_run:
                fact_model = m.get("fact_grounding", MODELS["fact_grounding"])
                content_ledger = step_content_aware_fact_ledger(
                    module_path, improved, model=fact_model
                )
                if content_ledger is None:
                    fallback_model = m.get("fact_fallback", MODELS["fact_fallback"])
                    if fallback_model != fact_model:
                        content_ledger = step_content_aware_fact_ledger(
                            module_path, improved, model=fallback_model
                        )
                if content_ledger is not None:
                    n_conflict, n_unverified = _count_fact_ledger_issues(content_ledger)
                    if (n_conflict >= DATA_CONFLICT_CONFLICT_THRESHOLD or
                            n_unverified >= DATA_CONFLICT_UNVERIFIED_THRESHOLD):
                        _atomic_write_text(staging_path, improved)
                        ms["phase"] = "data_conflict"
                        ms["errors"].append(
                            f"DATA_CONFLICT: {n_conflict} conflicting + {n_unverified} "
                            f"unverified claims in drafted content — manual triage required"
                        )
                        save_state(state)
                        return False
                    review_fact_ledger = (
                        _merge_fact_ledgers(ms.get("fact_ledger"), content_ledger)
                        or ms.get("fact_ledger")
                    )

            content_for_integrity = improved or module_path.read_text()
            integrity_passed, integrity_messages = step_check_integrity(
                content_for_integrity, review_fact_ledger or ms.get("fact_ledger") or {}
            )
            if not integrity_passed:
                integrity_errors = [
                    msg for msg in integrity_messages
                    if not any(msg.startswith(prefix) for prefix in INTEGRITY_WARNING_PREFIXES)
                ]
                needs_rewrite = True
                targeted_fix = False
                plan = (
                    "SEVERE REWRITE REQUIRED. Tier-1 integrity gate failed before "
                    "structural review. Rewrite the module and resolve every "
                    "integrity error.\n\nIntegrity errors:\n"
                )
                for msg in integrity_errors:
                    plan += f"\n- {msg}"
                ms["plan"] = plan
                ms["targeted_fix"] = False
                ms["severity"] = "severe"
                ms["checks_failed"] = [{"id": "INTEGRITY", "evidence": msg} for msg in integrity_errors]
                ms["reviewer_schema_version"] = 3
                ms.pop("scores", None)
                ms.pop("sum", None)
                ms.pop("sonnet_anchor_failures", None)
                if improved is not None:
                    _atomic_write_text(staging_path, improved)
                ms["phase"] = "write"
                save_state(state)
                emit_audit("INTEGRITY_FAIL", errors=integrity_errors)
                print("  ⚠ Tier-1 integrity gate failed — routing to severe rewrite")
                if attempt < max_retries:
                    continue
                ms["errors"].append("Integrity gate failed after max retries")
                return False

            review_started = datetime.now(UTC)
            reviewer_model = m["review"]
            used_fallback_reviewer = False
            needs_independent_review_if_approved = False
            review = step_review(
                module_path,
                improved or module_path.read_text(),
                model=reviewer_model,
                fact_ledger=review_fact_ledger,
            )

            # Structural reviewer rate-limit degradation:
            # 1. Try primary structural reviewer.
            # 2. If unavailable, try configured fallback.
            # 3. If both unavailable, use writer model as last resort.
            if isinstance(review, dict) and review.get("rate_limited"):
                fallback_model = m.get("review_fallback", MODELS["review_fallback"])
                writer_family = _model_family(m["write"])
                fallback_family = _model_family(fallback_model)
                fallback_allowed = True
                if fallback_family == writer_family:
                    print("  ⚠ Primary reviewer rate-limited and fallback matches writer family — skipping to last resort")
                    fallback_allowed = False
                elif fallback_family not in INDEPENDENT_REVIEWER_FAMILIES:
                    print(f"  ⚠ Review fallback {fallback_model} is not in approved independent families — skipping to last resort")
                    fallback_allowed = False

                if fallback_allowed:
                    print(f"  ⚠ {reviewer_model} rate-limited — falling back to {fallback_model}")
                    review = step_review(
                        module_path,
                        improved or module_path.read_text(),
                        model=fallback_model,
                        fact_ledger=review_fact_ledger,
                    )
                    if review is None:
                        ms["errors"].append("Fallback reviewer failed")
                        save_state(state)
                        return False
                    if not isinstance(review, dict) or not review.get("rate_limited"):
                        reviewer_model = fallback_model
                        used_fallback_reviewer = True

                if not fallback_allowed or (isinstance(review, dict) and review.get("rate_limited")):
                    last_resort_model = m["write"]
                    print(
                        f"  ⚠ {reviewer_model} and {fallback_model} unavailable — "
                        f"last-resort review with {last_resort_model}; module will "
                        f"require later independent re-review if approved"
                    )
                    review = step_review(
                        module_path,
                        improved or module_path.read_text(),
                        model=last_resort_model,
                        fact_ledger=review_fact_ledger,
                    )
                    if review is None:
                        ms["errors"].append("Last-resort reviewer failed")
                        save_state(state)
                        return False
                    if isinstance(review, dict) and review.get("rate_limited"):
                        ms["errors"].append("Primary, fallback, and last-resort reviewers all unavailable")
                        save_state(state)
                        emit_audit(
                            "REVIEW",
                            verdict="FAILED",
                            reviewer=last_resort_model,
                            attempt=f"{attempt+1}/{max_retries+1}",
                            severity="failed",
                            duration=(datetime.now(UTC) - review_started).total_seconds(),
                            checks=[],
                            feedback="Primary, fallback, and last-resort reviewers all unavailable.",
                            reviewer_fallback_used=True,
                        )
                        return False
                    reviewer_model = last_resort_model
                    used_fallback_reviewer = True
                    needs_independent_review_if_approved = True

            if review is None:
                ms["errors"].append(f"Review failed attempt {attempt+1}")
                ms["phase"] = "write"
                save_state(state)
                if attempt < max_retries:
                    continue
                return False

            review_verdict = review.get("verdict", "REJECT")
            review_checks_raw = review.get("checks")
            review_edits_raw = review.get("edits")
            review_checks = review_checks_raw if isinstance(review_checks_raw, list) else []
            review_severity = compute_review_payload_severity(review, rubric_profile)

            maybe_sample_second_reviewer(
                key,
                module_path,
                improved or module_path.read_text(),
                review,
                fact_ledger=review_fact_ledger,
            )

            if review_verdict == "APPROVE" and review_severity == "clean":
                # Binary gate: on APPROVE, the module's state records that
                # every check passed. Per Gemini pair-review critique B, we
                # ignore any `edits` returned alongside an APPROVE — an
                # approval is an immutable snapshot. If the reviewer wants
                # changes, it must REJECT with severity=targeted.
                if content_ledger is not None:
                    ms["fact_ledger"] = (
                        _merge_fact_ledgers(ms.get("fact_ledger"), content_ledger)
                        or ms.get("fact_ledger")
                    )
                ms["severity"] = "clean"
                ms["checks_failed"] = []
                ms["reviewer_schema_version"] = 3
                # Drop any legacy score fields so cmd_status renders the new
                # binary-gate view, not the old [D1..D8] vector.
                ms.pop("scores", None)
                ms.pop("sum", None)
                ms["check_failures"] = 0
                # Circuit breaker is a CONSECUTIVE counter — reset it on
                # any path that re-establishes a good state (APPROVE or
                # 100% deterministic apply). Without this reset, one past
                # partial-apply event poisons every future retry until
                # the module exits the pipeline (Gemini + Codex PR review
                # both flagged this as a hot-path routing bug).
                ms.pop("sonnet_anchor_failures", None)
                reviewer_family = _model_family(reviewer_model)
                ms["reviewer"] = reviewer_family
                ms["needs_independent_review"] = needs_independent_review_if_approved
                ms["phase"] = "check"
                save_state(state)
                emit_audit(
                    "REVIEW",
                    verdict=review_verdict,
                    reviewer=reviewer_model,
                    attempt=f"{attempt+1}/{max_retries+1}",
                    severity=ms["severity"],
                    duration=(datetime.now(UTC) - review_started).total_seconds(),
                    checks=review_checks,
                    feedback=review.get("feedback", ""),
                    reviewer_fallback_used=used_fallback_reviewer,
                )
                break
            else:
                # REJECT — binary-gate routing based on code-computed severity.
                # Per Gemini pair-review critique A ("code as arbiter"), we
                # ALWAYS recompute severity from the actual checks + edits,
                # even if the reviewer self-reported one. step_review also
                # sets this field, but computing again here makes run_module
                # robust to mocks and alternative reviewer code paths.
                r_feedback = review.get("feedback", "")
                r_checks = review_checks
                r_edits = review_edits_raw if isinstance(review_edits_raw, list) else []
                failed_checks = [c for c in r_checks if isinstance(c, dict) and not c.get("passed")]
                failed_ids = [c.get("id", "?") for c in failed_checks]
                r_valid = _has_valid_review_checks(review_checks_raw)
                r_severity = review_severity

                # Deterministic edit application — identical machinery as
                # before (PR #221/222), but gated on severity instead of
                # numeric sum. Applies for targeted severity with edits.
                content_before = improved if improved is not None else module_path.read_text()
                if r_valid and r_severity == "targeted" and r_edits:
                    patched, applied, failed_edits = apply_review_edits(content_before, r_edits)
                    total_edits = len(r_edits)
                    applied_count = len(applied)
                    failed_count = len(failed_edits)
                    print(f"  → Deterministic apply: {applied_count}/{total_edits} edits landed, {failed_count} failed")
                    if failed_edits:
                        for fe in failed_edits[:5]:
                            print(f"    ✗ {fe.get('reason', '?')}")
                        if len(failed_edits) > 5:
                            print(f"    ... and {len(failed_edits) - 5} more failed")

                    if applied_count > 0 and failed_count == 0:
                        # 100% success — re-review the patched content with
                        # no LLM writer call. Atomic staging write survives
                        # SIGKILL so a crash between here and CHECK doesn't
                        # lose the patch.
                        improved = patched
                        last_good = improved
                        staging_path = module_path.with_suffix(".staging.md")
                        _atomic_write_text(staging_path, patched)
                        ms["severity"] = "targeted"
                        ms["checks_failed"] = [{"id": c.get("id"), "evidence": c.get("evidence", "")} for c in failed_checks]
                        ms["reviewer_schema_version"] = 3
                        ms.pop("scores", None)
                        ms.pop("sum", None)
                        # Circuit breaker reset on 100% apply — see comment
                        # on the APPROVE branch for the rationale.
                        ms.pop("sonnet_anchor_failures", None)
                        ms["phase"] = "review"
                        save_state(state)
                        emit_audit(
                            "REVIEW",
                            verdict=review.get("verdict", "REJECT"),
                            reviewer=reviewer_model,
                            attempt=f"{attempt+1}/{max_retries+1}",
                            severity=ms["severity"],
                            duration=(datetime.now(UTC) - review_started).total_seconds(),
                            checks=r_checks,
                            feedback=r_feedback,
                            reviewer_fallback_used=used_fallback_reviewer,
                        )
                        print(f"  ✓ All {applied_count} edits applied cleanly — re-reviewing (no LLM writer call, staged to {staging_path.name})")
                        if attempt < max_retries:
                            continue
                        print("  ⚠ Max retries reached with staged deterministic edits — leaving phase=review for resume")
                        return True
                    elif applied_count > 0 and failed_count > 0:
                        # Partial — apply what worked, fall back to Sonnet
                        # for the remaining edits.
                        improved = patched
                        last_good = improved
                        staging_path = module_path.with_suffix(".staging.md")
                        _atomic_write_text(staging_path, patched)
                        needs_rewrite = False
                        targeted_fix = True
                        failed_blocks = []
                        for fe in failed_edits:
                            edit_payload = fe.get("edit", {})
                            reason = fe.get("reason", "?")
                            try:
                                edit_json = json.dumps(edit_payload, indent=2, ensure_ascii=False)
                            except (TypeError, ValueError):
                                edit_json = repr(edit_payload)
                            failed_blocks.append(
                                f"Failed edit (reason: {reason}):\n```json\n{edit_json}\n```"
                            )
                        failed_text = "\n\n".join(failed_blocks)
                        plan = (
                            f"FALLBACK FIX. The pipeline applied {applied_count} of {total_edits} "
                            f"structured edits deterministically; the remaining {failed_count} "
                            f"could not be applied mechanically (anchor not found, ambiguous, "
                            f"or overlapping). Apply ONLY these remaining edits, preserving "
                            f"everything else verbatim. Each failed edit below includes its "
                            f"exact find/new payload — apply them literally where the anchors "
                            f"appear in the current content.\n\n"
                            f"Failed binary checks: {', '.join(failed_ids)}\n\n"
                            f"{failed_text}\n\n"
                            f"Reviewer's qualitative notes (prose, not covered by structured edits):\n{r_feedback}"
                        )
                        ms["plan"] = plan
                        ms["targeted_fix"] = True
                        ms["severity"] = "targeted"
                        ms["checks_failed"] = [{"id": c.get("id"), "evidence": c.get("evidence", "")} for c in failed_checks]
                        ms["reviewer_schema_version"] = 3
                        ms.pop("scores", None)
                        ms.pop("sum", None)
                        ms["phase"] = "write"
                        print(f"  → Sonnet fallback for {failed_count} failed edits (partial progress staged + plan persisted)")
                        # Circuit breaker (Gemini pair-review critique D):
                        # count consecutive Sonnet anchor-failure rounds and
                        # escalate to severe rewrite if Sonnet also can't
                        # land the patch on the same check IDs.
                        ms["sonnet_anchor_failures"] = ms.get("sonnet_anchor_failures", 0) + 1
                        if ms["sonnet_anchor_failures"] >= 2:
                            print(f"  ⚠ Circuit breaker: {ms['sonnet_anchor_failures']} consecutive anchor failures — escalating to severe rewrite")
                            r_severity = "severe"
                            ms["severity"] = "severe"
                            ms.pop("sonnet_anchor_failures", None)
                            # Fall through to the severe rewrite block below
                            # instead of looping the partial-apply path.
                        else:
                            save_state(state)
                            emit_audit(
                                "REVIEW",
                                verdict=review.get("verdict", "REJECT"),
                                reviewer=reviewer_model,
                                attempt=f"{attempt+1}/{max_retries+1}",
                                severity=ms["severity"],
                                duration=(datetime.now(UTC) - review_started).total_seconds(),
                                checks=r_checks,
                                feedback=r_feedback,
                                reviewer_fallback_used=used_fallback_reviewer,
                            )
                            if attempt < max_retries:
                                continue
                            print("  ⚠ Max retries reached after partial deterministic apply — leaving phase=write for resume")
                            break
                    else:
                        # 0/N — reviewer anchors don't match. Escalate to
                        # severe rewrite (a fresh reviewer pass should
                        # produce fresh anchors against the same content).
                        print("  ⚠ Zero edits applied deterministically — escalating to severe rewrite")
                        r_severity = "severe"

                # Non-deterministic paths below: severe rewrite, or invalid
                # review output.
                if not r_valid:
                    needs_rewrite = True
                    targeted_fix = False
                    plan = (
                        "REVIEW OUTPUT INVALID. Rewrite the module from "
                        f"scratch and resolve these issues.\n\nReviewer feedback:\n{r_feedback}"
                    )
                    print("  ⚠ Review returned no valid checks — using full rewrite")
                elif r_severity == "severe":
                    needs_rewrite = True
                    targeted_fix = False
                    ms.pop("sonnet_anchor_failures", None)
                    plan = (
                        f"SEVERE REWRITE REQUIRED. The binary quality gate flagged "
                        f"{len(failed_checks)} failed checks ({', '.join(failed_ids)}) and "
                        f"the pipeline could not repair them via structured edits. "
                        f"Rewrite the module from scratch, addressing EVERY failed check "
                        f"explicitly while preserving all preserved content, labs, quizzes, "
                        f"and diagrams from the original.\n\n"
                        f"Failed checks and evidence:\n"
                    )
                    for c in failed_checks:
                        ev = c.get("evidence", "(no evidence)")
                        plan += f"\n- {c.get('id')}: {ev}"
                    plan += f"\n\nReviewer's full feedback:\n{r_feedback}"
                    print(f"  → Severe rewrite mode (Gemini): {len(failed_checks)} failed checks: {failed_ids}")
                else:
                    # Reached only via severity=targeted but no edits at all
                    # (compute_severity would have returned severe, so this
                    # is belt-and-suspenders). Fall back to severe.
                    needs_rewrite = True
                    targeted_fix = False
                    plan = (
                        f"INCONCLUSIVE REVIEW. Binary gate failed {len(failed_checks)} checks "
                        f"({', '.join(failed_ids)}) but no actionable edits were provided. "
                        f"Rewrite the module from scratch.\n\nReviewer feedback:\n{r_feedback}"
                    )
                    print(f"  → Catch-all rewrite mode (Gemini): {len(failed_checks)} failed checks, no edits")

                # Persist state for crash recovery: the rejection branch's
                # plan + targeted_fix + severity + failed checks must all
                # land in state so resume can reconstruct writer routing.
                ms["plan"] = plan
                ms["targeted_fix"] = targeted_fix
                ms["severity"] = r_severity
                ms["checks_failed"] = [{"id": c.get("id"), "evidence": c.get("evidence", "")} for c in failed_checks]
                ms["reviewer_schema_version"] = 3
                ms.pop("scores", None)
                ms.pop("sum", None)
                # Stage the current improved content so resume loads it as
                # previous_output rather than re-reading the unpatched
                # on-disk module. Deterministic branches already stage above.
                if improved is not None:
                    staging_path = module_path.with_suffix(".staging.md")
                    _atomic_write_text(staging_path, improved)
                ms["phase"] = "write"
                save_state(state)
                emit_audit(
                    "REVIEW",
                    verdict=review.get("verdict", "REJECT"),
                    reviewer=reviewer_model,
                    attempt=f"{attempt+1}/{max_retries+1}",
                    severity=ms["severity"],
                    duration=(datetime.now(UTC) - review_started).total_seconds(),
                    checks=r_checks,
                    feedback=r_feedback,
                    reviewer_fallback_used=used_fallback_reviewer,
                )
                if attempt < max_retries:
                    print(f"  ↻ Rejected, retrying ({attempt+1}/{max_retries})")
                    continue
                else:
                    print(f"  ❌ Rejected after {max_retries} retries")
                    ms["errors"].append(f"Review rejected {max_retries+1} times")
                    return False

    # CHECK
    if ms["phase"] == "check":
        # Load improved content from staging file if resuming
        staging = module_path.with_suffix(".staging.md")
        if improved:
            _atomic_write_text(staging, improved)
        elif staging.exists():
            improved = staging.read_text()
            print("  Resuming CHECK from staging file")
        else:
            print("  ❌ No improved content available for CHECK")
            return False

        results = []
        for check_attempt in range(max_retries + 1):
            check_started = datetime.now(UTC)
            passed, results = step_check(improved, module_path)
            if passed:
                break

            emit_audit(
                "CHECK_FAIL",
                duration=(datetime.now(UTC) - check_started).total_seconds(),
                failed_checks=_render_check_failures(results),
            )
            if check_attempt < max_retries:
                print(f"  ↻ CHECK failed, retrying ({check_attempt+1}/{max_retries})")
                continue

            ms["errors"].append("Deterministic checks failed after review")
            ms["check_failures"] = ms.get("check_failures", 0) + 1
            ms["targeted_fix"] = False
            save_state(state)
            # Keep staging file so we can resume after fixing thresholds
            print(f"  Staging file kept: {staging}")
            return False

        # Backup original, then atomically swap in the improved file. Using
        # _atomic_write_text guarantees the module file is either the old or
        # new content — never a half-written truncation — if the process is
        # killed mid-write.
        backup = module_path.with_suffix(".md.bak")
        shutil.copy2(module_path, backup)
        _atomic_write_text(module_path, improved)
        staging.unlink(missing_ok=True)
        backup.unlink(missing_ok=True)  # remove backup on success
        print(f"  ✓ File written: {module_path}")

        ms["check_failures"] = 0
        ms["phase"] = "score"
        save_state(state)
        warnings_count = len([
            r for r in results
            if getattr(r, "passed", True) is False and getattr(r, "severity", "") == "WARNING"
        ])
        emit_audit(
            "CHECK_PASS",
            duration=(datetime.now(UTC) - check_started).total_seconds(),
            warnings_count=warnings_count,
        )

    # SCORE
    if ms["phase"] == "score":
        # Binary gate: the SCORE phase is only entered after review APPROVE
        # and successful CHECK. In the old rubric this phase re-validated
        # the score sum — that check is redundant under the binary gate
        # (APPROVE means every check passed), so SCORE is now just the
        # commit step. A module landing here with severity != "clean" is
        # a state inconsistency; fail explicitly rather than silently
        # passing.
        severity = ms.get("severity")
        legacy_mode = severity is None and ms.get("scores")
        if legacy_mode:
            # Backwards compat: modules approved under the v1 rubric
            # still have ms["scores"] and no severity field. Trust the
            # legacy approval (they were already validated by the old
            # gate and reached this phase).
            scores = ms.get("scores", [4, 4, 4, 4, 4, 4, 4, 4])
            legacy_sum = sum(scores)
            legacy_min = min(scores)
            passes = legacy_min >= 4 and legacy_sum >= 33
            ms["passes"] = passes
            ms["sum"] = legacy_sum
            result_label = f"{legacy_sum}/40 (legacy rubric)"
        elif severity == "clean":
            passes = True
            ms["passes"] = True
            result_label = "all binary checks passed"
        else:
            print(f"\n  ✗ SCORE reached with severity={severity} — state inconsistency, manual review required")
            ms["errors"].append(f"SCORE phase entered with non-clean severity: {severity}")
            save_state(state)
            return False

        ms["phase"] = "done" if passes else "score"
        ms["last_run"] = datetime.now(UTC).isoformat()
        save_state(state)

        if passes:
            reviewer = ms.get("reviewer", "unknown")
            pending = ms.get("needs_independent_review", False)
            pending_tag = " needs-independent-review" if pending else ""
            print(f"\n  ✓ PASS: {result_label} reviewer={reviewer}{pending_tag}")
            add_paths = [str(module_path)]
            card_path = knowledge_card_path_for_key(key)
            if card_path.exists():
                add_paths.append(str(card_path))
            audit_path = emit_audit("DONE", reviewer=reviewer, pass_sum=result_label)
            if audit_path is not None and audit_path.exists():
                add_paths.append(str(audit_path))
            commit_msg = (
                f"chore(quality): v1 pipeline pass [{key}] "
                f"({result_label} reviewer={reviewer}{pending_tag})"
            )
            add_result, commit_result = _git_stage_and_commit(add_paths, commit_msg)
            if add_result.returncode != 0:
                print(f"  ⚠ git add failed: {add_result.stderr[:200]}")
            if commit_result.returncode != 0:
                print(f"  ⚠ git commit failed: {commit_result.stderr[:200]}")
            else:
                print("  ✓ Committed")
            return True
        else:
            print(f"\n  ✗ FAIL: {result_label} — needs manual intervention")
            return False

    return False


# ---------------------------------------------------------------------------
# CLI commands
# ---------------------------------------------------------------------------

def cmd_audit(args):
    """Deprecated no-op kept for one release to avoid breaking workflows."""
    print(
        "The `audit` command is deprecated and now a no-op. "
        "Issue #217 removed the audit phase; use `run --dry-run` for the "
        "initial plan or `run` to execute the pipeline."
    )
    sys.exit(0)


def cmd_audit_all(args):
    """Audit all modules (or a section) and produce a report."""
    if args.section:
        root = CONTENT_ROOT / args.section
    else:
        root = CONTENT_ROOT

    modules = sorted(root.glob("**/module-*.md"))
    # Exclude UK translations for now
    modules = [m for m in modules if "/uk/" not in str(m) and ".staging" not in str(m)]

    print(f"Found {len(modules)} modules to audit")

    report = {"timestamp": datetime.now(UTC).isoformat(), "modules": {}}
    for i, path in enumerate(modules, 1):
        key = module_key_from_path(path)
        print(f"\n[{i}/{len(modules)}] {key}")

        # Only deterministic checks for audit-all (LLM too expensive for 568 modules)
        content = path.read_text()
        results = structural.run_all(content, path)
        errors = [r for r in results if not r.passed and r.severity == "ERROR"]

        report["modules"][key] = {
            "errors": len(errors),
            "error_details": [r.message for r in errors],
        }

        if errors:
            for r in errors:
                print(r)

    # Save report
    REPORT_FILE.parent.mkdir(parents=True, exist_ok=True)
    REPORT_FILE.write_text(json.dumps(report, indent=2, ensure_ascii=False))
    print(f"\nReport saved to {REPORT_FILE}")

    total = len(report["modules"])
    clean = sum(1 for m in report["modules"].values() if m["errors"] == 0)
    print(f"\n{clean}/{total} modules pass deterministic checks")


def cmd_run(args):
    """Run a single module through the full pipeline."""
    global _quiet
    _quiet = not getattr(args, "verbose", False)
    if _quiet:
        _original_print(f"  Logging to: {LOG_FILE}")
        _original_print(f"  Use --verbose or tail -f {LOG_FILE} for full output\n")
    path = Path(args.module)
    if not path.exists():
        path = CONTENT_ROOT / f"{args.module}.md"
    if not path.exists():
        print(f"Module not found: {args.module}")
        sys.exit(1)

    models = dict(MODELS)
    if args.write_model:
        models["write"] = args.write_model
    if args.review_model:
        models["review"] = args.review_model

    state = load_state()
    ok = _run_module_with_retry_policy(
        path,
        state,
        models=models,
        dry_run=getattr(args, "dry_run", False),
        refresh_fact_ledger=getattr(args, "refresh_fact_ledger", False),
        write_only=getattr(args, "write_only", False),
    )
    sys.exit(0 if ok else 1)


def cmd_run_section(args):
    """Run all modules in a section through the pipeline."""
    global _quiet
    _quiet = not getattr(args, "verbose", False)
    if _quiet:
        _original_print(f"  Logging to: {LOG_FILE}")
        _original_print(f"  Use --verbose or tail -f {LOG_FILE} for full output\n")
    section_path = CONTENT_ROOT / args.section
    if not section_path.exists():
        print(f"Section not found: {args.section}")
        sys.exit(1)

    modules = sorted(section_path.glob("**/module-*.md"))
    modules = [m for m in modules if "/uk/" not in str(m) and ".staging" not in str(m)]

    print(f"Found {len(modules)} modules in {args.section}")

    # --- GAP-CHECK first (track level) ---
    track = args.track or _infer_track(args.section)
    print(f"\n{'='*60}")
    print(f"  GAP-CHECK: {args.section} (track: {track})")
    print(f"{'='*60}")

    gap_issues = gaps.run_track_gap_analysis(section_path, track=track)
    gap_errors = [i for i in gap_issues if i.severity == "ERROR"]
    gap_warnings = [i for i in gap_issues if i.severity == "WARNING"]

    if gap_issues:
        for issue in gap_issues:
            print(issue)
        print(f"\n  Gaps: {len(gap_errors)} errors, {len(gap_warnings)} warnings")

        # Persist gaps to file for later review
        gaps_file = REPO_ROOT / ".pipeline" / "gaps-report.json"
        gaps_file.parent.mkdir(parents=True, exist_ok=True)
        existing = json.loads(gaps_file.read_text()) if gaps_file.exists() else {"sections": {}}
        existing["sections"][args.section] = {
            "timestamp": datetime.now(UTC).isoformat(),
            "track": track,
            "issues": [
                {"module_a": i.module_a, "module_b": i.module_b,
                 "type": i.gap_type, "severity": i.severity, "message": i.message}
                for i in gap_issues
            ],
        }
        gaps_file.write_text(json.dumps(existing, indent=2, ensure_ascii=False))
        print("  Gaps saved to .pipeline/gaps-report.json")
    else:
        print("  ✓ No scaffolding gaps detected")

    if gap_errors and not args.skip_gaps:
        print(f"\n  ❌ {len(gap_errors)} gap errors — fix before processing modules")
        print("  Use --skip-gaps to override")
        sys.exit(1)

    models = dict(MODELS)
    if args.write_model:
        models["write"] = args.write_model
    if args.review_model:
        models["review"] = args.review_model

    state = load_state()
    passed = 0
    failed = 0
    dry_run = getattr(args, "dry_run", False)
    write_only = getattr(args, "write_only", False)

    workers = args.workers or 1

    if workers == 1:
        for i, path in enumerate(modules, 1):
            key = module_key_from_path(path)
            print(f"\n[{i}/{len(modules)}] {key}")
            ok = _run_module_with_retry_policy(
                path,
                state,
                models=models,
                dry_run=dry_run,
                refresh_fact_ledger=getattr(args, "refresh_fact_ledger", False),
                write_only=write_only,
            )
            if ok:
                passed += 1
            else:
                failed += 1
    else:
        global _PARALLEL_RUN_SECTION_STATE_LOCK, _PARALLEL_RUN_SECTION_GIT_LOCK
        previous_state_lock = _PARALLEL_RUN_SECTION_STATE_LOCK
        previous_git_lock = _PARALLEL_RUN_SECTION_GIT_LOCK
        _PARALLEL_RUN_SECTION_STATE_LOCK = threading.Lock()
        _PARALLEL_RUN_SECTION_GIT_LOCK = threading.Lock()
        try:
            with ThreadPoolExecutor(max_workers=workers) as executor:
                futures = {
                    executor.submit(
                        _run_module_in_parallel,
                        path,
                        state,
                        models=models,
                        dry_run=dry_run,
                        refresh_fact_ledger=getattr(args, "refresh_fact_ledger", False),
                        write_only=write_only,
                    ): path
                    for path in modules
                }
                for future in as_completed(futures):
                    path = futures[future]
                    try:
                        ok = future.result()
                        if ok:
                            passed += 1
                        else:
                            failed += 1
                    except Exception:
                        # Worker failures are isolated; never log generated exception details.
                        logger.exception("Module worker failed; continuing batch", exc_info=False)
                        failed += 1
        finally:
            _PARALLEL_RUN_SECTION_STATE_LOCK = previous_state_lock
            _PARALLEL_RUN_SECTION_GIT_LOCK = previous_git_lock

    print(f"\n{'='*60}")
    if dry_run:
        print(f"  DRY RUN: {passed} already pass, {failed} need improvement out of {len(modules)}")
        # Show summary of weak dimensions across all audited modules
        all_scores = {k: v.get("scores") for k, v in state.get("modules", {}).items()
                      if v.get("scores") and (k == args.section or k.startswith(f"{args.section}/"))}
        if all_scores:
            # 8-dimension rubric — keep this in sync with REVIEW_PROMPT_TEMPLATE.
            # Previously this array had 7 entries with stale names ("D2:Scaffold"
            # instead of "D2:Accuracy"), silently dropping D8 Practitioner Depth
            # from the weak-dim report.
            weak_counts = [0] * 8
            for scores in all_scores.values():
                for i, s in enumerate(scores[:8]):
                    if s < 4:
                        weak_counts[i] += 1
            dim_names = [
                "D1:Pedagogy", "D2:Accuracy", "D3:Depth", "D4:Practical",
                "D5:Assessment", "D6:Coverage", "D7:Production", "D8:Practitioner",
            ]
            print("\n  Weak dimensions across section:")
            for name, count in zip(dim_names, weak_counts):
                if count > 0:
                    print(f"    {name}: {count} modules below 4")
    else:
        print(f"  DONE: {passed} passed, {failed} failed out of {len(modules)}")
    print(f"{'='*60}")

    sys.exit(0 if (dry_run or failed == 0) else 1)


def cmd_learning_path(args):
    """Detect gaps across the full learning path (cross-track transitions)."""
    print("\nCross-Track Gap Analysis")
    print(f"{'='*60}")
    print(f"  Learning path: {' → '.join(d.split('/')[-1] for d, _ in gaps.LEARNING_PATH)}")
    print()

    issues = gaps.detect_cross_track_gaps(CONTENT_ROOT)

    if not issues:
        print("  ✓ No cross-track gaps detected")
        return

    for issue in issues:
        print(issue)
        print()

    errors = [i for i in issues if i.severity == "ERROR"]
    warnings = [i for i in issues if i.severity == "WARNING"]

    print(f"  Summary: {len(errors)} errors, {len(warnings)} warnings")

    # Categorize fixes
    new_modules = [i for i in issues if i.suggestion == "new_module"]
    expansions = [i for i in issues if i.suggestion == "expand"]
    cross_refs = [i for i in issues if i.suggestion == "cross_reference"]

    if new_modules:
        print(f"\n  NEW MODULES NEEDED: {len(new_modules)} transitions have too many gaps to fix inline")
    if expansions:
        print(f"  EXPAND EXISTING: {len(expansions)} transitions need existing modules expanded")
    if cross_refs:
        print(f"  CROSS-REFERENCES: {len(cross_refs)} transitions just need \"see Module X\" links")

    # Persist to file
    gaps_file = REPO_ROOT / ".pipeline" / "gaps-report.json"
    gaps_file.parent.mkdir(parents=True, exist_ok=True)
    existing = json.loads(gaps_file.read_text()) if gaps_file.exists() else {"sections": {}}
    existing["cross_track"] = {
        "timestamp": datetime.now(UTC).isoformat(),
        "issues": [
            {"from": i.from_section, "to": i.to_section,
             "type": i.gap_type, "severity": i.severity,
             "message": i.message, "suggestion": i.suggestion}
            for i in issues
        ],
    }
    gaps_file.write_text(json.dumps(existing, indent=2, ensure_ascii=False))
    print("\n  Saved to .pipeline/gaps-report.json")

    sys.exit(1 if errors else 0)


def _track_from_key(key: str) -> str:
    """Map a module key to its display group matching e2e aliases."""
    parts = key.split("/")
    if parts[0] == "k8s":
        sub = parts[1] if len(parts) > 1 else ""
        if sub in ("cka", "ckad", "cks", "kcna", "kcsa"):
            return "certs"
        if sub in ("extending",):
            return "certs"  # part of certs alias
        return "specialty"  # pca, cba, capa, kca, otca, ica, cca, finops
    if parts[0] == "prerequisites":
        return "prereqs"
    if parts[0] == "linux":
        return "linux"
    if parts[0] == "platform":
        sub = parts[1] if len(parts) > 1 else ""
        if sub == "foundations":
            return "platform/foundations"
        if sub == "disciplines":
            return "platform/disciplines"
        if sub == "toolkits":
            return "platform/toolkits"
        return "platform"
    if parts[0] in ("cloud", "on-premises"):
        return parts[0]
    return parts[0]


def _status_group_from_key(key: str) -> str:
    """Group module keys for four-stage completion reporting."""
    parts = key.split("/")
    if not parts:
        return key
    if parts[0] == "k8s" and len(parts) > 1:
        return f"k8s/{parts[1]}"
    return parts[0]


def _safe_read_len(path: Path) -> int:
    """Read text length, returning zero for unreadable files."""
    try:
        return len(path.read_text())
    except (OSError, UnicodeDecodeError):
        return 0


def _render_status_dashboard_html(
    module_rows: list[dict[str, object]],
    track_summaries: dict[str, dict[str, int]],
    totals: dict[str, int],
    generated_at: datetime,
) -> str:
    """Render a self-contained HTML dashboard for status heatmap data."""
    grouped: dict[str, dict[str, list[dict[str, object]]]] = {}
    for row in module_rows:
        track = str(row["track"])
        section = str(row["section"])
        track_rows = grouped.setdefault(track, {})
        section_rows = track_rows.setdefault(section, [])
        section_rows.append(row)

    def _bool_cell(done: bool) -> str:
        klass = "cell-done" if done else "cell-not-done"
        text = "Done" if done else "Not done"
        return f'<td class="{klass}">{text}</td>'

    def _count_cell(done: int, total: int) -> str:
        return f'<td class="cell-na">{done}/{total}</td>'

    stage_headers = ["Written", "Fact-Checked", "Reviewed", "UK-Translated"]
    lines = [
        "<!doctype html>",
        '<html lang="en">',
        "<head>",
        '<meta charset="utf-8">',
        '<meta name="viewport" content="width=device-width, initial-scale=1">',
        "<title>Pipeline Status Dashboard</title>",
        "<style>",
        ":root { color-scheme: light; }",
        "body { margin: 24px; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; background: #f7f9fc; color: #1f2937; }",
        "h1 { margin: 0 0 8px 0; font-size: 24px; }",
        ".meta { margin: 0 0 20px 0; color: #4b5563; font-size: 14px; }",
        ".table-wrap { overflow-x: auto; border: 1px solid #d1d5db; border-radius: 8px; background: #fff; }",
        "table { width: 100%; border-collapse: collapse; }",
        "th, td { border: 1px solid #e5e7eb; padding: 8px 10px; font-size: 13px; text-align: center; }",
        "th { background: #f3f4f6; font-weight: 600; }",
        "td.label { text-align: left; font-weight: 600; background: #f9fafb; }",
        "td.module { text-align: left; white-space: nowrap; }",
        "tr.section-row td.label { background: #edf2ff; }",
        "tr.track-summary td.label { background: #eefbf3; font-weight: 700; }",
        "tr.total-summary td.label { background: #e5e7eb; font-weight: 700; }",
        ".cell-done { background: #c8e6c9; color: #1b5e20; }",
        ".cell-not-done { background: #ffcdd2; color: #b71c1c; }",
        ".cell-na { background: #e0e0e0; color: #374151; }",
        "</style>",
        "</head>",
        "<body>",
        "<h1>Pipeline Status Dashboard</h1>",
        f'<p class="meta">Generated at: {html_lib.escape(generated_at.isoformat())}</p>',
        '<div class="table-wrap">',
        '<table id="status-heatmap">',
        "<thead>",
        "<tr>",
        "<th>Group</th>",
        "<th>Module</th>",
    ]
    for header in stage_headers:
        lines.append(f"<th>{header}</th>")
    lines.extend(["</tr>", "</thead>", "<tbody>"])

    for track in sorted(grouped):
        sections = grouped[track]
        for section in sorted(sections):
            section_esc = html_lib.escape(section)
            lines.append('<tr class="section-row">')
            lines.append(f'<td class="label" colspan="2">{section_esc}</td>')
            lines.append('<td class="cell-na">N/A</td>' * 4)
            lines.append("</tr>")
            for row in sorted(sections[section], key=lambda item: str(item["key"])):
                key = html_lib.escape(str(row["key"]))
                module_name = html_lib.escape(str(row["module"]))
                lines.append('<tr class="module-row">')
                lines.append(f'<td class="label">{html_lib.escape(track)}</td>')
                lines.append(f'<td class="module" title="{key}">{module_name}</td>')
                lines.append(_bool_cell(bool(row["written"])))
                lines.append(_bool_cell(bool(row["fact_checked"])))
                lines.append(_bool_cell(bool(row["reviewed"])))
                lines.append(_bool_cell(bool(row["uk_translated"])))
                lines.append("</tr>")
        summary = track_summaries.get(track, {"total": 0, "written": 0, "fact_checked": 0, "reviewed": 0, "uk_translated": 0})
        lines.append('<tr class="track-summary">')
        lines.append(f'<td class="label" colspan="2">Track Summary: {html_lib.escape(track)}</td>')
        lines.append(_count_cell(summary["written"], summary["total"]))
        lines.append(_count_cell(summary["fact_checked"], summary["total"]))
        lines.append(_count_cell(summary["reviewed"], summary["total"]))
        lines.append(_count_cell(summary["uk_translated"], summary["total"]))
        lines.append("</tr>")

    lines.append('<tr class="total-summary">')
    lines.append('<td class="label" colspan="2">TOTAL</td>')
    lines.append(_count_cell(totals["written"], totals["total"]))
    lines.append(_count_cell(totals["fact_checked"], totals["total"]))
    lines.append(_count_cell(totals["reviewed"], totals["total"]))
    lines.append(_count_cell(totals["uk_translated"], totals["total"]))
    lines.append("</tr>")
    lines.extend(["</tbody>", "</table>", "</div>", "</body>", "</html>"])
    return "\n".join(lines)


def cmd_status(args):
    """Show pipeline status."""
    global _quiet
    previous_quiet = _quiet
    _quiet = False
    state = load_state()
    modules = state.get("modules", {})
    verbose = getattr(args, "verbose", False)

    # Discover ALL EN modules + index pages on disk
    all_en_modules = sorted(CONTENT_ROOT.glob("**/module-*.md"))
    all_en_modules = [
        m for m in all_en_modules
        if "uk" not in m.relative_to(CONTENT_ROOT).parts[:1]
        and not m.name.endswith(".staging.md")
    ]
    all_en_indexes = sorted(CONTENT_ROOT.glob("**/index.md"))
    all_en_indexes = [
        f for f in all_en_indexes
        if "uk" not in f.relative_to(CONTENT_ROOT).parts[:1]
        and f != CONTENT_ROOT / "index.md"
    ]
    all_en = all_en_modules + all_en_indexes
    disk_keys = {module_key_from_path(m) for m in all_en}

    # Discover UK translations (modules + index pages)
    all_uk = []
    if (CONTENT_ROOT / "uk").exists():
        all_uk = sorted((CONTENT_ROOT / "uk").glob("**/module-*.md"))
        all_uk += sorted((CONTENT_ROOT / "uk").glob("**/index.md"))
    all_uk = [m for m in all_uk if not m.name.endswith(".staging.md")
              and m != CONTENT_ROOT / "uk" / "index.md"]
    uk_keys = set()
    for m in all_uk:
        rel = str(m.relative_to(CONTENT_ROOT / "uk")).replace(".md", "")
        uk_keys.add(rel)

    # Build track data from disk + state
    tracks: dict[str, dict] = {}
    legacy_count = 0
    binary_gate_count = 0
    split_reviewer_count = 0
    for key in disk_keys:
        track = _track_from_key(key)
        t = tracks.setdefault(track, {
            "total": 0, "pass": 0, "fail": 0, "wip": 0, "todo": 0,
            "legacy_sums": [], "uk": 0,
        })
        t["total"] += 1
        if key in uk_keys:
            t["uk"] += 1
        ms = modules.get(key, {})
        phase = ms.get("phase")
        schema_version = ms.get("reviewer_schema_version", 1 if ms.get("scores") else None)
        if schema_version == 3:
            split_reviewer_count += 1
        elif schema_version == 2:
            binary_gate_count += 1
        elif schema_version == 1:
            legacy_count += 1
            # Keep legacy sums available for a faded column — modules
            # approved under v1 still have their 8-dim score vector.
            legacy_sum = ms.get("sum")
            if legacy_sum is not None:
                t["legacy_sums"].append(legacy_sum)
        if phase == "done":
            t["pass"] += 1
        elif phase in ("write",):
            t["fail"] += 1
        elif phase and phase not in ("pending",):
            t["wip"] += 1
        else:
            t["todo"] += 1

    g_total = sum(t["total"] for t in tracks.values())
    g_pass = sum(t["pass"] for t in tracks.values())
    g_fail = sum(t["fail"] for t in tracks.values())
    g_wip = sum(t["wip"] for t in tracks.values())
    g_todo = sum(t["total"] - t["pass"] - t["fail"] - t["wip"] for t in tracks.values())
    g_uk = sum(t["uk"] for t in tracks.values())
    all_legacy = [s for t in tracks.values() for s in t["legacy_sums"]]

    print(f"\n  Modules: {g_total} total | {g_pass} pass | {g_fail} fail | {g_wip} in progress | {g_todo} not started")
    print(f"  Translations: {g_uk}/{g_total} UK")
    print(
        f"  Gate version: {split_reviewer_count} split-reviewer | "
        f"{binary_gate_count} binary-gate | {legacy_count} legacy rubric"
    )
    if all_legacy:
        print(f"  Legacy score distribution: avg {sum(all_legacy)/len(all_legacy):.1f} | lo {min(all_legacy)} | hi {max(all_legacy)} ({len(all_legacy)} modules)")
    print()
    hdr = f"  {'track':30s} {'pass':>6s} {'fail':>5s} {'wip':>5s} {'todo':>5s} {'total':>5s}  {'uk':>3s}"
    print(hdr)
    print(f"  {'-'*85}")

    for track in sorted(tracks):
        t = tracks[track]
        todo = t["total"] - t["pass"] - t["fail"] - t["wip"]
        uk = str(t["uk"]) if t["uk"] else "--"
        mark = " ok" if t["pass"] == t["total"] else ""
        print(f"  {track:30s} {t['pass']:>6d} {t['fail']:>5d} {t['wip']:>5d} {todo:>5d} {t['total']:>5d}  {uk:>3s}{mark}")

    # Four-stage module completion summary
    completion: dict[str, dict[str, int]] = {}
    module_rows: list[dict[str, object]] = []
    track_summaries: dict[str, dict[str, int]] = {}
    totals = {
        "total": 0,
        "written": 0,
        "fact_checked": 0,
        "reviewed": 0,
        "uk_translated": 0,
        "complete": 0,
    }
    for module_path in all_en:
        key = module_key_from_path(module_path)
        track = _status_group_from_key(key)
        row = completion.setdefault(track, {
            "total": 0,
            "written": 0,
            "fact_checked": 0,
            "reviewed": 0,
            "uk_translated": 0,
            "complete": 0,
        })

        row["total"] += 1
        totals["total"] += 1

        written = _safe_read_len(module_path) >= 2000
        ledger_path = fact_ledger_path_for_key(key)
        fact_checked = ledger_path.exists() and _cache_is_fresh(ledger_path, FACT_LEDGER_TTL)
        reviewed = modules.get(key, {}).get("passes") is True
        uk_path = CONTENT_ROOT / "uk" / module_path.relative_to(CONTENT_ROOT)
        uk_translated = uk_path.exists() and _safe_read_len(uk_path) >= 500
        key_parts = key.split("/")
        track = key_parts[0] if key_parts else key
        section = "/".join(key_parts[:-1]) if len(key_parts) > 1 else track

        module_rows.append({
            "key": key,
            "track": track,
            "section": section,
            "module": key_parts[-1] if key_parts else key,
            "written": written,
            "fact_checked": fact_checked,
            "reviewed": reviewed,
            "uk_translated": uk_translated,
        })
        track_summary = track_summaries.setdefault(track, {
            "total": 0,
            "written": 0,
            "fact_checked": 0,
            "reviewed": 0,
            "uk_translated": 0,
        })
        track_summary["total"] += 1

        if written:
            row["written"] += 1
            totals["written"] += 1
            track_summary["written"] += 1
        if fact_checked:
            row["fact_checked"] += 1
            totals["fact_checked"] += 1
            track_summary["fact_checked"] += 1
        if reviewed:
            row["reviewed"] += 1
            totals["reviewed"] += 1
            track_summary["reviewed"] += 1
        if uk_translated:
            row["uk_translated"] += 1
            totals["uk_translated"] += 1
            track_summary["uk_translated"] += 1
        if written and fact_checked and reviewed and uk_translated:
            row["complete"] += 1
            totals["complete"] += 1

    def _ratio(done: int, total: int) -> str:
        return f"{done}/{total}"

    track_width = len("Track")
    for track in completion:
        track_width = max(track_width, len(track))
    track_width = max(track_width, len("TOTAL"))

    print("\n=== Module Completion ===")
    print(
        f"{'Track':<{track_width}s}  {'Written':>8s}  {'FactChk':>8s}  "
        f"{'Reviewed':>8s}  {'UK-Trans':>8s}  {'Complete':>8s}"
    )
    for track in sorted(completion):
        row = completion[track]
        print(
            f"{track:<{track_width}s}  {_ratio(row['written'], row['total']):>8s}  "
            f"{_ratio(row['fact_checked'], row['total']):>8s}  "
            f"{_ratio(row['reviewed'], row['total']):>8s}  "
            f"{_ratio(row['uk_translated'], row['total']):>8s}  "
            f"{_ratio(row['complete'], row['total']):>8s}"
        )
    print(
        f"{'TOTAL':<{track_width}s}  {_ratio(totals['written'], totals['total']):>8s}  "
        f"{_ratio(totals['fact_checked'], totals['total']):>8s}  "
        f"{_ratio(totals['reviewed'], totals['total']):>8s}  "
        f"{_ratio(totals['uk_translated'], totals['total']):>8s}  "
        f"{_ratio(totals['complete'], totals['total']):>8s}"
    )
    if getattr(args, "html", False):
        dashboard_html = _render_status_dashboard_html(
            module_rows=module_rows,
            track_summaries=track_summaries,
            totals=totals,
            generated_at=datetime.now(UTC),
        )
        DASHBOARD_FILE.parent.mkdir(parents=True, exist_ok=True)
        DASHBOARD_FILE.write_text(dashboard_html, encoding="utf-8")
        print(f"\n  HTML dashboard: {DASHBOARD_FILE}")
        try:
            subprocess.run(["open", str(DASHBOARD_FILE)], check=False)
        except OSError as exc:
            print(f"  WARN: unable to open dashboard automatically: {exc}")

    # Index pages are now included in the main completion table above.

    # Errors (only with --verbose)
    failed = [k for k, m in modules.items() if m.get("errors")]
    if failed:
        print(f"\n  {len(failed)} modules with errors", end="")
        if verbose:
            print(":")
            for k in failed[:20]:
                latest_error = modules[k]["errors"][-1] if modules[k]["errors"] else "?"
                print(f"    {k}: {latest_error}")
            if len(failed) > 20:
                print(f"    ... and {len(failed) - 20} more")
        else:
            print(" (use --verbose to list)")
    _quiet = previous_quiet


def _apply_model_overrides(args) -> dict:
    """Build models dict from defaults + CLI overrides."""
    models = dict(MODELS)
    if getattr(args, "write_model", None):
        models["write"] = args.write_model
    if getattr(args, "review_model", None):
        models["review"] = args.review_model
    return models


def _resolve_max_retries(max_retries: int | None = None) -> int:
    """Return the shared retry cap used across execution modes."""
    return MAX_RETRIES if max_retries is None else max_retries


def _run_module_with_retry_policy(module_path: Path, state: dict, **kwargs) -> bool:
    """Run a module with the repo-wide retry cap."""
    return run_module(
        module_path,
        state,
        max_retries=_resolve_max_retries(),
        **kwargs,
    )


def _is_resettable_review_rejection(error: object, max_retries: int | None = None) -> bool:
    """Match historical rejection counters that should be reset under the current cap."""
    match = REVIEW_REJECTED_ERROR_RE.match(str(error))
    if not match:
        return False
    rejection_count = int(match.group(1))
    return 1 <= rejection_count <= (_resolve_max_retries(max_retries) + 1)


def cmd_resume(args):
    """Resume pipeline from where it stopped."""
    global _quiet
    _quiet = not getattr(args, "verbose", False)
    if _quiet:
        _original_print(f"  Logging to: {LOG_FILE}")
        _original_print(f"  Use --verbose or tail -f {LOG_FILE} for full output\n")
    state = load_state()
    modules = state.get("modules", {})

    # Find modules that aren't done
    incomplete = {k: m for k, m in modules.items()
                  if m.get("phase") not in ("done", "pending")}

    if not incomplete:
        print("Nothing to resume.")
        return

    print(f"Resuming {len(incomplete)} incomplete modules")

    models = _apply_model_overrides(args)

    for key in incomplete:
        path = find_module_path(key)
        if path and path.exists():
            _run_module_with_retry_policy(
                path,
                state,
                models=models,
                refresh_fact_ledger=getattr(args, "refresh_fact_ledger", False),
            )


def cmd_reset_stuck(args):
    """Reset modules stuck in dead-end states so they can re-enter the pipeline."""
    state = load_state()
    modules = state.get("modules", {})

    reset_count = 0
    reset_events: list[tuple[str, list[str], str]] = []
    for key, ms in sorted(modules.items()):
        was_stuck = False
        cleared_errors: list[str] = []
        module_path = find_module_path(key)
        staging_path = module_path.with_suffix(".staging.md") if module_path is not None else None

        # Deterministic check failures — route back to write
        errors = ms.get("errors", [])
        deterministic_errors = [str(e) for e in errors if "Deterministic" in str(e)]
        if deterministic_errors:
            ms["errors"] = [e for e in errors if "Deterministic" not in str(e)]
            cleared_errors.extend(deterministic_errors)
            ms.pop("check_failures", None)
            if ms.get("phase") == "check":
                ms["phase"] = "write"
            elif ms.get("phase") == "audit":
                ms["phase"] = "pending"
            _clear_resume_metadata(ms, staging_path)
            was_stuck = True

        # Integrity gate max retries — restart from pending
        errors = ms.get("errors", [])
        integrity_errors = [str(e) for e in errors if "Integrity gate failed" in str(e)]
        if integrity_errors:
            ms["errors"] = [e for e in errors if "Integrity" not in str(e)]
            cleared_errors.extend(integrity_errors)
            ms["phase"] = "pending"
            _clear_resume_metadata(ms, staging_path)
            was_stuck = True

        # Review rejected max times — match any count
        errors = ms.get("errors", [])
        rejected_errors = [
            str(e) for e in errors if _is_resettable_review_rejection(e)
        ]
        if rejected_errors:
            ms["errors"] = [e for e in errors if not _is_resettable_review_rejection(e)]
            cleared_errors.extend(rejected_errors)
            ms["phase"] = "pending"
            _clear_resume_metadata(ms, staging_path)
            was_stuck = True

        # Stale phase=write with valid draft on disk — route to review.
        # This catches modules left over from --write-only runs (before
        # the phase="review" fix) or crashed pipelines that left state
        # pointing at write even though the draft is complete.
        if ms.get("phase") == "write":
            has_legit_rewrite = bool(
                ms.get("severity") in ("severe", "targeted") and ms.get("checks_failed")
            )
            if (not has_legit_rewrite and module_path is not None
                    and _safe_read_len(module_path) >= 2000):
                ms["phase"] = "review"
                cleared_errors.append("stale phase=write (draft exists on disk)")
                was_stuck = True

        if was_stuck:
            reset_count += 1
            reset_events.append((key, cleared_errors, ms["phase"]))
            print(f"  ↻ {key}: → phase={ms['phase']}")

    if reset_count == 0:
        print("  No stuck modules found.")
        return

    save_state(state)
    audit_paths: list[str] = []
    for key, cleared_errors, new_phase in reset_events:
        path = find_module_path(key)
        if path is None:
            continue
        audit_path = append_review_audit(
            path,
            "RESET",
            cleared_errors=cleared_errors,
            new_phase=new_phase,
        )
        audit_paths.append(str(audit_path))
    if audit_paths:
        add_result, commit_result = _git_stage_and_commit(
            audit_paths,
            "chore(pipeline): reset stuck modules [audit log] (#236)",
        )
        if add_result.returncode != 0:
            print(f"  ⚠ git add failed: {add_result.stderr[:200]}")
        if commit_result.returncode != 0:
            print(f"  ⚠ git commit failed: {commit_result.stderr[:200]}")
    print(f"\n  Reset {reset_count} stuck modules. Run 'e2e' or 'resume' to re-process them.")


def cmd_e2e(args):
    """End-to-end pipeline: resume stuck modules, then process all sections."""
    global _quiet
    _quiet = not getattr(args, "verbose", False)
    _original_print(f"  Logging to: {LOG_FILE}")
    _original_print(f"  Use --verbose or tail -f {LOG_FILE} for full output\n")
    models = _apply_model_overrides(args)
    state = load_state()

    # Track aliases for convenience
    TRACK_ALIASES = {
        # Subsection aliases — run a single section
        "ztt": ["prerequisites/zero-to-terminal"],
        "git": ["prerequisites/git-deep-dive"],
        "cn101": ["prerequisites/cloud-native-101"],
        "k8sbasics": ["prerequisites/kubernetes-basics"],
        "philosophy": ["prerequisites/philosophy-design"],
        "devops": ["prerequisites/modern-devops"],
        "cka": ["k8s/cka"],
        "ckad": ["k8s/ckad"],
        "cks": ["k8s/cks"],
        "kcna": ["k8s/kcna"],
        "kcsa": ["k8s/kcsa"],
        "extending": ["k8s/extending"],
        "aws": ["cloud/aws-essentials"],
        "gcp": ["cloud/gcp-essentials"],
        "azure": ["cloud/azure-essentials"],
        "eks": ["cloud/eks-deep-dive"],
        "gke": ["cloud/gke-deep-dive"],
        "aks": ["cloud/aks-deep-dive"],
        # Track aliases — run all sections in a track
        "prereqs": [
            "prerequisites/zero-to-terminal", "prerequisites/git-deep-dive",
            "prerequisites/cloud-native-101", "prerequisites/kubernetes-basics",
            "prerequisites/philosophy-design", "prerequisites/modern-devops",
        ],
        "certs": [
            "k8s/cka", "k8s/ckad", "k8s/cks", "k8s/kcna", "k8s/kcsa",
            "k8s/extending",
        ],
        "specialty": [
            "k8s/pca", "k8s/cba", "k8s/capa", "k8s/kca", "k8s/otca",
            "k8s/ica", "k8s/cca", "k8s/finops",
        ],
        "cloud": [
            "cloud/aws-essentials", "cloud/gcp-essentials", "cloud/azure-essentials",
            "cloud/architecture-patterns", "cloud/eks-deep-dive", "cloud/gke-deep-dive",
            "cloud/aks-deep-dive", "cloud/advanced-operations", "cloud/managed-services",
            "cloud/enterprise-hybrid",
        ],
        "platform": [
            "platform/foundations", "platform/disciplines", "platform/toolkits",
        ],
        "on-prem": [
            "on-premises/planning", "on-premises/provisioning", "on-premises/networking",
            "on-premises/storage", "on-premises/multi-cluster", "on-premises/security",
            "on-premises/operations", "on-premises/resilience",
            "on-premises/ai-ml-infrastructure",
        ],
        "linux": [
            "linux/foundations/container-primitives", "linux/foundations/networking",
            "linux/foundations/system-essentials", "linux/foundations/everyday-use",
            "linux/operations", "linux/security",
        ],
    }

    # "all" = everything in priority order
    ALL_SECTIONS = (
        TRACK_ALIASES["prereqs"] + TRACK_ALIASES["certs"] + TRACK_ALIASES["specialty"]
        + TRACK_ALIASES["cloud"] + TRACK_ALIASES["platform"] + TRACK_ALIASES["on-prem"]
        + TRACK_ALIASES["linux"]
    )

    # Phase 1: Resume stuck modules (check, write, review phases)
    # Only resume modules that belong to the requested sections
    sections_to_run = ALL_SECTIONS
    if args.sections:
        expanded: list[str] = []
        for s in args.sections:
            if s in TRACK_ALIASES:
                expanded.extend(TRACK_ALIASES[s])
            else:
                # Auto-discover: if path is a directory, find all subsections with modules
                section_path = CONTENT_ROOT / s
                if section_path.is_dir():
                    # Check if this dir itself has modules
                    has_modules = list(section_path.glob("module-*.md"))
                    if has_modules:
                        expanded.append(s)
                    # Also add any subdirs that have modules
                    for sub in sorted(section_path.rglob("index.md")):
                        subdir = sub.parent
                        if list(subdir.glob("module-*.md")) and str(subdir) != str(section_path):
                            expanded.append(str(subdir.relative_to(CONTENT_ROOT)))
                    # Fallback: just use the path as-is
                    if (not expanded or expanded[-1] != s) and s not in expanded:
                        expanded.append(s)
                else:
                    expanded.append(s)
        sections_to_run = expanded

    section_prefixes = tuple(sections_to_run)
    incomplete = {k: m for k, m in state.get("modules", {}).items()
                  if m.get("phase") not in ("done", "pending")
                  and k.startswith(section_prefixes)}
    if incomplete:
        print(f"\n{'='*60}")
        print(f"  PHASE 1: Resuming {len(incomplete)} stuck modules")
        print(f"{'='*60}")
        resumed = 0
        phase1_failed_modules: set[str] = set()
        consecutive_failures = 0
        for key, ms in incomplete.items():
            path = find_module_path(key)
            if path and path.exists():
                ok = _run_module_with_retry_policy(
                    path,
                    state,
                    models=models,
                    refresh_fact_ledger=getattr(args, "refresh_fact_ledger", False),
                    write_only=getattr(args, "write_only", False),
                )
                if ok:
                    resumed += 1
                    consecutive_failures = 0
                else:
                    phase1_failed_modules.add(key)
                    consecutive_failures += 1
                if consecutive_failures >= 5:
                    print("\n  CIRCUIT BREAKER: 5 consecutive resume failures — halting")
                    print(f"  Check logs: {LOG_FILE}")
                    break
        print(f"\n  Resumed: {resumed}/{len(incomplete)} completed")
    else:
        phase1_failed_modules = set()

    for section in sections_to_run:
        section_path = CONTENT_ROOT / section
        if not section_path.exists():
            continue

        modules = sorted(section_path.glob("**/module-*.md"))
        modules = [m for m in modules if "/uk/" not in str(m) and ".staging" not in str(m)]
        if not modules:
            continue

        # Skip sections where all modules are already done
        all_done = all(
            state.get("modules", {}).get(module_key_from_path(m), {}).get("phase") == "done"
            for m in modules
        )
        if all_done:
            print(f"\n  SKIP: {section} — all {len(modules)} modules done")
            continue

        print(f"\n{'='*60}")
        print(f"  SECTION: {section} ({len(modules)} modules)")
        print(f"{'='*60}")

        passed = 0
        failed = 0
        skipped = 0
        consecutive_failures = 0
        for i, path in enumerate(modules, 1):
            key = module_key_from_path(path)
            ms = state.get("modules", {}).get(key, {})

            # Skip already done
            if ms.get("phase") == "done":
                skipped += 1
                continue
            if key in phase1_failed_modules:
                print(f"\n[{i}/{len(modules)}] {key}")
                print("  SKIP: failed during phase-1 resume; leaving for next run")
                skipped += 1
                continue

            print(f"\n[{i}/{len(modules)}] {key}")
            ok = _run_module_with_retry_policy(
                path,
                state,
                models=models,
                refresh_fact_ledger=getattr(args, "refresh_fact_ledger", False),
                write_only=getattr(args, "write_only", False),
            )
            if ok:
                passed += 1
                consecutive_failures = 0
            else:
                failed += 1
                consecutive_failures += 1

            if consecutive_failures >= 5:
                print(f"\n  CIRCUIT BREAKER: 5 consecutive failures in {section} — halting")
                print(f"  Check logs: {LOG_FILE}")
                break

        print(f"\n  {section}: {passed} passed, {failed} failed, {skipped} skipped")

        # Update section index.md if any modules passed this run
        if passed > 0:
            # Find all unique directories containing modules (handles subsections)
            module_dirs = sorted({m.parent for m in modules})
            index_files = []
            for mdir in module_dirs:
                idx = mdir / "index.md"
                if idx.exists():
                    step_update_index(mdir, model=models["write"])
                    index_files.append(str(idx))

            # Commit only the index files (not git add -A which could grab stray files)
            if index_files:
                subprocess.run(
                    ["git", "add"] + index_files,
                    cwd=str(REPO_ROOT), capture_output=True, text=True, check=False,
                )
                idx_commit = subprocess.run(
                    ["git", "commit", "-m",
                     f"docs: update section indexes for {section}"],
                    cwd=str(REPO_ROOT), capture_output=True, text=True, check=False,
                )
                if idx_commit.returncode == 0:
                    print("  ✓ Index updates committed")

    # UK translations: sync modules for completed sections
    if not getattr(args, "no_translate", False):
        for section in sections_to_run:
            uk_section = CONTENT_ROOT / "uk" / section
            if not uk_section.exists():
                continue

            # Find EN content files (modules + index.md, excluding staging)
            en_files = uk_find_content_files(CONTENT_ROOT / section)
            en_files = [m for m in en_files if "/uk/" not in str(m)]
            if not en_files:
                continue

            print(f"\n{'='*60}")
            print(f"  UK TRANSLATE: {section} ({len(en_files)} files)")
            print(f"{'='*60}")

            translated = 0
            failed = 0
            consecutive_uk_failures = 0
            for en_path in en_files:
                rel = en_path.relative_to(UK_CONTENT_ROOT)
                uk_path = UK_ROOT / rel

                print(f"  UK: {rel.name}")
                if uk_path.exists():
                    ok = uk_fix(uk_path)
                else:
                    ok = uk_translate(en_path)

                if ok:
                    translated += 1
                    consecutive_uk_failures = 0
                else:
                    failed += 1
                    consecutive_uk_failures += 1

                if consecutive_uk_failures >= 3:
                    print("  CIRCUIT BREAKER: 3 consecutive UK translation failures — skipping rest")
                    break

            print(f"\n  UK: {translated} translated, {failed} failed")

    # Final summary
    state = load_state()
    total = len(state.get("modules", {}))
    done = sum(1 for m in state["modules"].values() if m.get("phase") == "done")
    print(f"\n{'='*60}")
    print(f"  E2E COMPLETE: {done}/{total} modules done")
    print(f"{'='*60}")


def _infer_track(section: str) -> str:
    """Infer track type from section path for jargon lookup."""
    s = section.lower()
    if "prerequisite" in s or "zero-to-terminal" in s or "philosophy" in s or "modern-devops" in s or "cloud-native-101" in s or "kubernetes-basics" in s:
        return "prerequisites"
    if "linux" in s:
        return "linux"
    if "cloud" in s or "aws" in s or "gcp" in s or "azure" in s or "eks" in s or "gke" in s or "aks" in s:
        return "cloud"
    return "k8s"


def cmd_gap_check(args):
    """Detect scaffolding gaps in a track or section."""
    path = CONTENT_ROOT / args.path
    if not path.exists():
        print(f"Path not found: {args.path}")
        sys.exit(1)

    print(f"\nGap analysis: {args.path} (track: {args.track})")
    print(f"{'='*60}")

    issues = gaps.run_track_gap_analysis(path, track=args.track)

    if not issues:
        print("\n  ✓ No scaffolding gaps detected")
        return

    # Group by type
    by_type = {}
    for issue in issues:
        by_type.setdefault(issue.gap_type, []).append(issue)

    for gap_type, items in sorted(by_type.items()):
        print(f"\n  {gap_type} ({len(items)}):")
        for item in items:
            print(item)

    errors = [i for i in issues if i.severity == "ERROR"]
    warnings = [i for i in issues if i.severity == "WARNING"]
    print(f"\n  Summary: {len(errors)} errors, {len(warnings)} warnings")

    # Also run LLM gap analysis for deeper detection
    if args.track in ("prerequisites", "linux"):
        print("\n  For deeper analysis, consider running:")
        print(f"  python scripts/v1_pipeline.py gap-check {args.path} --track {args.track}")
        print("  and reviewing CONCEPT_JUMP warnings manually")

    sys.exit(1 if errors else 0)


def main():
    parser = argparse.ArgumentParser(
        description="KubeDojo Module Quality Pipeline v1",
        epilog="""quick start:
  status                           show progress across all 700+ modules
  e2e certs                        run all cert tracks (CKA, CKAD, CKS, KCNA, KCSA)
  e2e prereqs cloud                run prerequisites + cloud
  e2e                              run everything (overnight batch)
  resume                           retry stuck modules only

models:
  --write-model {GEMINI_WRITER_MODEL}     override the main writer
  --review-model claude-sonnet-4-6         override the primary reviewer
""", formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    # Global model overrides
    parser.add_argument("--audit-model", help=argparse.SUPPRESS)
    parser.add_argument("--write-model", help=f"Model for WRITE step (default: {GEMINI_WRITER_MODEL})")
    parser.add_argument("--review-model", help=f"Model for REVIEW step (default: {GEMINI_WRITER_MODEL})")

    subparsers = parser.add_subparsers(dest="command", help="Pipeline command")

    # audit
    ap = subparsers.add_parser("audit", help="Deprecated no-op (audit phase removed)")
    ap.add_argument("module", help="Module path or key")

    # audit-all
    aap = subparsers.add_parser("audit-all", help="Audit all modules (deterministic only)")
    aap.add_argument("--section", help="Limit to a section (e.g., cloud/aws-essentials)")

    # run
    rp = subparsers.add_parser("run", help="Run a module through the full pipeline")
    rp.add_argument("module", help="Module path or key")
    rp.add_argument("--verbose", "-v", action="store_true", help="Print full output to stdout (default: quiet, log only)")
    rp.add_argument("--dry-run", action="store_true", help="Plan only — show the initial write plan without making changes")
    rp.add_argument("--write-only", action="store_true", help="Draft content only — skip fact-ledger, review, and checks")
    rp.add_argument("--refresh-fact-ledger", action="store_true",
                    help="Bypass fact-ledger cache and regenerate from upstream sources")

    # run-section
    rsp = subparsers.add_parser("run-section", help="Run all modules in a section")
    rsp.add_argument("section", help="Section path (e.g., cloud/aws-essentials)")
    rsp.add_argument("--verbose", "-v", action="store_true", help="Print full output to stdout (default: quiet, log only)")
    rsp.add_argument("--workers", type=int, default=1, help="Parallel workers (default: 1)")
    rsp.add_argument("--track", help="Track type for gap check (auto-detected if omitted)",
                     choices=["prerequisites", "linux", "cloud", "k8s"])
    rsp.add_argument("--skip-gaps", action="store_true", help="Skip gap check even if errors found")
    rsp.add_argument("--dry-run", action="store_true", help="Plan only — show the initial write plan without making changes")
    rsp.add_argument("--write-only", action="store_true", help="Draft content only — skip fact-ledger, review, and checks")
    rsp.add_argument("--refresh-fact-ledger", action="store_true",
                     help="Bypass fact-ledger cache and regenerate from upstream sources")

    # gap-check
    gcp = subparsers.add_parser("gap-check", help="Detect scaffolding gaps in a track/section")
    gcp.add_argument("path", help="Track or section path (e.g., prerequisites/zero-to-terminal)")
    gcp.add_argument("--track", default="k8s",
                     choices=["prerequisites", "linux", "cloud", "k8s"],
                     help="Track type for jargon lookup (default: k8s)")

    # learning-path
    subparsers.add_parser("learning-path", help="Detect gaps across the full learning path (cross-track)")

    # status
    sp = subparsers.add_parser("status", help="Show pipeline status")
    sp.add_argument("--verbose", "-v", action="store_true", help="Show error details")
    sp.add_argument("--html", action="store_true", help="Generate and open HTML dashboard")

    # resume
    resume_parser = subparsers.add_parser("resume", help="Resume incomplete modules")
    resume_parser.add_argument("--verbose", "-v", action="store_true", help="Print full output to stdout (default: quiet, log only)")
    resume_parser.add_argument("--refresh-fact-ledger", action="store_true",
                               help="Bypass fact-ledger cache and regenerate from upstream sources")

    # e2e
    e2e_parser = subparsers.add_parser("e2e", help="End-to-end: resume stuck + process all sections",
        epilog="""track aliases:
  prereqs    zero-to-terminal, git-deep-dive, cloud-native-101, k8s-basics, philosophy, modern-devops
  certs      cka, ckad, cks, kcna, kcsa, extending
  specialty  pca, cba, capa, kca, otca, ica, cca, finops
  cloud      aws, gcp, azure, architecture, eks, gke, aks, advanced-ops, managed, enterprise
  platform   foundations, disciplines, toolkits
  on-prem    planning, provisioning, networking, storage, multi-cluster, security, operations, resilience, ai-ml-infrastructure
  linux      container-primitives, networking, system-essentials, everyday-use, operations, security

examples:
  e2e                      run everything
  e2e prereqs              just prerequisites
  e2e certs cloud          certs + cloud
  e2e k8s/cka              single section
""", formatter_class=argparse.RawDescriptionHelpFormatter)
    e2e_parser.add_argument("sections", nargs="*", help="track aliases or section paths (default: all)")
    e2e_parser.add_argument("--verbose", "-v", action="store_true", help="print full output to stdout (default: quiet, log only)")
    e2e_parser.add_argument("--no-translate", action="store_true", help="skip UK translation step")
    e2e_parser.add_argument("--write-only", action="store_true", help="Draft content only — skip fact-ledger, review, and checks")
    e2e_parser.add_argument("--refresh-fact-ledger", action="store_true",
                            help="Bypass fact-ledger cache and regenerate from upstream sources")

    # reset-stuck
    subparsers.add_parser("reset-stuck", help="Reset modules stuck in dead-end states (check failures, max retries)")

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        sys.exit(1)

    cmd_map = {
        "audit": cmd_audit,
        "audit-all": cmd_audit_all,
        "run": cmd_run,
        "run-section": cmd_run_section,
        "gap-check": cmd_gap_check,
        "learning-path": cmd_learning_path,
        "status": cmd_status,
        "resume": cmd_resume,
        "e2e": cmd_e2e,
        "reset-stuck": cmd_reset_stuck,
    }

    cmd_map[args.command](args)


if __name__ == "__main__":
    main()
