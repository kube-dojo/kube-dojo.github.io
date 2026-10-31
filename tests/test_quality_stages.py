"""Integration tests for ``scripts.quality.stages`` + ``pipeline``.

Uses a real temp git repo (not mocked subprocess) + stubbed LLM dispatch
so the worktree + merge + rebase behavior is exercised end-to-end. This
is where the Codex must-fixes that Phase C closes get their regression
guards:

* **#1** — reviewer reads from the worktree, not ``main``
* **#3** — rebase-before-ff survives main advancing between sibling merges
* **#4** — ``REVIEW_CHANGES`` routes back with ``must_fix``, retries
  capped at 2, Gemini tiebreaker kicks in after the cap
* **#5 (runtime half)** — crash recovery from ``WRITE_IN_PROGRESS`` /
  ``REVIEW_IN_PROGRESS``
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from contextlib import nullcontext
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
import citation_backfill
from conftest import _read_frontmatter

from scripts import quality_post_review as post_review
from scripts.quality import dispatchers, pipeline, stages, state, worktree
from scripts.quality.citations import CitationResult
from scripts.quality.dispatchers import DispatchResult

_PLAN = {"module_kind": "module", "outcomes": ["Explain pods"], "essential_topics": ["Pods"],
         "source_basis": [{"uri": "git:pods", "locator": "line 1", "excerpt": "Pods."}]}
_QUOTE = "Rewritten pedagogically sound content."

# ---- fixtures ---------------------------------------------------------


@pytest.fixture
def fake_repo(tmp_path: Path, monkeypatch):
    """Real git repo in tmpdir + module seed + path monkey-patches.

    Points every ``_REPO_ROOT`` / ``_CONTENT_ROOT`` / ``STATE_DIR``
    reference across the quality package at this isolated repo so tests
    don't collide with the real project state.
    """
    repo = tmp_path / "repo"
    repo.mkdir()
    subprocess.run(["git", "init", "-b", "main"], cwd=repo, check=True, capture_output=True)
    for k, v in [("user.email", "t@t"), ("user.name", "t"), ("commit.gpgsign", "false")]:
        subprocess.run(["git", "config", k, v], cwd=repo, check=True)
    (repo / ".gitignore").write_text(
        ".worktrees/\n.pipeline/\ndocs/quality-progress.tsv\ndocs/quality-progress.tsv.lock\n"
    )
    (repo / "README.md").write_text("seed\n")

    # Seed one module at a realistic path.
    module_rel = "src/content/docs/k8s/cka/module-1.1-pods.md"
    module_file = repo / module_rel
    module_file.parent.mkdir(parents=True)
    module_file.write_text("""---
title: Pods Fundamentals
sidebar:
  order: 1
---

# Pods

Original content about pods. The module has some quiz.

## Quiz

Question 1.
""")
    seed = repo / "docs/citation-seeds/k8s-cka-module-1.1-pods.json"
    seed.parent.mkdir(parents=True)
    seed.write_text(json.dumps({"module_path": module_rel, "module_key": "k8s/cka/module-1.1-pods", "coverage_plan": _PLAN}))

    # Seed a teaching audit so route_one has score + gaps immediately.
    audit_dir = repo / ".pipeline" / "teaching-audit"
    audit_dir.mkdir(parents=True)
    slug = "k8s-cka-module-1.1-pods"
    (audit_dir / f"{slug}.json").write_text(json.dumps({
        "teaching_score": 2.5,
        "rubric_score": 2.5,
        "teaching_gaps": ["Quiz tests recall, not scenarios", "No worked example"],
    }))

    subprocess.run(["git", "add", "-A"], cwd=repo, check=True)
    subprocess.run(["git", "commit", "-m", "seed"], cwd=repo, check=True, capture_output=True)

    # Patch every module's root pointer. Each module captured ``_REPO_ROOT``
    # at import time; overwrite them all to the fake repo.
    monkeypatch.setattr(state, "REPO_ROOT", repo)
    monkeypatch.setattr(state, "STATE_DIR", repo / ".pipeline" / "quality-pipeline")
    monkeypatch.setattr(state, "CONTENT_ROOT", repo / "src" / "content" / "docs")
    monkeypatch.setattr(stages, "_REPO_ROOT", repo)
    monkeypatch.setattr(stages, "_AUDIT_DIR", repo / ".pipeline" / "teaching-audit")
    monkeypatch.setattr(pipeline, "_REPO_ROOT", repo)
    monkeypatch.setattr(pipeline, "_CONTENT_ROOT", repo / "src" / "content" / "docs")
    # gates.py uses module-level constants captured at import for the
    # ledger and audit subprocesses. Without these patches, integration
    # tests that exercise merge_one would write rows to the REAL
    # docs/quality-progress.tsv and pollute the production audit trail.
    from scripts.quality import gates
    monkeypatch.setattr(gates, "_REPO_ROOT", repo)
    monkeypatch.setattr(gates, "_AUDIT_DIR", repo / ".pipeline" / "teaching-audit")
    monkeypatch.setattr(gates, "LEDGER_PATH", repo / "docs" / "quality-progress.tsv")
    # Disable real-LLM sampling in tests — the audit subprocess would
    # call gemini for real and the test rig has no dispatch stub for it.
    monkeypatch.setenv("KUBEDOJO_GATES_SAMPLE_RATE", "0")
    # Prompt docs aren't present in the fake repo; stub the startup check.
    monkeypatch.setattr("scripts.quality.pipeline.assert_required_docs_exist", lambda: None)
    # #388 density-gate bypass: the seed/rewrite fixtures are intentionally
    # tiny (~5 prose words) to keep the suite fast and readable. The
    # production density gate would (correctly) reject them as REWRITE-
    # tier, but every existing test was written to validate stage
    # mechanics, NOT density. Density behavior is exercised by dedicated
    # tests in test_quality_density.py and the round-trip test in this
    # file. The bypass forces ``classify() == PASS`` everywhere these
    # stub modules are read; tests that specifically need REWRITE-tier
    # behavior can monkeypatch this back to the real implementation.
    from scripts.quality import density as _density
    def _always_pass(_text: str) -> _density.DensityMetrics:
        return _density.DensityMetrics(
            prose_words=2000, textual_words=2200, nonblank_lines=100,
            total_paragraphs=80, prose_paragraphs=60,
            w_per_line=22.0, w_per_para=33.0,
        )
    monkeypatch.setattr(_density, "evaluate_text", _always_pass)

    return repo


def _bootstrap(fake_repo: Path) -> str:
    """Run bootstrap against the fake repo; return the seeded slug."""
    modules = pipeline.iter_all_modules()
    assert len(modules) == 1
    module_path = modules[0]
    slug = state.slug_for(module_path)
    st = state.new_state(module_path, module_index=0)
    state.save_state(st)
    return slug


# ---- dispatch stubs ---------------------------------------------------


_REWRITTEN_MODULE = """---
title: Pods Fundamentals
sidebar:
  order: 1
---

# Pods

Rewritten pedagogically sound content.

## Quiz

Scenario-based question.
"""


def _writer_stub_output(track: str = "rewrite") -> str:
    """Codex-style output: reasoning prose, then the module."""
    return f"Here is the {track}-ed module with improvements:\n\n{_REWRITTEN_MODULE}"


def _review_approve_output(quote: str = _QUOTE) -> str:
    """Reviewer verdict with reasoning prose FIRST, verdict JSON LAST."""
    payload = {
        "verdict": "approve",
        "rubric_score": 4.5,
        "teaching_score": 4.3,
        "must_fix": [],
        "nits": [],
        "strengths": ["Good worked example"],
        "reasoning": "Now teaches properly.",
        "dimensions": {f"D{i}": 5 for i in range(1, 9)},
        "dimension_evidence": {f"D{i}": quote for i in range(1, 9)},
        "coverage": {"outcomes": [{"outcome": "Explain pods", "teaching": quote, "practice": quote,
                                   "assessment": quote}], "topics": [{"topic": "Pods", "teaching": quote}]},
        "scope_assessment": {"basis_checked": True, "unjustified_omissions": [], "rationale": "Plan covered."},
    }
    return (
        "Let me reason through this module.\n\n"
        '{"thinking": "checking scenarios", "draft_score": 4.0}\n\n'
        "My verdict:\n\n" + json.dumps(payload)
    )


def _review_changes_output(must_fix: list[str]) -> str:
    payload = {
        "verdict": "changes_requested",
        "rubric_score": 3.5,
        "teaching_score": 3.5,
        "must_fix": must_fix,
        "nits": [],
        "strengths": [],
        "reasoning": "Quiz still weak.",
    }
    return "Reviewing.\n\n" + json.dumps(payload)


def _install_reviewed_candidate(repo: Path, st: dict) -> None:
    wt = worktree.create_worktree(repo, st["slug"])
    (wt / st["module_path"]).write_text(_REWRITTEN_MODULE)
    subprocess.run(["git", "add", st["module_path"]], cwd=wt, check=True)
    subprocess.run(["git", "commit", "-m", "candidate"], cwd=wt, check=True, capture_output=True)
    payload = json.loads(_review_approve_output().split("My verdict:\n\n")[1])
    candidate, plan = stages._review_digests(_REWRITTEN_MODULE, _PLAN)
    st["review"] = {"verdict": "approve", "must_fix": [], "payload": payload,
                    "candidate_sha256": candidate, "plan_sha256": plan}


def _stubbed_dispatch(writer_out: str, review_out: str):
    """Build a dispatch fake keyed by agent — so write and review paths
    can return different content, matching the cross-family boundary."""
    def fake_dispatch(agent, prompt, *, timeout, model=None, cwd=None, tools_disabled=False):
        if "## Your task" in prompt and "reviewing a KubeDojo module" in prompt:
            return DispatchResult(
                ok=True, stdout=review_out, stderr="", returncode=0,
                duration_sec=0.1, agent=agent, model=model,
            )
        return DispatchResult(
            ok=True, stdout=writer_out, stderr="", returncode=0,
            duration_sec=0.1, agent=agent, model=model,
        )
    return fake_dispatch


# ---- unit-ish stage tests --------------------------------------------


def test_route_rewrite_when_score_below_threshold(fake_repo, monkeypatch):
    slug = _bootstrap(fake_repo)
    stages.audit_one(slug)
    st = state.load_state(slug)
    assert st["stage"] == "AUDITED"
    assert st["audit"]["teaching_score"] == 2.5

    stages.route_one(slug)
    st = state.load_state(slug)
    assert st["stage"] == "WRITE_PENDING"
    assert st["route"]["track"] == "rewrite"
    assert st["writer"] == "agy"  # queue PRIMARY writer → agy Google lane (#2125)
    assert st["reviewer"] == "claude"


def test_route_reviewer_is_agy_when_author_is_claude(fake_repo, monkeypatch):
    """When the queue assigns Claude as the writer, the cross-family reviewer
    is agy (the Google lane that replaced the retired gemini-cli, #2125) — not
    the dead gemini agent. Guards stages.route_one's reviewer selection (#2230)."""
    slug = _bootstrap(fake_repo)
    stages.audit_one(slug)
    # Force the queue to hand back a Claude author for this slug.
    monkeypatch.setattr(
        stages.queue, "model_to_agent",
        lambda _writer: ("claude", "claude-opus-4-8"),
    )
    stages.route_one(slug)
    st = state.load_state(slug)
    assert st["writer"] == "claude"
    assert st["reviewer"] == "agy"


def test_route_skips_rewrite_when_score_high_and_structure_complete(fake_repo, monkeypatch):
    """Score ≥ 4.0 AND all structural sections present → CITATION_CLEANUP_ONLY."""
    slug = _bootstrap(fake_repo)
    # Seed a high audit score and a complete module.
    st = state.load_state(slug)
    st["audit"] = {"teaching_score": 4.5, "teaching_gaps": []}
    st["stage"] = "AUDITED"
    state.save_state(st)
    # Make the module structurally complete.
    full_module = """---
title: Pods
sidebar:
  order: 1
---

## Quiz

Q.

## Hands-On Exercise

Do the thing.

## Common Mistakes

Table.

## Did You Know?

Facts.
"""
    (fake_repo / st["module_path"]).write_text(full_module)
    stages.route_one(slug)
    st = state.load_state(slug)
    assert st["stage"] == "CITATION_CLEANUP_ONLY"


def test_write_one_happy_path_creates_worktree_commit(fake_repo, monkeypatch):
    slug = _bootstrap(fake_repo)
    stages.audit_one(slug)
    stages.route_one(slug)

    monkeypatch.setattr(stages, "dispatch", _stubbed_dispatch(_writer_stub_output(), _review_approve_output()))

    stages.write_one(slug, timeout=10)
    st = state.load_state(slug)
    assert st["stage"] == "WRITE_DONE"
    assert st["write"]["commit_sha"]
    assert st["write"]["agent"] == "agy"
    # The worktree should exist with the new content.
    wt = worktree.worktree_dir(fake_repo, slug)
    assert wt.exists()
    assert "Rewritten pedagogically sound content" in (wt / st["module_path"]).read_text()


def test_write_one_extract_failure_marks_failed(fake_repo, monkeypatch):
    """If Codex's output is truncated mid-code-block, extractor raises → FAILED."""
    slug = _bootstrap(fake_repo)
    stages.audit_one(slug)
    stages.route_one(slug)

    truncated = """---
title: Pods
---

Start of body.

```bash
kubectl get pods
"""  # no closing fence

    def bad_dispatch(agent, prompt, *, timeout, model=None, cwd=None, tools_disabled=False):
        return DispatchResult(
            ok=True, stdout=truncated, stderr="", returncode=0,
            duration_sec=0.1, agent=agent, model=model,
        )

    monkeypatch.setattr(stages, "dispatch", bad_dispatch)
    stages.write_one(slug, timeout=10)
    st = state.load_state(slug)
    assert st["stage"] == "FAILED"
    assert "truncated" in (st.get("failure_reason") or "").lower()


def test_write_one_extract_failure_persists_raw_diag(fake_repo, monkeypatch):
    """When the extractor rejects the writer's output, ``_write_in_worktree``
    must persist the raw stdout/stderr to
    ``.pipeline/quality-pipeline/<slug>.write.<attempt_id>.failed.json``
    so the failure is debuggable without re-dispatching the same prompt.

    Regression guard for the v2 first-real-module smoke (k8s-capa
    module-1.2-argo-events) where ``failure_reason`` only said
    "no frontmatter delimiter found" and we had no way to see what
    Claude actually returned.
    """
    slug = _bootstrap(fake_repo)
    stages.audit_one(slug)
    stages.route_one(slug)

    bogus_output = "I think the user wants me to refuse this rewrite."

    def bad_dispatch(agent, prompt, *, timeout, model=None, cwd=None, tools_disabled=False):
        return DispatchResult(
            ok=True, stdout=bogus_output, stderr="some chatter",
            returncode=0, duration_sec=0.42, agent=agent, model=model,
        )

    monkeypatch.setattr(stages, "dispatch", bad_dispatch)
    stages.write_one(slug, timeout=10)

    st = state.load_state(slug)
    assert st["stage"] == "FAILED"
    reason = (st.get("failure_reason") or "").lower()
    assert "frontmatter" in reason or "extractor" in reason
    assert ".failed.json" in reason, "failure_reason should reference the diag artifact"

    diag_dir = fake_repo / ".pipeline" / "quality-pipeline" / "diagnostics"
    diag_files = sorted(diag_dir.glob(f"{slug}.write.*.failed.json"))
    assert len(diag_files) == 1, f"expected exactly one diag file, got {diag_files}"
    payload = json.loads(diag_files[0].read_text())
    assert payload["slug"] == slug
    assert payload["error"].startswith("extract_failed")
    assert payload["stdout"] == bogus_output
    assert payload["stderr"] == "some chatter"
    assert payload["dispatch"]["returncode"] == 0
    assert payload["prompt_sha256"] and len(payload["prompt_sha256"]) == 64
    assert payload["prompt_len_chars"] > 0


def test_write_one_dispatch_nonzero_persists_raw_diag(fake_repo, monkeypatch):
    """Dispatcher non-zero exit (not a refusal — those are
    ``DispatcherUnavailable``) is a real failure. The raw stdout/stderr
    must be persisted alongside the FAILED transition.
    """
    slug = _bootstrap(fake_repo)
    stages.audit_one(slug)
    stages.route_one(slug)

    def crashing_dispatch(agent, prompt, *, timeout, model=None, cwd=None, tools_disabled=False):
        return DispatchResult(
            ok=False, stdout="partial output before crash",
            stderr="Traceback (most recent call last): RuntimeError: kaboom",
            returncode=1, duration_sec=2.7, agent=agent, model=model,
        )

    monkeypatch.setattr(stages, "dispatch", crashing_dispatch)
    stages.write_one(slug, timeout=10)

    st = state.load_state(slug)
    assert st["stage"] == "FAILED"
    reason = (st.get("failure_reason") or "")
    assert "dispatch failed" in reason.lower()
    assert ".failed.json" in reason

    diag_dir = fake_repo / ".pipeline" / "quality-pipeline" / "diagnostics"
    diag_files = sorted(diag_dir.glob(f"{slug}.write.*.failed.json"))
    assert len(diag_files) == 1
    payload = json.loads(diag_files[0].read_text())
    assert payload["error"] == "dispatch_failed"
    assert payload["dispatch"]["returncode"] == 1
    assert payload["dispatch"]["ok"] is False
    assert "kaboom" in payload["stderr"]
    assert payload["stdout"] == "partial output before crash"


def test_write_one_hang_retry_succeeds(fake_repo, monkeypatch):
    """Hang signature (ok=False, empty stdout, "timed out" in stderr) on the
    first dispatch must trigger ONE retry. If the retry returns valid
    markdown, the write succeeds and the first-attempt raw is persisted
    under the ``-r0`` sub-id so the postmortem keeps both. Regression
    guard for v2 smoke round 4 (argo-events) where the retry write hung
    after a successful write 1 ~10 min earlier — same Anthropic-side rate
    window theory.
    """
    slug = _bootstrap(fake_repo)
    stages.audit_one(slug)
    stages.route_one(slug)

    monkeypatch.setattr(stages, "_HANG_RETRY_SLEEP_SEC", 0)
    sleep_calls: list[float] = []
    monkeypatch.setattr(stages.time, "sleep", lambda s: sleep_calls.append(s))

    call_count = {"n": 0}

    def hang_then_ok(agent, prompt, *, timeout, model=None, cwd=None, tools_disabled=False):
        call_count["n"] += 1
        if call_count["n"] == 1:
            return DispatchResult(
                ok=False, stdout="", stderr="Claude timed out after 900s",
                returncode=1, duration_sec=900.17, agent=agent, model=model,
            )
        return DispatchResult(
            ok=True, stdout=_writer_stub_output(), stderr="",
            returncode=0, duration_sec=0.1, agent=agent, model=model,
        )

    monkeypatch.setattr(stages, "dispatch", hang_then_ok)
    stages.write_one(slug, timeout=10)

    st = state.load_state(slug)
    assert st["stage"] == "WRITE_DONE", st.get("failure_reason")
    assert st["write"]["commit_sha"]
    assert call_count["n"] == 2, "second dispatch must have run"
    assert sleep_calls == [0], "exactly one bounded sleep before the retry"

    # Only the first-attempt raw is persisted; the successful retry
    # doesn't leave a diag because there's nothing to debug.
    diag_dir = fake_repo / ".pipeline" / "quality-pipeline" / "diagnostics"
    diag_files = sorted(diag_dir.glob(f"{slug}.write.*.failed.json"))
    assert len(diag_files) == 1, f"expected exactly one r0 diag, got {diag_files}"
    payload = json.loads(diag_files[0].read_text())
    assert payload["error"] == "dispatch_hang_attempt1"
    assert payload["attempt_id"].endswith("-r0")
    assert payload["stdout"] == ""
    assert "timed out" in payload["stderr"].lower()


def test_write_one_hang_double_retry_fails(fake_repo, monkeypatch):
    """If both the original dispatch and the retry hang, FAIL with both
    diags persisted under ``-r0`` and ``-r1`` sub-ids. Bound is ONE retry
    so a stuck rate window can't infinitely loop the writer."""
    slug = _bootstrap(fake_repo)
    stages.audit_one(slug)
    stages.route_one(slug)

    monkeypatch.setattr(stages, "_HANG_RETRY_SLEEP_SEC", 0)
    monkeypatch.setattr(stages.time, "sleep", lambda s: None)

    call_count = {"n": 0}

    def always_hang(agent, prompt, *, timeout, model=None, cwd=None, tools_disabled=False):
        call_count["n"] += 1
        return DispatchResult(
            ok=False, stdout="", stderr="Claude timed out after 900s",
            returncode=1, duration_sec=900.17, agent=agent, model=model,
        )

    monkeypatch.setattr(stages, "dispatch", always_hang)
    stages.write_one(slug, timeout=10)

    st = state.load_state(slug)
    assert st["stage"] == "FAILED"
    assert call_count["n"] == 2, "must retry exactly once before giving up"
    reason = (st.get("failure_reason") or "")
    assert "hung twice" in reason.lower()
    assert "-r0.failed.json" in reason and "-r1.failed.json" in reason

    diag_dir = fake_repo / ".pipeline" / "quality-pipeline" / "diagnostics"
    diag_files = sorted(diag_dir.glob(f"{slug}.write.*.failed.json"))
    assert len(diag_files) == 2, f"expected r0 + r1 diags, got {diag_files}"

    by_attempt = {json.loads(p.read_text())["attempt_id"]: json.loads(p.read_text())
                  for p in diag_files}
    r0_id = next(k for k in by_attempt if k.endswith("-r0"))
    r1_id = next(k for k in by_attempt if k.endswith("-r1"))
    assert by_attempt[r0_id]["error"] == "dispatch_hang_attempt1"
    assert by_attempt[r1_id]["error"] == "dispatch_hang_attempt2"
    # Both share the same lease attempt prefix — they're sub-IDs of one attempt.
    assert r0_id[:-3] == r1_id[:-3]

    # Worktree + branch cleaned up so the next retry starts fresh
    # (Codex must-fix #6/#8 — broad cleanup handler).
    assert not worktree.worktree_dir(fake_repo, slug).exists()


def test_write_one_dispatcher_unavailable_reverts_to_pending(fake_repo, monkeypatch):
    """Dispatcher unavailability must REVERT to WRITE_PENDING so the
    module stays retryable. v1's failure mode silently drained the queue."""
    slug = _bootstrap(fake_repo)
    stages.audit_one(slug)
    stages.route_one(slug)

    def unavail(agent, prompt, *, timeout, model=None, cwd=None, tools_disabled=False):
        raise dispatchers.DispatcherUnavailable("claude unavailable")

    monkeypatch.setattr(stages, "dispatch", unavail)
    with pytest.raises(dispatchers.DispatcherUnavailable):
        stages.write_one(slug, timeout=10)
    st = state.load_state(slug)
    assert st["stage"] == "WRITE_PENDING"
    # Branch cleaned up so next run starts fresh.
    assert not worktree.worktree_dir(fake_repo, slug).exists()


# ---- reviewer-reads-from-worktree regression guard (Codex must-fix #1) ----


def test_reviewer_reads_module_from_worktree_not_primary(fake_repo, monkeypatch):
    """Codex must-fix #1 regression guard.

    v1 reviewer always read from ``main``. In this test, the worktree
    has the new content, primary has the old content. The reviewer
    prompt captured by our stub must contain the NEW content — if it
    contains the old content, the fix regressed.
    """
    slug = _bootstrap(fake_repo)
    stages.audit_one(slug)
    stages.route_one(slug)

    captured_review_prompt: list[str] = []

    def capturing_dispatch(agent, prompt, *, timeout, model=None, cwd=None, tools_disabled=False):
        if "reviewing a KubeDojo module" in prompt:
            captured_review_prompt.append(prompt)
            return DispatchResult(
                ok=True, stdout=_review_approve_output(), stderr="", returncode=0,
                duration_sec=0.1, agent=agent, model=model,
            )
        return DispatchResult(
            ok=True, stdout=_writer_stub_output(), stderr="", returncode=0,
            duration_sec=0.1, agent=agent, model=model,
        )

    monkeypatch.setattr(stages, "dispatch", capturing_dispatch)
    # No-op citations so we reach review.
    monkeypatch.setattr(
        stages, "process_module_citations",
        lambda p, *, verifier=None, fetcher=None: CitationResult(new_text=p.read_text(), had_sources_section=False),
    )

    stages.write_one(slug, timeout=10)
    stages.citation_verify_one(slug)
    stages.review_one(slug, timeout=10)

    assert captured_review_prompt, "reviewer was never invoked"
    prompt = captured_review_prompt[0]
    # The primary file still has "Original content about pods". The
    # worktree has "Rewritten pedagogically sound content". Regression
    # guard: the NEW text must be in the reviewer prompt.
    assert "Rewritten pedagogically sound content" in prompt
    assert "Original content about pods" not in prompt


# ---- REVIEW_CHANGES retry loop (Codex must-fix #4) -------------------


def test_review_changes_routes_back_to_write_pending_with_retry_count(fake_repo, monkeypatch):
    slug = _bootstrap(fake_repo)
    stages.audit_one(slug)
    stages.route_one(slug)

    monkeypatch.setattr(
        stages, "dispatch",
        _stubbed_dispatch(_writer_stub_output(), _review_changes_output(["fix quiz Q3"])),
    )
    monkeypatch.setattr(
        stages, "process_module_citations",
        lambda p, *, verifier=None, fetcher=None: CitationResult(new_text=p.read_text(), had_sources_section=False),
    )

    stages.write_one(slug, timeout=10)
    stages.citation_verify_one(slug)
    stages.review_one(slug, timeout=10)
    st = state.load_state(slug)
    assert st["stage"] == "REVIEW_CHANGES"
    assert st["review"]["must_fix"] == ["fix quiz Q3"]

    # Must route back to WRITE_PENDING with retry_count bumped.
    stages.handle_review_changes(slug)
    st = state.load_state(slug)
    assert st["stage"] == "WRITE_PENDING"
    assert st["retry_count"] == 1


def test_review_changes_tiebreaker_after_cap(fake_repo, monkeypatch):
    slug = _bootstrap(fake_repo)
    st = state.load_state(slug)
    st["stage"] = "REVIEW_CHANGES"
    st["retry_count"] = stages.RETRY_CAP
    st["writer"] = "codex"
    st["reviewer"] = "claude"
    state.save_state(st)

    stages.handle_review_changes(slug)
    st = state.load_state(slug)
    assert st["stage"] == "REVIEW_PENDING"
    assert st["reviewer"] == "agy"  # tiebreaker is agy now (#2125)
    assert st["retry_count"] == stages.RETRY_CAP  # not bumped past cap


def test_review_changes_tiebreaker_also_changes_fails_terminally(fake_repo, monkeypatch):
    """Tiebreaker (agy) returning CHANGES must mark FAILED, not loop.

    Regression for the infinite-tiebreaker bug caught while running
    9.4 in the #378 recovery: previously, every call after the
    tiebreaker's CHANGES re-routed back to tiebreaker forever (only
    ``run_module``'s max_cycles eventually bailed, after wasting ~5
    tiebreaker calls per module).
    """
    slug = _bootstrap(fake_repo)
    st = state.load_state(slug)
    st["stage"] = "REVIEW_CHANGES"
    st["retry_count"] = stages.RETRY_CAP
    st["writer"] = "codex"
    st["reviewer"] = "agy"  # tiebreaker already ran (agy, #2125)
    st["review"] = {
        "verdict": "changes_requested",
        "must_fix": ["scaffold complexity is missing", "no inline prompts", "two facts wrong"],
    }
    state.save_state(st)

    stages.handle_review_changes(slug)
    st = state.load_state(slug)
    assert st["stage"] == "FAILED"
    assert st.get("failure_reason")
    assert "tiebreaker" in st["failure_reason"]
    assert "manual review required" in st["failure_reason"]
    assert "scaffold complexity is missing" in st["failure_reason"]


# ---- rebase-then-ff merge across main advancing (Codex must-fix #3) ---


def test_ff_merge_after_main_advances_with_real_pipeline_modules(fake_repo, monkeypatch):
    """Two modules merge cleanly even though the second's branch was cut
    before the first's merge landed on main.

    Uses the stages + merge path (not the worktree helpers directly) so
    the regression guard covers the full pipeline wiring of Codex #3,
    not just the ``rebase_onto_main`` helper (already tested in
    test_quality_worktree.py)."""
    # Add a second module.
    mod2_rel = "src/content/docs/k8s/cka/module-1.2-services.md"
    (fake_repo / mod2_rel).parent.mkdir(parents=True, exist_ok=True)
    (fake_repo / mod2_rel).write_text("---\ntitle: Services\nsidebar:\n  order: 2\n---\n\nBody.\n")
    (fake_repo / "docs/citation-seeds/k8s-cka-module-1.2-services.json").write_text(json.dumps({
        "module_path": mod2_rel, "module_key": "k8s/cka/module-1.2-services", "coverage_plan": _PLAN,
    }))
    audit_dir = fake_repo / ".pipeline" / "teaching-audit"
    slug2 = "k8s-cka-module-1.2-services"
    (audit_dir / f"{slug2}.json").write_text(json.dumps({
        "teaching_score": 2.0,
        "teaching_gaps": ["Thin"],
    }))
    subprocess.run(["git", "add", "-A"], cwd=fake_repo, check=True)
    subprocess.run(["git", "commit", "-m", "seed m2"], cwd=fake_repo, check=True, capture_output=True)

    monkeypatch.setattr(
        stages, "dispatch",
        _stubbed_dispatch(_writer_stub_output(), _review_approve_output()),
    )
    monkeypatch.setattr(
        stages, "process_module_citations",
        lambda p, *, verifier=None, fetcher=None: CitationResult(new_text=p.read_text(), had_sources_section=False),
    )

    modules = sorted(pipeline.iter_all_modules())
    for i, mod_path in enumerate(modules):
        slug = state.slug_for(mod_path)
        if state.load_state(slug) is None:
            st = state.new_state(mod_path, module_index=i)
            state.save_state(st)

    # Drive both through a full run — they both merge to main.
    slugs = sorted(state.iter_state_slugs())
    for slug in slugs:
        terminal = stages.run_module(slug)
        assert terminal == "COMMITTED", f"{slug}: expected COMMITTED, got {terminal}"

    # Both files now on main with rewritten content.
    log = subprocess.run(
        ["git", "log", "--oneline", "-5"], cwd=fake_repo, capture_output=True, text=True, check=True
    ).stdout
    assert "rewrite" in log.lower() or "quality" in log.lower()
    # Primary stays on main, clean.
    assert worktree.current_branch(fake_repo) == "main"
    assert not worktree.has_uncommitted(fake_repo)


# ---- crash recovery ---------------------------------------------------


def test_recover_write_in_progress_with_branch_commit_advances_to_done(fake_repo, monkeypatch):
    slug = _bootstrap(fake_repo)
    stages.audit_one(slug)
    stages.route_one(slug)
    monkeypatch.setattr(
        stages, "dispatch",
        _stubbed_dispatch(_writer_stub_output(), _review_approve_output()),
    )
    # Start the write, then simulate SIGKILL: manually reset stage to
    # WRITE_IN_PROGRESS after the branch has a commit.
    stages.write_one(slug, timeout=10)
    st = state.load_state(slug)
    assert st["stage"] == "WRITE_DONE"
    committed_sha = st["write"]["commit_sha"]
    # Simulate SIGKILL scenario: stage back to WRITE_IN_PROGRESS, branch
    # still has the commit.
    st["stage"] = "WRITE_IN_PROGRESS"
    state.save_state(st)

    stages.recover_in_progress(slug)
    st = state.load_state(slug)
    assert st["stage"] == "WRITE_DONE"
    assert st["write"]["commit_sha"] == committed_sha
    assert st["write"].get("recovered") is True


def test_recover_write_in_progress_with_no_branch_reverts_to_pending(fake_repo):
    slug = _bootstrap(fake_repo)
    st = state.load_state(slug)
    st["stage"] = "WRITE_IN_PROGRESS"
    st["attempt_id"] = "abcdef123456"
    state.save_state(st)

    stages.recover_in_progress(slug)
    st = state.load_state(slug)
    assert st["stage"] == "WRITE_PENDING"


def test_recover_review_in_progress_reverts_to_pending(fake_repo):
    slug = _bootstrap(fake_repo)
    st = state.load_state(slug)
    st["stage"] = "REVIEW_IN_PROGRESS"
    state.save_state(st)
    stages.recover_in_progress(slug)
    st = state.load_state(slug)
    assert st["stage"] == "REVIEW_PENDING"


# ---- full-pipeline happy path ----------------------------------------


def test_full_pipeline_single_module_ends_committed(fake_repo, monkeypatch):
    slug = _bootstrap(fake_repo)
    monkeypatch.setattr(
        stages, "dispatch",
        _stubbed_dispatch(_writer_stub_output(), _review_approve_output()),
    )
    monkeypatch.setattr(
        stages, "process_module_citations",
        lambda p, *, verifier=None, fetcher=None: CitationResult(new_text=p.read_text(), had_sources_section=False),
    )

    terminal = stages.run_module(slug)
    assert terminal == "COMMITTED"

    st = state.load_state(slug)
    assert st["write"]["commit_sha"]
    assert st["review"]["verdict"] == "approve"
    assert st["commit"]["sha"]
    # Primary has the new content.
    new_text = (fake_repo / st["module_path"]).read_text()
    assert "Rewritten pedagogically sound content" in new_text
    # Worktree torn down.
    assert not worktree.worktree_dir(fake_repo, slug).exists()


# ---- pipeline CLI helpers ---------------------------------------------


def test_iter_all_modules_excludes_uk_and_index(fake_repo, monkeypatch):
    # Seed a UK translation and an index.md — both must be excluded.
    (fake_repo / "src/content/docs/uk/cka").mkdir(parents=True, exist_ok=True)
    (fake_repo / "src/content/docs/uk/cka/module-1.1-pods.md").write_text("---\ntitle: UK\n---\n")
    (fake_repo / "src/content/docs/k8s/cka/index.md").write_text("---\ntitle: Index\n---\n")
    modules = pipeline.iter_all_modules()
    assert all("/uk/" not in p.as_posix() for p in modules)
    assert all(p.name != "index.md" for p in modules)


def test_bootstrap_is_idempotent(fake_repo, monkeypatch):
    class NSMock:
        pass

    ns = NSMock()
    pipeline.cmd_bootstrap(ns)  # type: ignore[arg-type]
    first_slugs = state.iter_state_slugs()
    pipeline.cmd_bootstrap(ns)  # type: ignore[arg-type]
    second_slugs = state.iter_state_slugs()
    assert first_slugs == second_slugs


def test_bootstrap_migrates_v1_state_missing_module_index(fake_repo, monkeypatch):
    """v1 state files had no ``module_index``. Bootstrap must add it
    without destroying audit / history fields — non-destructive migration.
    """
    # Seed a v1-shaped state (no module_index, has audit + history).
    modules = pipeline.iter_all_modules()
    assert modules
    slug = state.slug_for(modules[0])
    state.STATE_DIR.mkdir(parents=True, exist_ok=True)
    v1_state = {
        "slug": slug,
        "module_path": modules[0].relative_to(fake_repo).as_posix(),
        "stage": "AUDITED",
        "audit": {"teaching_score": 3.0, "teaching_gaps": ["thin"]},
        "history": [{"at": "2026-04-24T00:00:00Z", "stage": "AUDITED", "note": "v1"}],
        "retry_count": 0,
    }
    state.save_state(v1_state)

    class NSMock:
        pass

    pipeline.cmd_bootstrap(NSMock())  # type: ignore[arg-type]
    migrated = state.load_state(slug)
    assert migrated is not None
    assert migrated["module_index"] == 0  # first module in sorted order
    # Pre-existing fields preserved.
    assert migrated["stage"] == "AUDITED"
    assert migrated["audit"]["teaching_score"] == 3.0
    assert migrated["history"][0]["note"] == "v1"


# ---- Codex v2-review fatals + musts --------------------------------


def _high_score_module_setup(fake_repo: Path) -> str:
    """Helper: seed a module at high audit score + complete structure
    so route_one sends it to CITATION_CLEANUP_ONLY.

    COMMITS the module content — the cleanup-only path creates a
    worktree from ``main``'s tip, so uncommitted primary changes would
    be invisible to the citation pass.
    """
    slug = _bootstrap(fake_repo)
    st = state.load_state(slug)
    assert st is not None
    st["audit"] = {"teaching_score": 4.5, "teaching_gaps": []}
    st["stage"] = "AUDITED"
    state.save_state(st)
    module_path = fake_repo / st["module_path"]
    module_path.write_text("""---
title: Pods
sidebar:
  order: 1
---

# Body

## Quiz

Q.

## Hands-On Exercise

Do.

## Common Mistakes

Table.

## Did You Know?

Facts.

## Sources

- [Official docs](https://kubernetes.io/docs/) — authoritative reference

## Next
""")
    subprocess.run(["git", "add", st["module_path"]], cwd=fake_repo, check=True)
    subprocess.run(
        ["git", "commit", "-m", "seed high-score module"],
        cwd=fake_repo, check=True, capture_output=True,
    )
    stages.route_one(slug)
    return slug


def test_cleanup_only_never_writes_primary_checkout(fake_repo, monkeypatch):
    """Codex fatal #1 regression guard.

    CITATION_CLEANUP_ONLY path must NOT mutate the primary module file.
    All work happens in a throwaway worktree from main.
    """
    slug = _high_score_module_setup(fake_repo)
    st = state.load_state(slug)
    assert st["stage"] == "CITATION_CLEANUP_ONLY"
    primary_module = fake_repo / st["module_path"]
    primary_content_before = primary_module.read_text()

    # Citation has a removal, so result.changed is True.
    def partial_verifier(_prompt):
        return DispatchResult(
            ok=True,
            stdout=json.dumps({"verdict": "partial", "reasoning": "weak", "excerpt": ""}),
            stderr="", returncode=0, duration_sec=0.1, agent="gemini", model=None,
        )

    stages.citation_verify_one(
        slug, verifier_fn=partial_verifier, fetcher_fn=lambda _u: "page"
    )
    # Primary must be byte-identical through the cleanup-only stage.
    assert primary_module.read_text() == primary_content_before

    # The work landed on a worktree branch, not main.
    st = state.load_state(slug)
    assert st["stage"] == "REVIEW_APPROVED"
    assert worktree.current_branch(fake_repo) == "main"
    assert not worktree.has_uncommitted(fake_repo)
    wt = worktree.worktree_dir(fake_repo, slug)
    assert wt.exists()
    # Worktree version has the removed citation; primary still does not.
    assert "kubernetes.io/docs" not in (wt / st["module_path"]).read_text()
    assert "kubernetes.io/docs" in primary_content_before


def test_cleanup_only_no_changes_ends_at_skipped_without_merge(fake_repo, monkeypatch):
    """Codex fatal #2 regression guard.

    When every citation verifies as 'supports', the cleanup-only path
    must NOT create a mergeable branch. It terminates at SKIPPED and
    tears down the throwaway worktree.
    """
    slug = _high_score_module_setup(fake_repo)

    def supports_verifier(_prompt):
        return DispatchResult(
            ok=True,
            stdout=json.dumps({"verdict": "supports", "reasoning": "direct", "excerpt": "q"}),
            stderr="", returncode=0, duration_sec=0.1, agent="gemini", model=None,
        )

    stages.citation_verify_one(
        slug, verifier_fn=supports_verifier, fetcher_fn=lambda _u: "page"
    )
    st = state.load_state(slug)
    assert st["stage"] == "SKIPPED"
    # Worktree torn down — no merge required.
    assert not worktree.worktree_dir(fake_repo, slug).exists()
    # No branch left over.
    import subprocess as _sp
    branch = worktree.branch_name(slug)
    rc = _sp.run(
        ["git", "rev-parse", "--verify", branch], cwd=fake_repo, capture_output=True,
        check=False,
    ).returncode
    assert rc != 0, "branch should be cleaned up"


def test_citation_verify_is_resumable_after_sigkill(fake_repo, monkeypatch):
    """Codex must #3 regression guard.

    If a SIGKILL lands after CITATION_VERIFY transition but before
    completion, re-running citation_verify_one should resume (not
    raise and not duplicate the transition).
    """
    slug = _high_score_module_setup(fake_repo)
    # Simulate "entered CITATION_VERIFY, then process died" by manually
    # setting the state without completing the work.
    st = state.load_state(slug)
    st["stage"] = "CITATION_VERIFY"
    st["citation_origin"] = "CITATION_CLEANUP_ONLY"
    state.save_state(st)

    def partial_verifier(_prompt):
        return DispatchResult(
            ok=True,
            stdout=json.dumps({"verdict": "partial", "reasoning": "weak", "excerpt": ""}),
            stderr="", returncode=0, duration_sec=0.1, agent="gemini", model=None,
        )

    # Resume — must not raise, must complete.
    stages.citation_verify_one(
        slug, verifier_fn=partial_verifier, fetcher_fn=lambda _u: "page"
    )
    st = state.load_state(slug)
    assert st["stage"] in ("REVIEW_APPROVED", "SKIPPED")  # depends on changes
    # _STAGE_FN also has CITATION_VERIFY handler so run_module can drive it.
    assert "CITATION_VERIFY" in stages._STAGE_FN


def test_recovery_does_not_trust_stale_branch_at_old_main(fake_repo, monkeypatch):
    """Codex must #4 regression guard.

    A branch sitting at the old main tip (no writer commit appended)
    should NOT falsely count as a completed write after main advances.
    """
    slug = _bootstrap(fake_repo)
    stages.audit_one(slug)
    stages.route_one(slug)

    import subprocess as _sp
    # Create the worktree/branch at current main, simulating the
    # writer's worktree just after create_worktree but before commit.
    worktree.create_worktree(fake_repo, slug)
    # Advance main via an unrelated commit on the primary.
    (fake_repo / "UNRELATED.md").write_text("advance\n")
    _sp.run(["git", "add", "UNRELATED.md"], cwd=fake_repo, check=True)
    _sp.run(["git", "commit", "-m", "unrelated"], cwd=fake_repo, check=True, capture_output=True)

    # Mark state WRITE_IN_PROGRESS as if a SIGKILL had landed pre-commit.
    st = state.load_state(slug)
    st["stage"] = "WRITE_IN_PROGRESS"
    st["attempt_id"] = "deadbeef"
    state.save_state(st)

    stages.recover_in_progress(slug)
    st = state.load_state(slug)
    # Branch never had a commit AHEAD of main, so recovery MUST revert.
    assert st["stage"] == "WRITE_PENDING"


def test_failed_modules_have_branches_cleaned_up(fake_repo, monkeypatch):
    """Codex must #9 regression guard.

    record_failure via _fail_and_cleanup must delete the worktree branch
    so FAILED modules don't leak branches forever.
    """
    slug = _bootstrap(fake_repo)
    stages.audit_one(slug)
    stages.route_one(slug)

    # Force a write failure by making Codex output malformed.
    def bad_dispatch(agent, prompt, *, timeout, model=None, cwd=None, tools_disabled=False):
        return DispatchResult(
            ok=True, stdout="garbage no frontmatter",
            stderr="", returncode=0, duration_sec=0.1, agent=agent, model=model,
        )
    monkeypatch.setattr(stages, "dispatch", bad_dispatch)

    stages.write_one(slug, timeout=10)
    st = state.load_state(slug)
    assert st["stage"] == "FAILED"

    # Branch deleted.
    import subprocess as _sp
    branch = worktree.branch_name(slug)
    rc = _sp.run(
        ["git", "rev-parse", "--verify", branch], cwd=fake_repo, capture_output=True,
        check=False,
    ).returncode
    assert rc != 0, "FAILED module must not leak its branch"
    # Worktree gone.
    assert not worktree.worktree_dir(fake_repo, slug).exists()


def test_approve_with_weak_dimension_cannot_pass_gate() -> None:
    payload = json.loads(_review_approve_output().split("My verdict:\n\n")[1])
    payload["dimensions"]["D1"] = 3
    result = DispatchResult(
        ok=True, stdout=json.dumps(payload), stderr="", returncode=0,
        duration_sec=0.1, agent="claude", model=None,
    )
    verdict = stages._parse_review_verdict(result)
    assert verdict == payload
    assert any("dimensions" in error for error in stages.validate_teaching_review(verdict, _QUOTE, _PLAN))


def test_scalar_approval_cannot_pass_gate() -> None:
    payload = json.dumps({
        "verdict": "approve",
        "rubric_score": "n/a",  # non-numeric
        "teaching_score": 4.5,
        "must_fix": [],
    })
    result = DispatchResult(
        ok=True, stdout=payload, stderr="", returncode=0,
        duration_sec=0.1, agent="claude", model=None,
    )
    verdict = stages._parse_review_verdict(result)
    assert verdict is not None
    assert stages.validate_teaching_review(verdict, _QUOTE, _PLAN)


def test_complete_eight_dimension_approval_needs_no_scalar_scores() -> None:
    payload = json.loads(_review_approve_output().split("My verdict:\n\n")[1])
    del payload["rubric_score"], payload["teaching_score"]
    result = DispatchResult(
        ok=True, stdout=json.dumps(payload), stderr="", returncode=0,
        duration_sec=0.1, agent="claude", model=None,
    )
    verdict = stages._parse_review_verdict(result)
    assert verdict is not None
    assert verdict["verdict"] == "approve"
    assert stages.validate_teaching_review(verdict, _QUOTE, _PLAN) == []


def test_merge_retries_on_transient_rebase_failure(fake_repo, monkeypatch):
    """Codex must #5 regression guard for the retry aspect.

    When rebase/ff fails (simulating a lost race — another worker landed
    on main first), merge_one should re-enter the lock + re-rebase +
    re-merge up to ``_MERGE_RETRY_CAP`` times rather than marking FAILED
    on first failure. This lets workers>1 operate without incorrectly
    killing racing modules.
    """
    slug = _bootstrap(fake_repo)
    monkeypatch.setattr(
        stages, "dispatch",
        _stubbed_dispatch(_writer_stub_output(), _review_approve_output()),
    )
    monkeypatch.setattr(
        stages, "process_module_citations",
        lambda p, *, verifier=None, fetcher=None: CitationResult(new_text=p.read_text(), had_sources_section=False),
    )
    stages.audit_one(slug)
    stages.route_one(slug)
    stages.write_one(slug, timeout=10)
    stages.citation_verify_one(slug)
    stages.review_one(slug, timeout=10)

    calls = {"rebase": 0}
    real_rebase = stages.rebase_onto_main

    def flaky_rebase(primary, slug_arg, **kw):
        calls["rebase"] += 1
        if calls["rebase"] == 1:
            raise worktree.WorktreeError("simulated race: another merge landed first")
        return real_rebase(primary, slug_arg, **kw)

    monkeypatch.setattr(stages, "rebase_onto_main", flaky_rebase)
    stages.merge_one(slug)

    st = state.load_state(slug)
    assert st["stage"] == "COMMITTED", f"retry should succeed after transient failure, got {st['stage']}"
    assert calls["rebase"] == 2, "rebase should have been retried once"


def test_merge_aborts_when_visual_aids_regressed(fake_repo, monkeypatch):
    """#377 hard gate: a rewrite that strips a Mermaid block must NOT
    land on main. ``merge_one`` aborts with FAILED + a visual-aid-
    regression reason; main stays untouched; worktree + branch are
    cleaned up.

    Seeds a module on main with a Mermaid diagram, then has the writer
    return a rewrite that drops the Mermaid block. The pipeline must
    refuse to merge.
    """
    # Re-seed the module on main with Mermaid content.
    slug = _bootstrap(fake_repo)
    module_rel = "src/content/docs/k8s/cka/module-1.1-pods.md"
    (fake_repo / module_rel).write_text("""---
title: Pods Fundamentals
sidebar:
  order: 1
---

# Pods

Original content.

```mermaid
graph TD
  A --> B
```

## Quiz

Question.
""")
    subprocess.run(["git", "add", "-A"], cwd=fake_repo, check=True)
    subprocess.run(["git", "commit", "-m", "seed mermaid"], cwd=fake_repo, check=True, capture_output=True)
    main_sha_before = subprocess.run(
        ["git", "rev-parse", "main"], cwd=fake_repo, capture_output=True, text=True, check=True,
    ).stdout.strip()

    # Writer stub strips the Mermaid block on rewrite (regression).
    rewritten_no_mermaid = """---
title: Pods Fundamentals
sidebar:
  order: 1
---

# Pods

Rewritten content but I forgot the diagram.

## Quiz

Better scenario question.
"""
    monkeypatch.setattr(
        stages, "dispatch",
        _stubbed_dispatch(
            f"reasoning prose...\n\n{rewritten_no_mermaid}",
            _review_approve_output("Rewritten content but I forgot the diagram."),
        ),
    )
    monkeypatch.setattr(
        stages, "process_module_citations",
        lambda p, *, verifier=None, fetcher=None: CitationResult(new_text=p.read_text(), had_sources_section=False),
    )

    terminal = stages.run_module(slug)
    assert terminal == "FAILED", f"expected FAILED on visual-aid regression, got {terminal}"

    st = state.load_state(slug)
    reason = (st.get("failure_reason") or "").lower()
    assert "visual-aid" in reason or "mermaid" in reason, f"reason missing regression context: {st.get('failure_reason')!r}"

    # Main must NOT have advanced — the abort happened before ff-merge.
    main_sha_after = subprocess.run(
        ["git", "rev-parse", "main"], cwd=fake_repo, capture_output=True, text=True, check=True,
    ).stdout.strip()
    assert main_sha_after == main_sha_before, "main advanced despite gate fail"

    # Module on main still has the Mermaid block (writer's drop didn't land).
    on_main = (fake_repo / module_rel).read_text()
    assert "```mermaid" in on_main

    # Worktree + branch torn down by _fail_and_cleanup.
    assert not worktree.worktree_dir(fake_repo, slug).exists()
    rc = subprocess.run(
        ["git", "rev-parse", "--verify", worktree.branch_name(slug)],
        cwd=fake_repo, capture_output=True, check=False,
    ).returncode
    assert rc != 0, "branch must be deleted after gate fail"


def test_cleanup_only_scrubs_worktree_when_state_file_disappears(fake_repo, monkeypatch):
    """Codex fourth-pass regression guard.

    On the cleanup-only changed path, if ``lease.load()`` returns None
    (state file vanished between create_worktree and final transition),
    the stage returns early WITHOUT an exception. The throwaway
    worktree + branch must still be scrubbed — the exception-only
    cleanup handler wouldn't fire, so the cleanup is inline in the
    st2-is-None branch.
    """
    slug = _high_score_module_setup(fake_repo)

    def partial_verifier(_prompt):
        return DispatchResult(
            ok=True,
            stdout=json.dumps({"verdict": "partial", "reasoning": "weak", "excerpt": ""}),
            stderr="", returncode=0, duration_sec=0.1, agent="gemini", model=None,
        )

    # Delete the state file just after the first CITATION_VERIFY
    # transition but before the final REVIEW_APPROVED transition.
    # Hook into state.load_state; on the THIRD load (first CITATION_VERIFY
    # transition load, then the "do we continue" load inside the final
    # lease, then our target — the pre-transition load), return None.
    original_load = state.load_state
    calls = {"n": 0}

    def vanishing_load(slug_arg):
        calls["n"] += 1
        # Let the CITATION_VERIFY transition succeed (first lease's load),
        # then claim the state has vanished on subsequent loads.
        if calls["n"] >= 3:
            return None
        return original_load(slug_arg)

    monkeypatch.setattr(state, "load_state", vanishing_load)

    # Should NOT raise — the st2-is-None branch returns cleanly after cleanup.
    stages.citation_verify_one(
        slug, verifier_fn=partial_verifier, fetcher_fn=lambda _u: "page"
    )

    # Worktree + branch must be gone despite the silent early-return.
    assert not worktree.worktree_dir(fake_repo, slug).exists()
    import subprocess as _sp
    rc = _sp.run(
        ["git", "rev-parse", "--verify", worktree.branch_name(slug)],
        cwd=fake_repo, capture_output=True, check=False,
    ).returncode
    assert rc != 0, "cleanup-only branch must not leak when state file vanishes"


def test_cleanup_only_removes_worktree_when_lease_raises_after_create(fake_repo, monkeypatch):
    """Codex third-pass regression guard.

    If the final ``state.state_lease`` times out or ``state.transition``
    raises AFTER ``create_worktree`` on the cleanup-only path, the new
    worktree + branch must still be torn down.
    """
    slug = _high_score_module_setup(fake_repo)

    def partial_verifier(_prompt):
        return DispatchResult(
            ok=True,
            stdout=json.dumps({"verdict": "partial", "reasoning": "weak", "excerpt": ""}),
            stderr="", returncode=0, duration_sec=0.1, agent="gemini", model=None,
        )

    # Force state_lease to raise TimeoutError on the SECOND call
    # (first is for the initial CITATION_VERIFY transition; second is
    # the final-state lease after the citation work completed).
    original_lease = state.state_lease
    calls = {"n": 0}

    from contextlib import contextmanager

    @contextmanager
    def flaky_lease(slug_arg, timeout=5.0):
        calls["n"] += 1
        if calls["n"] >= 2:
            raise TimeoutError("simulated post-write lease contention")
        with original_lease(slug_arg, timeout=timeout) as lease:
            yield lease

    monkeypatch.setattr(state, "state_lease", flaky_lease)

    with pytest.raises(TimeoutError):
        stages.citation_verify_one(
            slug, verifier_fn=partial_verifier, fetcher_fn=lambda _u: "page"
        )

    # Even though the final transition raised, the cleanup-only worktree
    # + branch must be gone.
    assert not worktree.worktree_dir(fake_repo, slug).exists()
    import subprocess as _sp
    rc = _sp.run(
        ["git", "rev-parse", "--verify", worktree.branch_name(slug)],
        cwd=fake_repo, capture_output=True, check=False,
    ).returncode
    assert rc != 0, "cleanup-only branch must not leak on post-write lease failure"


def test_cleanup_only_scrubs_worktree_when_create_worktree_raises_after_creation(
    fake_repo, monkeypatch
):
    """Codex round-5 regression guard.

    On the cleanup-only path the throwaway worktree must be scrubbed
    even if a BaseException-class exception (KeyboardInterrupt) lands
    AFTER ``create_worktree`` has physically created the worktree but
    BEFORE any post-call assignment in the calling function. Round-4's
    flag-based design (``worktree_created_here = True`` set after the
    call) had a Python-bytecode-level race window — round-5 closes it
    with an invariant ownership predicate (``from_stage`` +
    ``preexisting_worktree``) plus a filesystem .exists() probe in the
    BaseException handler.
    """
    slug = _high_score_module_setup(fake_repo)

    real_create = stages.create_worktree
    raised = {"n": 0}

    def real_then_raise(primary, slug_arg):
        # Honor the real contract: physically create the worktree +
        # branch on disk, then simulate a Ctrl-C landing immediately
        # post-return, before any caller-side flag could be set.
        real_create(primary, slug_arg)
        raised["n"] += 1
        raise KeyboardInterrupt("simulated post-create-worktree interrupt")

    monkeypatch.setattr(stages, "create_worktree", real_then_raise)

    with pytest.raises(KeyboardInterrupt):
        stages.citation_verify_one(slug)

    assert raised["n"] == 1, "create_worktree wrapper must have been hit"
    assert not worktree.worktree_dir(fake_repo, slug).exists(), (
        "round-5: throwaway worktree must be scrubbed after a post-create raise"
    )
    rc = subprocess.run(
        ["git", "rev-parse", "--verify", worktree.branch_name(slug)],
        cwd=fake_repo, capture_output=True, check=False,
    ).returncode
    assert rc != 0, "round-5: throwaway branch must not leak"


def test_cleanup_only_removes_worktree_when_write_text_raises(fake_repo, monkeypatch):
    """Codex re-review must regression guard.

    The cleanup-only path creates a fresh worktree. If
    ``module_file.write_text(result.new_text)`` raises (disk full,
    permissions, unicode error, ...) the worktree + branch must still
    be torn down — the prior fix had the write outside the inner
    try/except, so a write failure leaked the throwaway worktree.
    """
    slug = _high_score_module_setup(fake_repo)

    def partial_verifier(_prompt):
        return DispatchResult(
            ok=True,
            stdout=json.dumps({"verdict": "partial", "reasoning": "weak", "excerpt": ""}),
            stderr="", returncode=0, duration_sec=0.1, agent="gemini", model=None,
        )

    # Force write_text to raise. Patch Path.write_text for the specific
    # module_file the stage is about to write.
    original_write_text = Path.write_text
    wt = worktree.worktree_dir(fake_repo, slug)
    # (worktree doesn't exist yet; citation_verify_one will create it)

    def boomy_write_text(self, *a, **kw):
        # Only fail for writes inside the worktree (i.e. the result.new_text
        # write) — leave state-file writes alone.
        if str(self).startswith(str(fake_repo / ".worktrees")):
            raise OSError("simulated disk failure")
        return original_write_text(self, *a, **kw)

    monkeypatch.setattr(Path, "write_text", boomy_write_text)

    with pytest.raises(OSError):
        stages.citation_verify_one(
            slug, verifier_fn=partial_verifier, fetcher_fn=lambda _u: "page"
        )

    # Worktree + branch scrubbed despite the crash.
    assert not wt.exists()
    import subprocess as _sp
    rc = _sp.run(
        ["git", "rev-parse", "--verify", worktree.branch_name(slug)],
        cwd=fake_repo, capture_output=True, check=False,
    ).returncode
    assert rc != 0, "cleanup-only branch must not leak on write_text failure"


def test_merge_lock_timeout_reaches_fail_and_cleanup(fake_repo, monkeypatch):
    """Codex re-review nit: lock-contention TimeoutError must reach
    _fail_and_cleanup, not loop or silently succeed."""
    slug = _bootstrap(fake_repo)
    monkeypatch.setattr(
        stages, "dispatch",
        _stubbed_dispatch(_writer_stub_output(), _review_approve_output()),
    )
    monkeypatch.setattr(
        stages, "process_module_citations",
        lambda p, *, verifier=None, fetcher=None: CitationResult(new_text=p.read_text(), had_sources_section=False),
    )
    stages.audit_one(slug)
    stages.route_one(slug)
    stages.write_one(slug, timeout=10)
    stages.citation_verify_one(slug)
    stages.review_one(slug, timeout=10)

    # Force _merge_lock to raise TimeoutError (as if another worker held
    # the lock past the contention budget).
    from contextlib import contextmanager

    @contextmanager
    def timeout_lock(timeout=None):
        raise TimeoutError("simulated lock contention")
        yield  # unreachable

    monkeypatch.setattr(stages, "_merge_lock", timeout_lock)
    stages.merge_one(slug)

    st = state.load_state(slug)
    assert st["stage"] == "FAILED"
    assert "TimeoutError" in (st.get("failure_reason") or "") or "lock" in (st.get("failure_reason") or "").lower()


def test_write_cleanup_even_when_commit_fails(fake_repo, monkeypatch):
    """Codex must #8 regression guard.

    If git add/commit/rev-parse (post-dispatch operations) raise, the
    worktree + branch must still be cleaned up — the write path's
    try/except BaseException catches all exception classes.
    """
    slug = _bootstrap(fake_repo)
    stages.audit_one(slug)
    stages.route_one(slug)
    # Writer dispatch succeeds with valid module content.
    monkeypatch.setattr(stages, "dispatch", _stubbed_dispatch(_writer_stub_output(), ""))

    # But let git commit raise — simulate a post-dispatch git failure.
    original_run = subprocess.run

    def boomy_run(args, *a, **k):
        if args[:2] == ["git", "commit"]:
            raise subprocess.CalledProcessError(1, args, stderr="simulated commit failure")
        return original_run(args, *a, **k)

    monkeypatch.setattr(stages.subprocess, "run", boomy_run)

    with pytest.raises(subprocess.CalledProcessError):
        stages.write_one(slug, timeout=10)

    # Worktree + branch removed despite the crash mid-stage.
    assert not worktree.worktree_dir(fake_repo, slug).exists()
    import subprocess as _sp
    branch = worktree.branch_name(slug)
    rc = _sp.run(
        ["git", "rev-parse", "--verify", branch], cwd=fake_repo, capture_output=True,
        check=False,
    ).returncode
    assert rc != 0


# ---- backfill-pending (close v2 → citation_backfill seam) ----


def _seed_committed_state(fake_repo: Path, monkeypatch) -> tuple[str, dict]:
    """Drive the fake-repo's seed module to COMMITTED for backfill tests."""
    slug = _bootstrap(fake_repo)
    stages.audit_one(slug)
    stages.route_one(slug)
    monkeypatch.setattr(stages, "dispatch", _stubbed_dispatch(_writer_stub_output(), _review_approve_output()))
    stages.write_one(slug, timeout=10)
    stages.citation_verify_one(slug, verifier_fn=lambda *a, **k: None, fetcher_fn=lambda url: None)
    stages.review_one(slug, timeout=10)
    stages.merge_one(slug)
    st = state.load_state(slug)
    assert st["stage"] == "COMMITTED", st.get("failure_reason")
    return slug, st


def _seed_inherited_citation_bit(fake_repo: Path, module_rel: str) -> None:
    """Give the backfill input a pre-existing bit with no attached receipt."""
    module_path = fake_repo / module_rel
    module_path.write_text(
        module_path.read_text().replace("---\n", "---\ncitations_verified: true\n", 1)
    )
    subprocess.run(["git", "add", module_rel], cwd=fake_repo, check=True)
    subprocess.run(
        ["git", "commit", "-m", "seed inherited citation bit"],
        cwd=fake_repo,
        check=True,
        capture_output=True,
    )


def test_backfill_pending_happy_path_records_done_and_commits(fake_repo, monkeypatch):
    """When research + inject both succeed and inject modifies the file,
    cmd_backfill_pending stamps state.backfill={done, ok, sha} and adds
    a backfill commit on main. Regression guard for the v2 → citation_backfill
    seam: a COMMITTED module without backfill should be picked up; once
    backfill.done is True, the same module is skipped on subsequent calls.
    """
    slug, st = _seed_committed_state(fake_repo, monkeypatch)

    module_rel = st["module_path"]
    _seed_inherited_citation_bit(fake_repo, module_rel)
    sources_block = "\n## Sources\n\n- [Test](https://example.com) — example citation.\n"

    def fake_subcmd(module_key, sub, *, agent=None):
        if sub == "research":
            return {"ok": True, "stdout": '{"ok": true}', "stderr": "", "returncode": 0}
        # inject: append a Sources section to the actual module file
        target = fake_repo / module_rel
        target.write_text(target.read_text() + sources_block)
        return {"ok": True, "stdout": '{"ok": true, "inline_applied": 1}', "stderr": "", "returncode": 0}

    monkeypatch.setattr(pipeline, "_run_citation_subcommand", fake_subcmd)

    rc = pipeline.cmd_backfill_pending(
        argparse.Namespace(only=None, limit=None, module=[], agent=None)
    )
    assert rc == 0

    st2 = state.load_state(slug)
    bf = st2["backfill"]
    assert bf["done"] is True and bf["ok"] is True
    assert bf["sha"] and len(bf["sha"]) == 40
    assert bf["source_acceptance"] == "unverified"
    assert bf["readiness_impact"] == "not_cleared_until_independent_source_evidence"
    # Module file on disk has the Sources section.
    assert "## Sources" in (fake_repo / module_rel).read_text()
    assert _read_frontmatter(fake_repo / module_rel).get("citations_verified") is None
    assert "source acceptance unverified" in st2["history"][-1]["note"]
    # Stage is still COMMITTED — backfill is a metadata layer, not a stage.
    assert st2["stage"] == "COMMITTED"
    # Re-running is a no-op (filtered out by backfill.done).
    rc2 = pipeline.cmd_backfill_pending(
        argparse.Namespace(only=None, limit=None, module=[], agent=None)
    )
    assert rc2 == 0


def test_backfill_pending_cli_accepts_module_filter(monkeypatch):
    seen_filters = []

    def fake_iter_states(filters=None):
        seen_filters.append(list(filters) if filters is not None else None)
        return []

    monkeypatch.setattr(pipeline, "iter_states", fake_iter_states)
    rc = pipeline.main(["backfill-pending", "--module", "k8s-cka-module-1.1-pods"])
    assert rc == 0
    assert seen_filters == [["k8s-cka-module-1.1-pods"]]


def test_backfill_pending_research_failure_records_error_no_commit(fake_repo, monkeypatch):
    """Research subcommand failure must record stage_failed=research, leave
    state.backfill.done=False, and NOT touch the working tree. Repeating
    the command will retry (because done=False), which is the desired
    behavior for transient LLM failures."""
    slug, _st = _seed_committed_state(fake_repo, monkeypatch)

    head_before = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=fake_repo, check=True, capture_output=True, text=True,
    ).stdout.strip()

    def fake_subcmd(module_key, sub, *, agent=None):
        if sub == "research":
            return {"ok": False, "stdout": "", "stderr": "rate limit", "returncode": 1}
        raise AssertionError("inject must not run after research failed")

    monkeypatch.setattr(pipeline, "_run_citation_subcommand", fake_subcmd)
    rc = pipeline.cmd_backfill_pending(
        argparse.Namespace(only=None, limit=None, module=[], agent=None)
    )
    assert rc == 1

    st2 = state.load_state(slug)
    bf = st2["backfill"]
    assert bf["done"] is False and bf["ok"] is False
    assert bf["stage_failed"] == "research"
    assert "rate limit" in bf["error"]

    head_after = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=fake_repo, check=True, capture_output=True, text=True,
    ).stdout.strip()
    assert head_before == head_after, "no commit should be made on research failure"


def test_backfill_pending_commits_seed_alongside_module(fake_repo, monkeypatch):
    """Real citation_backfill writes both ``docs/citation-seeds/<flat>.json``
    (research step) and the module markdown (inject step). Both must land
    in the same backfill commit so the provenance is traceable in git
    history (matches the prior pipeline_v3 convention from commit ec20ddef).
    """
    _slug, st = _seed_committed_state(fake_repo, monkeypatch)
    module_rel = st["module_path"]
    module_key = pipeline._module_key_from_path(module_rel)
    seed_rel = f"docs/citation-seeds/{module_key.replace('/', '-')}.json"
    seed_path = fake_repo / seed_rel
    seed_path.parent.mkdir(parents=True, exist_ok=True)
    # Mirror production: docs/citation-seeds/ is tracked in git so any
    # new seed shows up as an individual modified file rather than
    # being collapsed into a "?? docs/" untracked-dir line.
    (seed_path.parent / ".gitkeep").touch()
    subprocess.run(["git", "add", str(seed_path.parent / ".gitkeep")], cwd=fake_repo, check=True)
    subprocess.run(["git", "commit", "-m", "track citation-seeds dir"], cwd=fake_repo, check=True, capture_output=True)

    def fake_subcmd(mk, sub, *, agent=None):
        if sub == "research":
            seed_path.write_text(f'{{"module_key": "{mk}", "claims": []}}\n')
            return {"ok": True, "stdout": "", "stderr": "", "returncode": 0}
        target = fake_repo / module_rel
        target.write_text(target.read_text() + "\n## Sources\n\n- [Test](https://example.com).\n")
        return {"ok": True, "stdout": "", "stderr": "", "returncode": 0}

    monkeypatch.setattr(pipeline, "_run_citation_subcommand", fake_subcmd)
    rc = pipeline.cmd_backfill_pending(
        argparse.Namespace(only=None, limit=None, module=[], agent=None)
    )
    assert rc == 0

    # Seed file is committed alongside the module — git log shows BOTH paths.
    log_out = subprocess.run(
        ["git", "log", "-1", "--name-only", "--pretty=format:"],
        cwd=fake_repo, check=True, capture_output=True, text=True,
    ).stdout
    files_committed = {line.strip() for line in log_out.splitlines() if line.strip()}
    assert module_rel in files_committed
    assert seed_rel in files_committed


def test_backfill_pending_refuses_when_foreign_changes_appear(fake_repo, monkeypatch):
    """If a file outside the backfill scope appears in the working tree
    after inject (concurrent edit, fsync race, etc.), refuse to drag it
    into our commit. Roll back our own writes so primary stays clean."""
    slug, st = _seed_committed_state(fake_repo, monkeypatch)
    module_rel = st["module_path"]

    def fake_subcmd(mk, sub, *, agent=None):
        if sub == "inject":
            (fake_repo / module_rel).write_text(
                (fake_repo / module_rel).read_text() + "\n## Sources\n\n- [t](https://x.com).\n"
            )
            # Simulate a concurrent edit appearing during inject.
            (fake_repo / "README.md").write_text("seed\nconcurrent edit\n")
        return {"ok": True, "stdout": "", "stderr": "", "returncode": 0}

    monkeypatch.setattr(pipeline, "_run_citation_subcommand", fake_subcmd)
    rc = pipeline.cmd_backfill_pending(
        argparse.Namespace(only=None, limit=None, module=[], agent=None)
    )
    assert rc == 1

    st2 = state.load_state(slug)
    bf = st2["backfill"]
    assert bf["done"] is False
    assert bf["stage_failed"] == "concurrent_edit"
    # Backfill's own write was rolled back; only the foreign edit remains.
    assert "## Sources" not in (fake_repo / module_rel).read_text()


def test_backfill_pending_inject_nothing_to_do_marks_done(fake_repo, monkeypatch):
    """A no-op completes processing but cannot promote source acceptance."""
    slug, st = _seed_committed_state(fake_repo, monkeypatch)
    _seed_inherited_citation_bit(fake_repo, st["module_path"])

    def fake_subcmd(module_key, sub, *, agent=None):
        if sub == "research":
            return {"ok": True, "stdout": '{"ok": true}', "stderr": "", "returncode": 0}
        return {
            "ok": False,
            "error": "nothing_to_do",
            "detail": "seed has no cited, rewrite, or further_reading actions",
            "stdout": "",
            "stderr": "",
            "returncode": 0,
        }

    monkeypatch.setattr(pipeline, "_run_citation_subcommand", fake_subcmd)
    rc = pipeline.cmd_backfill_pending(
        argparse.Namespace(only=None, limit=None, module=[], agent=None)
    )
    assert rc == 0

    st2 = state.load_state(slug)
    bf = st2["backfill"]
    assert bf["done"] is True and bf["ok"] is True and bf.get("no_op") is True
    assert bf.get("reason") == "nothing_to_do"
    assert bf.get("sha") is None or len(bf["sha"]) == 40
    assert bf["source_acceptance"] == "unverified"
    assert bf["readiness_impact"] == "not_cleared_until_independent_source_evidence"
    assert _read_frontmatter(fake_repo / st["module_path"]).get("citations_verified") is None


def test_backfill_pending_inject_nothing_to_do_includes_seed_in_commit(fake_repo, monkeypatch):
    """When inject is no-op after research changed the seed, both module and
    seed must be committed so the checkout stays clean."""
    _slug, st = _seed_committed_state(fake_repo, monkeypatch)
    module_rel = st["module_path"]
    _seed_inherited_citation_bit(fake_repo, module_rel)
    module_key = pipeline._module_key_from_path(module_rel)
    seed_rel = f"docs/citation-seeds/{module_key.replace('/', '-')}.json"
    seed_path = fake_repo / seed_rel
    seed_path.parent.mkdir(parents=True, exist_ok=True)
    seed_before = json.dumps({
        "schema_version": 3,
        "module_key": module_key,
        "module_path": module_rel,
        "claims": [{"claim_text": "initial"}],
    }, indent=2) + "\n"
    seed_path.write_text(seed_before, encoding="utf-8")
    subprocess.run(["git", "add", str(seed_path)], cwd=fake_repo, check=True, capture_output=True)
    subprocess.run(["git", "commit", "-m", "seed module for no-op backfill"], cwd=fake_repo, check=True, capture_output=True)

    head_before = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=fake_repo, check=True, capture_output=True, text=True,
    ).stdout.strip()

    def fake_subcmd(module_key_arg: str, sub: str, *, agent=None):
        del agent
        if sub == "research":
            seed_path.write_text(
                json.dumps({
                    "schema_version": 3,
                    "module_key": module_key,
                    "module_path": module_rel,
                    "claims": [{"claim_text": "updated"}],
                }, indent=2) + "\n",
                encoding="utf-8",
            )
            return {"ok": True, "stdout": '{"ok": true}', "stderr": "", "returncode": 0}
        return {
            "ok": False,
            "error": "nothing_to_do",
            "detail": "seed has no cited, rewrite, or further_reading actions",
            "stdout": "",
            "stderr": "",
            "returncode": 0,
        }

    monkeypatch.setattr(pipeline, "_run_citation_subcommand", fake_subcmd)
    outcome = pipeline._backfill_one(st, agent=None)
    assert outcome["done"] is True and outcome["ok"] is True
    assert outcome["no_op"] is True
    assert outcome.get("reason") == "nothing_to_do"

    head_after = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=fake_repo, check=True, capture_output=True, text=True,
    ).stdout.strip()
    assert head_after != head_before

    log_out = subprocess.run(
        ["git", "log", "-1", "--name-only", "--pretty=format:"],
        cwd=fake_repo, check=True, capture_output=True, text=True,
    ).stdout
    files = {line.strip() for line in log_out.splitlines() if line.strip()}
    assert module_rel in files
    assert seed_rel in files

    status = subprocess.run(
        ["git", "status", "--porcelain"], cwd=fake_repo, check=True, capture_output=True, text=True,
    ).stdout
    assert status == "", "no-op backfill must leave a clean working tree"


def test_backfill_pending_research_error_payload_preserves_seed(fake_repo, monkeypatch):
    """A bridge error seed payload (`from_model: codex-bridge-error`) must fail
    research cleanly and preserve the existing seed file on disk."""
    slug, st = _seed_committed_state(fake_repo, monkeypatch)
    module_rel = st["module_path"]
    module_key = pipeline._module_key_from_path(module_rel)
    seed_rel = f"docs/citation-seeds/{module_key.replace('/', '-')}.json"
    seed_path = fake_repo / seed_rel
    seed_path.parent.mkdir(parents=True, exist_ok=True)
    seed_before = json.dumps({
        "schema_version": 3,
        "module_key": module_key,
        "module_path": module_rel,
        "claims": [{"claim_text": "keep"}],
    }, indent=2) + "\n"
    seed_path.write_text(seed_before, encoding="utf-8")
    subprocess.run(["git", "add", str(seed_path)], cwd=fake_repo, check=True, capture_output=True)
    subprocess.run(["git", "commit", "-m", "seed module for bridge-error reseach"], cwd=fake_repo, check=True, capture_output=True)

    # Point citation_backfill to the fake repo and force an error-shaped response.
    monkeypatch.setattr(citation_backfill, "REPO_ROOT", fake_repo)
    monkeypatch.setattr(citation_backfill, "DOCS_ROOT", fake_repo / "src" / "content" / "docs")
    monkeypatch.setattr(citation_backfill, "SEED_DIR", fake_repo / "docs" / "citation-seeds")

    def fake_dispatch(_prompt: str, *, task_id: str) -> tuple[bool, str]:
        del task_id
        return True, json.dumps({
            "from_model": "codex-bridge-error",
            "module_key": module_key,
            "module_path": module_rel,
        })

    monkeypatch.setattr(citation_backfill, "dispatch_codex", fake_dispatch)

    research_result: dict[str, object] = {}
    research_returncode = 0

    def fake_subcmd(module_key_arg: str, sub: str, *, agent=None):
        del agent
        if sub == "research":
            result = citation_backfill.run_research(module_key_arg, agent="codex")
            research_result.update({"ok": result.get("ok"), "detail": result.get("detail")})
            nonlocal research_returncode
            research_returncode = 1 if not result.get("ok") else 0
            return {
                "ok": bool(result.get("ok")),
                "stdout": json.dumps(result, ensure_ascii=False),
                "stderr": result.get("detail", "") if not result.get("ok") else "",
                "returncode": research_returncode,
            }
        raise AssertionError("inject must not run after research failed")

    monkeypatch.setattr(pipeline, "_run_citation_subcommand", fake_subcmd)

    rc = pipeline.cmd_backfill_pending(
        argparse.Namespace(only=None, limit=None, module=[], agent=None)
    )
    assert rc == 1
    assert research_returncode == 1
    assert research_result.get("ok") is False
    assert research_result.get("detail") == "agent response missing claims/schema_version or bridge error payload"

    assert seed_path.read_text(encoding="utf-8") == seed_before

    st2 = state.load_state(slug)
    bf = st2["backfill"]
    assert bf["done"] is False and bf["ok"] is False
    assert bf["stage_failed"] == "research"
    assert bf["error"] == "agent response missing claims/schema_version or bridge error payload"


def test_backfill_pending_inject_failure_does_not_set_citations_verified(fake_repo, monkeypatch):
    """Inject hard failures (non-`nothing_to_do`) keep ``citations_verified``
    unset in frontmatter so readiness treats the module as not cleared."""
    slug, st = _seed_committed_state(fake_repo, monkeypatch)
    module_rel = st["module_path"]
    module_path = fake_repo / module_rel

    def fake_subcmd(module_key, sub, *, agent=None):
        if sub == "research":
            return {"ok": True, "stdout": '{"ok": true}', "stderr": "", "returncode": 0}
        return {
            "ok": False,
            "error": "agent_timeout",
            "detail": "agent call timed out",
            "stdout": "",
            "stderr": "agent timeout",
            "returncode": 1,
        }

    monkeypatch.setattr(pipeline, "_run_citation_subcommand", fake_subcmd)
    rc = pipeline.cmd_backfill_pending(
        argparse.Namespace(only=None, limit=None, module=[], agent=None)
    )
    assert rc == 1
    st2 = state.load_state(slug)
    bf = st2["backfill"]
    assert bf["done"] is False and bf["ok"] is False
    assert bf["stage_failed"] == "inject"
    assert "agent timeout" in bf["error"].lower()
    assert _read_frontmatter(module_path).get("citations_verified") is None


def test_run_order_is_worst_first(fake_repo, monkeypatch):
    # Add a second module with HIGHER score.
    mod2_rel = "src/content/docs/k8s/cka/module-1.2-services.md"
    (fake_repo / mod2_rel).parent.mkdir(parents=True, exist_ok=True)
    (fake_repo / mod2_rel).write_text("---\ntitle: Services\nsidebar:\n  order: 2\n---\n\n")
    audit_dir = fake_repo / ".pipeline" / "teaching-audit"
    slug2 = "k8s-cka-module-1.2-services"
    (audit_dir / f"{slug2}.json").write_text(json.dumps({
        "teaching_score": 3.9, "teaching_gaps": [],
    }))
    subprocess.run(["git", "add", "-A"], cwd=fake_repo, check=True)
    subprocess.run(["git", "commit", "-m", "m2"], cwd=fake_repo, check=True, capture_output=True)

    # Bootstrap so both have state + audit.
    modules = pipeline.iter_all_modules()
    for i, m in enumerate(modules):
        st = state.new_state(m, module_index=i)
        state.save_state(st)
        stages.audit_one(state.slug_for(m))

    slugs = state.iter_state_slugs()
    ordered = pipeline._order_worst_first(slugs)
    # Module 1.1 (score 2.5) should come before module 1.2 (score 3.9).
    assert ordered.index("k8s-cka-module-1.1-pods") < ordered.index(slug2)


# ---- #388 density-aware routing + density hard-gate -------------------


def test_route_one_density_rewrite_overrides_high_audit_score(fake_repo, monkeypatch):
    """A module with a 4.5 audit score AND complete structure that fails
    the density classifier (REWRITE) must still go to track=rewrite —
    pad-bombs and punchy-bullets are exactly what the audit missed."""
    slug = _bootstrap(fake_repo)
    # High audit score + structurally complete
    st = state.load_state(slug)
    st["audit"] = {"teaching_score": 4.5, "teaching_gaps": []}
    st["stage"] = "AUDITED"
    state.save_state(st)
    full_module = """---
title: Pods
sidebar:
  order: 1
---

## Quiz

Q.

## Hands-On Exercise

Do.

## Common Mistakes

T.

## Did You Know?

F.
"""
    (fake_repo / st["module_path"]).write_text(full_module)

    # Override the fixture-default density bypass with a REWRITE-tier
    # DensityMetrics so route_one's density check fires the override path.
    from scripts.quality import density as _density
    monkeypatch.setattr(
        _density, "evaluate_text",
        lambda _text: _density.DensityMetrics(
            prose_words=200, textual_words=210, nonblank_lines=10,
            total_paragraphs=4, prose_paragraphs=4,
            w_per_line=21.0, w_per_para=10.0,  # wpp below REWRITE floor
        ),
    )

    stages.route_one(slug)
    st = state.load_state(slug)
    assert st["stage"] == "WRITE_PENDING"
    assert st["route"]["track"] == "rewrite"
    assert st["route"]["density"]["verdict"] == "rewrite"


def test_density_gate_failure_bounces_to_write_pending(fake_repo, monkeypatch):
    """When merge_one's density gate raises, the slug must go back to
    WRITE_PENDING with the reason in retry context (not FAILED)."""
    slug = _bootstrap(fake_repo)
    # Drive to REVIEW_APPROVED — bypass writer/reviewer dispatch entirely
    # by hand-editing state.
    st = state.load_state(slug)
    st.update({
        "stage": "REVIEW_APPROVED",
        "writer": "codex",
        "reviewer": "claude",
        "write": {"agent": "codex", "attempt_id": "abc", "commit_sha": "deadbeef", "worktree": ".worktrees/x"},
        "review": {"verdict": "approve", "must_fix": []},
        "route": {"track": "rewrite", "score": 2.0, "missing": []},
        "retry_count": 0,
    })
    _install_reviewed_candidate(fake_repo, st)
    state.save_state(st)

    # Stub out the merge mechanics — we only want to test the density-fail
    # bounce. NB: stages.py imports these symbols by value at module
    # import time, so monkey-patching the source modules doesn't reach
    # them — patch the names AS BOUND IN stages.
    from scripts.quality import gates as _gates
    monkeypatch.setattr(stages, "current_branch", lambda primary: "main")
    monkeypatch.setattr(stages, "has_uncommitted", lambda primary: False)
    monkeypatch.setattr(stages, "rebase_onto_main", lambda primary, slug: None)
    monkeypatch.setattr(stages, "remove_worktree", lambda primary, slug, delete_branch=True: None)
    monkeypatch.setattr(stages.gates, "assert_visual_aids_preserved", lambda *a, **kw: {})
    def _raise(*a, **kw):
        raise _gates.GateError("density gate failed on test-slug: wpp 8.0 < 22.0")
    monkeypatch.setattr(stages.gates, "assert_density_threshold", _raise)

    stages.merge_one(slug)
    st = state.load_state(slug)
    assert st["stage"] == "WRITE_PENDING", st.get("failure_reason")
    assert st["retry_count"] == 1
    must_fix = (st.get("review") or {}).get("must_fix") or []
    assert any("[density]" in m for m in must_fix), f"expected [density] tag in must_fix; got {must_fix}"


def test_density_gate_failure_after_retry_cap_marks_failed(fake_repo, monkeypatch):
    """After RETRY_CAP density bounces, the next failure marks FAILED
    (manual rewrite required)."""
    slug = _bootstrap(fake_repo)
    st = state.load_state(slug)
    st.update({
        "stage": "REVIEW_APPROVED",
        "writer": "codex",
        "reviewer": "claude",
        "write": {"agent": "codex", "attempt_id": "abc", "commit_sha": "deadbeef", "worktree": ".worktrees/x"},
        "review": {"verdict": "approve", "must_fix": []},
        "route": {"track": "rewrite", "score": 2.0, "missing": []},
        "retry_count": stages.RETRY_CAP,  # already at cap
    })
    _install_reviewed_candidate(fake_repo, st)
    state.save_state(st)

    from scripts.quality import gates as _gates
    monkeypatch.setattr(stages, "current_branch", lambda primary: "main")
    monkeypatch.setattr(stages, "has_uncommitted", lambda primary: False)
    monkeypatch.setattr(stages, "rebase_onto_main", lambda primary, slug: None)
    monkeypatch.setattr(stages, "remove_worktree", lambda primary, slug, delete_branch=True: None)
    monkeypatch.setattr(stages.gates, "assert_visual_aids_preserved", lambda *a, **kw: {})
    monkeypatch.setattr(stages.gates, "assert_density_threshold",
                        lambda *a, **kw: (_ for _ in ()).throw(_gates.GateError("density failed")))

    stages.merge_one(slug)
    st = state.load_state(slug)
    assert st["stage"] == "FAILED"
    assert "density gate failed after" in (st.get("failure_reason") or "")


def test_skip_review_stays_pending_without_dispatch(fake_repo, monkeypatch):
    slug = _bootstrap(fake_repo)
    st = state.load_state(slug)
    st.update({"stage": "REVIEW_PENDING", "reviewer": "claude"})
    state.save_state(st)
    monkeypatch.setenv("KUBEDOJO_SKIP_REVIEW", "1")
    monkeypatch.setattr(stages, "dispatch", lambda *_a, **_k: pytest.fail("unexpected provider call"))
    stages.review_one(slug)
    st = state.load_state(slug)
    assert st["stage"] == "REVIEW_PENDING" and "deferred" in st["review_blocked"] and st["review"] is None


@pytest.mark.parametrize("kind", ["auto", "scalar", "weak"])
def test_untrusted_approval_cannot_merge_or_delete_candidate(fake_repo, monkeypatch, kind):
    slug = _bootstrap(fake_repo)
    st = state.load_state(slug)
    _install_reviewed_candidate(fake_repo, st)
    st["stage"] = "REVIEW_APPROVED"
    if kind == "auto":
        st["review"]["auto_approved"] = True
    elif kind == "scalar":
        del st["review"]["payload"]["dimensions"]
    else:
        st["review"]["payload"]["dimensions"]["D1"] = 3
    state.save_state(st)
    monkeypatch.setattr(stages, "merge_ff_only", lambda *_a: pytest.fail("unexpected merge"))
    stages.merge_one(slug)
    st = state.load_state(slug)
    assert st["stage"] == "REVIEW_PENDING" and st["review_blocked"] and st["review_contract_paused"]
    assert worktree.worktree_dir(fake_repo, slug).exists()
    monkeypatch.setattr(stages, "dispatch", lambda *_a, **_k: pytest.fail("unexpected reviewer retry"))
    assert stages.run_module(slug) == "REVIEW_PENDING"


def test_post_merge_sampler_exception_is_nonfatal_and_redacted(monkeypatch, caplog):
    secret = "private-model-payload-should-not-appear"
    reports = []
    monkeypatch.setattr(stages.state, "load_state", lambda _slug: {"module_path": "x.md"})
    monkeypatch.setattr(stages.gates, "should_sample", lambda _slug: True)
    def fail(_path):
        raise RuntimeError(secret)
    monkeypatch.setattr(stages.gates, "run_real_llm_rubric", fail)
    monkeypatch.setattr(stages, "_merge_lock", lambda: nullcontext())
    monkeypatch.setattr(stages.gates, "build_ledger_row", lambda **kw: reports.append(kw["real_llm_result"]) or {})
    monkeypatch.setattr(stages.gates, "append_ledger", lambda _row: None)
    monkeypatch.setattr(stages, "_commit_ledger_row", lambda _slug: None)
    stages._post_merge_gates("slug")
    assert reports == [{"ok": False, "error": "sampler raised: RuntimeError"}]
    assert "sampler failed" in caplog.text and secret not in caplog.text


def _pending_review(fake_repo):
    slug = _bootstrap(fake_repo)
    st = state.load_state(slug)
    st.update({"stage": "REVIEW_PENDING", "writer": "codex", "reviewer": "claude"})
    _install_reviewed_candidate(fake_repo, st)
    state.save_state(st)
    return slug, worktree.worktree_dir(fake_repo, slug)


def test_review_missing_plan_never_dispatches(fake_repo, monkeypatch):
    slug, wt = _pending_review(fake_repo)
    seed = "docs/citation-seeds/k8s-cka-module-1.1-pods.json"
    (wt / seed).unlink()
    subprocess.run(["git", "add", seed], cwd=wt, check=True)
    subprocess.run(["git", "commit", "-m", "remove plan"], cwd=wt, check=True, capture_output=True)
    monkeypatch.setattr(stages, "dispatch", lambda *_a, **_k: pytest.fail("unexpected provider call"))
    stages.review_one(slug)
    st = state.load_state(slug)
    assert st["stage"] == "REVIEW_PENDING" and "research input blocked" in st["review_blocked"] and wt.exists()


def test_review_digests_bind_candidate_and_plan():
    candidate, plan = stages._review_digests(_REWRITTEN_MODULE, _PLAN)
    assert stages._review_digests(_REWRITTEN_MODULE + "changed", _PLAN)[0] != candidate
    assert stages._review_digests(_REWRITTEN_MODULE, {**_PLAN, "essential_topics": ["Other"]})[1] != plan


@pytest.mark.parametrize("kind", ["weak", "scalar"])
def test_invalid_review_remains_pending_without_duplicate_dispatch(fake_repo, monkeypatch, kind):
    slug, wt = _pending_review(fake_repo)
    payload = json.loads(_review_approve_output().split("My verdict:\n\n")[1])
    if kind == "scalar":
        del payload["dimensions"]
    else:
        payload["dimensions"]["D8"] = 3
    calls = []
    result = DispatchResult(ok=True, stdout=json.dumps(payload), stderr="", returncode=0,
                            duration_sec=0.1, agent="claude", model=None)
    monkeypatch.setattr(stages, "dispatch", lambda *_a, **_k: calls.append(1) or result)
    assert stages.run_module(slug) == "REVIEW_PENDING"
    st = state.load_state(slug)
    assert calls == [1] and st["review_failure"]["payload"] == payload and wt.exists()
    stages.review_one(slug)
    assert calls == [1]  # a failed attempt is not retried automatically


@pytest.mark.parametrize("changed", ["candidate", "plan"])
def test_changed_committed_input_blocks_merge(fake_repo, monkeypatch, changed):
    slug, wt = _pending_review(fake_repo)
    st = state.load_state(slug)
    st["stage"] = "REVIEW_APPROVED"
    state.save_state(st)
    path = wt / (st["module_path"] if changed == "candidate" else "docs/citation-seeds/k8s-cka-module-1.1-pods.json")
    if changed == "candidate":
        path.write_text(path.read_text() + "Changed.\n")
    else:
        seed = json.loads(path.read_text())
        seed["coverage_plan"]["essential_topics"].append("New topic")
        path.write_text(json.dumps(seed))
    subprocess.run(["git", "add", str(path.relative_to(wt))], cwd=wt, check=True)
    subprocess.run(["git", "commit", "-m", "changed input"], cwd=wt, check=True, capture_output=True)
    monkeypatch.setattr(stages, "merge_ff_only", lambda *_a: pytest.fail("unexpected merge"))
    stages.merge_one(slug)
    st = state.load_state(slug)
    assert st["stage"] == "REVIEW_PENDING" and "changed since review" in st["review_blocked"] and wt.exists()


def test_candidate_changed_during_review_is_not_approved(fake_repo, monkeypatch):
    slug, wt = _pending_review(fake_repo)
    def dispatch_after_edit(*_args, **_kwargs):
        path = wt / state.load_state(slug)["module_path"]
        path.write_text(path.read_text() + "Changed while reviewing.\n")
        return DispatchResult(ok=True, stdout=_review_approve_output(), stderr="", returncode=0,
                              duration_sec=0.1, agent="claude", model=None)
    monkeypatch.setattr(stages, "dispatch", dispatch_after_edit)
    stages.review_one(slug)
    st = state.load_state(slug)
    assert st["stage"] == "REVIEW_PENDING" and "changed during review" in st["review_blocked"]
    assert st["review_failure"]["payload"]["verdict"] == "approve" and wt.exists()


def test_complete_approval_without_scalars_is_bound_unchanged(fake_repo, monkeypatch):
    slug, _ = _pending_review(fake_repo)
    payload = json.loads(_review_approve_output().split("My verdict:\n\n")[1])
    del payload["rubric_score"], payload["teaching_score"]
    result = DispatchResult(ok=True, stdout=json.dumps(payload), stderr="", returncode=0,
                            duration_sec=0.1, agent="claude", model=None)
    monkeypatch.setattr(stages, "dispatch", lambda *_a, **_k: result)
    stages.review_one(slug)
    st = state.load_state(slug)
    assert st["stage"] == "REVIEW_APPROVED" and st["review"]["payload"] == payload
    assert st["review"]["candidate_sha256"] and st["review"]["plan_sha256"]
    assert stages._merge_review_error(st) is None


def test_rebase_changed_plan_is_rechecked_before_merge(fake_repo, monkeypatch):
    slug, wt = _pending_review(fake_repo)
    st = state.load_state(slug)
    st["stage"] = "REVIEW_APPROVED"
    state.save_state(st)
    def changed_rebase(*_args):
        path = wt / "docs/citation-seeds/k8s-cka-module-1.1-pods.json"
        seed = json.loads(path.read_text())
        seed["coverage_plan"]["essential_topics"].append("New topic")
        path.write_text(json.dumps(seed))
        subprocess.run(["git", "add", str(path.relative_to(wt))], cwd=wt, check=True)
        subprocess.run(["git", "commit", "-m", "changed by rebase"], cwd=wt, check=True, capture_output=True)
    monkeypatch.setattr(stages, "rebase_onto_main", changed_rebase)
    monkeypatch.setattr(stages, "merge_ff_only", lambda *_a: pytest.fail("unexpected merge"))
    stages.merge_one(slug)
    st = state.load_state(slug)
    assert st["stage"] == "REVIEW_PENDING" and "changed since review" in st["review_blocked"] and wt.exists()


def _post_review_case(fake_repo, monkeypatch):
    slug = _bootstrap(fake_repo)
    st = state.load_state(slug)
    st.update({"stage": "COMMITTED", "writer": "codex", "reviewer": "claude",
               "review": {"auto_approved": True}})
    module = fake_repo / st["module_path"]
    module.write_text(_REWRITTEN_MODULE)
    saved, flags = [], []
    lease = type("Lease", (), {"load": lambda self: st, "save": lambda self, value: saved.append(value)})()
    monkeypatch.setattr(post_review.qstate, "REPO_ROOT", fake_repo)
    monkeypatch.setattr(post_review.qstate, "load_state", lambda _slug: st)
    monkeypatch.setattr(post_review.qstate, "state_lease", lambda *_a, **_k: nullcontext(lease))
    monkeypatch.setattr(post_review, "clear_qa_pending_frontmatter", lambda _p: flags.append("clear"))
    monkeypatch.setattr(post_review, "set_revision_pending_frontmatter", lambda _p: flags.append("revision") or True)
    return slug, st, module, saved, flags


def test_post_review_missing_plan_does_not_dispatch_or_clear(fake_repo, monkeypatch):
    slug, st, _, saved, flags = _post_review_case(fake_repo, monkeypatch)
    (fake_repo / "docs/citation-seeds/k8s-cka-module-1.1-pods.json").unlink()
    monkeypatch.setattr(post_review, "dispatch", lambda *_a, **_k: pytest.fail("unexpected provider call"))
    outcome, detail = post_review.review_slug(slug, reviewer_override=None, timeout=10, dry_run=False)
    assert outcome == "fail" and "research input blocked" in detail
    assert st["review"]["auto_approved"] is True and saved == flags == []


def test_post_review_scalar_approval_cannot_clear_flags(fake_repo, monkeypatch):
    slug, st, _, saved, flags = _post_review_case(fake_repo, monkeypatch)
    scalar = json.dumps({"verdict": "approve", "rubric_score": 5, "teaching_score": 5, "must_fix": []})
    result = DispatchResult(ok=True, stdout=scalar, stderr="", returncode=0, duration_sec=0.1, agent="claude", model=None)
    monkeypatch.setattr(post_review, "dispatch", lambda *_a, **_k: result)
    outcome, detail = post_review.review_slug(slug, reviewer_override=None, timeout=10, dry_run=False)
    assert outcome == "fail" and "dimensions" in detail
    assert st["review"]["auto_approved"] is True and saved == flags == []


@pytest.mark.parametrize("changed", ["candidate", "plan"])
def test_post_review_stale_candidate_or_plan_cannot_clear_flags(fake_repo, monkeypatch, changed):
    slug, st, module, saved, flags = _post_review_case(fake_repo, monkeypatch)
    def change_then_review(*_args, **_kwargs):
        if changed == "candidate":
            module.write_text(module.read_text() + "Changed.\n")
        else:
            seed_path = fake_repo / "docs/citation-seeds/k8s-cka-module-1.1-pods.json"
            seed = json.loads(seed_path.read_text())
            seed["coverage_plan"]["essential_topics"].append("New topic")
            seed_path.write_text(json.dumps(seed))
        return DispatchResult(ok=True, stdout=_review_approve_output(), stderr="", returncode=0,
                              duration_sec=0.1, agent="claude", model=None)
    monkeypatch.setattr(post_review, "dispatch", change_then_review)
    outcome, detail = post_review.review_slug(slug, reviewer_override=None, timeout=10, dry_run=False)
    assert outcome == "fail" and "changed during review" in detail
    assert st["review"]["auto_approved"] is True and saved == flags == []


def test_post_review_complete_approval_binds_payload_before_clear(fake_repo, monkeypatch):
    slug, st, _, saved, flags = _post_review_case(fake_repo, monkeypatch)
    output = _review_approve_output()
    payload = json.loads(output.split("My verdict:\n\n")[1])
    result = DispatchResult(ok=True, stdout=output, stderr="", returncode=0, duration_sec=0.1, agent="claude", model=None)
    monkeypatch.setattr(post_review, "dispatch", lambda *_a, **_k: result)
    outcome, _ = post_review.review_slug(slug, reviewer_override=None, timeout=10, dry_run=False)
    assert outcome == "approve" and st["review"]["auto_approved"] is False and saved and flags == ["clear"]
    assert st["review"]["deferred"]["payload"] == payload
    assert st["review"]["deferred"]["candidate_sha256"] and st["review"]["deferred"]["plan_sha256"]
    assert st["review"]["deferred"]["prior_review"]["auto_approved"] is True


def test_post_review_negative_keeps_historical_auto_approval(fake_repo, monkeypatch):
    slug, st, _, saved, flags = _post_review_case(fake_repo, monkeypatch)
    result = DispatchResult(ok=True, stdout=_review_changes_output(["fix quiz"]), stderr="", returncode=0,
                            duration_sec=0.1, agent="claude", model=None)
    monkeypatch.setattr(post_review, "dispatch", lambda *_a, **_k: result)
    outcome, _ = post_review.review_slug(slug, reviewer_override=None, timeout=10, dry_run=False)
    assert outcome == "changes" and st["review"]["auto_approved"] is True and saved
    assert flags == ["clear", "revision"] and st["review"]["deferred"]["payload"]["verdict"] == "changes_requested"
