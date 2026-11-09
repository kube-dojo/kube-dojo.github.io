from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
import detect_uk_divergence as detect


def _run(repo: Path, *args: str) -> str:
    return subprocess.run(["git", *args], cwd=repo, check=True, text=True, capture_output=True).stdout.strip()


def _init_repo(repo: Path) -> None:
    _run(repo, "init")
    _run(repo, "config", "user.email", "test@example.com")
    _run(repo, "config", "user.name", "Test User")


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _en(repo: Path, key: str, body: str = "English body") -> tuple[Path, str]:
    path = repo / "src/content/docs" / f"{key}.md"
    _write(path, "\n".join(["---", 'title: English', "---", "", "## Body", "", body]))
    _run(repo, "add", str(path)); _run(repo, "commit", "-m", "en")
    return path, _run(repo, "log", "-1", "--format=%H", "--", str(path))


def _uk(path: Path, commit: str | None, en_file: Path) -> None:
    lines = ["---", 'title: Українська']
    if commit:
        lines.append(f'en_commit: "{commit}"')
    _write(path, "\n".join(lines + [f'en_file: "{en_file}"', "---", "", "## Тіло", "", "Переклад"]))


def test_matching_commits_are_not_flagged(tmp_path: Path) -> None:
    _init_repo(tmp_path)
    en_path, en_commit = _en(tmp_path, "prerequisites/zero-to-terminal/module-0.1-alpha")
    _uk(tmp_path / "src/content/docs/uk/prerequisites/zero-to-terminal/module-0.1-alpha.md", en_commit, en_path.relative_to(tmp_path))
    _run(tmp_path, "add", "."); _run(tmp_path, "commit", "-m", "uk")

    summary = detect.detect_uk_divergence(repo_root=tmp_path, dry_run=True)
    assert not summary["stale"]
    assert not summary["missing_en_commit"]


def test_drift_above_threshold(tmp_path: Path) -> None:
    _init_repo(tmp_path)
    en_path, en_commit = _en(tmp_path, "prerequisites/zero-to-terminal/module-0.2-beta", "old")
    _uk(tmp_path / "src/content/docs/uk/prerequisites/zero-to-terminal/module-0.2-beta.md", en_commit, en_path.relative_to(tmp_path))
    _run(tmp_path, "add", "."); _run(tmp_path, "commit", "-m", "uk")

    _write(en_path, "\n".join(["---", 'title: English', "---", "", "## Body", "", "changed", *[f"x{i}" for i in range(8)]]))
    _run(tmp_path, "add", str(en_path)); _run(tmp_path, "commit", "-m", "en update")

    summary = detect.detect_uk_divergence(repo_root=tmp_path, threshold=5, dry_run=True)
    assert summary["stale"][0]["module_key"] == "prerequisites/zero-to-terminal/module-0.2-beta"
    assert summary["enqueued"] == []
    db = tmp_path / ".pipeline/translation_v2.db"
    with pytest.raises(RuntimeError, match="legacy dispatcher removed"):
        detect.detect_uk_divergence(repo_root=tmp_path, threshold=5, db_path=db)


def test_missing_en_commit_reported(tmp_path: Path) -> None:
    _init_repo(tmp_path)
    en_path, _ = _en(tmp_path, "prerequisites/zero-to-terminal/module-0.3-gamma")
    _uk(tmp_path / "src/content/docs/uk/prerequisites/zero-to-terminal/module-0.3-gamma.md", None, en_path.relative_to(tmp_path))
    _run(tmp_path, "add", "."); _run(tmp_path, "commit", "-m", "uk")

    summary = detect.detect_uk_divergence(repo_root=tmp_path, dry_run=True)
    assert summary["missing_en_commit"][0]["module_key"] == "prerequisites/zero-to-terminal/module-0.3-gamma"
    assert summary["stale"] == []


def test_idempotent_enqueue(tmp_path: Path) -> None:
    # A second identical call must not re-enqueue the same module.
    # After the first call, _has_pending_or_leased_job returns True for the module,
    # so the enqueue branch is skipped and summary["enqueued"] == [] on the second run.
    # Uses a real ControlPlane against a tempdir SQLite db (no mocks).
    _init_repo(tmp_path)
    en_path, en_commit = _en(tmp_path, "prerequisites/zero-to-terminal/module-0.4-delta", "old")
    _uk(tmp_path / "src/content/docs/uk/prerequisites/zero-to-terminal/module-0.4-delta.md", en_commit, en_path.relative_to(tmp_path))
    _run(tmp_path, "add", "."); _run(tmp_path, "commit", "-m", "uk")

    _write(en_path, "\n".join(["---", 'title: English', "---", "", "## Body", "", "changed", *[f"x{i}" for i in range(8)]]))
    _run(tmp_path, "add", str(en_path)); _run(tmp_path, "commit", "-m", "en update")

    db = tmp_path / ".pipeline/translation_v2.db"
    with pytest.raises(RuntimeError, match="legacy dispatcher removed"):
        detect.detect_uk_divergence(repo_root=tmp_path, threshold=5, db_path=db)
