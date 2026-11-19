from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent


@pytest.fixture
def deployment(tmp_path):
    extensions = tmp_path / "agents_extensions"
    shutil.copytree(ROOT / "agents_extensions", extensions)
    subprocess.run(["git", "init", "--quiet", str(tmp_path)], check=True, timeout=10)
    source = extensions / "codex" / "config.toml"
    script = extensions / "deploy.sh"
    target = tmp_path / ".codex/config.toml"

    def run(*args):
        return subprocess.run(
            ["bash", str(script), *args],
            capture_output=True, text=True, check=False, timeout=30,
        )

    return source, target, run


def test_config_deployment_and_idempotent_check(deployment):
    source, target, run = deployment
    assert run("--check").returncode == 1
    assert not target.exists()
    assert run().returncode == 0
    assert target.read_bytes() == source.read_bytes()
    modified = target.stat().st_mtime_ns
    assert run().returncode == 0
    assert target.stat().st_mtime_ns == modified
    assert run("--check").returncode == 0


def test_differing_unowned_config_is_preserved(deployment):
    source, target, run = deployment
    target.parent.mkdir()
    original = 'model = "local-choice"\n'
    target.write_text(original)
    result = run()
    assert result.returncode == 2
    assert "differing unowned output: .codex/config.toml" in result.stderr
    assert target.read_text() == original
    assert run("--check").returncode == 2
    assert target.read_text() == original
    backup = target.with_name("config.toml.backup")
    target.rename(backup)
    assert run().returncode == 0
    assert backup.read_text() == original
    assert target.read_bytes() == source.read_bytes()
    assert run("--check").returncode == 0


@pytest.mark.parametrize("obsolete_option", ["--force-config", "--target=codex"])
def test_obsolete_options_never_replace_config(deployment, obsolete_option):
    _source, target, run = deployment
    target.parent.mkdir()
    target.write_text('model = "preserve-me"\n')
    result = run(obsolete_option)
    assert result.returncode == 2
    assert "Usage:" in result.stderr
    assert target.read_text() == 'model = "preserve-me"\n'
    assert not list(target.parent.glob("config.toml.bak.*"))


def test_default_deploy_refuses_config_drift_before_other_agents(deployment):
    _source, target, run = deployment
    target.parent.mkdir()
    target.write_text('model = "preserve-me"\n')
    assert run().returncode == 2
    assert not (target.parent.parent / ".claude/settings.json").exists()


@pytest.mark.parametrize("enabled", ["1", "0"])
def test_launcher_sets_v2_and_honors_multi_agent_opt_out(tmp_path, enabled):
    binary_dir = tmp_path / ".local/bin"
    binary_dir.mkdir(parents=True)
    fake_codex = binary_dir / "codex"
    fake_codex.write_text('#!/bin/bash\nprintf "%s\\n" "$@" > "$CLI_CAPTURE"\n')
    fake_codex.chmod(0o755)
    capture = tmp_path / "argv"
    env = dict(os.environ)
    env.pop("CODEX_EPIC", None)
    env.update(HOME=str(tmp_path), CODEX_TARGET="main", CODEX_ENABLE_MULTI_AGENT=enabled, CLI_CAPTURE=str(capture))
    result = subprocess.run(
        ["bash", str(ROOT / "start-codex.sh"), "--main", "--model", "chosen-model"],
        env=env, capture_output=True, text=True, check=False,
    )
    assert result.returncode == 0, result.stderr
    args = capture.read_text().splitlines()
    assert args[1:5] == [
        "--enable" if enabled == "1" else "--disable", "multi_agent", "-c",
        f"features.multi_agent_v2.enabled={'true' if enabled == '1' else 'false'}",
    ]
    assert args[-2:] == ["--model", "chosen-model"]
