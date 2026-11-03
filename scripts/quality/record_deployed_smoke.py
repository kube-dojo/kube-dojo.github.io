"""Record HTTP smoke evidence from the active GitHub Pages deployment only."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
import urllib.request
from datetime import UTC, datetime
from pathlib import Path

import yaml

from scripts.quality.build_source_receipt import (
    ROOT,
    committed_page,
    digest,
    git,
    require,
    review_output,
    write_json,
)


def gh_json(*args: str) -> dict | list:
    return json.loads(subprocess.run(["gh", *args], capture_output=True, check=True).stdout)


def active_deployment(repository: str) -> dict:
    deployments = gh_json("api", f"repos/{repository}/deployments?environment=github-pages&per_page=1")
    require(isinstance(deployments, list) and bool(deployments), "no Pages deployment")
    deployment = deployments[0]
    statuses = gh_json("api", f"repos/{repository}/deployments/{deployment['id']}/statuses")
    require(isinstance(statuses, list) and bool(statuses) and statuses[0].get("state") == "success", "latest Pages deployment is not successful")
    match = re.fullmatch(rf"https://github.com/{re.escape(repository)}/actions/runs/(\d+)(?:/job/\d+)?", statuses[0].get("log_url", ""))
    require(match is not None, "Pages deployment has no workflow run provenance")
    run = gh_json("run", "view", match[1], "--repo", repository, "--json", "conclusion,headSha,status,url")
    require(run.get("conclusion") == "success" and run.get("status") == "completed", "Pages deployment run is not success")
    require(run.get("headSha") == deployment["sha"], "deployment run head mismatch")
    return {"id": deployment["id"], "environment_url": statuses[0]["environment_url"], "run": run}


def live_html(url: str) -> bytes:
    request = urllib.request.Request(url, headers={"Cache-Control": "no-cache", "User-Agent": "KubeDojo-deployed-smoke"})
    with urllib.request.urlopen(request, timeout=30) as response:
        require(response.status == 200, "deployed page returned non-200")
        require(response.geturl() == url, "deployed page redirected to a different URL")
        require("text/html" in response.headers.get("Content-Type", ""), "deployed response is not HTML")
        return response.read()


def record(root: Path, page: str, checks: list[str], repository: str) -> dict:
    require(re.fullmatch(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+", repository) is not None, "invalid repository")
    raw, _ = committed_page(root, page)
    require(bool(checks) and all(isinstance(c, str) and bool(c.strip()) for c in checks), "at least one nonempty exact HTML check is required")
    deployed = active_deployment(repository)
    head = deployed["run"]["headSha"]
    require(re.fullmatch(r"[0-9a-f]{40,64}", head) is not None, "invalid deployment head")
    # Do not treat ancestry as proof: compare this path's actual committed bytes.
    deployed_raw = git(root, "show", f"{head}:{page}")
    require(digest(deployed_raw) == digest(raw), "deployed head page digest mismatch; fetch deployment commit if unavailable")
    site = gh_json("api", f"repos/{repository}/pages")["html_url"].rstrip("/") + "/"
    require(site.startswith("https://") and deployed["environment_url"].rstrip("/") + "/" == site, "Pages environment URL mismatch")
    text = raw.decode()
    frontmatter = yaml.safe_load(text.split("---", 2)[1]) if text.startswith("---\n") else {}
    route = (frontmatter or {}).get("slug")
    if not route:
        route = page.removeprefix("src/content/docs/").rsplit(".", 1)[0]
        route = route.removesuffix("/index")
        if route == "index":
            route = ""
    require(isinstance(route, str) and not any(c in route for c in (":", "?", "#", "\\")) and ".." not in route.split("/"), "invalid page route")
    url = site + route.strip("/") + ("/" if route.strip("/") else "")
    body = live_html(url)
    html = body.decode("utf-8")
    results = {check: check in html for check in checks}
    require(all(results.values()), "expected strings missing from live HTML")
    require(active_deployment(repository) == deployed, "Pages deployment changed during smoke; retry against a stable deployment")
    return {
        "page": page, "page_digest": digest(raw),
        "publication": {"http": {
            "url": url, "status": 200, "retrieved_at": datetime.now(UTC).isoformat(),
            "html_sha256": hashlib.sha256(body).hexdigest(), "checks": results,
            "deployment": deployed["run"],
        }},
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", type=Path, default=ROOT)
    parser.add_argument("--repository", default="kube-dojo/kube-dojo.github.io")
    parser.add_argument("--page", required=True, help="Committed src/content/docs page; route comes from slug or file path")
    parser.add_argument("--expect", action="append", required=True, help="Exact string required in live HTML; repeat for each check")
    parser.add_argument("--output", type=Path, required=True, help="New named JSON under docs/content-upgrade/reviews/")
    args = parser.parse_args(argv)
    try:
        root = args.repo_root.resolve()
        output = review_output(root, args.output)
        value = record(root, args.page, args.expect, args.repository)
        write_json(output, value)
        print(json.dumps(value["publication"]["http"]))
        return 0
    except (OSError, ValueError, KeyError, TypeError, AttributeError, subprocess.SubprocessError) as exc:
        parser.exit(1, f"refused: {exc}\n")


if __name__ == "__main__":
    raise SystemExit(main())
