#!/usr/bin/env python3
"""Rigorous writer calibration with hallucination fact-checking.

Tests 6 LLM writer candidates across 3 distinct topics, then fact-checks every
output with the calibrated fact-grounder (gpt-5.3-codex-spark). Produces a single
JSON results file the human can score.

This replaces the sloppy "single topic + assumed factual scoring" first pass.

Usage:
    .venv/bin/python scripts/research/writer-calibration-rigorous.py
    .venv/bin/python scripts/research/writer-calibration-rigorous.py --resume

Output:
    /tmp/writer-rigorous/<topic>/<candidate>.md       — clean section markdown
    /tmp/writer-rigorous/<topic>/<candidate>.fact.json — fact-check ledger
    /tmp/writer-rigorous/results.json                 — full aggregated results
    /tmp/writer-rigorous/log.txt                       — progress log

The script is sequential within a candidate (per the never-parallelize-Gemini
memory rule for Gemini specifically) but PARALLEL across candidates where possible:
each candidate gets its own subprocess that handles all 3 topics.
"""
from __future__ import annotations

import json
import re
import subprocess
import sys
import time
from datetime import UTC, datetime
from pathlib import Path

REPO_ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(REPO_ROOT / "scripts"))
VENV_PYTHON = str((REPO_ROOT / ".venv" / "bin" / "python").resolve())
GEMINI_WRITER_MODEL = "gemini-3.1-pro-high"

OUTPUT_DIR = Path("/tmp/writer-rigorous")
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
LOG_FILE = OUTPUT_DIR / "log.txt"
RESULTS_FILE = OUTPUT_DIR / "results.json"

# ---------- Configuration ----------

CANDIDATES = [
    {"name": GEMINI_WRITER_MODEL, "family": "gemini", "tier": "frontier"},
    {"name": "gpt-5.4", "family": "codex", "tier": "frontier"},
    {"name": "gpt-5.2", "family": "codex", "tier": "long-running"},
    {"name": "gpt-5.3-codex", "family": "codex", "tier": "codex-tuned"},
    {"name": "claude-sonnet-4-6", "family": "anthropic", "tier": "mid"},
    {"name": "claude-opus-4-6", "family": "anthropic", "tier": "frontier"},
]

FACT_CHECKER = "gpt-5.3-codex-spark"  # the calibrated winner from PR-equivalent test

TOPICS = [
    {
        "id": "psa",
        "label": "Pod Security Admission (PSA)",
        "domain": "CKS — security",
        "section_topic": "Pod Security Admission (PSA) — replacing PodSecurityPolicy with the built-in PSA controller",
        "audience": "a CKS exam candidate who has read the previous section about RBAC and ServiceAccount hardening, and now needs to understand how cluster admins enforce baseline pod security without the deprecated PodSecurityPolicy.",
        "required_elements": [
            "Why PSP was removed in Kubernetes 1.25, what gap PSA fills, and what the three Pod Security Standards (privileged, baseline, restricted) cover.",
            "A worked example with runnable kubectl commands showing how to enable PSA enforcement on a namespace using the standard namespace labels. Include the resulting namespace YAML manifest. Explain the three enforcement modes (enforce, audit, warn).",
            "A practitioner gotcha — production failure mode (e.g. enforce only applies to new pods; PSA vs admission webhooks; what happens when an existing workload violates a newly applied label).",
            "A scenario-based quiz question with exactly one correct answer.",
        ],
    },
    {
        "id": "seccomp",
        "label": "Seccomp profiles in K8s SecurityContext",
        "domain": "CKS — runtime hardening",
        "section_topic": "Seccomp profiles via SecurityContext.seccompProfile — restricting container syscalls in Kubernetes",
        "audience": "a CKS exam candidate who has just learned about Pod Security Admission and now needs to understand how to restrict container syscalls at the kernel level using seccomp profiles.",
        "required_elements": [
            "Why seccomp matters for container security, the difference between RuntimeDefault and Localhost profile types, and what changed between the deprecated annotation-based approach and the current SecurityContext.seccompProfile field.",
            "A worked example showing a Pod manifest that sets seccompProfile: {type: RuntimeDefault} and a separate example using a custom Localhost profile. Include the kubectl apply command and how to verify the profile is in effect.",
            "A practitioner gotcha — production failure mode (e.g. profile not loaded on the node; container CrashLoopBackOff because the profile blocks a required syscall; debugging seccomp denials with audit logs).",
            "A scenario-based quiz question with exactly one correct answer.",
        ],
    },
    {
        "id": "kubecost",
        "label": "Kubecost on bare metal",
        "domain": "Platform engineering — FinOps (the original flap zone)",
        "section_topic": "Installing Kubecost on a bare-metal Kubernetes cluster — Helm chart values and Prometheus integration",
        "audience": "a platform engineer running a bare-metal cluster who needs to deploy Kubecost for showback/chargeback and wants to understand the chart's helm values, Prometheus dependencies, and the customPricing schema for setting on-prem hourly rates.",
        "required_elements": [
            "What Kubecost is and how it differs from OpenCost (the OSS upstream). Whether the current Kubecost release requires Prometheus. The version differences if any (2.x vs 3.x).",
            "A worked example showing a helm install command with custom values for the chart. Include a values.yaml snippet showing how to set customPricing CPU/RAM/GPU/storage hourly rates and how to point Kubecost at an existing Prometheus.",
            "A practitioner gotcha — production failure mode (e.g. Prometheus retention too short for cost data; misconfigured customPricing keys causing all costs to show as 0; the trap of mixing 2.x and 3.x docs).",
            "A scenario-based quiz question with exactly one correct answer.",
        ],
    },
]

# ---------- Prompts ----------

WRITER_PROMPT = """Write a 600-800 word teaching section for the KubeDojo curriculum on the topic:

**"{section_topic}"**

Audience: {audience}

The section MUST include:

{required_elements}

Voice constraints:
- Practitioner-grade, no fluff
- No marketing language ("delve into", "leverage", "robust", "powerful", "seamless", "comprehensive")
- No filler phrases ("In this section, we will explore...")
- Direct, terse, technically precise
- All commands and YAML must be syntactically valid for current Kubernetes (1.32+)
- Length target: 600-800 words

Output: just the section markdown. No preamble, no commentary, no "here is the section".
"""

FACT_CHECKER_PROMPT = """You are doing a fact-grounding pass on a KubeDojo curriculum section. Your job
is to identify every externally-versioned factual claim in the section and verify it
against current authoritative upstream sources.

As-of date: 2026-04-12

For each factual claim — version numbers, API names, deprecation status, helm chart
keys, command flags, YAML field paths, project status, vendor docs — return a verdict:

- VERIFIED: the claim is supported by current authoritative sources.
- CONFLICTING: authoritative sources disagree.
- UNVERIFIED: you cannot establish a reliable answer from authoritative sources.
- HALLUCINATED: you can verify the claim is factually wrong against authoritative sources.

Rules:
- Do NOT answer from memory. Use current upstream documentation.
- Prefer official vendor/project docs.
- Be honest about uncertainty. Saying UNVERIFIED costs nothing. Saying VERIFIED on
  something you cannot actually verify is the worst possible answer.
- Only flag claims that a reader would actually act on. Skip narrative framing.
- HALLUCINATED is the most important verdict — it means the section asserts something
  that is demonstrably false.

Return strict JSON only, no prose preamble.

Required JSON shape:
{{
  "section_topic": "{section_topic_label}",
  "as_of_date": "2026-04-12",
  "claims": [
    {{
      "id": "C1",
      "claim": "exact claim from the section",
      "verdict": "VERIFIED | CONFLICTING | UNVERIFIED | HALLUCINATED",
      "current_truth": "what is actually true (or null if VERIFIED matches the claim)",
      "sources": [
        {{"url": "...", "source_date": "YYYY-MM-DD or null"}}
      ],
      "note": "one sentence explaining the verdict, especially if HALLUCINATED or CONFLICTING"
    }}
  ],
  "summary": {{
    "total_claims": N,
    "verified": N,
    "conflicting": N,
    "unverified": N,
    "hallucinated": N
  }}
}}

The section to fact-check is below the marker.

---SECTION---
{section_text}
---END SECTION---
"""

# ---------- Helpers ----------

def log(msg: str) -> None:
    line = f"[{datetime.now(UTC).strftime('%H:%M:%S')}] {msg}"
    print(line, flush=True)
    with open(LOG_FILE, "a", encoding="utf-8") as f:
        f.write(line + "\n")


def extract_section_from_codex_output(raw: str) -> str:
    """Strip Codex CLI noise (banner, prompt echo, tokens, duplicated output) and
    return just the markdown response."""
    # Codex output structure:
    #   banner / preamble lines starting with -- or non-markdown
    #   `user` line then the prompt
    #   `codex` line then the response
    #   `tokens used` line
    #   N      (token count)
    #   the response duplicated
    # Strategy: find the LAST `codex\n` marker. Take everything after it. Stop at
    # `tokens used` if present.
    if "codex\n" in raw:
        # take after the FIRST `codex\n` (the actual response, not the duplicate)
        after = raw.split("codex\n", 1)[1]
        if "\ntokens used\n" in after:
            after = after.split("\ntokens used\n", 1)[0]
        return after.strip()
    # No codex marker — assume it's a clean response (e.g. from gemini or claude)
    return raw.strip()


def extract_first_json_object(text: str) -> dict | None:
    """Find the first balanced {...} JSON object in text and parse it."""
    text = text.strip()
    # strip fenced code blocks
    if text.startswith("```"):
        parts = text.split("```")
        if len(parts) >= 2:
            cand = parts[1]
            if cand.startswith("json"):
                cand = cand[4:]
            try:
                return json.loads(cand.strip())
            except json.JSONDecodeError:
                pass
    # direct parse
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass
    # last balanced {...} scan
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
                    cand = text[i:end + 1]
                    try:
                        return json.loads(cand)
                    except json.JSONDecodeError:
                        end = -1
                        continue
    return None


def dispatch_writer(candidate: dict, prompt: str, timeout: int = 900) -> tuple[bool, str]:
    """Dispatch a writer prompt to a candidate. Returns (ok, raw_output)."""
    family = candidate["family"]
    model = candidate["name"]
    if family == "codex":
        cmd = [
            "codex", "--search", "exec",
            "--skip-git-repo-check",
            "--dangerously-bypass-approvals-and-sandbox",
            "-m", model,
            prompt,
        ]
    elif family == "gemini":
        cmd = [
            VENV_PYTHON,
            str(REPO_ROOT / "scripts" / "dispatch.py"),
            "gemini", "-",
            "--model", model,
        ]
    elif family == "anthropic":
        cmd = [
            VENV_PYTHON,
            str(REPO_ROOT / "scripts" / "dispatch.py"),
            "claude", "-",
            "--model", model,
        ]
    else:
        return False, f"unknown family: {family}"

    try:
        if family in ("gemini", "anthropic"):
            result = subprocess.run(
                cmd, input=prompt, capture_output=True, text=True,
                timeout=timeout, cwd=str(REPO_ROOT),
            )
        else:
            result = subprocess.run(
                cmd, capture_output=True, text=True,
                timeout=timeout, cwd=str(REPO_ROOT),
            )
    except subprocess.TimeoutExpired:
        return False, "TIMEOUT"
    except FileNotFoundError as e:
        return False, f"CLI not found: {e}"

    if result.returncode != 0:
        return False, f"exit {result.returncode}: {result.stderr[:500]}"
    return True, result.stdout


def dispatch_fact_checker(section_text: str, section_topic_label: str) -> tuple[bool, str]:
    """Run the calibrated fact-checker on a section."""
    prompt = FACT_CHECKER_PROMPT.format(
        section_text=section_text,
        section_topic_label=section_topic_label,
    )
    cmd = [
        "codex", "--search", "exec",
        "--skip-git-repo-check",
        "--dangerously-bypass-approvals-and-sandbox",
        "-m", FACT_CHECKER,
        prompt,
    ]
    try:
        result = subprocess.run(
            cmd, capture_output=True, text=True,
            timeout=900, cwd=str(REPO_ROOT),
        )
    except subprocess.TimeoutExpired:
        return False, "TIMEOUT"

    if result.returncode != 0:
        return False, f"exit {result.returncode}: {result.stderr[:500]}"
    return True, result.stdout


def safe_filename(s: str) -> str:
    return re.sub(r"[^a-zA-Z0-9_-]+", "-", s).strip("-")


# ---------- Main pipeline ----------

def run_one_topic_one_candidate(topic: dict, candidate: dict) -> dict:
    topic_dir = OUTPUT_DIR / topic["id"]
    topic_dir.mkdir(parents=True, exist_ok=True)
    cand_name = safe_filename(candidate["name"])
    section_path = topic_dir / f"{cand_name}.md"
    fact_path = topic_dir / f"{cand_name}.fact.json"

    result = {
        "topic_id": topic["id"],
        "candidate": candidate["name"],
        "family": candidate["family"],
        "tier": candidate["tier"],
        "section_path": str(section_path),
        "fact_path": str(fact_path),
        "writer_ok": False,
        "writer_word_count": None,
        "fact_check_ok": False,
        "fact_summary": None,
        "fact_claims_total": None,
        "fact_hallucinated": None,
        "fact_verified": None,
        "errors": [],
    }

    # Cache hit?
    if section_path.exists() and fact_path.exists():
        try:
            with fact_path.open() as f:
                fact_data = json.load(f)
            result["writer_ok"] = True
            result["writer_word_count"] = len(section_path.read_text().split())
            result["fact_check_ok"] = True
            result["fact_summary"] = fact_data.get("summary")
            if isinstance(result["fact_summary"], dict):
                result["fact_claims_total"] = result["fact_summary"].get("total_claims")
                result["fact_hallucinated"] = result["fact_summary"].get("hallucinated")
                result["fact_verified"] = result["fact_summary"].get("verified")
            log(f"  CACHE HIT: {topic['id']}/{candidate['name']}")
            return result
        except Exception as e:
            log(f"  CACHE INVALID for {topic['id']}/{candidate['name']}: {e}; redoing")

    # Step 1: writer
    required = "\n".join(f"{i+1}. {req}" for i, req in enumerate(topic["required_elements"]))
    writer_prompt = WRITER_PROMPT.format(
        section_topic=topic["section_topic"],
        audience=topic["audience"],
        required_elements=required,
    )
    log(f"  WRITER: {topic['id']} / {candidate['name']}")
    t0 = time.time()
    ok, raw = dispatch_writer(candidate, writer_prompt)
    elapsed = time.time() - t0
    if not ok:
        log(f"    ❌ writer failed in {elapsed:.0f}s: {raw[:200]}")
        result["errors"].append(f"writer: {raw[:300]}")
        return result

    section_text = extract_section_from_codex_output(raw)
    if not section_text:
        log("    ❌ writer returned empty section")
        result["errors"].append("writer: empty section")
        return result

    section_path.write_text(section_text, encoding="utf-8")
    result["writer_ok"] = True
    result["writer_word_count"] = len(section_text.split())
    log(f"    ✓ writer wrote {result['writer_word_count']} words in {elapsed:.0f}s")

    # Step 2: fact-checker
    log(f"  FACT-CHECK: {topic['id']} / {candidate['name']}")
    t0 = time.time()
    ok, raw_fact = dispatch_fact_checker(section_text, topic["label"])
    elapsed = time.time() - t0
    if not ok:
        log(f"    ❌ fact-check failed in {elapsed:.0f}s: {raw_fact[:200]}")
        result["errors"].append(f"fact-check: {raw_fact[:300]}")
        return result

    cleaned_fact = extract_section_from_codex_output(raw_fact)
    fact_obj = extract_first_json_object(cleaned_fact)
    if fact_obj is None:
        log("    ❌ fact-check JSON parse failed")
        result["errors"].append("fact-check: JSON parse failed")
        return result

    fact_path.write_text(json.dumps(fact_obj, indent=2), encoding="utf-8")
    result["fact_check_ok"] = True
    summary = fact_obj.get("summary") or {}
    result["fact_summary"] = summary
    result["fact_claims_total"] = summary.get("total_claims")
    result["fact_hallucinated"] = summary.get("hallucinated")
    result["fact_verified"] = summary.get("verified")
    log(f"    ✓ fact-check complete in {elapsed:.0f}s — "
        f"total={result['fact_claims_total']}, hallucinated={result['fact_hallucinated']}")
    return result


def main() -> int:
    log("="*70)
    log("Rigorous writer calibration starting")
    log(f"  Candidates: {len(CANDIDATES)}")
    log(f"  Topics: {len(TOPICS)}")
    log(f"  Total dispatches: writers={len(CANDIDATES)*len(TOPICS)}, "
        f"fact-checks={len(CANDIDATES)*len(TOPICS)}")
    log(f"  Output dir: {OUTPUT_DIR}")
    log("="*70)

    all_results: list[dict] = []
    for topic in TOPICS:
        log("")
        log(f"==== TOPIC {topic['id']}: {topic['label']} ====")
        for candidate in CANDIDATES:
            result = run_one_topic_one_candidate(topic, candidate)
            all_results.append(result)
            # Save incrementally so we don't lose progress on a crash
            with RESULTS_FILE.open("w") as f:
                json.dump(all_results, f, indent=2)

    log("")
    log("="*70)
    log("BATCH COMPLETE")
    log(f"  Wrote {len(all_results)} results to {RESULTS_FILE}")

    # Score summary
    by_candidate: dict[str, dict] = {}
    for r in all_results:
        c = r["candidate"]
        if c not in by_candidate:
            by_candidate[c] = {
                "total_topics": 0,
                "successful_writes": 0,
                "successful_fact_checks": 0,
                "total_claims": 0,
                "hallucinated_claims": 0,
                "verified_claims": 0,
                "total_words": 0,
            }
        by_candidate[c]["total_topics"] += 1
        if r["writer_ok"]:
            by_candidate[c]["successful_writes"] += 1
            by_candidate[c]["total_words"] += r["writer_word_count"] or 0
        if r["fact_check_ok"]:
            by_candidate[c]["successful_fact_checks"] += 1
            by_candidate[c]["total_claims"] += r["fact_claims_total"] or 0
            by_candidate[c]["hallucinated_claims"] += r["fact_hallucinated"] or 0
            by_candidate[c]["verified_claims"] += r["fact_verified"] or 0

    log("")
    log("==== AGGREGATED SCORES ====")
    log(f"  {'candidate':<28} {'writes':>6} {'fact':>5} {'claims':>7} {'halluc':>7} {'verif':>6} {'words':>7}")
    for cand, stats in sorted(by_candidate.items(),
                              key=lambda x: (x[1]["hallucinated_claims"], -x[1]["verified_claims"])):
        log(f"  {cand:<28} "
            f"{stats['successful_writes']}/{stats['total_topics']:<3} "
            f"{stats['successful_fact_checks']}/{stats['total_topics']:<3} "
            f"{stats['total_claims']:>7} "
            f"{stats['hallucinated_claims']:>7} "
            f"{stats['verified_claims']:>6} "
            f"{stats['total_words']:>7}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
