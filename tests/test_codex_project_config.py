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
    source = extensions / "codex" / "config.toml"
    source.parent.mkdir(parents=True)
    shutil.copy2(ROOT / "agents_extensions/codex/config.toml", source)
    script = extensions / "deploy.sh"
    shutil.copy2(ROOT / "agents_extensions/deploy.sh", script)
    target = tmp_path / ".codex/config.toml"

    def run(*args):
        return subprocess.run(
            ["bash", str(script), "--target", "codex", *args],
            capture_output=True, text=True, check=False,
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


def test_differing_config_is_preserved_unless_explicitly_backed_up(deployment):
    source, target, run = deployment
    target.parent.mkdir()
    original = 'model = "local-choice"\n'
    target.write_text(original)
    assert run().returncode == 1
    assert target.read_text() == original
    assert not list(target.parent.glob("config.toml.bak.*"))
    assert run("--check", "--force-config").returncode == 1
    assert target.read_text() == original
    assert run("--force-config").returncode == 0
    backups = list(target.parent.glob("config.toml.bak.*"))
    assert len(backups) == 1
    assert backups[0].read_text() == original
    assert target.read_bytes() == source.read_bytes()
    assert run("--check").returncode == 0


@pytest.mark.parametrize("failed_command", ["mktemp", "cp"])
def test_backup_failure_never_replaces_config(deployment, tmp_path, monkeypatch, failed_command):
    _source, target, run = deployment
    target.parent.mkdir()
    target.write_text('model = "preserve-me"\n')
    commands = tmp_path / "bin"
    commands.mkdir()
    command = commands / failed_command
    command.write_text(
        "#!/bin/sh\nexit 1\n" if failed_command == "mktemp" else
        '#!/bin/sh\ncase "$*" in *".bak."*) exit 1;; esac\nexec /bin/cp "$@"\n'
    )
    command.chmod(0o755)
    monkeypatch.setenv("PATH", str(commands) + os.pathsep + os.environ["PATH"])
    assert run("--force-config").returncode == 1
    assert target.read_text() == 'model = "preserve-me"\n'


def test_default_deploy_refuses_config_drift_before_other_agents(deployment):
    source, target, run = deployment
    target.parent.mkdir()
    target.write_text('model = "preserve-me"\n')
    hook = source.parent.parent / "claude/hooks/probe.sh"
    hook.parent.mkdir(parents=True)
    hook.write_text("#!/bin/sh\nexit 0\n")
    assert run("--target", "all").returncode == 1
    assert not (target.parent.parent / ".claude/hooks/probe.sh").exists()


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
