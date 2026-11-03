"""Build source receipts from recorded independent judgments, never infer verdicts.

Run with `.venv/bin/python -m scripts.quality.build_source_receipt --help`.
"""

from __future__ import annotations

import argparse
import base64
import binascii
import hashlib
import json
import os
import re
import subprocess
import tempfile
from datetime import UTC, datetime
from pathlib import Path
from urllib.parse import urlsplit

from scripts import fetch_citation
from scripts.quality.source_acceptance import SCHEMA, bind_page, evaluate_source_acceptance

ROOT = Path(__file__).resolve().parents[2]
REVIEW_DIR = Path("docs/content-upgrade/reviews")
VERIFIER_SCHEMA = "kubedojo.source_verdicts.v1"


def digest(data: bytes) -> str:
    return "sha256:" + hashlib.sha256(data).hexdigest()


def require(condition: bool, reason: str) -> None:
    if not condition:
        raise ValueError(reason)


def read_json(path: Path) -> dict:
    value = json.loads(path.read_bytes())
    require(isinstance(value, dict), "expected a JSON object")
    return value


def write_json(path: Path, value: dict) -> None:
    """Validate before calling; exclusive creation preserves prior attempt evidence."""
    data = (json.dumps(value, indent=2, ensure_ascii=False) + "\n").encode()
    with tempfile.NamedTemporaryFile(dir=path.parent, prefix=".source-record-", delete=False) as stream:
        temporary = Path(stream.name)
        try:
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
            os.link(temporary, path)
        finally:
            temporary.unlink()


def review_output(root: Path, path: Path) -> Path:
    path = path.resolve()
    require(path.parent == (root / REVIEW_DIR).resolve(), "output must be directly under docs/content-upgrade/reviews/")
    require(path.suffix == ".json", "output must be a named JSON file")
    return path


def git(root: Path, *args: str) -> bytes:
    return subprocess.run(
        ["git", "-C", str(root), *args], check=True, capture_output=True,
    ).stdout


def repo_path(value: str) -> str:
    path = Path(value)
    require(not path.is_absolute() and ".." not in path.parts and bool(path.parts), "expected a repository-relative path")
    return path.as_posix()


def committed_page(root: Path, page: str, revision: str = "HEAD") -> tuple[bytes, str]:
    page = repo_path(page)
    require(page.startswith("src/content/docs/") and Path(page).suffix in {".md", ".mdx"}, "expected a curriculum page")
    blob = git(root, "rev-parse", f"{revision}:{page}").decode().strip()
    raw = git(root, "cat-file", "blob", blob)
    require((root / page).read_bytes() == raw, "page digest is stale or page has uncommitted changes")
    return raw, blob


def family(value: str) -> str:
    value = value.strip().lower() if isinstance(value, str) else ""
    for name, aliases in {
        "openai": ("openai", "codex", "gpt"),
        "anthropic": ("anthropic", "claude"),
        "google": ("google", "gemini"),
        "xai": ("xai", "grok"),
        "meta": ("meta", "muse", "llama"),
        "deepseek": ("deepseek",),
    }.items():
        if value in aliases:
            return name
    raise ValueError("unknown model family; use a documented canonical family")


def identity(block: dict) -> dict:
    require(isinstance(block, dict), "identity must be an object")
    require(isinstance(block.get("identity"), str) and bool(block["identity"].strip()), "identity is missing")
    return {**block, "family": family(block.get("family"))}


def source_text(raw: bytes, content_type: str) -> str:
    text = raw.decode("utf-8", errors="strict")
    if "html" in content_type:
        return fetch_citation._html_to_text(text)
    require(content_type.startswith("text/") or any(t in content_type for t in ("json", "xml")), "source content type is unreadable")
    return text


def capture(url: str) -> dict:
    """Use the existing fetcher's byte reader and extractor; retain raw bytes too."""
    require(urlsplit(url).scheme == "https", "external sources require https")
    require(fetch_citation.allowlist_tier(url) is not None, "domain grant request required; allowlist unchanged")
    meta, raw = fetch_citation._fetch_once(url, timeout=fetch_citation.DEFAULT_TIMEOUT)
    require(meta.get("status") == 200 and not meta.get("truncated"), "source fetch failed or truncated")
    final = meta["final_url"]
    require(urlsplit(final).scheme == "https" and fetch_citation.allowlist_tier(final) is not None, "redirect domain grant request required")
    text = source_text(raw, meta["content_type"])
    require(bool(text.strip()), "source is unreadable")
    return {
        "retrieval_uri": url, "final_url": final,
        "retrieved_at": datetime.now(UTC).isoformat(),
        "snapshot_digest": digest(raw), "content_type": meta["content_type"],
        "body_base64": base64.b64encode(raw).decode(), "text": text,
        "capture_method": "scripts.fetch_citation._fetch_once",
    }


def validate_capture(source: dict) -> str:
    for key in ("retrieval_uri", "final_url"):
        url = source[key]
        require(urlsplit(url).scheme == "https" and fetch_citation.allowlist_tier(url) is not None, "domain grant request required")
    timestamp = datetime.fromisoformat(source["retrieved_at"].replace("Z", "+00:00"))
    require(timestamp.tzinfo is not None, "source capture date lacks timezone")
    require(source.get("capture_method") == "scripts.fetch_citation._fetch_once", "source must use the existing fetcher")
    raw = base64.b64decode(source["body_base64"], validate=True)
    require(digest(raw) == source["snapshot_digest"], "source snapshot digest is stale")
    text = source_text(raw, source["content_type"])
    require(bool(text.strip()) and text == source["text"], "captured source text differs from snapshot")
    return text


def seed(root: Path, page: str, proposals: dict) -> dict:
    raw, blob = committed_page(root, page)
    author = identity(proposals["author"])
    require(bool(author.get("evidence_ref")), "author identity needs a work-record evidence_ref")
    claims, sources = [], {}
    lines = raw.decode().splitlines()
    for proposal in proposals["claims"]:
        cid = proposal["claim_id"]
        require(isinstance(cid, str) and bool(cid.strip()) and cid == cid.strip(), "invalid claim id")
        start, end = proposal["line_start"], proposal["line_end"]
        require(type(start) is int and type(end) is int and 1 <= start <= end <= len(lines), "invalid claim span")
        quote = proposal["claim_text"]
        require(isinstance(quote, str) and bool(quote.strip()) and quote in "\n".join(lines[start - 1:end]), "claim text does not match its page span")
        require(proposal["kind"] in {"internal", "external"}, "claim kind must be internal or external")
        refs = []
        for candidate in proposal["candidate_sources"]:
            if proposal["kind"] == "internal":
                path = repo_path(candidate["path"])
                source_blob = git(root, "rev-parse", f"HEAD:{path}").decode().strip()
                source_raw = git(root, "cat-file", "blob", source_blob)
                source = {"retrieval_uri": f"git-object://{source_blob}", "snapshot_digest": digest(source_raw), "path": path}
            else:
                source = read_json(Path(candidate["capture"]))
                validate_capture(source)
            key = source["retrieval_uri"]
            require(key not in sources or sources[key] == source, "conflicting source snapshots")
            sources[key] = source
            refs.append(key)
        require(bool(refs), "claim has no candidate sources")
        claims.append({"claim_id": cid, "claim_text": quote, "line_start": start, "line_end": end, "kind": proposal["kind"], "candidate_source_refs": refs})
    ids = [c["claim_id"] for c in claims]
    require(bool(ids) and len(ids) == len(set(ids)), "empty or duplicate claim ids")
    return {
        "schema_version": 2, "module_path": page,
        "module_key": page.removeprefix("src/content/docs/").rsplit(".", 1)[0],
        "page_sha256": digest(raw).removeprefix("sha256:"),
        "page_commit": git(root, "rev-parse", "HEAD").decode().strip(), "page_blob": blob,
        "author": author, "claims": claims, "sources": sources,
        "notes": "Author proposals only; no source verdicts. Verifier must inspect the entire page for omitted material claims.",
    }


def packet(root: Path, seed_path: Path) -> dict:
    seed_raw = seed_path.read_bytes()
    data = json.loads(seed_raw)
    raw, blob = committed_page(root, data["module_path"])
    require(digest(raw) == "sha256:" + data["page_sha256"] and blob == data["page_blob"], "page digest is stale")
    claims = data["claims"]
    ids = [c["claim_id"] for c in claims]
    require(bool(ids) and len(set(ids)) == len(ids), "empty or duplicate claim ids")
    sources = {}
    for key, source in data["sources"].items():
        require(key == source["retrieval_uri"], "source reference mismatch")
        if key.startswith("git-object://"):
            sha = key.removeprefix("git-object://")
            require(re.fullmatch(r"[0-9a-f]{40,64}", sha) is not None, "invalid blob id")
            body = git(root, "cat-file", "blob", sha)
            require(digest(body) == source["snapshot_digest"], "source snapshot digest is stale")
            sources[key] = {**source, "text": body.decode()}
        else:
            validate_capture(source)
            sources[key] = {k: v for k, v in source.items() if k != "body_base64"}
    for claim in claims:
        start, end = claim["line_start"], claim["line_end"]
        lines = raw.decode().splitlines()
        require(type(start) is int and type(end) is int and 1 <= start <= end <= len(lines), "invalid claim span")
        require(bool(claim["claim_text"].strip()) and claim["claim_text"] in "\n".join(lines[start - 1:end]), "claim text does not match page span")
        require(claim["kind"] in {"internal", "external"}, "invalid claim kind")
        refs = claim["candidate_source_refs"]
        require(bool(refs) and all(ref in sources for ref in refs), "missing candidate source")
        require(all(ref.startswith("git-object://" if claim["kind"] == "internal" else "https://") for ref in refs), "source kind mismatch")
    return {
        "schema": "kubedojo.source_packet.v1", "page": data["module_path"],
        "page_digest": digest(raw), "seed_digest": digest(seed_raw),
        "author": identity(data["author"]), "page_text": raw.decode(),
        "claims": claims, "sources": sources,
        "instructions": "Inspect full page for omitted material claims. Record every claim verdict with exact source, quote, locator and rationale. Set coverage_complete false for omissions. Never infer support from digest or matching text. Write kubedojo.source_verdicts.v1 JSON as documented in source-receipt-procedure.md.",
    }


def receipt(root: Path, seed_path: Path, packet_path: Path, verdicts: dict) -> dict:
    current = packet(root, seed_path)
    packet_raw = packet_path.read_bytes()
    require(json.loads(packet_raw) == current, "verifier packet is stale")
    require(verdicts.get("schema") == VERIFIER_SCHEMA, "invalid verifier-output schema")
    for field in ("page_digest", "seed_digest"):
        require(verdicts.get(field) == current[field], f"{field} is stale")
    require(verdicts.get("packet_digest") == digest(packet_raw), "packet digest is stale")
    verifier = identity(verdicts["verifier"])
    require(verifier["family"] != current["author"]["family"], "verifier family equals author family")
    require(verdicts.get("coverage_complete") is True, "verifier found omitted or unreviewed material claims")
    run = verdicts["run"]
    require(isinstance(run, dict) and run.get("status") == "complete" and isinstance(run.get("identity"), str) and bool(run["identity"].strip()), "verifier run incomplete")
    wanted = {c["claim_id"]: c for c in current["claims"]}
    judgments = verdicts["claims"]
    ids = [c["claim_id"] for c in judgments]
    require(len(ids) == len(set(ids)) and set(ids) == set(wanted), "missing, extra or duplicate claim id")
    for judgment in judgments:
        require(judgment.get("verdict") == "SUPPORTED", f"claim {judgment['claim_id']} is not SUPPORTED")
        require(isinstance(judgment.get("rationale"), str) and bool(judgment["rationale"].strip()), "verifier rationale missing")
        additional = judgment.get("additional_sources", [])
        require(isinstance(additional, list), "additional_sources must be an array")
        for supplied in [judgment["source"], *additional]:
            uri = supplied["retrieval_uri"]
            require(uri in wanted[judgment["claim_id"]]["candidate_source_refs"], "verifier selected an uncaptured source")
            captured = current["sources"][uri]
            require(supplied["snapshot_digest"] == captured["snapshot_digest"], "verifier source digest mismatch")
            require(isinstance(supplied.get("quote"), str) and bool(supplied["quote"].strip()) and supplied["quote"] in captured["text"], "verifier quote absent from source snapshot")
            require(isinstance(supplied.get("locator"), str) and bool(supplied["locator"].strip()), "verifier locator missing")
    result = {
        "schema": SCHEMA, "schema_version": 1, "disposition": "applicable",
        "page_digest": current["page_digest"], "seed_digest": current["seed_digest"],
        "coverage": {"material_claim_ids": list(wanted), "reviewed_claim_ids": ids, "uncovered_claim_ids": []},
        "claims": judgments, "author": current["author"], "verifier": verifier, "run": run,
    }
    evaluation = evaluate_source_acceptance(result, page_digest=current["page_digest"], seed_digest=current["seed_digest"], seed_claim_ids=list(wanted))
    require(evaluation["accepted"], ", ".join(evaluation["reasons"]))
    return result


def check(root: Path, seed_path: Path, candidate: dict) -> dict:
    """Overlay candidate in a temporary copy of live ledger bytes; never edit it."""
    data = read_json(seed_path)
    page = data["module_path"]
    raw, _ = committed_page(root, page)
    relative = page.removeprefix("src/content/docs/")
    ledger_raw = (root / "docs/content-upgrade/page-reviews.json").read_bytes()
    ledger = json.loads(ledger_raw)
    entries = ledger["pages"]
    rows = [entries[relative]] if isinstance(entries, dict) and relative in entries else [row for row in entries if isinstance(row, dict) and row.get("path") == relative]
    require(len(rows) == 1, "live ledger needs exactly one page row")
    rows[0]["source_acceptance"] = candidate
    with tempfile.TemporaryDirectory(prefix="kubedojo-source-check-") as tmp:
        overlay = Path(tmp)
        (overlay / REVIEW_DIR.parent).mkdir(parents=True)
        (overlay / "docs/citation-seeds").mkdir()
        (overlay / "docs/content-upgrade/page-reviews.json").write_text(json.dumps(ledger))
        name = Path(relative).with_suffix("").as_posix().replace("/", "-") + ".json"
        (overlay / "docs/citation-seeds" / name).write_bytes(seed_path.read_bytes())
        result = bind_page(overlay, relative, raw)
    result["live_ledger_digest"] = digest(ledger_raw)
    return result


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", type=Path, default=ROOT)
    commands = parser.add_subparsers(dest="command", required=True)
    cap = commands.add_parser("capture", help="Capture an allowlisted https source with the existing fetcher")
    cap.add_argument("url")
    cap.add_argument("--output", required=True, type=Path)
    make_seed = commands.add_parser("seed", help="Bind author claim proposals and candidate snapshots to committed page bytes")
    make_seed.add_argument("--page", required=True)
    make_seed.add_argument("--claims", type=Path, required=True)
    make_seed.add_argument("--output", type=Path, required=True)
    for name, help_text in (("packet", "Emit full page, claim spans and captured source text for independent review"), ("receipt", "Ingest independent verifier JSON; refuse any incomplete, negative or stale result"), ("check", "Run bind_page on a candidate over live ledger bytes without changing the ledger")):
        sub = commands.add_parser(name, help=help_text)
        sub.add_argument("--seed", type=Path, required=True)
        if name == "receipt":
            sub.add_argument("--packet", type=Path, required=True)
            sub.add_argument("--verdicts", type=Path, required=True)
        if name == "check":
            sub.add_argument("--receipt", type=Path, required=True)
        else:
            sub.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        root = args.repo_root.resolve()
        if args.command == "check":
            result = check(root, args.seed, read_json(args.receipt))
            print(json.dumps(result))
            return 0 if result["accepted"] else 1
        if args.command == "capture":
            result = capture(args.url)
        elif args.command == "seed":
            result = seed(root, args.page, read_json(args.claims))
        elif args.command == "packet":
            result = packet(root, args.seed)
        else:
            review_output(root, args.output)
            result = receipt(root, args.seed, args.packet, read_json(args.verdicts))
        write_json(args.output, result)
        print(json.dumps({"command": args.command, "claims": len(result.get("claims", [])), "sources": len(result.get("sources", {})), "output": args.output.as_posix()}))
        return 0
    except (OSError, ValueError, KeyError, TypeError, AttributeError, binascii.Error, subprocess.SubprocessError) as exc:
        parser.exit(1, f"refused: {exc}\n")


if __name__ == "__main__":
    raise SystemExit(main())
