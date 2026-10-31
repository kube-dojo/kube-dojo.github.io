from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

SCRIPT = Path(__file__).resolve().parent.parent / "scripts" / "dispatch_smart.py"
SCRIPTS_DIR = SCRIPT.parent
REPO = SCRIPT.parents[1]
PRIMARY_REPO = REPO.parent.parent if REPO.parent.name == ".worktrees" else REPO


def _run_dispatch_smart(args: list[str]) -> subprocess.CompletedProcess:
    cmd = [str(PRIMARY_REPO / ".venv/bin/python"), str(SCRIPT)] + args
    return subprocess.run(cmd, capture_output=True, text=True, check=False)


def test_dispatch_smart_danger_requires_worktree() -> None:
    """Dispatching danger mode without --worktree should hard-fail."""
    result = _run_dispatch_smart(["edit", "--mode", "danger", "x"])

    assert result.returncode != 0
    merged_output = (result.stdout + result.stderr).lower()
    assert "danger" in merged_output
    assert "worktree" in merged_output


def test_dispatch_smart_danger_allows_dry_run_with_worktree() -> None:
    """Dry-run should not touch missing worktrees and should still resolve mode checks."""
    result = _run_dispatch_smart(
        ["edit", "--mode", "danger", "--worktree", ".worktrees/foo", "--dry-run", "x"]
    )

    assert result.returncode == 0
    assert "mode=danger" in result.stdout
    assert "[dry-run] task_id=" in result.stdout


def test_agy_review_cannot_override_unverified_read_only_isolation() -> None:
    for task in ("review", "search"):
        for mode in (None, "read-only", "workspace-write", "danger"):
            result = _run_dispatch_smart(
                [task, "--agent", "agy", *([] if mode is None else ["--mode", mode]), "--dry-run", "x"]
            )
            assert result.returncode != 0
            assert "read-only route disabled" in result.stderr
            assert "[dry-run]" not in result.stdout
    result = _run_dispatch_smart(["edit", "--agent", "agy", "--worktree", ".worktrees/foo", "--dry-run", "x"])
    assert result.returncode == 0 and "[dry-run]" in result.stdout


def test_agy_direct_fire_cannot_bypass_review_pause() -> None:
    import pytest

    sys.path.insert(0, str(SCRIPTS_DIR))
    from dispatch_smart import fire

    for task in ("review", "search"):
        with pytest.raises(ValueError, match="read-only route disabled"):
            fire(agent="agy", task_class=task, prompt="x", mode="danger", model="gemini-4-argon-high",
                 worktree=None, task_id="must-not-spawn", timeout_s=1)


def test_hermes_agent_is_retired_fail_closed() -> None:
    """--agent hermes must refuse with a redirect to grok / deepseek."""
    result = _run_dispatch_smart(
        ["review", "--agent", "hermes", "--dry-run", "x"]
    )
    assert result.returncode != 0
    merged = (result.stdout or "") + (result.stderr or "")
    assert "retired" in merged.lower()
    assert "grok" in merged.lower()
    assert "deepseek" in merged.lower()


def test_opencode_and_qwen_are_not_routing_seats() -> None:
    for agent in ("opencode", "qwen"):
        result = _run_dispatch_smart(
            ["review", "--agent", agent, "--dry-run", "x"]
        )
        assert result.returncode != 0
        merged = (result.stdout or "") + (result.stderr or "")
        assert "not routing seats" in merged.lower()


def test_hermes_router_command_raises() -> None:
    """Direct router path also refuse hermes (defense in depth)."""
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
    import pytest
    from dispatch_smart import HERMES_RETIRED_MESSAGE, _router_command

    with pytest.raises(ValueError, match="retired"):
        _router_command("hermes", "grok-4.7", "hello")
    assert "grok-4.7" in HERMES_RETIRED_MESSAGE


def test_grok_default_model_is_grok_47() -> None:
    """Native grok lane defaults to grok-4.7 (replaces grok-4.6; Fable/Astra tier)."""
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
    from dispatch_smart import TASK_CLASSES

    for task_class, cfg in TASK_CLASSES.items():
        assert cfg.models["grok"] == "grok-4.7", task_class
        assert "hermes" not in cfg.models


def test_hermes_provider_helpers_still_map_deepseek_first_party(monkeypatch) -> None:
    """Residual _hermes_provider_for_model keeps #2245 first-party mapping for
    leftover bridge/qwen callers — not a live --agent hermes path."""
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
    from dispatch_smart import _hermes_provider_for_model

    monkeypatch.delenv("KUBEDOJO_HERMES_PROVIDER", raising=False)
    assert _hermes_provider_for_model("deepseek-v4-pro") == "deepseek"
    assert _hermes_provider_for_model("deepseek-v4-flash") == "deepseek"
    assert _hermes_provider_for_model("deepseek-flash") == "deepseek"


def test_hermes_provider_unknown_model_raises(monkeypatch) -> None:
    """Unknown models raise instead of silently billing a metered proxy (#2245)."""
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
    import pytest
    from dispatch_smart import _hermes_provider_for_model

    monkeypatch.delenv("KUBEDOJO_HERMES_PROVIDER", raising=False)
    with pytest.raises(ValueError, match="2245"):
        _hermes_provider_for_model("kimi-k2.6")


def test_hermes_provider_openrouter_prefix_is_the_explicit_opt_in(monkeypatch) -> None:
    """openrouter/ prefix selects the proxy; the prefix is stripped for -m."""
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
    from dispatch_smart import _hermes_cli_model, _hermes_provider_for_model

    monkeypatch.delenv("KUBEDOJO_HERMES_PROVIDER", raising=False)
    assert _hermes_provider_for_model("openrouter/deepseek/deepseek-v4-pro") == "openrouter"
    assert _hermes_cli_model("openrouter/deepseek/deepseek-v4-pro") == "deepseek/deepseek-v4-pro"


def test_opencode_router_argv_uses_json_format() -> None:
    sys.path.insert(0, str(SCRIPTS_DIR))
    from dispatch_smart import _router_command

    cmd = _router_command("opencode", "zai-coding-plan/glm-5.2", "hello")
    assert cmd[1:4] == ["run", "--format", "json"]
    assert cmd[-3:] == ["-m", "zai-coding-plan/glm-5.2", "-"]


def test_parse_opencode_json_events_extracts_final_assistant_text() -> None:
    sys.path.insert(0, str(SCRIPTS_DIR))
    from dispatch_smart import _parse_opencode_json_events

    ndjson = "\n".join(
        [
            json.dumps(
                {
                    "type": "step_start",
                    "part": {"messageID": "msg_tool", "type": "step-start"},
                }
            ),
            json.dumps(
                {
                    "type": "tool_use",
                    "part": {"messageID": "msg_tool", "type": "tool", "tool": "bash"},
                }
            ),
            json.dumps(
                {
                    "type": "step_finish",
                    "part": {
                        "messageID": "msg_tool",
                        "reason": "tool-calls",
                        "type": "step-finish",
                    },
                }
            ),
            json.dumps(
                {
                    "type": "step_start",
                    "part": {"messageID": "msg_final", "type": "step-start"},
                }
            ),
            json.dumps(
                {
                    "type": "text",
                    "part": {
                        "messageID": "msg_final",
                        "type": "text",
                        "text": "VERDICT: ",
                    },
                }
            ),
            json.dumps(
                {
                    "type": "text",
                    "part": {
                        "messageID": "msg_final",
                        "type": "text",
                        "text": "APPROVE",
                    },
                }
            ),
            json.dumps(
                {
                    "type": "step_finish",
                    "part": {
                        "messageID": "msg_final",
                        "reason": "stop",
                        "type": "step-finish",
                    },
                }
            ),
        ]
    )
    assert _parse_opencode_json_events(ndjson) == "VERDICT: APPROVE"


def test_codex_defaults_use_terra_execution_sol_judgment_luna_scouting() -> None:
    sys.path.insert(0, str(SCRIPTS_DIR))
    from dispatch_smart import TASK_CLASSES

    for task_class, cfg in TASK_CLASSES.items():
        assert "opencode" not in cfg.models
        assert "qwen" not in cfg.models
        assert cfg.models["deepseek"] == "deepseek-flash"
        assert cfg.codex_reasoning_effort == "high", task_class
        assert not cfg.models["codex"].startswith("gpt-5.6"), task_class
        if task_class == "search":
            assert cfg.models["codex"] == "gpt-6-luna", task_class
        elif task_class in {"edit", "draft"}:
            assert cfg.models["codex"] == "gpt-6.1-terra", task_class
        elif task_class in {"review", "architect"}:
            assert cfg.models["codex"] == "gpt-6.1-sol", task_class
        if task_class == "search":
            assert cfg.models["cursor"] == "composer-2.5"
        else:
            assert cfg.models["cursor"] == "grok-4.7-high"


def test_codex_environment_override_reaches_cli() -> None:
    code = (
        "from pathlib import Path;from scripts.agent_runtime.adapters.codex import CodexAdapter;"
        "p=CodexAdapter().build_invocation(prompt='x',mode='danger',cwd=Path.cwd(),model=None,task_id=None,session_id=None,tool_config=None);"
        "assert p.cmd[p.cmd.index('-m')+1]=='gpt-6.1-sol'"
    )
    result = subprocess.run([str(PRIMARY_REPO / ".venv/bin/python"), "-c", code], cwd=REPO, env={**os.environ, "AB_CODEX_MODEL": "gpt-6.1-sol"}, capture_output=True, text=True, check=False)
    assert result.returncode == 0, result.stderr


def test_grok_search_argv_sets_low_effort() -> None:
    sys.path.insert(0, str(SCRIPTS_DIR))
    from dispatch_smart import _router_command

    cmd = _router_command("grok", "grok-4.7", "hello", grok_effort="low")
    assert cmd[cmd.index("-m") + 1] == "grok-4.7"
    assert cmd[cmd.index("--reasoning-effort") + 1] == "low"


def test_claude_opus_default_fable_advisor_sonnet_routine() -> None:
    sys.path.insert(0, str(SCRIPTS_DIR))
    from dispatch_smart import TASK_CLASSES

    assert TASK_CLASSES["architect"].models["claude"] == "claude-fable-5-1"
    assert TASK_CLASSES["review"].models["claude"] == "claude-opus-5-5"
    for task_class in ("edit", "draft"):
        assert TASK_CLASSES[task_class].models["claude"] == "claude-sonnet-5"
    assert TASK_CLASSES["search"].models["claude"] == "claude-haiku-4-5-20251001"
    assert TASK_CLASSES["search"].models["codex"] == "gpt-6-luna"
    assert TASK_CLASSES["search"].models["cursor"] == "composer-2.5"
    assert TASK_CLASSES["search"].models["grok"] == "grok-4.7"
    assert TASK_CLASSES["search"].grok_reasoning_effort == "low"
    assert TASK_CLASSES["draft"].grok_reasoning_effort is None


def test_dispatch_smart_codex_forces_danger_mode() -> None:
    """Codex always resolves to danger mode."""
    # Codex auto-forces mode=danger, so non-read-only-like dispatches still
    # require a worktree.
    result = _run_dispatch_smart(["edit", "--agent", "codex", "x"])
    merged_output = (result.stdout or "") + (result.stderr or "")
    assert result.returncode != 0
    assert "danger" in merged_output
    assert "worktree" in merged_output


def test_dispatch_smart_codex_review_no_worktree_required() -> None:
    """Codex review/search remain runtime-necessary in danger mode but do not need a worktree.

    Regression test for #1586: dispatch_smart.py previously forced --worktree for any
    codex dispatch because mode=danger required it; that broke Decision Card C codex-as-reviewer
    pairings. The fix carves out the worktree REQUIREMENT for codex review/search while keeping
    codex in danger mode (codex adapter needs network+FS for tool-calls).
    """
    result = _run_dispatch_smart(["review", "--agent", "codex", "--dry-run", "x"])
    assert result.returncode == 0
    assert "mode=danger" in result.stdout
    assert "worktree=(none — danger)" in result.stdout
    merged_output = (result.stdout or "") + (result.stderr or "")
    assert "requires --worktree" not in merged_output


def test_ci_marker_guard_blocks_glm_and_first_party_deepseek(monkeypatch) -> None:
    """CI guard refuses GLM/z.ai markers and the first-party DeepSeek lane."""
    sys.path.insert(0, str(SCRIPTS_DIR))
    import pytest
    from dispatch_smart import guard_no_china_provider_in_ci

    monkeypatch.setenv("GITHUB_ACTIONS", "true")

    with pytest.raises(SystemExit):
        guard_no_china_provider_in_ci("opencode", "zai-coding-plan/glm-5.2")

    with pytest.raises(SystemExit):
        guard_no_china_provider_in_ci("deepseek", "deepseek-flash")

    with pytest.raises(SystemExit):
        guard_no_china_provider_in_ci("opencode", "deepseek-direct/deepseek-flash")

    # OpenRouter-routed deepseek slug is not a direct China marker.
    guard_no_china_provider_in_ci("opencode", "openrouter/deepseek/deepseek-chat")


def test_ci_guard_noop_outside_ci(monkeypatch) -> None:
    """Outside CI the guard never fires, even for a China-hosted marker."""
    sys.path.insert(0, str(SCRIPTS_DIR))
    from dispatch_smart import guard_no_china_provider_in_ci

    monkeypatch.delenv("GITHUB_ACTIONS", raising=False)
    monkeypatch.delenv("CI", raising=False)
    guard_no_china_provider_in_ci("opencode", "zai-coding-plan/glm-5.2")
    guard_no_china_provider_in_ci("deepseek", "deepseek-flash")
