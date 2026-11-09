from __future__ import annotations

import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]
SCRIPTS_DIR = REPO_ROOT / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))


def _drop_bridge_modules() -> None:
    for name in list(sys.modules):
        if name == "ai_agent_bridge" or name.startswith("ai_agent_bridge."):
            del sys.modules[name]


def _load_cli(monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
    monkeypatch.setenv("AB_DB_PATH", str(tmp_path / "messages.db"))
    monkeypatch.setenv("AB_REPO_ROOT", str(REPO_ROOT))
    _drop_bridge_modules()

    from ai_agent_bridge import _cli, _messaging

    monkeypatch.setattr(
        _messaging.subprocess,
        "run",
        lambda *_args, **_kwargs: None,
    )
    return _cli


@pytest.mark.parametrize(
    "command",
    ["ask-agy"],
)
def test_new_ask_subparsers_register(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    command: str,
) -> None:
    cli = _load_cli(monkeypatch, tmp_path)

    args = cli._build_parser().parse_args([command, "OK test"])

    assert args.command == command
    assert args.content == "OK test"
    assert args.task_id is None
    assert args.no_timeout is False
    assert args.review is False


@pytest.mark.parametrize(
    ("command", "agent"),
    [
        ("ask-agy", "agy"),
    ],
)
def test_new_ask_handlers_invoke_runtime_with_default_model(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    command: str,
    agent: str,
) -> None:
    cli = _load_cli(monkeypatch, tmp_path)
    calls: list[tuple[str, str, dict]] = []

    from agent_runtime.registry import get_agent_entry
    import agent_runtime.runner as runner

    def fake_invoke(agent_name: str, prompt: str, **kwargs):
        calls.append((agent_name, prompt, kwargs))
        return SimpleNamespace(
            ok=True,
            response=f"{agent_name} response",
            stderr_excerpt=None,
            session_id=None,
        )

    monkeypatch.setattr(runner, "invoke", fake_invoke)

    args = cli._build_parser().parse_args(
        [command, "OK test", "--task-id", "bridge-test", "--from", "claude"]
    )

    assert cli._dispatch_command(args) is True
    assert len(calls) == 1

    agent_name, prompt, kwargs = calls[0]
    expected_model = str(get_agent_entry(agent)["default_model"])
    assert agent_name == agent
    assert "OK test" in prompt
    assert kwargs["mode"] == "read-only"
    assert kwargs["model"] == expected_model
    assert kwargs["task_id"] == "bridge-test"
    assert kwargs["entrypoint"] == "bridge"
    assert kwargs["hard_timeout"] == 900
