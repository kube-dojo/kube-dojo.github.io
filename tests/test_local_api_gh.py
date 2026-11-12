from __future__ import annotations

import http.client
import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path
from threading import Thread
from unittest.mock import patch


def _load_module():
    module_path = Path(__file__).resolve().parent.parent / "scripts" / "local_api.py"
    spec = importlib.util.spec_from_file_location("local_api", module_path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


local_api = _load_module()


def _completed(stdout: str) -> object:
    return local_api.subprocess.CompletedProcess(args=["gh"], returncode=0, stdout=stdout, stderr="")


class LocalApiGitHubTests(unittest.TestCase):
    def setUp(self) -> None:
        with local_api._CACHE_LOCK:
            local_api._CACHE.clear()

    def test_issue_list_normalizes_items_and_supports_304(self) -> None:
        payload = json.dumps(
            [
                {
                    "number": 276,
                    "title": "First",
                    "state": "OPEN",
                    "labels": [{"name": "api"}],
                    "assignees": [{"login": "alice"}],
                    "comments": [{"body": "one"}],
                    "updatedAt": "2026-04-18T08:09:11Z",
                    "url": "https://example.test/issues/276",
                },
                {
                    "number": 279,
                    "title": "Second",
                    "state": "OPEN",
                    "labels": [],
                    "assignees": [],
                    "comments": [],
                    "updatedAt": "2026-04-18T09:09:11Z",
                    "url": "https://example.test/issues/279",
                },
            ]
        )
        with tempfile.TemporaryDirectory() as tmpdir, patch.object(
            local_api.subprocess, "run", return_value=_completed(payload)
        ) as mock_run:
            repo_root = Path(tmpdir)
            handler_cls = local_api.make_handler(repo_root)
            server = local_api.ThreadingHTTPServer(("127.0.0.1", 0), handler_cls)
            thread = Thread(target=server.serve_forever, daemon=True)
            thread.start()
            try:
                conn = http.client.HTTPConnection("127.0.0.1", server.server_address[1], timeout=5)
                conn.request("GET", "/api/gh/issues?state=open&limit=2")
                resp = conn.getresponse()
                body = resp.read().decode("utf-8")
                etag = resp.getheader("ETag")
                self.assertEqual(resp.status, 200)
                data = json.loads(body)
                self.assertEqual(data["count"], 2)
                self.assertEqual(data["items"][0]["labels"], ["api"])
                self.assertEqual(data["items"][0]["assignees"], ["alice"])
                self.assertEqual(data["items"][0]["comments_count"], 1)
                self.assertEqual(etag, local_api._gh_payload_etag("/api/gh/issues", data))

                conn.request("GET", "/api/gh/issues?state=open&limit=2", headers={"If-None-Match": etag})
                resp2 = conn.getresponse()
                self.assertEqual(resp2.status, 304)
                self.assertEqual(resp2.read(), b"")
                self.assertEqual(mock_run.call_count, 1)
            finally:
                server.shutdown()
                server.server_close()

    def test_issue_detail_returns_last_five_comments(self) -> None:
        comments = [
            {
                "author": {"login": f"user{i}"},
                "body": f"comment {i}",
                "createdAt": f"2026-04-18T0{i}:00:00Z",
                "url": f"https://example.test/c/{i}",
            }
            for i in range(6)
        ]
        payload = json.dumps(
            {
                "number": 276,
                "title": "Issue detail",
                "state": "OPEN",
                "labels": [{"name": "infra"}],
                "assignees": [{"login": "owner"}],
                "comments": comments,
                "updatedAt": "2026-04-18T10:00:00Z",
                "url": "https://example.test/issues/276",
            }
        )
        with tempfile.TemporaryDirectory() as tmpdir, patch.object(
            local_api.subprocess, "run", return_value=_completed(payload)
        ):
            status_code, data, _ = local_api.route_request(Path(tmpdir), "/api/gh/issues/276")
        self.assertEqual(status_code, 200)
        self.assertEqual(data["comments_count"], 6)
        self.assertEqual(len(data["comments"]), 5)
        self.assertEqual(data["comments"][0]["author"], "user1")
        self.assertEqual(data["comments"][-1]["author"], "user5")

    def test_gh_unavailable_returns_503(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir, patch.object(
            local_api.subprocess, "run", side_effect=FileNotFoundError("gh")
        ):
            status_code, data, _ = local_api.route_request(Path(tmpdir), "/api/gh/issues")
        self.assertEqual(status_code, 503)
        self.assertEqual(data, {"error": "gh CLI not available"})

    def test_schema_lists_gh_endpoints(self) -> None:
        paths = {entry["path"] for entry in local_api.build_api_schema()["endpoints"]}
        self.assertIn("/api/gh/issues", paths)
        self.assertIn("/api/gh/issues/{n}", paths)
        self.assertNotIn("/api/gh/prs", paths)
        self.assertNotIn("/api/gh/prs/{n}", paths)


if __name__ == "__main__":
    unittest.main()
