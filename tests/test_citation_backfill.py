from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

import citation_backfill  # noqa: E402


def test_primary_checkout_root_strips_worktree_layout() -> None:
    """From `<repo>/.worktrees/<name>/` (AGENTS.md §1 mandated layout)
    the helper must return `<repo>` — otherwise `_VENV_PYTHON` points
    at a non-existent `<worktree>/.venv/bin/python` and the subprocess
    launch fails inside a worktree.

    Pure function over paths; no filesystem required.
    """
    # Primary checkout case: no worktree, returns input unchanged.
    primary = Path("/home/user/kubedojo")
    assert citation_backfill._primary_checkout_root(primary) == primary

    # Worktree case: step up past .worktrees/<name>/ to the primary.
    worktree = Path("/home/user/kubedojo/.worktrees/feature-x")
    assert (
        citation_backfill._primary_checkout_root(worktree)
        == Path("/home/user/kubedojo")
    )

    # Edge: a directory literally named ".worktrees" as the parent of
    # a non-worktree path (unlikely but possible) — still handled
    # correctly by stepping up. Documents the name-based heuristic.
    nested = Path("/tmp/.worktrees/foo")
    assert (
        citation_backfill._primary_checkout_root(nested) == Path("/tmp")
    )


def test_venv_python_points_at_primary_even_when_loaded_from_worktree() -> None:
    """Regression guard for the #374 round-3 finding: _VENV_PYTHON
    must resolve to <primary>/.venv/bin/python, not
    <worktree>/.venv/bin/python. This test doesn't reload the module
    from a worktree (expensive) — it recomputes what the module would
    compute and asserts the shape.
    """
    pretend_worktree_root = Path("/home/u/kubedojo/.worktrees/feat-x")
    expected_interpreter = (
        citation_backfill._primary_checkout_root(pretend_worktree_root)
        / ".venv" / "bin" / "python"
    )
    assert expected_interpreter == Path("/home/u/kubedojo/.venv/bin/python"), (
        f"worktree lookup must resolve to primary .venv, got "
        f"{expected_interpreter}"
    )
    # And for the module's own _VENV_PYTHON in the primary checkout,
    # it must not contain '.worktrees' at all.
    assert ".worktrees" not in citation_backfill._VENV_PYTHON, (
        f"module-level _VENV_PYTHON leaked a worktree segment: "
        f"{citation_backfill._VENV_PYTHON}"
    )


def test_dispatch_agy_reports_removed_dispatcher() -> None:
    with pytest.raises(RuntimeError, match="legacy dispatcher removed"):
        citation_backfill.dispatch_agy("hello")


def test_dispatch_claude_reports_removed_dispatcher() -> None:
    with pytest.raises(RuntimeError, match="legacy dispatcher removed"):
        citation_backfill.dispatch_claude("hi", timeout=180)


def test_apply_inject_plan_skips_rewrite_disposition_claims() -> None:
    body = "Marcus ran a local model on 16 GB of RAM.\n"
    seed = {
        "claims": [
            {
                "claim_id": "C-rewrite",
                "disposition": "soften_to_illustration",
                "anchor_text": "Marcus ran a local model on 16 GB of RAM.",
                "suggested_rewrite": "A developer ran a local model.",
            }
        ],
        "further_reading": [],
    }

    new_body, applied = citation_backfill.apply_inject_plan(body, {}, seed)

    assert "Marcus ran a local model on 16 GB of RAM." in new_body
    assert "A developer ran a local model." not in new_body
    assert {
        "claim_id": "C-rewrite",
        "kind": "prose_rewrite",
        "status": "skipped",
        "reason": "rewrites_disabled_pending_redesign",
    } in applied


def test_apply_inject_plan_skips_overlapping_wrap_when_phrase_already_cited() -> None:
    """Regression test for #1216 (Pattern B): inject must not double-wrap a phrase
    that already lives inside an existing [label](url) region. The claim should
    be recorded as applied with note='already_cited_in_body' so the coverage
    gate in run_inject treats it as addressed."""
    body = "Lead.\\n\\n[Kubernetes](https://kubernetes.io/) is a container orchestrator.\\n"
    plan = {
        "inline_insertions": [
            {
                "claim_id": "k8s-orchestrator",
                "target_line": "[Kubernetes](https://kubernetes.io/) is a container orchestrator.",
                "original_phrase": "Kubernetes",
                "replace_with": "[Kubernetes](https://kubernetes.io/)",
            }
        ],
        "skipped_claims": [],
    }
    seed = {"claims": [{"claim_id": "k8s-orchestrator", "disposition": "supported"}]}
    new_body, applied = citation_backfill.apply_inject_plan(body, plan, seed)
    assert new_body == body, "body must not be mutated when phrase already cited"
    matching = [a for a in applied if a.get("claim_id") == "k8s-orchestrator"]
    assert len(matching) == 1
    assert matching[0]["status"] == "applied"
    assert matching[0]["note"] == "already_cited_in_body"


def test_apply_inject_plan_preserves_next_module_after_sources() -> None:
    body = (
        "Body text.\n\n"
        "## Sources\n\n"
        "- [Existing](https://example.com/a)\n\n"
        "## Next Module\n\n"
        "Continue to ...\n"
    )
    seed = {
        "claims": [],
        "further_reading": [
            {
                "title": "New",
                "url": "https://example.com/b",
                "why_relevant": "Additional context.",
            }
        ],
    }

    new_body, _ = citation_backfill.apply_inject_plan(body, {}, seed)

    assert "- [New](https://example.com/b)" in new_body
    assert "- [Existing](https://example.com/a)" in new_body
    assert "## Next Module\n\nContinue to ..." in new_body


def test_apply_inject_plan_sources_merge_dedupes_by_url() -> None:
    body = (
        "Body text.\n\n"
        "## Sources\n\n"
        "- [A](https://x.com/a)\n"
    )
    seed = {
        "claims": [],
        "further_reading": [
            {
                "title": "Different A",
                "url": "https://x.com/a",
                "why_relevant": "Duplicate URL.",
            },
            {
                "title": "B",
                "url": "https://y.com/b",
                "why_relevant": "New URL.",
            },
        ],
    }

    new_body, _ = citation_backfill.apply_inject_plan(body, {}, seed)
    bullets = [
        line for line in new_body.splitlines()
        if line.startswith("- ")
    ]

    assert len(bullets) == 2
    assert new_body.count("https://x.com/a") == 1
    assert "- [A](https://x.com/a)" in new_body
    assert "Different A" not in new_body
    assert "- [B](https://y.com/b)" in new_body


def test_run_inject_soft_skips_codex_dropped_cited_claims(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Use an isolated fake repo, so this test can run in parallel with
    # other citation fixtures without touching actual source files.
    monkeypatch.setattr(citation_backfill, "REPO_ROOT", tmp_path)
    monkeypatch.setattr(citation_backfill, "DOCS_ROOT", tmp_path / "src" / "content" / "docs")
    monkeypatch.setattr(citation_backfill, "SEED_DIR", tmp_path / "docs" / "citation-seeds")

    module_key = "platform/cluster-api-demo"
    module_path = tmp_path / "src" / "content" / "docs" / "platform" / "cluster-api-demo.md"
    module_path.parent.mkdir(parents=True, exist_ok=True)
    module_body = (
        "Cluster API bootstraps nodes for production use.\n"
        "The operator reviews cluster events and scales workloads.\n"
        "Kubernetes handles control-plane scheduling automatically.\n"
    )
    module_path.write_text(module_body, encoding="utf-8")

    seed = {
        "claims": [
            {
                "claim_id": "C001",
                "disposition": "supported",
                "claim_text": "Cluster API bootstraps nodes for production use.",
                "span_hint": "line 1",
                "proposed_url": "https://kubernetes.io/docs/concepts/overview/",
            },
            {
                "claim_id": "C002",
                "disposition": "supported",
                "claim_text": "The operator reviews cluster events and scales workloads.",
                "span_hint": "line 2",
                "proposed_url": "https://kubernetes.io/docs/concepts/architecture/control-plane-node-communication/",
            },
            {
                "claim_id": "C003",
                "disposition": "supported",
                "claim_text": "Kubernetes handles control-plane scheduling automatically.",
                "span_hint": "line 3",
                "proposed_url": "https://kubernetes.io/docs/concepts/scheduling-eviction/",
            },
        ]
    }
    citation_backfill.seed_path_for(module_key).write_text(
        json.dumps(seed, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )

    plan = {
        "inline_insertions": [
            {
                "claim_id": "C001",
                "target_line": "Cluster API bootstraps nodes for production use.",
                "original_phrase": "Cluster API",
                "replace_with": "[Cluster API](https://kubernetes.io/docs/concepts/overview/)",
            },
            {
                "claim_id": "C002",
                "target_line": "The operator reviews cluster events and scales workloads.",
                "original_phrase": "scales workloads",
                "replace_with": "[scales workloads](https://kubernetes.io/docs/concepts/architecture/control-plane-node-communication/)",
            },
        ],
        "skipped_claims": [],
    }

    def _fake_dispatch(
        _prompt: str,
        *,
        task_id: str | None = None,
        timeout: int = 900,
    ) -> tuple[bool, str]:
        del _prompt, task_id, timeout
        return True, json.dumps(plan, ensure_ascii=False)

    monkeypatch.setattr(citation_backfill, "dispatch_codex", _fake_dispatch)

    result = citation_backfill.run_inject(module_key, agent="codex")

    assert result["ok"] is True
    assert not any(
        "cited_dispositions_not_addressed" in str(item)
        for item in result["diff_issues"]
    )
    assert result["codex_dropped_count"] == 1

    revision_rel = result["deferred_record"]
    assert isinstance(revision_rel, str)
    revision_path = tmp_path / revision_rel
    assert revision_path.exists()
    revision = json.loads(revision_path.read_text(encoding="utf-8"))
    dropped = revision.get("codex_dropped") or []
    assert len(dropped) == 1
    assert dropped[0]["claim_id"] == "C003"

    c003 = [entry for entry in result["applied"] if entry.get("claim_id") == "C003"]
    assert len(c003) == 1
    assert c003[0]["kind"] == "inline"
    assert c003[0]["status"] == "skipped"
    assert c003[0]["reason"] == "not_addressed_by_agent"


def test_run_research_agent_response_invalid_preserves_raw_snippets(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path,
) -> None:
    """Regression for #1621: invalid agent JSON must retain raw_head/raw_tail."""
    module_path = tmp_path / "on-premises" / "storage" / "module-4.4-object-storage.md"
    module_path.parent.mkdir(parents=True)
    module_path.write_text("# Object storage\n\nBare-metal object storage notes.\n", encoding="utf-8")

    monkeypatch.setattr(citation_backfill, "REPO_ROOT", tmp_path)
    monkeypatch.setattr(citation_backfill, "DOCS_ROOT", tmp_path)
    monkeypatch.setattr(citation_backfill, "resolve_module_path", lambda _key: module_path)
    monkeypatch.setattr(citation_backfill, "load_section_pool", lambda *a, **kw: None)

    pad_head = "HEAD-" * 80
    pad_tail = "TAIL-" * 80
    inner = json.dumps({"foo": "bar"})
    raw = f"{pad_head}{inner}{pad_tail}"

    def fake_dispatch(_prompt: str, *, task_id: str) -> tuple[bool, str]:
        del task_id
        return True, raw

    monkeypatch.setattr(citation_backfill, "dispatch_codex", fake_dispatch)

    result = citation_backfill.run_research(
        "on-premises/storage/module-4.4-object-storage-bare-metal",
        agent="codex",
    )

    assert result["ok"] is False
    assert result["error"] == "agent_response_invalid"
    assert result["detail"] == (
        "agent response missing claims/schema_version or bridge error payload"
    )
    assert result["raw_head"] == raw[:400]
    assert result["raw_tail"] == raw[-400:]
