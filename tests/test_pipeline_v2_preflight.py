from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

from pipeline_v2.preflight import _normalize_external_url, run_preflight

REPRESENTATIVE_MARKDOWN = """---
title: Sample Module
slug: sample/module
sidebar:
  order: 1
---

# Sample Module Overview

Paragraph with a deliberately very long line that reflects the docs style used in the repository and should not fail markdownlint in v2 preflight.

<details>
<summary>Expandable answer</summary>
Inline HTML is allowed in this docs site.
</details>

```
plain fenced block without language
```

|a|b|
|---|---|
|1|2|

- list item one
- list item two
"""


def test_normalize_external_url_ignores_placeholder_and_local_hosts():
    assert _normalize_external_url("http://localhost:8080`.") is None
    assert _normalize_external_url("http://YOUR_PUBLIC_IP`") is None
    assert _normalize_external_url("https://example.com/docs,") == "https://example.com/docs"


def test_run_preflight_uses_relaxed_repo_markdownlint_config(tmp_path):
    repo_root = Path(__file__).resolve().parent.parent
    config_src = repo_root / ".markdownlint-cli2.yaml"
    (tmp_path / ".markdownlint-cli2.yaml").write_text(config_src.read_text(encoding="utf-8"), encoding="utf-8")

    module_path = tmp_path / "docs" / "sample.md"
    module_path.parent.mkdir(parents=True, exist_ok=True)
    module_path.write_text(REPRESENTATIVE_MARKDOWN, encoding="utf-8")

    result = run_preflight(module_path, repo_root=tmp_path, link_cache_path=tmp_path / "link-cache.json")

    markdownlint_findings = [finding for finding in result.findings if finding.id == "MARKDOWNLINT"]
    assert markdownlint_findings
    assert all(finding.passed for finding in markdownlint_findings)


def test_real_markdownlint_checks_snapshot_stdin_and_root_configuration(tmp_path):
    root = Path(__file__).resolve().parent.parent
    (tmp_path / ".markdownlint-cli2.yaml").write_text((root / ".markdownlint-cli2.yaml").read_text())
    path = tmp_path / "snapshot.md"
    path.write_text("not the candidate")
    for text, expected in ((REPRESENTATIVE_MARKDOWN, True), ("# Duplicate\n# Duplicate\n", False)):
        result = run_preflight(path, repo_root=tmp_path, content=text)
        lint = [finding for finding in result.findings if finding.id == "MARKDOWNLINT"]
        assert lint and all(finding.passed for finding in lint) is expected
    assert path.read_text() == "not the candidate"


def test_run_preflight_downgrades_missing_yamllint_to_warning(tmp_path):
    repo_root = Path(__file__).resolve().parent.parent
    config_src = repo_root / ".markdownlint-cli2.yaml"
    (tmp_path / ".markdownlint-cli2.yaml").write_text(config_src.read_text(encoding="utf-8"), encoding="utf-8")

    module_path = tmp_path / "docs" / "sample-yaml.md"
    module_path.parent.mkdir(parents=True, exist_ok=True)
    module_path.write_text(
        """---
title: YAML Sample
slug: sample/yaml
sidebar:
  order: 1
---

# YAML Sample

```yaml
apiVersion: v1
kind: ConfigMap
metadata:
  name: sample
```
""",
        encoding="utf-8",
    )

    real_run = __import__("subprocess").run

    def side_effect(cmd, *args, **kwargs):
        if cmd and cmd[0] == "yamllint":
            raise FileNotFoundError("yamllint")
        return real_run(cmd, *args, **kwargs)

    with patch("pipeline_v2.preflight.subprocess.run", side_effect=side_effect):
        result = run_preflight(module_path, repo_root=tmp_path, link_cache_path=tmp_path / "link-cache.json")

    yamllint_findings = [finding for finding in result.findings if finding.id == "YAMLLINT"]
    assert yamllint_findings
    assert yamllint_findings[0].severity == "WARNING"
