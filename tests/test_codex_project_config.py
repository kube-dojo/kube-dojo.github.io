from __future__ import annotations

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
