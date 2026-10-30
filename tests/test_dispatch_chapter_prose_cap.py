"""The chapter dispatcher checks every successful output without a provider."""
import sys
from types import ModuleType
from unittest.mock import MagicMock

import pytest

from scripts import dispatch_chapter_prose as prose


@pytest.fixture
def isolated(tmp_path, monkeypatch):
    class RateLimitedError(Exception):
        pass

    class AgentTimeoutError(Exception):
        pass

    runner = ModuleType("agent_runtime.runner")
    runner.invoke = MagicMock(side_effect=AssertionError("unexpected provider invocation"))
    errors = ModuleType("agent_runtime.errors")
    errors.RateLimitedError = RateLimitedError
    errors.AgentTimeoutError = AgentTimeoutError
    package = ModuleType("agent_runtime")
    package.__path__ = []
    for name, module in (("agent_runtime", package), ("agent_runtime.runner", runner),
                         ("agent_runtime.errors", errors)):
        monkeypatch.setitem(sys.modules, name, module)
    setup = MagicMock(return_value=(tmp_path, "test-branch"))
    monkeypatch.setattr(prose, "setup_worktree", setup)
    monkeypatch.setattr(prose, "stage_contract_locally", lambda **kwargs: {"brief.md": "test"})
    fetch = MagicMock(side_effect=AssertionError("unexpected network access"))
    monkeypatch.setattr(prose, "fetch_pr_verdicts", fetch)
    original_phase = prose.fire_phase
    phase = MagicMock(side_effect=AssertionError("unexpected phase dispatch"))
    monkeypatch.setattr(prose, "fire_phase", phase)
    path = tmp_path / "src/content/docs/ai-history/ch-01-test.md"
    return {"setup": setup, "fetch": fetch, "phase": phase, "path": path, "original_phase": original_phase,
            "runner": runner, "rate_limited": RateLimitedError}


def arguments(monkeypatch, cap="2", phases="agy,codex", extra=()):
    monkeypatch.setattr(sys, "argv", ["dispatch", "1", "--slug", "ch-01-test",
                                    "--research-branch", "test", "--cap-words", cap,
                                    "--phases", phases, *extra])


@pytest.mark.parametrize(("cap", "phases", "message"), [
    ("0", "agy", "--cap-words must be positive"), ("-1", "agy", "--cap-words must be positive"),
    ("2", "", "--phases must name at least one phase"),
])
def test_bad_arguments_rejected_before_setup_or_fetch(isolated, monkeypatch, cap, phases, message, capsys):
    arguments(monkeypatch, cap=cap, phases=phases, extra=("--verdict-notes-pr", "123"))
    with pytest.raises(SystemExit) as result:
        prose.main()
    assert result.value.code != 0
    assert message in capsys.readouterr().err
    isolated["setup"].assert_not_called()
    isolated["fetch"].assert_not_called()
    isolated["phase"].assert_not_called()
    isolated["runner"].invoke.assert_not_called()


@pytest.mark.parametrize(
    ("case", "diagnostic"),
    [("missing", "unreadable"), ("directory", "unreadable"), ("invalid_utf8", "unreadable"),
     ("empty", "empty body"), ("markup_only", "empty body"), ("frontmatter_only", "empty body"),
     ("unclosed_frontmatter", "unterminated frontmatter"), ("bad_frontmatter", "invalid frontmatter"), ("over", "over cap")],
)
def test_bad_first_phase_stops_and_preserves_output(isolated, monkeypatch, capsys, case, diagnostic):
    arguments(monkeypatch)
    path = isolated["path"]
    path.parent.mkdir(parents=True)
    bodies = {"invalid_utf8": b"\xff", "empty": b" \n", "markup_only": b"# \n", "frontmatter_only": b"---\ntitle: test\n---\n",
              "unclosed_frontmatter": b"---\ntitle: test\n", "bad_frontmatter": b"---\ntext\n---\none", "over": b"one two three"}
    if case == "directory":
        path.mkdir()
    elif case in bodies:
        path.write_bytes(bodies[case])
    isolated["phase"].side_effect = lambda **kwargs: True

    assert prose.main() != 0
    captured = capsys.readouterr()
    assert diagnostic in captured.err and "cap=2" in captured.err and "count=" in captured.err
    assert "[done]" not in captured.out and "[next]" not in captured.out
    assert [c.kwargs["agent"] for c in isolated["phase"].call_args_list] == ["agy"]
    assert path.is_dir() if case == "directory" else (path.read_bytes() == bodies[case] if case in bodies else not path.exists())
    isolated["runner"].invoke.assert_not_called()


@pytest.mark.parametrize("body", ["one", "one two", "---\ntitle: not counted\n---\none two", "# Heading", "---\ntitle: test\ndescription: |\n  alpha\n  ---\n  beta\n---\none two"])
def test_short_and_exact_cap_continue_across_phases(isolated, monkeypatch, capsys, body):
    arguments(monkeypatch)
    path = isolated["path"]
    path.parent.mkdir(parents=True)
    path.write_text(body, encoding="utf-8")
    isolated["phase"].side_effect = lambda **kwargs: True
    assert prose.main() == 0
    assert [c.kwargs["agent"] for c in isolated["phase"].call_args_list] == ["agy", "codex"]
    assert "[done]" in capsys.readouterr().out
    isolated["runner"].invoke.assert_not_called()


def test_second_phase_over_cap_blocks_final_success(isolated, monkeypatch, capsys):
    arguments(monkeypatch)
    path = isolated["path"]
    path.parent.mkdir(parents=True)
    path.write_text("one", encoding="utf-8")

    def phase(**kwargs):
        if kwargs["agent"] == "codex":
            path.write_text("one two three", encoding="utf-8")
        return True

    isolated["phase"].side_effect = phase
    assert prose.main() != 0
    output = capsys.readouterr()
    assert "count=3, cap=2" in output.err and "[done]" not in output.out and "[next]" not in output.out
    assert path.read_text(encoding="utf-8") == "one two three"
    assert [c.kwargs["agent"] for c in isolated["phase"].call_args_list] == ["agy", "codex"]


@pytest.mark.parametrize(("body", "success"), [("one two", True), ("one two three", False)])
def test_recovered_commit_success_still_checks_actual_output(isolated, monkeypatch, tmp_path, capsys, body, success):
    arguments(monkeypatch, phases="agy")
    path = isolated["path"]
    path.parent.mkdir(parents=True)
    path.write_text(body, encoding="utf-8")
    isolated["runner"].invoke.side_effect = isolated["rate_limited"]("simulated")
    committed = MagicMock(return_value=True)
    monkeypatch.setattr(prose, "_prose_committed_on_branch", committed)
    real_phase = isolated["original_phase"]

    def recovered(**kwargs):
        kwargs["log_path"] = tmp_path / "phase.log"
        return real_phase(**kwargs)

    monkeypatch.setattr(prose, "fire_phase", recovered)
    assert (prose.main() == 0) == success
    output = capsys.readouterr()
    assert ("[done]" in output.out) == success
    assert ("over cap" in output.err) is not success
    assert path.read_text(encoding="utf-8") == body
    committed.assert_called_once()
    isolated["runner"].invoke.assert_called_once()
