#!/usr/bin/env python3
"""Headless Kimi Code oneshot via Agent Client Protocol (ACP).

``kimi -p`` is text-only (no file tools). Interactive ``kimi --yolo`` needs a
TTY. ACP (``kimi acp``) is the supported headless path: the agent requests
``fs/read_text_file`` / ``fs/write_text_file`` and the client performs them.

Usage:
  .venv/bin/python scripts/agent_runtime/kimi_acp_oneshot.py \\
      --cwd /path/to/worktree --model kimi-code/k3-256k --prompt-file brief.md

Stdout: assistant text. Stderr: ACP diagnostics. Exit 0 on stopReason end_turn
(or equivalent) with a response; non-zero on hard failure.
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import threading
import time
from pathlib import Path


def _read_text(path: Path, line: int | None = None, limit: int | None = None) -> str:
    if not path.is_file():
        raise FileNotFoundError(str(path))
    text = path.read_text(encoding="utf-8", errors="replace")
    if line is None and limit is None:
        return text
    lines = text.splitlines(keepends=True)
    start = max((line or 1) - 1, 0)
    end = None if limit is None else start + max(limit, 0)
    return "".join(lines[start:end])


def _write_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def _pick_allow_option(options: list[dict]) -> str | None:
    """Prefer allow_always, then allow_once, else first optionId."""
    if not options:
        return None
    by_kind = {o.get("kind"): o.get("optionId") for o in options if o.get("optionId")}
    for kind in ("allow_always", "allow_once"):
        if by_kind.get(kind):
            return by_kind[kind]
    return options[0].get("optionId")


class KimiAcpClient:
    def __init__(
        self,
        *,
        cwd: Path,
        model: str,
        timeout_s: int,
        kimi_bin: str,
    ) -> None:
        self.cwd = cwd.resolve()
        self.model = model
        self.timeout_s = timeout_s
        self._req_id = 0
        self._results: dict[int, dict] = {}
        self._results_cv = threading.Condition()
        self._agent_text: list[str] = []
        self._stop_reason: str | None = None
        self._fatal: str | None = None
        self._proc = subprocess.Popen(
            [kimi_bin, "acp"],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            cwd=str(self.cwd),
            text=True,
            bufsize=1,
        )
        assert self._proc.stdin and self._proc.stdout
        self._reader = threading.Thread(target=self._read_loop, daemon=True)
        self._reader.start()

    def _send(self, method: str, params: dict | None = None, *, notif: bool = False) -> int | None:
        assert self._proc.stdin is not None
        msg: dict = {"jsonrpc": "2.0", "method": method}
        if params is not None:
            msg["params"] = params
        req_id = None
        if not notif:
            self._req_id += 1
            req_id = self._req_id
            msg["id"] = req_id
        line = json.dumps(msg, ensure_ascii=False)
        print(f"[kimi-acp] >> {method}", file=sys.stderr)
        self._proc.stdin.write(line + "\n")
        self._proc.stdin.flush()
        return req_id

    def _respond(self, req_id: int | str, result: dict | None = None, error: dict | None = None) -> None:
        assert self._proc.stdin is not None
        msg: dict = {"jsonrpc": "2.0", "id": req_id}
        if error is not None:
            msg["error"] = error
        else:
            msg["result"] = result if result is not None else {}
        self._proc.stdin.write(json.dumps(msg, ensure_ascii=False) + "\n")
        self._proc.stdin.flush()

    def _wait_result(self, req_id: int, label: str) -> dict:
        deadline = time.time() + min(30, self.timeout_s)
        with self._results_cv:
            while req_id not in self._results and time.time() < deadline:
                self._results_cv.wait(timeout=0.5)
            if req_id not in self._results:
                raise TimeoutError(f"timed out waiting for {label}")
            msg = self._results.pop(req_id)
        if "error" in msg:
            raise RuntimeError(f"{label} failed: {msg['error']}")
        return msg.get("result") or {}

    def _handle_agent_request(self, msg: dict) -> None:
        method = msg.get("method")
        req_id = msg["id"]
        params = msg.get("params") or {}
        try:
            if method == "fs/read_text_file":
                path = Path(params["path"])
                content = _read_text(
                    path,
                    line=params.get("line"),
                    limit=params.get("limit"),
                )
                self._respond(req_id, {"content": content})
            elif method == "fs/write_text_file":
                path = Path(params["path"])
                _write_text(path, params.get("content", ""))
                print(f"[kimi-acp] wrote {path}", file=sys.stderr)
                self._respond(req_id, {})
            elif method == "session/request_permission":
                option_id = _pick_allow_option(params.get("options") or [])
                if not option_id:
                    self._respond(
                        req_id,
                        {"outcome": {"outcome": "cancelled"}},
                    )
                else:
                    self._respond(
                        req_id,
                        {
                            "outcome": {
                                "outcome": "selected",
                                "optionId": option_id,
                            }
                        },
                    )
            else:
                print(f"[kimi-acp] unhandled agent request: {method}", file=sys.stderr)
                self._respond(
                    req_id,
                    error={"code": -32601, "message": f"unsupported: {method}"},
                )
        except Exception as exc:  # noqa: BLE001 — surface to agent as JSON-RPC error
            self._respond(
                req_id,
                error={"code": -32000, "message": f"{type(exc).__name__}: {exc}"},
            )

    def _handle_update(self, params: dict) -> None:
        update = params.get("update") or {}
        kind = update.get("sessionUpdate")
        if kind == "agent_message_chunk":
            content = update.get("content") or {}
            if content.get("type") == "text" and content.get("text"):
                self._agent_text.append(content["text"])
        elif kind == "agent_thought_chunk":
            # Keep quiet on thoughts; optional debug only.
            pass

    def _read_loop(self) -> None:
        assert self._proc.stdout is not None
        for raw in self._proc.stdout:
            line = raw.strip()
            if not line:
                continue
            try:
                msg = json.loads(line)
            except json.JSONDecodeError:
                print(f"[kimi-acp] non-json: {line[:200]}", file=sys.stderr)
                continue
            if "method" in msg and "id" in msg:
                self._handle_agent_request(msg)
            elif msg.get("method") == "session/update":
                self._handle_update(msg.get("params") or {})
            elif "id" in msg and ("result" in msg or "error" in msg):
                with self._results_cv:
                    self._results[msg["id"]] = msg
                    # Capture stopReason from session/prompt result
                    result = msg.get("result") or {}
                    if isinstance(result, dict) and "stopReason" in result:
                        self._stop_reason = result.get("stopReason")
                    self._results_cv.notify_all()
            else:
                print(f"[kimi-acp] ignored: {str(msg)[:200]}", file=sys.stderr)

    def run(self, prompt: str) -> str:
        init_id = self._send(
            "initialize",
            {
                "protocolVersion": 1,
                "clientCapabilities": {
                    "fs": {"readTextFile": True, "writeTextFile": True},
                    "terminal": False,
                },
                "clientInfo": {"name": "kubedojo-kimi-acp", "version": "0.1"},
            },
        )
        assert init_id is not None
        self._wait_result(init_id, "initialize")

        new_id = self._send(
            "session/new",
            {"cwd": str(self.cwd), "mcpServers": []},
        )
        assert new_id is not None
        session = self._wait_result(new_id, "session/new")
        session_id = session["sessionId"]

        # Prefer explicit model when the agent exposes set_config_option.
        if self.model:
            try:
                cfg_id = self._send(
                    "session/set_config_option",
                    {
                        "sessionId": session_id,
                        "configId": "model",
                        "value": self.model,
                    },
                )
                if cfg_id is not None:
                    self._wait_result(cfg_id, "session/set_config_option")
            except Exception as exc:  # noqa: BLE001 — model already defaulted
                print(f"[kimi-acp] set model skipped: {exc}", file=sys.stderr)

        prompt_id = self._send(
            "session/prompt",
            {
                "sessionId": session_id,
                "prompt": [{"type": "text", "text": prompt}],
            },
        )
        assert prompt_id is not None

        deadline = time.time() + self.timeout_s
        with self._results_cv:
            while prompt_id not in self._results and time.time() < deadline:
                self._results_cv.wait(timeout=0.5)
            if prompt_id not in self._results:
                self._fatal = f"session/prompt timed out after {self.timeout_s}s"
                raise TimeoutError(self._fatal)
            prompt_result = self._results.pop(prompt_id)

        if "error" in prompt_result:
            raise RuntimeError(f"session/prompt error: {prompt_result['error']}")
        stop = (prompt_result.get("result") or {}).get("stopReason")
        self._stop_reason = stop or self._stop_reason
        text = "".join(self._agent_text).strip()
        if not text and isinstance(prompt_result.get("result"), dict):
            # Some agents put final text only in the result payload.
            maybe = prompt_result["result"].get("message") or prompt_result["result"].get(
                "text"
            )
            if isinstance(maybe, str):
                text = maybe.strip()
        return text

    def close(self) -> None:
        if self._proc.poll() is None:
            self._proc.terminate()
            try:
                self._proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self._proc.kill()
        err = ""
        if self._proc.stderr is not None:
            try:
                err = self._proc.stderr.read() or ""
            except Exception:  # noqa: BLE001
                err = ""
        if err.strip():
            print(err[-4000:], file=sys.stderr)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cwd", type=Path, default=Path.cwd())
    parser.add_argument(
        "--model",
        default=os.environ.get("KUBEDOJO_KIMI_MODEL", "kimi-code/k3-256k"),
    )
    parser.add_argument("--timeout", type=int, default=1800)
    parser.add_argument("--prompt-file", type=Path, default=None)
    parser.add_argument(
        "--kimi-bin",
        default=os.environ.get("KUBEDOJO_KIMI_CMD") or "",
    )
    parser.add_argument("prompt", nargs="?", default=None)
    args = parser.parse_args()

    if args.prompt_file:
        prompt = args.prompt_file.read_text(encoding="utf-8")
    elif args.prompt is not None:
        prompt = args.prompt
    elif not sys.stdin.isatty():
        prompt = sys.stdin.read()
    else:
        parser.error("provide prompt via argv, --prompt-file, or stdin")

    kimi_bin = (
        args.kimi_bin
        or shutil_which("kimi")
        or str(Path.home() / ".local/bin/kimi")
    )
    if not Path(kimi_bin).exists() and kimi_bin == str(Path.home() / ".local/bin/kimi"):
        print("kimi binary not found on PATH or ~/.local/bin/kimi", file=sys.stderr)
        return 127

    client = KimiAcpClient(
        cwd=args.cwd,
        model=args.model,
        timeout_s=args.timeout,
        kimi_bin=kimi_bin,
    )
    try:
        text = client.run(prompt)
    except Exception as exc:  # noqa: BLE001
        print(f"[kimi-acp] FAIL: {exc}", file=sys.stderr)
        client.close()
        return 1
    client.close()
    if not text:
        print("[kimi-acp] empty assistant response", file=sys.stderr)
        return 2
    print(text)
    return 0


def shutil_which(name: str) -> str | None:
    import shutil

    return shutil.which(name)


if __name__ == "__main__":
    raise SystemExit(main())
