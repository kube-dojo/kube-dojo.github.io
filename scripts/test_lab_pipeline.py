#!/usr/bin/env python3
"""Tests for the decoupled lab pipeline."""

from __future__ import annotations

import json
import os
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import yaml

REPO_ROOT = Path(__file__).parent.parent
import sys

sys.path.insert(0, str(REPO_ROOT / "scripts"))

import lab_pipeline as lp
GEMINI_WRITER_MODEL = "gemini-3.1-pro-high"


def _write_module(path: Path, *, lab: str | dict | None = None) -> None:
    frontmatter = {
        "title": "Module 1.1: Control Plane",
        "slug": "k8s/cka/part1-cluster-architecture/module-1.1-control-plane",
    }
    if lab is not None:
        frontmatter["lab"] = lab
    body = """\
## What You'll Be Able to Do

- Explain the control plane
- Diagnose scheduler issues

## What You'll Learn

- API server
- etcd

## Hands-On Exercise

Use the linked lab to practice control plane debugging.
"""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(f"---\n{yaml.dump(frontmatter, sort_keys=False)}---\n{body}")


def _write_lab(
    lab_dir: Path,
    *,
    key: str,
    module: str | None = None,
    include_solution: bool = True,
    include_difficulty: bool = True,
) -> Path:
    lab_path = lab_dir / key
    (lab_path / "step1").mkdir(parents=True, exist_ok=True)
    index = {
        "title": "CKA 1.1 Control Plane",
        "description": "Control plane practice",
        "time": "30 minutes",
        "details": {
            "intro": {"text": "intro.md", "background": "setup.sh"},
            "steps": [
                {
                    "title": "Inspect components",
                    "text": "step1/text.md",
                    "verify": "step1/verify.sh",
                }
            ],
            "finish": {"text": "finish.md"},
        },
        "backend": {"imageid": "ubuntu"},
    }
    if include_difficulty:
        index["difficulty"] = "Intermediate"
    if module is not None:
        index["module"] = module
    if include_solution:
        index["details"]["steps"][0]["solution"] = "step1/solution.sh"
    lab_path.mkdir(parents=True, exist_ok=True)
    (lab_path / "index.json").write_text(json.dumps(index, indent=2))
    (lab_path / "intro.md").write_text("Intro text")
    (lab_path / "setup.sh").write_text("#!/usr/bin/env bash\nexit 0\n")
    (lab_path / "finish.md").write_text("Finish text")
    (lab_path / "step1" / "text.md").write_text("Step text")
    (lab_path / "step1" / "verify.sh").write_text("#!/usr/bin/env bash\nkubectl get pods -o jsonpath='{.items[0].metadata.name}' >/dev/null\n")
    if include_solution:
        (lab_path / "step1" / "solution.sh").write_text("#!/usr/bin/env bash\nexit 0\n")
    return lab_path


class TestModuleMapping(unittest.TestCase):
    def setUp(self) -> None:
        self.tmpdir = Path(tempfile.mkdtemp())
        self.content_root = self.tmpdir / "content"
        self.labs_dir = self.tmpdir / "labs"

    def tearDown(self) -> None:
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_find_module_for_lab_uses_metadata(self):
        module_path = self.content_root / "k8s/cka/part1-cluster-architecture/module-1.1-control-plane.md"
        _write_module(module_path, lab={"id": "cka-1.1-control-plane"})
        lab_path = _write_lab(
            self.labs_dir,
            key="cka-1.1-control-plane",
            module="k8s/cka/part1-cluster-architecture/module-1.1-control-plane",
        )

        resolution = lp.find_module_for_lab(
            lab_path,
            content_root=self.content_root,
        )

        self.assertEqual(resolution.module_path, module_path)
        self.assertEqual(
            resolution.module_key,
            "k8s/cka/part1-cluster-architecture/module-1.1-control-plane",
        )
        self.assertEqual(resolution.warnings, [])
        self.assertEqual(resolution.errors, [])

    def test_find_module_for_lab_falls_back_to_pattern(self):
        module_path = self.content_root / "k8s/cka/part1-cluster-architecture/module-1.1-control-plane.md"
        _write_module(module_path, lab="cka-1.1-control-plane")
        lab_path = _write_lab(self.labs_dir, key="cka-1.1-control-plane")

        resolution = lp.find_module_for_lab(
            lab_path,
            content_root=self.content_root,
        )

        self.assertEqual(resolution.module_path, module_path)
        self.assertTrue(
            any("filename fallback" in warning for warning in resolution.warnings),
            resolution.warnings,
        )


class TestLabState(unittest.TestCase):
    def setUp(self) -> None:
        self.tmpdir = Path(tempfile.mkdtemp())
        self.state_file = self.tmpdir / "lab-state.yaml"

    def tearDown(self) -> None:
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_state_roundtrip(self):
        state = {
            "labs": {
                "cka-1.1-control-plane": {
                    "phase": "done",
                    "last_run": "2026-04-14T08:30:00Z",
                    "severity": "clean",
                    "reviewer": GEMINI_WRITER_MODEL,
                    "module": "k8s/cka/part1-cluster-architecture/module-1.1-control-plane",
                    "checks_failed": [],
                    "errors": [],
                }
            }
        }
        with patch.object(lp, "LAB_STATE_FILE", self.state_file):
            lp.save_lab_state(state)
            loaded = lp.load_lab_state()

        self.assertEqual(loaded, state)


class TestLabReviewFlow(unittest.TestCase):
    def setUp(self) -> None:
        self.tmpdir = Path(tempfile.mkdtemp())
        self.content_root = self.tmpdir / "content"
        self.labs_dir = self.tmpdir / "labs"
        self.state_file = self.tmpdir / ".pipeline" / "lab-state.yaml"
        self.review_dir = self.tmpdir / ".pipeline" / "lab-reviews"

        self.module_path = self.content_root / "k8s/cka/part1-cluster-architecture/module-1.1-control-plane.md"
        _write_module(self.module_path, lab={"id": "cka-1.1-control-plane"})
        self.lab_path = _write_lab(
            self.labs_dir,
            key="cka-1.1-control-plane",
            module="k8s/cka/part1-cluster-architecture/module-1.1-control-plane",
        )

    def tearDown(self) -> None:
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def _mock_static_review(self, *_args, **_kwargs):
        return {
            "verdict": "APPROVE",
            "feedback": "",
            "checks": {
                "STRUCTURE": {"id": "STRUCTURE", "passed": True, "evidence": "ok"},
                "DOCS": {"id": "DOCS", "passed": True, "evidence": "ok"},
                "COVERAGE": {"id": "COVERAGE", "passed": True, "evidence": "ok"},
                "CALIBRATION": {"id": "CALIBRATION", "passed": True, "evidence": "ok"},
                "VERIFY": {"id": "VERIFY", "passed": True, "evidence": "ok"},
            },
        }

    def test_static_review_runs_all_five_static_checks(self):
        with patch.object(lp, "CONTENT_ROOT", self.content_root), \
             patch.object(lp, "LAB_STATE_FILE", self.state_file), \
             patch.object(lp, "LAB_REVIEW_DIR", self.review_dir), \
             patch.object(lp, "review_static_checks_with_model", side_effect=self._mock_static_review):
            result = lp.review_lab(self.lab_path, run_exec=False)

        static_ids = [check["id"] for check in result["checks"][:5]]
        self.assertEqual(static_ids, lp.STATIC_CHECK_IDS)
        self.assertEqual(result["verdict"], "APPROVE")
        self.assertEqual(result["severity"], "clean")
        not_run = [check["id"] for check in result["checks"] if check.get("not_run")]
        self.assertEqual(not_run, ["EXEC", "DETERM"])

    def test_exec_handles_missing_docker_in_dev(self):
        with patch.object(lp, "CONTENT_ROOT", self.content_root), \
             patch.object(lp, "LAB_STATE_FILE", self.state_file), \
             patch.object(lp, "LAB_REVIEW_DIR", self.review_dir), \
             patch.object(lp, "review_static_checks_with_model", side_effect=self._mock_static_review), \
             patch.dict(os.environ, {}, clear=False):
            result = lp.review_lab(
                self.lab_path,
                run_exec=True,
                docker_status=(False, "docker unavailable"),
            )

        self.assertEqual(result["errors"], [])
        self.assertTrue(any("EXEC tier skipped" in warning for warning in result["warnings"]))
        exec_checks = [check for check in result["checks"] if check["id"] in {"EXEC", "DETERM"}]
        self.assertTrue(all(check.get("not_run") for check in exec_checks))

    def test_exec_handles_missing_docker_in_ci(self):
        with patch.object(lp, "CONTENT_ROOT", self.content_root), \
             patch.object(lp, "LAB_STATE_FILE", self.state_file), \
             patch.object(lp, "LAB_REVIEW_DIR", self.review_dir), \
             patch.object(lp, "review_static_checks_with_model", side_effect=self._mock_static_review), \
             patch.dict(os.environ, {"CI": "true"}, clear=False):
            result = lp.review_lab(
                self.lab_path,
                run_exec=True,
                docker_status=(False, "docker unavailable"),
            )

        self.assertTrue(any("Docker unavailable" in error for error in result["errors"]))
        exec_checks = [check for check in result["checks"] if check["id"] in {"EXEC", "DETERM"}]
        self.assertTrue(all(not check.get("passed") for check in exec_checks))
        self.assertTrue(all(not check.get("not_run") for check in exec_checks))

    def test_lab_audit_log_writes_expected_events(self):
        state = {
            "labs": {
                "cka-1.1-control-plane": {
                    "phase": "done",
                    "last_run": "2026-04-14T08:30:00Z",
                    "severity": "clean",
                    "reviewer": GEMINI_WRITER_MODEL,
                    "module": "k8s/cka/part1-cluster-architecture/module-1.1-control-plane",
                    "checks_failed": [],
                    "errors": [],
                }
            }
        }
        with patch.object(lp, "LAB_STATE_FILE", self.state_file), \
             patch.object(lp, "LAB_REVIEW_DIR", self.review_dir):
            lp.save_lab_state(state)
            lp.append_lab_review_audit(
                "cka-1.1-control-plane",
                "LAB_REVIEW",
                verdict="APPROVE",
                reviewer=GEMINI_WRITER_MODEL,
                severity="clean",
                module="k8s/cka/part1-cluster-architecture/module-1.1-control-plane",
                checks=[{"id": "STRUCTURE", "passed": True}],
                feedback="Looks good",
                warnings=[],
            )
            lp.append_lab_review_audit(
                "cka-1.1-control-plane",
                "LAB_DONE",
                reviewer=GEMINI_WRITER_MODEL,
                module="k8s/cka/part1-cluster-architecture/module-1.1-control-plane",
            )

            content = (self.review_dir / "cka-1.1-control-plane.md").read_text()

        self.assertIn("# Lab Review Audit: cka-1.1-control-plane", content)
        self.assertIn("`LAB_REVIEW`", content)
        self.assertIn("`LAB_DONE`", content)
        self.assertLess(content.index("`LAB_DONE`"), content.index("`LAB_REVIEW`"))


class TestRealLabIntegration(unittest.TestCase):
    def test_review_one_real_lab_in_static_mode(self):
        labs = lp.discover_labs()
        lab_path = None
        for candidate in ("cka-0.1-cluster-setup", "prereq-1.1-shell-mastery", "prereq-0.3-first-commands"):
            if candidate in labs:
                lab_path = labs[candidate]
                break
        if lab_path is None:
            self.skipTest("no real lab fixture available in local kubedojo-labs checkout")

        tmpdir = Path(tempfile.mkdtemp())
        try:
            state_file = tmpdir / ".pipeline" / "lab-state.yaml"
            review_dir = tmpdir / ".pipeline" / "lab-reviews"

            def fake_static_review(*_args, **_kwargs):
                return {
                    "verdict": "APPROVE",
                    "feedback": "",
                    "checks": {
                        "STRUCTURE": {"id": "STRUCTURE", "passed": True, "evidence": "ok"},
                        "DOCS": {"id": "DOCS", "passed": True, "evidence": "ok"},
                        "COVERAGE": {"id": "COVERAGE", "passed": True, "evidence": "ok"},
                        "CALIBRATION": {"id": "CALIBRATION", "passed": True, "evidence": "ok"},
                        "VERIFY": {"id": "VERIFY", "passed": True, "evidence": "ok"},
                    },
                }

            with patch.object(lp, "LAB_STATE_FILE", state_file), \
                 patch.object(lp, "LAB_REVIEW_DIR", review_dir), \
                 patch.object(lp, "review_static_checks_with_model", side_effect=fake_static_review):
                result = lp.review_lab(lab_path, run_exec=False)

            self.assertIn(result["verdict"], {"APPROVE", "REJECT"})
            self.assertTrue(Path(result["audit_path"]).exists())
        finally:
            shutil.rmtree(tmpdir, ignore_errors=True)


if __name__ == "__main__":
    unittest.main()
