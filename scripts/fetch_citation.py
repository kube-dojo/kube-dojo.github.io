#!/usr/bin/env python3
"""Deterministic citation-URL fetcher with text extraction + caching.

Used by the citation backfill pipeline's semantic gate: fetches the page
text once, caches it, and hands it to the verifier LLM so the LLM never
touches the network (per session-5 consult, 2026-04-19).

Usage:
    python scripts/fetch_citation.py <url>                # JSON to stdout
    python scripts/fetch_citation.py --refresh <url>      # bypass cache
    python scripts/fetch_citation.py --allowlist <url>    # check allowlist only
    python scripts/fetch_citation.py --dry-run-seeds      # exercise all tiers

Output schema (JSON):
    {
      "url": "https://...",
      "final_url": "https://...",            # after redirects
      "status": 200,
      "content_type": "text/html; charset=utf-8",
      "allowlist_tier": "standards" | ... | null,
      "bytes": 123456,
      "truncated": false,                  # null on failed fetches
      "text_length": 45678,
      "text_sha256": "...",                 # exact cached UTF-8 bytes
      "text_bytes": 45678,
      "text_preview": "first ~400 chars",
      "cached_at": "2026-04-19T...",
      "fetch_attempt_completed_at": "2026-04-19T...",
      "from_cache": false,
      "issues": []
    }

The full extracted text is written to a sibling file
(`.pipeline/citation-fetch-cache/<sha>.txt`) so the verifier can load it
without blowing up stdout.
"""

from __future__ import annotations

import argparse
import datetime as _dt
import hashlib
import html.parser
import http.client
import json
import posixpath
import re
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any, ClassVar

try:
    import yaml
except ImportError as _exc:  # pragma: no cover
    raise RuntimeError(
        "PyYAML is required for the citation allowlist. Install with "
        "`uv sync --locked` and run pipeline scripts via "
        "`.venv/bin/python`. Silent fallback previously caused 100% of "
        "URLs to be rejected as off_allowlist — see session 8 handoff."
    ) from _exc


REPO_ROOT = Path(__file__).resolve().parents[1]
ALLOWLIST_PATH = REPO_ROOT / "docs" / "citation-trusted-domains.yaml"
CACHE_DIR = REPO_ROOT / ".pipeline" / "citation-fetch-cache"
DEFAULT_TIMEOUT = 20
DEFAULT_UA = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/127.0.0.0 Safari/537.36"
)
DEFAULT_ACCEPT = (
    "text/html,application/xhtml+xml,application/xml;q=0.9,"
    "application/pdf;q=0.8,*/*;q=0.5"
)
MAX_BYTES = 4 * 1024 * 1024  # 4 MiB ceiling; large PDFs skip text extraction

# ---- HTML → text ---------------------------------------------------------


class _TextExtractor(html.parser.HTMLParser):
    """Strip script/style, collapse whitespace, emit readable plain text."""

    _SKIP_TAGS: ClassVar[set[str]] = {"script", "style", "noscript", "template", "svg", "iframe"}

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self._out: list[str] = []
        self._skip_depth = 0

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        del attrs
        if tag in self._SKIP_TAGS:
            self._skip_depth += 1
        elif tag in {"br", "p", "div", "li", "tr", "h1", "h2", "h3", "h4", "h5", "h6"}:
            self._out.append("\n")

    def handle_endtag(self, tag: str) -> None:
        if tag in self._SKIP_TAGS and self._skip_depth > 0:
            self._skip_depth -= 1

    def handle_data(self, data: str) -> None:
        if self._skip_depth == 0:
            self._out.append(data)

    def text(self) -> str:
        raw = "".join(self._out)
        # collapse runs of whitespace, keep paragraph breaks
        raw = re.sub(r"[ \t\r\f\v]+", " ", raw)
        raw = re.sub(r"\n{3,}", "\n\n", raw)
        return raw.strip()


def _html_to_text(body: str) -> str:
    parser = _TextExtractor()
    try:
        parser.feed(body)
        parser.close()
    except Exception:  # noqa: BLE001 - malformed HTML shouldn't kill us
        return parser.text()
    return parser.text()


# ---- allowlist -----------------------------------------------------------


_ALLOWLIST_CACHE: dict[str, Any] | None = None
_HOST_ENTRY_RE = re.compile(
    r"^[a-z0-9](?:[a-z0-9-]*[a-z0-9])?(?:\.[a-z0-9](?:[a-z0-9-]*[a-z0-9])?)+$"
)


class _UniqueKeySafeLoader(yaml.SafeLoader):
    """Safe YAML loader that rejects duplicate mapping keys fail-closed."""


def _construct_unique_mapping(
    loader: _UniqueKeySafeLoader,
    node: yaml.MappingNode,
    deep: bool = False,
) -> dict[Any, Any]:
    mapping: dict[Any, Any] = {}
    for key_node, value_node in node.value:
        key = loader.construct_object(key_node, deep=deep)
        if key in mapping:
            raise ValueError(f"Duplicate YAML key in citation allowlist: {key!r}")
        mapping[key] = loader.construct_object(value_node, deep=deep)
    return mapping


_UniqueKeySafeLoader.add_constructor(
    yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG,
    _construct_unique_mapping,
)


def _normalize_url_host(raw_host: str) -> str | None:
    """Normalize a parsed URL hostname without trimming whitespace (fail-closed)."""
    if not raw_host or any(ch.isspace() for ch in raw_host):
        return None
    host = raw_host.lower().removeprefix("www.")
    return host or None


def _validate_config_host(raw_host: str, *, kind: str) -> str:
    if not isinstance(raw_host, str) or raw_host != raw_host.strip():
        raise ValueError(f"Invalid {kind} entry: {raw_host!r}")
    lowered = raw_host.lower()
    if not _HOST_ENTRY_RE.fullmatch(lowered):
        raise ValueError(f"Invalid {kind} entry: {raw_host!r}")
    norm = lowered.removeprefix("www.")
    if not _HOST_ENTRY_RE.fullmatch(norm):
        raise ValueError(f"Invalid {kind} entry: {raw_host!r}")
    return norm


def _host_matches(host: str, domain: str) -> bool:
    return host == domain or host.endswith("." + domain)


def _normalize_path(raw_path: str) -> str:
    """Decode percent-encoding, normalize slashes and dot-segments, lowercase."""
    decoded = urllib.parse.unquote(raw_path or "/").replace("\\", "/")
    # Collapse repeated slashes before normpath so POSIX's leading '//' rule cannot bypass prefix checks.
    collapsed = re.sub(r"/+", "/", decoded)
    if not collapsed.startswith("/"):
        collapsed = "/" + collapsed
    return posixpath.normpath(collapsed).lower()


def _parse_excluded(allow: dict[str, Any]) -> tuple[tuple[str, ...], tuple[tuple[str, str], ...]]:
    """Validate and normalize the optional ``excluded`` allowlist section fail-closed."""
    if "excluded" not in allow:
        return (), ()
    raw_excluded = allow["excluded"]
    if not isinstance(raw_excluded, dict):
        raise TypeError("Citation allowlist `excluded` section must be a mapping")
    unknown_keys = set(raw_excluded) - {"hosts", "path_prefixes"}
    if unknown_keys:
        raise ValueError(
            f"Citation allowlist `excluded` has unsupported keys: {sorted(unknown_keys)}"
        )

    hosts: list[str] = []
    if "hosts" in raw_excluded:
        raw_hosts = raw_excluded["hosts"]
        if not isinstance(raw_hosts, list):
            raise TypeError("Citation allowlist `excluded.hosts` must be a list")
        hosts = [_validate_config_host(item, kind="excluded host") for item in raw_hosts]

    prefixes: list[tuple[str, str]] = []
    if "path_prefixes" in raw_excluded:
        raw_prefixes = raw_excluded["path_prefixes"]
        if not isinstance(raw_prefixes, list):
            raise TypeError("Citation allowlist `excluded.path_prefixes` must be a list")
        for item in raw_prefixes:
            if not isinstance(item, str) or item != item.strip() or "/" not in item:
                raise ValueError(f"Invalid excluded path_prefix entry: {item!r}")
            host_part, path_part = item.split("/", 1)
            norm_host = _validate_config_host(host_part, kind="excluded path_prefix")
            if (
                not path_part
                or path_part.startswith("/")
                or any(ch.isspace() or ord(ch) < 32 or ch in "?#:\\;%" for ch in path_part)
                or any(seg in {".", ".."} for seg in path_part.split("/"))
            ):
                raise ValueError(f"Invalid excluded path_prefix entry: {item!r}")
            norm_prefix = _normalize_path("/" + path_part)
            if norm_prefix == "/":
                raise ValueError(f"Invalid excluded path_prefix entry: {item!r}")
            prefixes.append((norm_host, norm_prefix))

    return tuple(hosts), tuple(prefixes)


def _is_excluded(host: str, norm_path: str, allow: dict[str, Any]) -> bool:
    excluded_hosts, excluded_prefixes = _parse_excluded(allow)
    if any(_host_matches(host, d) for d in excluded_hosts):
        return True
    for excl_host, excl_prefix in excluded_prefixes:
        if _host_matches(host, excl_host) and (
            norm_path == excl_prefix
            or norm_path.startswith((excl_prefix + "/", excl_prefix + ";"))
        ):
            return True
    return False


def _load_allowlist() -> dict[str, Any]:
    global _ALLOWLIST_CACHE
    if _ALLOWLIST_CACHE is not None:
        return _ALLOWLIST_CACHE
    if not ALLOWLIST_PATH.exists():
        raise FileNotFoundError(
            f"Citation allowlist not found at {ALLOWLIST_PATH}. The pipeline "
            "will reject every URL as off_allowlist without it."
        )
    loaded = yaml.load(
        ALLOWLIST_PATH.read_text(encoding="utf-8"),
        Loader=_UniqueKeySafeLoader,
    )
    if not isinstance(loaded, dict):
        raise TypeError("Citation allowlist root must be a YAML mapping")
    _parse_excluded(loaded)
    _ALLOWLIST_CACHE = loaded
    return _ALLOWLIST_CACHE


def allowlist_tier(url: str) -> str | None:
    """Return the first tier whose domains match the URL's host unless excluded, else None."""
    try:
        parsed = urllib.parse.urlsplit(url)
        raw_host = parsed.hostname or ""
    except ValueError:
        return None
    host = _normalize_url_host(raw_host)
    if host is None:
        return None
    norm_path = _normalize_path(parsed.path)
    allow = _load_allowlist()
    if _is_excluded(host, norm_path, allow):
        return None
    for tier, domains in (allow.get("tiers") or {}).items():
        if not isinstance(domains, list):
            continue
        for dom in domains:
            d = str(dom).strip().lower()
            if d and _host_matches(host, d):
                return str(tier)
    return None


# ---- cache ---------------------------------------------------------------


def _cache_paths(url: str) -> tuple[Path, Path]:
    sha = hashlib.sha1(url.encode("utf-8")).hexdigest()
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    return CACHE_DIR / f"{sha}.json", CACHE_DIR / f"{sha}.txt"


def _load_cached(url: str) -> dict[str, Any] | None:
    meta_path, _ = _cache_paths(url)
    if not meta_path.exists():
        return None
    try:
        data = json.loads(meta_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    data["from_cache"] = True
    return data


def _store_cache(url: str, meta: dict[str, Any], text_bytes: bytes) -> None:
    meta_path, text_path = _cache_paths(url)
    meta_path.write_text(
        json.dumps(meta, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    text_path.write_bytes(text_bytes)


def cached_text_path(url: str) -> Path:
    """Return the path where the extracted text is stored (exists or not)."""
    return _cache_paths(url)[1]


# ---- network -------------------------------------------------------------


def _fetch_once(url: str, timeout: int) -> tuple[dict[str, Any], bytes]:
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": DEFAULT_UA,
            "Accept": DEFAULT_ACCEPT,
            "Accept-Language": "en-US,en;q=0.9",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            body = resp.read(MAX_BYTES + 1)
            truncated = len(body) > MAX_BYTES
            meta = {
                "final_url": resp.geturl(),
                "status": int(resp.getcode()),
                "content_type": resp.headers.get("Content-Type", "").lower(),
                "bytes": len(body),
                "truncated": truncated,
            }
            return meta, body[:MAX_BYTES]
    except urllib.error.HTTPError as e:
        body = b""
        try:
            body = e.read(MAX_BYTES + 1)[:MAX_BYTES]
        except Exception:  # noqa: BLE001
            body = b""
        return {
            "final_url": getattr(e, "url", url) or url,
            "status": int(e.code),
            "content_type": (e.headers or {}).get("Content-Type", "").lower(),
            "bytes": len(body),
            "truncated": False,
            "error": f"http_error_{e.code}",
        }, body
    except (urllib.error.URLError, TimeoutError, http.client.InvalidURL,
            ValueError, OSError) as e:
        return {
            "final_url": url,
            "status": 0,
            "content_type": "",
            "bytes": 0,
            "truncated": False,
            "error": f"{type(e).__name__}: {e}",
        }, b""


def fetch(url: str, *, refresh: bool = False, timeout: int = DEFAULT_TIMEOUT) -> dict[str, Any]:
    """Fetch a URL with text extraction + caching. Returns the meta dict."""
    if not refresh:
        cached = _load_cached(url)
        if cached is not None:
            final_url = cached.get("final_url")
            cached["allowlist_tier"] = allowlist_tier(
                final_url if isinstance(final_url, str) and final_url else url
            )
            return cached

    meta, body = _fetch_once(url, timeout=timeout)
    fetch_attempt_completed_at = _dt.datetime.now(_dt.UTC).isoformat(timespec="seconds")
    issues: list[str] = []
    if meta.get("error"):
        issues.append(str(meta["error"]))
    status = int(meta.get("status", 0))
    if status == 0:
        issues.append("network_failure")
    elif status >= 400:
        issues.append(f"http_{status}")

    content_type = str(meta.get("content_type") or "")
    text = ""
    if body and status < 400:
        if "text/html" in content_type or "application/xhtml" in content_type:
            try:
                decoded = body.decode("utf-8", errors="replace")
            except Exception:  # noqa: BLE001
                decoded = ""
            text = _html_to_text(decoded)
        elif "text/" in content_type or "application/json" in content_type or \
             "application/xml" in content_type:
            text = body.decode("utf-8", errors="replace")
        elif "application/pdf" in content_type:
            issues.append("pdf_needs_adapter")
            text = ""
        else:
            issues.append(f"unsupported_content_type:{content_type or 'unknown'}")

    if meta.get("truncated"):
        issues.append("truncated_body")

    text_bytes = text.encode("utf-8")

    out = {
        "url": url,
        "final_url": meta.get("final_url", url),
        "status": status,
        "content_type": content_type,
        "allowlist_tier": allowlist_tier(meta.get("final_url", url) or url),
        "bytes": int(meta.get("bytes", 0)),
        "truncated": bool(meta.get("truncated", False)) if 0 < status < 400 else None,
        "text_length": len(text),
        "text_sha256": hashlib.sha256(text_bytes).hexdigest(),
        "text_bytes": len(text_bytes),
        "text_preview": text[:400],
        "cached_at": _dt.datetime.now(_dt.UTC).isoformat(timespec="seconds"),
        "fetch_attempt_completed_at": fetch_attempt_completed_at,
        "from_cache": False,
        "issues": issues,
    }
    _store_cache(url, out, text_bytes)
    return out


# ---- dry-run harness -----------------------------------------------------


_DRY_RUN_URLS: list[tuple[str, str | None]] = [
    # (url, expected_tier)
    ("https://kubernetes.io/docs/concepts/overview/", "standards"),
    ("https://www.nist.gov/itl/ai-risk-management-framework", "standards"),
    ("https://owasp.org/www-project-top-10-for-large-language-model-applications/", "standards"),
    ("https://www.mitre.org/news-insights", "standards"),
    ("https://arxiv.org/abs/1706.03762", "standards"),
    ("https://github.com/kubernetes/kubernetes", "upstream"),
    ("https://helm.sh/docs/", "upstream"),
    ("https://prometheus.io/docs/introduction/overview/", "upstream"),
    ("https://istio.io/latest/docs/", "upstream"),
    ("https://docs.aws.amazon.com/eks/latest/userguide/what-is-eks.html", "vendor"),
    ("https://cloud.google.com/kubernetes-engine/docs/concepts/kubernetes-engine-overview", "vendor"),
    ("https://learn.microsoft.com/en-us/azure/aks/intro-kubernetes", "vendor"),
    ("https://docs.docker.com/get-started/overview/", "vendor"),
    ("https://www.anthropic.com/news", "vendor"),
    # Multi-tier domains (nvd.nist.gov also under standards;
    # status.cloud.google.com under vendor): first-match wins, both allowed.
    ("https://nvd.nist.gov/vuln/detail/CVE-2023-5528", "standards"),
    ("https://www.cisa.gov/news-events/cybersecurity-advisories", "incidents"),
    ("https://status.cloud.google.com/", "vendor"),
    ("https://developer.mozilla.org/en-US/docs/Web/HTTP", "general"),
    ("https://en.wikipedia.org/wiki/Kubernetes", "general"),
    # Official pages on #3916 hosts that also have user-content exclusions.
    ("https://nginx.org/en/docs/http/load_balancing.html", "upstream"),
    ("https://blog.nginx.org/blog/celebrating-20-years-of-nginx", "upstream"),
    ("https://curl.se/docs/manpage.html", "upstream"),
    ("https://developer.apple.com/documentation/kernel/1387446-sysctlbyname/determining_system_capabilities", "vendor"),
    # Project-hosted user content on allowlisted domains — MUST report allowlist_tier=null.
    ("https://forum.nginx.org/read.php?2,250000", None),
    ("https://community.nginx.org/t/example/123", None),
    ("https://trac.nginx.org/nginx/ticket/1234", None),
    ("https://mailman.nginx.org/pipermail/nginx/", None),
    ("https://forums.developer.apple.com/forums/thread/12345", None),
    ("https://developer.apple.com/forums/thread/12345", None),
    ("https://curl.se/mail/lib-2017-02/0075.html", None),
    # Intentionally off-allowlist — MUST report allowlist_tier=null.
    ("https://medium.com/example", None),
]


def run_dry_run(refresh: bool = False) -> int:
    print(f"{'URL':<70}  {'TIER':<10}  {'EXPECT':<10}  STATUS  LEN     ISSUES")
    print("-" * 140)
    bad = 0
    for url, expected in _DRY_RUN_URLS:
        try:
            result = fetch(url, refresh=refresh)
        except Exception as exc:  # noqa: BLE001
            print(f"{url[:68]:<70}  FAIL        {expected or '-':<10}  -       -       {type(exc).__name__}: {exc}")
            bad += 1
            continue
        tier = result.get("allowlist_tier") or "-"
        issues = ",".join(result.get("issues") or []) or "-"
        status = result.get("status", 0)
        textlen = result.get("text_length", 0)
        # When expected tier is None, the URL is deliberately off-allowlist;
        # the correct outcome is tier=None AND fetch failure/block. We only
        # care that the allowlist rejected it; the status is incidental.
        is_off_allowlist_case = expected is None
        tier_ok = (result.get("allowlist_tier") == expected) or \
                  (is_off_allowlist_case and result.get("allowlist_tier") is None)
        fetch_ok = bool(status) and status < 400
        # Off-allowlist case passes on rejection alone; on-allowlist needs both.
        passed = tier_ok if is_off_allowlist_case else (tier_ok and fetch_ok)
        marker = " " if passed else "!"
        if not passed:
            bad += 1
        print(f"{marker} {url[:68]:<68}  {tier:<10}  {expected or '-'!s:<10}  {status:<6}  {textlen:<6}  {issues}")
    print("-" * 140)
    print(f"failed: {bad}/{len(_DRY_RUN_URLS)}")
    return 0 if bad == 0 else 1


# ---- main ----------------------------------------------------------------


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Citation URL fetcher")
    parser.add_argument("url", nargs="?", help="URL to fetch")
    parser.add_argument("--refresh", action="store_true", help="Bypass cache")
    parser.add_argument("--allowlist", action="store_true", help="Only print the allowlist tier for URL")
    parser.add_argument("--dry-run-seeds", action="store_true", help="Fetch known seed URLs and report")
    parser.add_argument("--timeout", type=int, default=DEFAULT_TIMEOUT)
    args = parser.parse_args(argv)

    if args.dry_run_seeds:
        return run_dry_run(refresh=args.refresh)
    if not args.url:
        parser.error("url or --dry-run-seeds required")
    if args.allowlist:
        tier = allowlist_tier(args.url)
        print(json.dumps({"url": args.url, "allowlist_tier": tier}, indent=2))
        return 0 if tier else 2

    result = fetch(args.url, refresh=args.refresh, timeout=args.timeout)
    print(json.dumps(result, indent=2, ensure_ascii=False))
    issues = result.get("issues") or []
    status = result.get("status", 0)
    if not status or status >= 400 or any(i != "pdf_needs_adapter" for i in issues):
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
