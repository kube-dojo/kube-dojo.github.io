#!/usr/bin/env python3
"""Deterministic #388 curriculum module verifier."""
from __future__ import annotations

import argparse
import concurrent.futures
import glob as globlib
import json
import re
import shlex
import statistics
import sys
from collections import Counter
from collections.abc import Iterable
from itertools import pairwise
from pathlib import Path

_HERE = str(Path(__file__).resolve().parent)
sys.path = [p for p in sys.path if p not in ("", _HERE)]

REPO_ROOT = Path(__file__).resolve().parents[2]

WORD_RE = re.compile(r"(?=\S*[A-Za-z0-9])\S+")
HEADING_RE = re.compile(r"^(#{1,6})\s+(.+?)\s*$", re.MULTILINE)
MD_LINK_RE = re.compile(r"\[[^\]]*\]\((https?://[^)\s]+)\)")
BARE_URL_RE = re.compile(r"(?<![(\[])\bhttps?://[^\s)<>\]]+")
LIST_RE = re.compile(r"^\s*(?:[-*+]\s+|\d+[.)]\s+)")
TABLE_SEPARATOR_RE = re.compile(r"^\s*\|?\s*:?-{3,}:?\s*(?:\|\s*:?-{3,}:?\s*)+\|?\s*$")
FORBIDDEN_TOKENS = [
    "TBD",
    "TODO",
    "FIXME",
    "XXX",
    "lorem ipsum",
    "as an AI",
    "I cannot",
    "I'm sorry",
    "as a large language model",
    "###  ",
    "[INSERT",
    "[REPLACE",
    "<placeholder>",
]
STOPWORDS = {
    "a",
    "an",
    "and",
    "are",
    "as",
    "be",
    "by",
    "for",
    "from",
    "how",
    "in",
    "into",
    "of",
    "on",
    "or",
    "the",
    "to",
    "with",
    "using",
    "use",
    "module",
    "learn",
    "explain",
    "describe",
    "identify",
    "implement",
    "configure",
    "debug",
    "troubleshoot",
    "compare",
}
RUNNABLE_SHELL_LANGS = {"bash", "sh", "shell", "zsh"}
KUBECTL_ALIAS_RE = re.compile(r"(?m)^\s*alias\s+k\s*=\s*['\"]?kubectl['\"]?\s*$")
KUBECTL_SHORTHAND_RE = re.compile(
    r"(?m)(?:^|[;&|]\s*)k\s+(get|describe|logs|apply|delete|set|edit|diff|version|exec|"
    r"port-forward|cp|create|patch|scale|rollout|expose|run|label|annotate|drain|cordon|"
    r"uncordon|taint|top|wait|api-resources|config|auth)\b"
)
UNSOURCED_ANECDOTE_RE = re.compile(
    r"\bwar story\s*:"
    r"|\b(?:one|a) (?:team|customer|client|company|organization) (?:I|we) "
    r"(?:worked with|consulted for|helped|saw)\b"
    r"|\b(?:a|an) (?:payments|retail|fintech|trading|insurance|telecom|saas|gaming|"
    r"marketplace|e-commerce|healthcare) (?:company|platform|team|firm|startup|enterprise) "
    r"(?:once|recently)\b",
    re.IGNORECASE,
)
SCENARIO_PREFIX_RE = re.compile(r"^(?:[*_#\s]*)(?:Hypothetical scenario|Exercise scenario):", re.IGNORECASE)
MCQ_OPTION_RE = re.compile(r"(?m)^(?:[-*]\s*)?(?:\*\*)?(?:[A-D]|[1-4])[\).:](?:\*\*)?\s+\S")
MCQ_REASONING_KEYWORD_RE = re.compile(r"\b(?:wrong|not correct|incorrect|because|why)\b", re.IGNORECASE)

# Sources: Docker Official image Dockerfiles, Debian/Ubuntu coreutils + util-linux
# packages, Alpine/BusyBox applets, curlimages/curl Dockerfile, and nicolaka/netshoot
# Dockerfile package list.
DEBIAN_COREUTILS_UTIL_LINUX_BINARIES = {
    "[",
    "base64",
    "basename",
    "chmod",
    "chown",
    "cmp",
    "cp",
    "cut",
    "date",
    "dd",
    "df",
    "diff",
    "dirname",
    "du",
    "false",
    "file",
    "gunzip",
    "gzip",
    "hostname",
    "id",
    "less",
    "ln",
    "md5sum",
    "mkdir",
    "mktemp",
    "more",
    "mount",
    "mv",
    "paste",
    "readlink",
    "rm",
    "rmdir",
    "sha1sum",
    "sha256sum",
    "sleep",
    "sort",
    "stat",
    "tar",
    "tee",
    "test",
    "touch",
    "tr",
    "true",
    "type",
    "umount",
    "uname",
    "uniq",
    "wc",
    "which",
    "whoami",
    "xargs",
}
DEBIAN_EXTENDED_UTIL_LINUX_BINARIES = {
    "blkid",
    "dmesg",
    "free",
    "getconf",
    "getent",
    "getopt",
    "groups",
    "hexdump",
    "ipcrm",
    "ipcs",
    "kill",
    "killall",
    "ldd",
    "less",
    "locale",
    "lsof",
    "lsblk",
    "more",
    "nice",
    "od",
    "pgrep",
    "pkill",
    "sleep",
    "strings",
    "sync",
    "uname",
    "users",
    "w",
    "who",
    "whoami",
}
BUSYBOX_EXTENDED_APPLET_BINARIES = {
    "blkid",
    "dmesg",
    "free",
    "getopt",
    "groups",
    "hexdump",
    "ipcs",
    "kill",
    "killall",
    "ldd",
    "less",
    "lsblk",
    "more",
    "nice",
    "od",
    "pgrep",
    "pkill",
    "strings",
    "sync",
    "uname",
    "users",
    "w",
    "who",
    "whoami",
}
BUSYBOX_COREUTILS_NETWORK_BINARIES = DEBIAN_COREUTILS_UTIL_LINUX_BINARIES | {
    "hexdump",
    "ifconfig",
    "ip",
    "netstat",
    "nslookup",
    "od",
    "route",
    "telnet",
    "traceroute",
}
CURLIMAGES_CURL_BUSYBOX_SUBSET = {
    "ash",
    "cat",
    "cp",
    "curl",
    "echo",
    "env",
    "find",
    "grep",
    "head",
    "ls",
    "mkdir",
    "mv",
    "rm",
    "sh",
    "sleep",
    "tail",
    "touch",
}
NETSHOOT_EXTRA_BINARIES = {
    "ab",
    "arping",
    "bpftool",
    "conntrack",
    "dog",
    "drill",
    "ebpf-exporter",
    "fortio",
    "fping",
    "helm",
    "iperf3",
    "jq",
    "kubectl",
    "mtr",
    "ngrep",
    "openssl",
    "scp",
    "socat",
    "ssh",
    "tshark",
}

# Image-binary allowlist for the lab-runnability preflight. Entries are intentionally
# conservative: known images use strict membership; unknown images are informational.
IMAGE_BINARY_ALLOWLIST: dict[str, set[str]] = {
    # Docker Official nginx Debian-family images; audit #1257 requires no wget/curl for plain nginx tags.
    "nginx": {
        "sh",
        "dash",
        "ls",
        "cat",
        "head",
        "tail",
        "grep",
        "find",
        "ps",
        "nginx",
        "sed",
        "awk",
        "echo",
        "env",
    }
    | DEBIAN_COREUTILS_UTIL_LINUX_BINARIES
    | DEBIAN_EXTENDED_UTIL_LINUX_BINARIES,
    "nginx:stable": {
        "sh",
        "dash",
        "ls",
        "cat",
        "head",
        "tail",
        "grep",
        "find",
        "ps",
        "nginx",
        "sed",
        "awk",
        "echo",
        "env",
    }
    | DEBIAN_COREUTILS_UTIL_LINUX_BINARIES
    | DEBIAN_EXTENDED_UTIL_LINUX_BINARIES,
    "nginx:1.27": {
        "sh",
        "dash",
        "ls",
        "cat",
        "head",
        "tail",
        "grep",
        "find",
        "ps",
        "nginx",
        "sed",
        "awk",
        "echo",
        "env",
    }
    | DEBIAN_COREUTILS_UTIL_LINUX_BINARIES
    | DEBIAN_EXTENDED_UTIL_LINUX_BINARIES,
    # Docker Official nginx Alpine variants inherit Alpine/BusyBox applets, including wget.
    "nginx:alpine": {
        "sh",
        "ash",
        "wget",
        "ls",
        "cat",
        "head",
        "tail",
        "grep",
        "find",
        "ps",
        "nginx",
        "sed",
        "awk",
        "echo",
        "env",
        "nc",
        "ping",
        "vi",
    }
    | BUSYBOX_COREUTILS_NETWORK_BINARIES
    | BUSYBOX_EXTENDED_APPLET_BINARIES,
    "nginx:1.27-alpine": {
        "sh",
        "ash",
        "wget",
        "ls",
        "cat",
        "head",
        "tail",
        "grep",
        "find",
        "ps",
        "nginx",
        "sed",
        "awk",
        "echo",
        "env",
        "nc",
        "ping",
        "vi",
    }
    | BUSYBOX_COREUTILS_NETWORK_BINARIES
    | BUSYBOX_EXTENDED_APPLET_BINARIES,
    # Docker Official BusyBox image: BusyBox applet set, including ash and wget.
    "busybox": {
        "sh",
        "ash",
        "wget",
        "ls",
        "cat",
        "head",
        "tail",
        "grep",
        "find",
        "ps",
        "sed",
        "awk",
        "echo",
        "env",
        "nc",
        "ping",
        "vi",
        "id",
    }
    | BUSYBOX_COREUTILS_NETWORK_BINARIES
    | BUSYBOX_EXTENDED_APPLET_BINARIES,
    "busybox:1.36": {
        "sh",
        "ash",
        "wget",
        "ls",
        "cat",
        "head",
        "tail",
        "grep",
        "find",
        "ps",
        "sed",
        "awk",
        "echo",
        "env",
        "nc",
        "ping",
        "vi",
        "id",
    }
    | BUSYBOX_COREUTILS_NETWORK_BINARIES
    | BUSYBOX_EXTENDED_APPLET_BINARIES,
    # Docker Alpine Official Image uses BusyBox and apk.
    "alpine": {
        "sh",
        "ash",
        "apk",
        "wget",
        "ls",
        "cat",
        "head",
        "tail",
        "grep",
        "find",
        "ps",
        "sed",
        "awk",
        "echo",
        "env",
        "nc",
        "ping",
        "vi",
    }
    | BUSYBOX_COREUTILS_NETWORK_BINARIES
    | BUSYBOX_EXTENDED_APPLET_BINARIES,
    "alpine:3.20": {
        "sh",
        "ash",
        "apk",
        "wget",
        "ls",
        "cat",
        "head",
        "tail",
        "grep",
        "find",
        "ps",
        "sed",
        "awk",
        "echo",
        "env",
        "nc",
        "ping",
        "vi",
    }
    | BUSYBOX_COREUTILS_NETWORK_BINARIES
    | BUSYBOX_EXTENDED_APPLET_BINARIES,
    # curlimages/curl Docker Hub overview documents curl as the image entrypoint/tool.
    "curlimages/curl": CURLIMAGES_CURL_BUSYBOX_SUBSET,
    "curlimages/curl:latest": CURLIMAGES_CURL_BUSYBOX_SUBSET,
    # Docker Official Debian/Ubuntu slim bases: shell/coreutils only, no wget/curl in this seed.
    "debian:bookworm-slim": {
        "sh",
        "bash",
        "dash",
        "ls",
        "cat",
        "head",
        "tail",
        "grep",
        "find",
        "ps",
        "sed",
        "awk",
        "echo",
        "env",
        "apt",
        "apt-get",
        "dpkg",
    }
    | DEBIAN_COREUTILS_UTIL_LINUX_BINARIES
    | DEBIAN_EXTENDED_UTIL_LINUX_BINARIES,
    "ubuntu:24.04": {
        "sh",
        "bash",
        "dash",
        "ls",
        "cat",
        "head",
        "tail",
        "grep",
        "find",
        "ps",
        "sed",
        "awk",
        "echo",
        "env",
        "apt",
        "apt-get",
        "dpkg",
    }
    | DEBIAN_COREUTILS_UTIL_LINUX_BINARIES
    | DEBIAN_EXTENDED_UTIL_LINUX_BINARIES,
    # nicolaka/netshoot Dockerfile installs network-debug tools via apk.
    "nicolaka/netshoot": {
        "curl",
        "wget",
        "sh",
        "bash",
        "ls",
        "cat",
        "head",
        "tail",
        "grep",
        "find",
        "ps",
        "sed",
        "awk",
        "echo",
        "env",
        "nc",
        "ping",
        "dig",
        "tcpdump",
        "ip",
        "iptables",
        "ss",
        "host",
    }
    | BUSYBOX_COREUTILS_NETWORK_BINARIES
    | NETSHOOT_EXTRA_BINARIES,
    # Docker Official Python 3.12 slim Dockerfile builds Python on debian:bookworm-slim and adds pip symlinks.
    "python:3.12-slim": {
        "sh",
        "bash",
        "python3",
        "python",
        "pip",
        "ls",
        "cat",
        "head",
        "tail",
        "grep",
        "find",
        "ps",
        "sed",
        "awk",
        "echo",
        "env",
        "pip3",
    }
    | DEBIAN_COREUTILS_UTIL_LINUX_BINARIES
    | DEBIAN_EXTENDED_UTIL_LINUX_BINARIES,
}

LEARNING_OUTCOME_HEADINGS = (
    "Learning Outcomes",
    "Learning Objectives",
    "What You'll Be Able to Do",
    "What You'll Learn",
    "What You Will Learn",
)
DID_YOU_KNOW_HEADINGS = ("Did You Know", "Did You Know?")
COMMON_MISTAKES_PREFIX_HEADINGS = ("Common Mistakes",)
QUIZ_HEADINGS = ("Knowledge Check",)
QUIZ_PREFIX_HEADINGS = ("Quiz",)
HANDS_ON_HEADINGS = ("Lab", "Exercise", "Hands-On Practice", "Hands-On Practical Exercises")
HANDS_ON_PREFIX_HEADINGS = ("Hands-On",)
SOURCES_HEADINGS = ("Sources", "Further Reading", "References", "Resources")

try:
    import regex as _regex  # type: ignore

    EMOJI_RE = _regex.compile(r"\p{Emoji_Presentation}|\p{Extended_Pictographic}")
except ImportError:
    EMOJI_RE = re.compile(r"[\U0001f300-\U0001faff\u2600-\u27bf]")


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _module_budget_slug(module_path: str) -> str:
    module = Path(module_path)
    if not module.is_absolute():
        module = REPO_ROOT / module
    try:
        relative = module.relative_to(REPO_ROOT / "src" / "content" / "docs")
        rel = relative.as_posix()
    except ValueError:
        rel = module.as_posix()
        if rel.startswith(f"{REPO_ROOT.as_posix().removesuffix('/')}/"):
            rel = rel.removeprefix(f"{REPO_ROOT.as_posix().removesuffix('/')}/")
        if rel.startswith("src/content/docs/"):
            rel = rel.removeprefix("src/content/docs/")
    return rel.replace("/", "__")


def _body_words_floor_for_module(module_path: Path) -> int:
    sidecar_path = REPO_ROOT / ".pipeline" / "budgets" / f"{_module_budget_slug(str(module_path))}.json"
    try:
        sidecar = json.loads(sidecar_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return 5000
    body_words_min = sidecar.get("body_words_min") if isinstance(sidecar, dict) else None
    if isinstance(body_words_min, bool):
        return 5000
    try:
        return int(body_words_min)
    except (TypeError, ValueError):
        return 5000


def _strip_frontmatter(text: str) -> tuple[dict[str, object], str]:
    if not text.startswith("---"):
        return {}, text
    match = re.match(r"^---\s*\n(.*?)\n---\s*(?:\n|$)(.*)\Z", text, re.DOTALL)
    if not match:
        return {}, text
    frontmatter: dict[str, object] = {}
    for raw_line in match.group(1).splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or ":" not in line:
            continue
        key, value = line.split(":", 1)
        value = value.strip().strip("\"'")
        lowered = value.lower()
        if lowered == "true":
            parsed: object = True
        elif lowered == "false":
            parsed = False
        elif re.fullmatch(r"-?\d+", value):
            parsed = int(value)
        else:
            parsed = value
        frontmatter[key.strip()] = parsed
    return frontmatter, match.group(2)


def _strip_code_blocks(text: str, replacement: str = "") -> str:
    return re.sub(r"```.*?```", replacement, text, flags=re.DOTALL)


def _fenced_code_blocks(text: str) -> list[tuple[str, str]]:
    return [
        (match.group(1).strip(), match.group(2))
        for match in re.finditer(r"```([^\n]*)\n(.*?)```", text, re.DOTALL)
    ]


def _fence_language(info: str) -> str:
    return info.strip().split(maxsplit=1)[0].lower() if info.strip() else ""


def _word_count(text: str) -> int:
    return len(WORD_RE.findall(text))


def _line_has_diagram_chars(line: str) -> bool:
    stripped = line.strip()
    if not stripped:
        return False
    diagram_chars = sum(1 for char in stripped if char in "|+-─│┌└┐┘┬┴┼")
    return diagram_chars >= max(2, len(stripped) // 5)


def _ascii_diagram_line_indexes(lines: list[str]) -> set[int]:
    indexes: set[int] = set()
    start: int | None = None
    hits = 0
    total = 0
    for idx, line in enumerate(lines + [""]):
        if line.strip():
            if start is None:
                start = idx
                hits = 0
                total = 0
            total += 1
            if _line_has_diagram_chars(line):
                hits += 1
            continue
        if start is not None:
            if total >= 2 and hits / total > 0.5:
                indexes.update(range(start, idx))
            start = None
    return indexes


def extract_body_paragraphs(text: str) -> list[str]:
    """Return canonical body teaching paragraphs for density metrics."""
    _, body = _strip_frontmatter(text)
    lines = body.splitlines()
    ascii_indexes = _ascii_diagram_line_indexes(lines)
    kept: list[str] = []
    in_fence = False
    in_html: str | None = None
    in_sources = False
    in_list = False
    in_table = False
    seen_heading = False

    for idx, line in enumerate(lines):
        stripped = line.strip()
        lower = stripped.lower()

        if stripped.startswith("```"):
            in_fence = not in_fence
            kept.append("")
            continue
        if in_fence:
            kept.append("")
            continue

        heading = re.match(r"^(#{1,6})\s+(.+?)\s*$", stripped)
        if heading:
            seen_heading = True
        if heading and len(heading.group(1)) <= 2:
            in_sources = _heading_matches(heading.group(2), SOURCES_HEADINGS)
        if in_sources:
            kept.append("")
            continue

        if not seen_heading and stripped.startswith(">"):
            kept.append("")
            continue
        if in_html:
            if f"</{in_html}" in lower:
                in_html = None
            kept.append("")
            continue
        html_open = re.match(r"^<([a-zA-Z][\w:-]*)\b", stripped)
        if html_open:
            tag = html_open.group(1).lower()
            if not re.search(rf"</{re.escape(tag)}\s*>", lower):
                in_html = tag
            kept.append("")
            continue

        if not stripped:
            in_list = False
            in_table = False
            kept.append("")
            continue
        if re.fullmatch(r"-{3,}", stripped):
            kept.append("")
            continue

        if idx in ascii_indexes:
            kept.append("")
            continue
        if heading:
            kept.append("")
            continue

        next_line = lines[idx + 1] if idx + 1 < len(lines) else ""
        if TABLE_SEPARATOR_RE.match(stripped) or (
            "|" in stripped and TABLE_SEPARATOR_RE.match(next_line.strip())
        ):
            in_table = True
            kept.append("")
            continue
        if in_table and "|" in stripped:
            kept.append("")
            continue
        if in_table and "|" not in stripped:
            in_table = False

        if LIST_RE.match(line):
            in_list = True
            kept.append("")
            continue
        if in_list and (line.startswith((" ", "\t")) or not stripped):
            kept.append("")
            continue
        in_list = False

        kept.append(line)

    paragraphs: list[str] = []
    current: list[str] = []
    for line in kept:
        if line.strip():
            current.append(line.strip())
        elif current:
            paragraphs.append(" ".join(current))
            current = []
    if current:
        paragraphs.append(" ".join(current))
    return paragraphs


def _sentence_lengths(paragraphs: list[str]) -> list[int]:
    prose = " ".join(paragraphs)
    parts = re.split(r"[.!?]+(?=\s+[A-Z]|\s*$)", prose)
    return [count for part in parts if (count := _word_count(part)) >= 3]


def density_metrics(text: str) -> dict[str, float | int]:
    paragraphs = extract_body_paragraphs(text)
    counts = [_word_count(paragraph) for paragraph in paragraphs]
    sentence_counts = _sentence_lengths(paragraphs)
    short_flags = [count < 18 for count in counts]
    max_run = 0
    current = 0
    for is_short in short_flags:
        current = current + 1 if is_short else 0
        max_run = max(max_run, current)
    return {
        "body_words": sum(counts),
        "paragraph_count": len(counts),
        "mean_wpp": round(statistics.mean(counts), 1) if counts else 0.0,
        "median_wpp": statistics.median(counts) if counts else 0,
        "short_paragraph_rate": round((sum(short_flags) / len(counts)) if counts else 0.0, 3),
        "max_consecutive_short_run": max_run,
        "mean_sentence_length": round(statistics.mean(sentence_counts), 1) if sentence_counts else 0.0,
        "sentence_count": len(sentence_counts),
    }


def _sections(body: str) -> list[dict[str, object]]:
    matches = _markdown_heading_matches(body)
    sections: list[dict[str, object]] = []
    for idx, match in enumerate(matches):
        level = len(match.group(1))
        start = match.end()
        end = len(body)
        for next_match in matches[idx + 1 :]:
            if len(next_match.group(1)) <= level:
                end = next_match.start()
                break
        sections.append(
            {
                "level": level,
                "title": match.group(2).strip(),
                "start": match.start(),
                "content": body[start:end],
            }
        )
    return sections


def _markdown_heading_matches(body: str) -> list[re.Match[str]]:
    matches: list[re.Match[str]] = []
    in_fence = False
    offset = 0
    for line in body.splitlines(keepends=True):
        if line.strip().startswith("```"):
            in_fence = not in_fence
            offset += len(line)
            continue
        if not in_fence:
            match = re.match(r"^(#{1,6})\s+(.+?)\s*$", line.rstrip("\n"))
            if match:
                matches.append(HEADING_RE.match(body, offset))  # type: ignore[arg-type]
        offset += len(line)
    return [match for match in matches if match is not None]


def _heading_title(line: str) -> str:
    match = re.match(r"^\s*#{1,6}\s+(.+?)\s*$", line)
    title = match.group(1) if match else line
    return re.sub(r"\s+#+\s*$", "", title).strip()


def _heading_matches(line: str, candidates: Iterable[str], prefix: bool = False) -> bool:
    title = _heading_title(line).casefold()
    for candidate in candidates:
        expected = candidate.casefold()
        if title == expected or title.startswith(f"{expected}:"):
            return True
        if prefix and title.startswith((f"{expected} ", f"{expected}:")):
            return True
    return False


def _find_h2(body: str, pattern: str) -> dict[str, object] | None:
    regex = re.compile(pattern, re.IGNORECASE)
    for section in _sections(body):
        if section["level"] == 2 and regex.search(str(section["title"])):
            return section
    return None


def _find_matching_h2(body: str, candidates: Iterable[str], prefix: bool = False) -> dict[str, object] | None:
    for section in _sections(body):
        if section["level"] == 2 and _heading_matches(str(section["title"]), candidates, prefix):
            return section
    return None


def _count_bullets(section: dict[str, object] | None) -> int:
    if not section:
        return 0
    return sum(
        1
        for line in str(section["content"]).splitlines()
        if re.match(r"^\s*(?:[-*+]\s+|\d+[.)]\s+)", line)
    )


def _common_mistakes_rows(section: dict[str, object] | None) -> int:
    if not section:
        return 0
    rows = [line.strip() for line in str(section["content"]).splitlines() if line.strip().startswith("|")]
    data_rows = 0
    seen_separator = False
    for row in rows:
        if TABLE_SEPARATOR_RE.match(row):
            seen_separator = True
            continue
        if seen_separator:
            data_rows += 1
    return data_rows


def _quiz_items(section: dict[str, object] | None) -> list[tuple[str, str]]:
    if not section:
        return []
    content = str(section["content"])
    details = list(
        re.finditer(
            r"<details\b[^>]*>\s*<summary>(.*?)</summary>(.*?)</details>",
            content,
            re.IGNORECASE | re.DOTALL,
        )
    )
    if details:
        return [
            (re.sub(r"\s+", " ", match.group(1)).strip(), f"<details>{match.group(2)}</details>")
            for match in details
        ]
    matches = list(re.finditer(r"^(?:###\s+(.+)|\s*\d+[.)]\s+(.+))$", content, re.MULTILINE))
    items: list[tuple[str, str]] = []
    for idx, match in enumerate(matches):
        question = (match.group(1) or match.group(2) or "").strip()
        end = matches[idx + 1].start() if idx + 1 < len(matches) else len(content)
        items.append((question, content[match.end() : end]))
    return items


def _is_practice_question_path(path: Path) -> bool:
    try:
        relative = path.resolve().relative_to(REPO_ROOT.resolve())
    except ValueError:
        relative = path
    normalized = relative.as_posix().lower()
    if "src/content/docs/k8s/" not in normalized:
        return False
    return any(
        marker in normalized
        for marker in ("practice-questions", "questions", "mock-exam", "cumulative-quiz")
    )


def _practice_question_blocks(text: str) -> list[tuple[str, str, int | None]]:
    _, body = _strip_frontmatter(text)
    quiz = _find_matching_h2(body, QUIZ_HEADINGS) or _find_matching_h2(body, QUIZ_PREFIX_HEADINGS, prefix=True)
    raw_content = str(quiz["content"]) if quiz else body
    content_start = body.find(raw_content, int(quiz["start"])) if quiz else 0
    content_start = max(content_start, 0)
    content = raw_content
    content = _strip_code_blocks(content, "\n")
    details = list(
        re.finditer(
            r"<details\b[^>]*>\s*<summary>(.*?)</summary>(.*?)</details>",
            content,
            re.IGNORECASE | re.DOTALL,
        )
    )
    if details:
        blocks: list[tuple[str, str, int | None]] = []
        previous_end = 0
        for match in details:
            visible = f"{content[previous_end:match.start()]}\n{match.group(1)}"
            blocks.append((visible, match.group(2), None))
            previous_end = match.end()
        return blocks

    markers = list(
        re.finditer(
            r"(?m)^\s*(?:#{3,6}\s+)?Question\s+\d+\b",
            content,
            re.IGNORECASE,
        )
    )
    blocks = []
    for marker in markers:
        question_start = marker.start() + len(marker.group(0)) - len(marker.group(0).lstrip())
        line_number = body[: content_start + question_start].count("\n") + 1
        blocks.append((content[marker.start() : marker.end()], "", line_number))
    return blocks


def _answer_option_references(answer: str) -> set[str]:
    references: set[str] = set()
    patterns = (
        r"\b(?:options?|choices?|answers?)\s+([A-D1-4](?:\s*(?:,|and|or)\s*[A-D1-4])*)\b",
        r"\b([A-D1-4])[\).:]\s",
        r"\b([A-D1-4])\s+(?:is|works|fails|would|does|because)\b",
    )
    for pattern in patterns:
        for match in re.finditer(pattern, answer, re.IGNORECASE):
            references.update(label.upper() for label in re.findall(r"[A-D1-4]", match.group(1)))
    return references


def practice_mcq_metrics(path: Path, text: str) -> dict[str, object]:
    if not _is_practice_question_path(path):
        return {"applies": False, "question_count": 0, "violations": []}
    blocks = _practice_question_blocks(text)
    violations: list[dict[str, object]] = []
    for idx, (visible, answer, missing_details_line) in enumerate(blocks, 1):
        option_count = len(MCQ_OPTION_RE.findall(visible))
        if missing_details_line is not None:
            violations.append(
                {
                    "question": idx,
                    "line": missing_details_line,
                    "message": f"MCQ at line {missing_details_line} missing `<details>` answer block",
                    "visible_options": option_count,
                    "labels_referenced": [],
                    "has_distractor_reasoning": False,
                }
            )
            continue
        labels_referenced = _answer_option_references(answer)
        has_distractor_reasoning = len(labels_referenced) >= 3 and bool(MCQ_REASONING_KEYWORD_RE.search(answer))
        if option_count < 4 or not has_distractor_reasoning:
            violations.append(
                {
                    "question": idx,
                    "message": "MCQ needs ≥4 visible MCQ options"
                    if option_count < 4
                    else "MCQ answer must explain the correct option and distractors",
                    "visible_options": option_count,
                    "labels_referenced": sorted(labels_referenced),
                    "has_distractor_reasoning": has_distractor_reasoning,
                }
            )
    if not blocks:
        violations.append(
            {
                "question": 0,
                "visible_options": 0,
                "labels_referenced": [],
                "has_distractor_reasoning": False,
            }
        )
    return {"applies": True, "question_count": len(blocks), "violations": violations}


def _hands_on_lines(section: dict[str, object] | None) -> list[str]:
    if not section:
        return []
    return [
        line.strip()
        for line in str(section["content"]).splitlines()
        if re.match(r"^\s*-\s+\[\s*\]\s+", line)
    ]


def _next_module_link(body: str) -> bool:
    if _find_h2(body, r"^Next Module$"):
        return True
    for line in reversed([line.strip() for line in body.splitlines()]):
        if not line:
            continue
        return bool(("[Next" in line or "Next Module" in line) and re.search(r"\[[^\]]+\]\([^)]+\)", line))
    return False


def structure_metrics(text: str) -> dict[str, object]:
    _, body = _strip_frontmatter(text)
    learning = _find_matching_h2(body, LEARNING_OUTCOME_HEADINGS)
    why = next(
        (
            section
            for section in _sections(body)
            if section["level"] == 2
            and re.search("why", str(section["title"]), re.IGNORECASE)
            and re.search(r"matter|module", str(section["title"]), re.IGNORECASE)
        ),
        None,
    )
    common = _find_matching_h2(body, COMMON_MISTAKES_PREFIX_HEADINGS, prefix=True)
    quiz = _find_matching_h2(body, QUIZ_HEADINGS) or _find_matching_h2(body, QUIZ_PREFIX_HEADINGS, prefix=True)
    hands = _find_matching_h2(body, HANDS_ON_HEADINGS) or _find_matching_h2(
        body, HANDS_ON_PREFIX_HEADINGS, prefix=True
    )
    quiz_items = _quiz_items(quiz)
    did_section = _find_matching_h2(body, DID_YOU_KNOW_HEADINGS)
    did_you_know_count = _count_bullets(did_section)
    if did_you_know_count == 0:
        did_you_know_count = sum(
            1
            for line in body.splitlines()
            if re.match(r"^\s*(?:#{2,6}\s+|[-*+]\s+).*Did You Know\b", line, re.IGNORECASE)
        )

    positions = {
        "learning": learning["start"] if learning else None,
        "why": why["start"] if why else None,
        "did": body.lower().find("did you know") if "did you know" in body.lower() else None,
        "common": common["start"] if common else None,
        "quiz": quiz["start"] if quiz else None,
        "hands": hands["start"] if hands else None,
        "next": _find_h2(body, r"^Next Module$")["start"] if _find_h2(body, r"^Next Module$") else None,
    }
    next_link = _next_module_link(body)
    ordered_values = [positions[key] for key in ("learning", "why", "did", "common", "quiz", "hands", "next")]
    section_order_correct = (
        next_link
        and all(value is not None for value in ordered_values)
        and ordered_values == sorted(ordered_values)
    )

    return {
        "has_learning_outcomes": learning is not None,
        "learning_outcome_count": _count_bullets(learning),
        "has_why_matters": why is not None,
        "did_you_know_count": did_you_know_count,
        "common_mistakes_rows": _common_mistakes_rows(common),
        "quiz_count": len(quiz_items),
        "quiz_with_details": sum(1 for _, block in quiz_items if "<details" in block.lower()),
        "hands_on_checkboxes": len(_hands_on_lines(hands)),
        "section_order_correct": section_order_correct,
        "next_module_link": next_link,
    }


def _extract_section_text(text: str, pattern: str) -> str:
    _, body = _strip_frontmatter(text)
    section = _find_h2(body, pattern)
    return str(section["content"]) if section else ""


def _extract_matching_section_text(text: str, candidates: Iterable[str], prefix: bool = False) -> str:
    _, body = _strip_frontmatter(text)
    section = _find_matching_h2(body, candidates, prefix)
    return str(section["content"]) if section else ""


def extract_urls(section_text: str) -> list[str]:
    seen: dict[str, None] = {}
    for url in MD_LINK_RE.findall(section_text):
        seen.setdefault(url.rstrip(".,);'\""), None)
    for url in BARE_URL_RE.findall(section_text):
        cleaned = url.rstrip(".,);'\"")
        seen.setdefault(cleaned, None)
    return list(seen)


def _check_url(url: str) -> str:
    head_was_botblock_pattern = False
    try:
        import requests
    except ImportError:
        return "fetch_failed"
    try:
        session = requests.Session()
        session.max_redirects = 5
        response = session.head(url, timeout=10, allow_redirects=True)
        if response.status_code in (403, 404, 405, 501):
            # 403/404/405/501 on HEAD often means a real-browser-only page (Cloudflare bot-block, server lying about method support, etc.).
            head_was_botblock_pattern = True
            try:
                response = session.get(url, timeout=10, allow_redirects=True, stream=True)
                response.close()
            except requests.RequestException:
                # GET also failed (tarpit, drop, timeout) — fall through to lightpanda.
                response = None
    except requests.RequestException:
        # HEAD itself raised — treat as network failure, no lightpanda attempt.
        return "fetch_failed"
    if response is not None and 200 <= response.status_code <= 299:
        return "redirect" if response.history else "200"
    if head_was_botblock_pattern:
        # Cloudflare and similar bot-blockers reject HEAD (and sometimes GET) for traffic that a real browser handles fine.
        try:
            import subprocess

            result = subprocess.run(
                ["lightpanda", "fetch", "--dump", "markdown", url],
                capture_output=True,
                text=True,
                timeout=15,
                check=False,
            )
            if result.returncode == 0 and len(result.stdout.strip()) > 0:
                return "200"
        except (FileNotFoundError, subprocess.TimeoutExpired):
            return "404"
    return "404"


def sources_metrics(text: str, skip_source_check: bool, max_workers: int) -> dict[str, object]:
    section = _extract_matching_section_text(text, SOURCES_HEADINGS)
    urls = extract_urls(section)
    if skip_source_check:
        statuses: dict[str, int] = {"skipped": len(urls)}
    else:
        statuses = {"200": 0, "redirect": 0, "404": 0, "fetch_failed": 0}
        with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
            for status in executor.map(_check_url, urls):
                statuses[status] = statuses.get(status, 0) + 1
    return {"count": len(urls), "url_status": statuses, "urls": urls}


def anti_leak_metrics(text: str) -> dict[str, object]:
    _, body = _strip_frontmatter(text)
    body_no_code = _strip_code_blocks(body, " ")
    lowered = body_no_code.lower()
    forbidden = [token for token in FORBIDDEN_TOKENS if token.lower() in lowered]
    return {
        "forbidden_tokens": forbidden,
        "has_emoji": bool(EMOJI_RE.search(body_no_code)),
        "has_47": bool(re.search(r"(?<!\d)47(?!\d)", body_no_code)),
    }


def runnable_shell_metrics(text: str) -> dict[str, object]:
    _, body = _strip_frontmatter(text)
    runnable_blocks = [
        code for info, code in _fenced_code_blocks(body) if _fence_language(info) in RUNNABLE_SHELL_LANGS
    ]
    alias_defined = any(KUBECTL_ALIAS_RE.search(code) for code in runnable_blocks)
    if alias_defined:
        return {"kubectl_alias_violations": []}

    violations: list[str] = []
    for code in runnable_blocks:
        for match in KUBECTL_SHORTHAND_RE.finditer(code):
            violations.append(match.group(0).strip())
    return {"kubectl_alias_violations": violations}


def _fenced_code_blocks_with_lines(text: str) -> list[tuple[str, str, int]]:
    blocks: list[tuple[str, str, int]] = []
    for match in re.finditer(r"```([^\n]*)\n(.*?)```", text, re.DOTALL):
        blocks.append((match.group(1).strip(), match.group(2), text[: match.start(2)].count("\n") + 1))
    return blocks


def _shell_logical_lines(code: str, start_line: int) -> list[tuple[str, int]]:
    logical_lines: list[tuple[str, int]] = []
    current = ""
    current_start = start_line
    for offset, physical in enumerate(code.splitlines()):
        stripped = physical.strip()
        if not current:
            current_start = start_line + offset
            current = stripped
        else:
            current = f"{current} {stripped}"
        if current.rstrip().endswith("\\"):
            current = current.rstrip()[:-1].rstrip()
            continue
        if current:
            logical_lines.append((current, current_start))
        current = ""
    if current:
        logical_lines.append((current, current_start))
    return logical_lines


def _shell_tokens(line: str) -> list[str]:
    if line.lstrip().startswith("$ "):
        line = line.lstrip()[2:]
    try:
        return shlex.split(line, comments=True, posix=True)
    except ValueError:
        return line.split()


def _kubectl_indices(tokens: list[str], verb: str) -> Iterable[int]:
    for idx, token in enumerate(tokens[:-1]):
        if token == "kubectl" and tokens[idx + 1] == verb:
            yield idx


def _option_consumes_value(token: str) -> bool:
    return token in {
        "-n",
        "--namespace",
        "-c",
        "--container",
        "--context",
        "--kubeconfig",
        "--as",
        "--as-group",
        "--field-manager",
        "--request-timeout",
        "--image",
    }


def _skip_option(tokens: list[str], idx: int) -> int:
    token = tokens[idx]
    if _option_consumes_value(token) and idx + 1 < len(tokens):
        return idx + 2
    if token.startswith("-"):
        return idx + 1
    return idx


def _namespace_from_tokens(tokens: list[str]) -> str:
    for idx, token in enumerate(tokens):
        if token in {"-n", "--namespace"} and idx + 1 < len(tokens):
            return tokens[idx + 1]
        if token.startswith("--namespace="):
            return token.split("=", 1)[1]
        if token.startswith("-n="):
            return token.split("=", 1)[1]
    return ""


def _parse_kubectl_run_images(tokens: list[str]) -> list[tuple[str, str, str]]:
    pod_images: list[tuple[str, str, str]] = []
    for kubectl_idx in _kubectl_indices(tokens, "run"):
        pod_name = ""
        namespace = _namespace_from_tokens(tokens[kubectl_idx + 2 :])
        idx = kubectl_idx + 2
        while idx < len(tokens):
            token = tokens[idx]
            if token == "--":
                break
            if token.startswith("-"):
                idx = _skip_option(tokens, idx)
                continue
            pod_name = token
            break
        if not pod_name:
            continue
        image = ""
        for idx, token in enumerate(tokens[kubectl_idx + 2 :], start=kubectl_idx + 2):
            if token == "--image" and idx + 1 < len(tokens):
                image = tokens[idx + 1]
                break
            if token.startswith("--image="):
                image = token.split("=", 1)[1]
                break
        if image:
            pod_images.append((namespace, pod_name, image))
    return pod_images


def _parse_kubectl_execs(tokens: list[str]) -> list[tuple[str, str, str]]:
    execs: list[tuple[str, str, str]] = []
    for kubectl_idx in _kubectl_indices(tokens, "exec"):
        pod_name = ""
        namespace = _namespace_from_tokens(tokens[kubectl_idx + 2 :])
        idx = kubectl_idx + 2
        while idx < len(tokens):
            token = tokens[idx]
            if token == "--":
                break
            if token.startswith("-"):
                idx = _skip_option(tokens, idx)
                continue
            pod_name = token
            idx += 1
            break
        if not pod_name:
            continue
        while idx < len(tokens) and tokens[idx] != "--":
            idx += 1
        if idx + 1 >= len(tokens):
            continue
        binary = tokens[idx + 1].rsplit("/", 1)[-1]
        if binary:
            execs.append((namespace, pod_name, binary))
    return execs


def _yaml_name_image_pairs(code: str) -> list[tuple[str, str]]:
    name_re = re.compile(r"^\s*name:\s*['\"]?([^'\"\s#]+)")
    image_re = re.compile(r"^\s*image:\s*['\"]?([^'\"\s#]+)")
    lines = code.splitlines()
    pairs: list[tuple[str, str]] = []
    for idx, line in enumerate(lines):
        name_match = name_re.match(line)
        if not name_match:
            continue
        name = name_match.group(1)
        for following in lines[idx + 1 : idx + 31]:
            image_match = image_re.match(following)
            if image_match:
                pairs.append((name, image_match.group(1)))
                break
    return pairs


def _normalize_image_name(image: str) -> str:
    normalized = image.strip().strip("'\"").lower()
    normalized = normalized.split("@", 1)[0]
    parts = normalized.split("/")
    if len(parts) > 1 and ("." in parts[0] or ":" in parts[0] or parts[0] == "localhost"):
        parts = parts[1:]
    if len(parts) == 2 and parts[0] == "library":
        parts = parts[1:]
    return "/".join(parts)


def _image_without_tag(image: str) -> str:
    slash_idx = image.rfind("/")
    colon_idx = image.rfind(":")
    if colon_idx > slash_idx:
        return image[:colon_idx]
    return image


def _allowlist_key_for_image(image: str) -> str | None:
    normalized = _normalize_image_name(image)
    if normalized in IMAGE_BINARY_ALLOWLIST:
        return normalized
    without_tag = _image_without_tag(normalized)
    if without_tag in IMAGE_BINARY_ALLOWLIST:
        return without_tag
    return None


def lab_runnability_metrics(text: str) -> dict[str, object]:
    """Detect kubectl-exec calls whose binary is not in the target pod's image.

    Algorithm:
      1. Walk fenced bash/sh/shell/zsh code blocks for kubectl commands.
      2. Build a pod image map from `kubectl run NAME --image=IMAGE` and simple
         inline YAML `name:` / following `image:` pairs within about 30 lines.
      3. Find every `kubectl exec [-n NS] POD -- BIN [args]`.
      4. If POD's image is unknown, skip the exec check because there is no ground truth.
      5. Look up BIN in IMAGE_BINARY_ALLOWLIST and flag strict allowlist misses.

    Returns:
      {
        "image_binary_violations": [
          {
            "pod": str,
            "image": str,
            "binary": str,
            "line": int,
            "snippet": str,
          },
          ...
        ],
        "unknown_images": [str, ...],
      }
    """
    pod_images: dict[tuple[str, str], str] = {}
    blocks = _fenced_code_blocks_with_lines(text)

    for info, code, _start_line in blocks:
        language = _fence_language(info)
        if language in RUNNABLE_SHELL_LANGS:
            for line, _line_number in _shell_logical_lines(code, 1):
                for namespace, pod, image in _parse_kubectl_run_images(_shell_tokens(line)):
                    pod_images[(namespace, pod)] = image
        if language in RUNNABLE_SHELL_LANGS or language in {"yaml", "yml"}:
            for pod, image in _yaml_name_image_pairs(code):
                pod_images[("", pod)] = image

    unknown_images: dict[str, None] = {}
    for image in pod_images.values():
        if _allowlist_key_for_image(image) is None:
            unknown_images.setdefault(image, None)

    violations: list[dict[str, object]] = []
    for info, code, start_line in blocks:
        if _fence_language(info) not in RUNNABLE_SHELL_LANGS:
            continue
        for line, line_number in _shell_logical_lines(code, start_line):
            tokens = _shell_tokens(line)
            for namespace, pod, binary in _parse_kubectl_execs(tokens):
                image = pod_images.get((namespace, pod)) or pod_images.get(("", pod))
                if not image and not namespace:
                    matching_images = {value for (image_namespace, image_pod), value in pod_images.items() if image_pod == pod}
                    if len(matching_images) == 1:
                        image = next(iter(matching_images))
                if not image:
                    continue
                allowlist_key = _allowlist_key_for_image(image)
                if allowlist_key is None:
                    continue
                if binary.lower() in IMAGE_BINARY_ALLOWLIST[allowlist_key]:
                    continue
                violations.append(
                    {
                        "pod": pod,
                        "image": image,
                        "binary": binary,
                        "line": line_number,
                        "snippet": line.strip()[:120],
                    }
                )

    return {"image_binary_violations": violations, "unknown_images": list(unknown_images)}


def anti_fabrication_metrics(text: str) -> dict[str, object]:
    _, body = _strip_frontmatter(text)
    body_no_code = _strip_code_blocks(body, "\n")
    violations: list[str] = []
    for paragraph in re.split(r"\n\s*\n", body_no_code):
        normalized = " ".join(paragraph.split())
        if not normalized or SCENARIO_PREFIX_RE.match(normalized):
            continue
        for match in UNSOURCED_ANECDOTE_RE.finditer(normalized):
            violations.append(match.group(0))
    return {"unsourced_anecdotes": violations}


def source_h1_metrics(text: str) -> dict[str, object]:
    match = re.match(r"^---\s*\n(.*?)\n---\s*(?:\n|$)", text, re.DOTALL)
    body = text[match.end() :] if match else text
    body_start_line = text[: match.end()].count("\n") + 1 if match else 1

    for line_number, line in enumerate(body.splitlines(), start=body_start_line):
        stripped = line.strip()
        if not stripped or stripped.startswith((">", "<!--")) or stripped == "---":
            continue
        if stripped.startswith("# "):
            return {
                "violation": True,
                "line": line_number,
                "message": (
                    f"source_h1_after_frontmatter: line {line_number} — "
                    "Starlight already renders H1 from title:; remove this line"
                ),
            }
        break

    return {"violation": False, "line": None, "message": ""}


def _strip_top_metadata(body: str) -> str:
    """Drop canonical metadata blockquotes before prose checks."""
    lines = body.splitlines()
    start = 0
    while start < len(lines) and not lines[start].strip():
        start += 1
    while start < len(lines) and lines[start].strip().startswith(">"):
        start += 1
    while start < len(lines) and not lines[start].strip():
        start += 1
    if start < len(lines) and re.fullmatch(r"-{3,}", lines[start].strip()):
        start += 1
    while start < len(lines) and not lines[start].strip():
        start += 1
    return "\n".join(lines[start:])


def protected_assets(text: str) -> dict[str, int]:
    _, body = _strip_frontmatter(text)
    fences = re.findall(r"```([^\n]*)\n.*?```", body, flags=re.DOTALL)
    lines = body.splitlines()
    return {
        "code_blocks": len(fences),
        "ascii_diagrams": _count_ascii_diagrams(lines),
        "mermaid_diagrams": sum(1 for info in fences if info.strip().lower().startswith("mermaid")),
        "tables": _count_markdown_tables(lines),
    }


def _count_ascii_diagrams(lines: list[str]) -> int:
    indexes = sorted(_ascii_diagram_line_indexes(lines))
    if not indexes:
        return 0
    groups = 1
    for prev, current in pairwise(indexes):
        if current != prev + 1:
            groups += 1
    return groups


def _count_markdown_tables(lines: list[str]) -> int:
    count = 0
    for idx, line in enumerate(lines[:-1]):
        if "|" in line and TABLE_SEPARATOR_RE.match(lines[idx + 1].strip()):
            count += 1
    return count


def _content_tokens(text: str) -> list[str]:
    tokens = [token.lower() for token in re.findall(r"[A-Za-z][A-Za-z0-9-]*", text)]
    tokens = [token[:-1] if len(token) > 4 and token.endswith("s") else token for token in tokens]
    return [token for token in tokens if len(token) >= 3 and token not in STOPWORDS]


def _token_match(outcome_tokens: list[str], target: str) -> bool:
    if not outcome_tokens:
        return False
    target_tokens = set(_content_tokens(target))
    required = min(2, len(outcome_tokens))
    return len(set(outcome_tokens) & target_tokens) >= required


def _learning_outcomes(text: str) -> list[str]:
    section_text = _extract_matching_section_text(text, LEARNING_OUTCOME_HEADINGS)
    outcomes = []
    for line in section_text.splitlines():
        match = re.match(r"^\s*(?:[-*+]\s+|\d+[.)]\s+)(.+)", line)
        if match:
            outcomes.append(match.group(1).strip())
    return outcomes


def alignment_metrics(text: str) -> dict[str, object]:
    _, body = _strip_frontmatter(text)
    outcomes = _learning_outcomes(text)
    paragraphs = extract_body_paragraphs(text)
    sections = _sections(body)
    section_targets = [str(section["title"]) for section in sections if section["level"] == 2]
    section_targets.extend(paragraphs)
    quiz = _find_matching_h2(body, QUIZ_HEADINGS) or _find_matching_h2(body, QUIZ_PREFIX_HEADINGS, prefix=True)
    hands = _find_matching_h2(body, HANDS_ON_HEADINGS) or _find_matching_h2(
        body, HANDS_ON_PREFIX_HEADINGS, prefix=True
    )
    assessment_items = [
        (f"quiz_{idx}", f"{question} {block}")
        for idx, (question, block) in enumerate(_quiz_items(quiz), 1)
    ]
    assessment_items.extend(
        (f"hands_on_{idx}", line) for idx, line in enumerate(_hands_on_lines(hands), 1)
    )

    section_results: list[dict[str, object]] = []
    assessment_results: list[dict[str, object]] = []
    for outcome in outcomes:
        tokens = _content_tokens(outcome)[:8]
        section_name: str | None = None
        assessment_name: str | None = None
        if tokens:
            for target in section_targets:
                if _token_match(tokens, target):
                    section_name = target[:80]
                    break
            for name, target in assessment_items:
                if _token_match(tokens, target):
                    assessment_name = name
                    break
        section_results.append({"outcome": outcome, "covered": section_name is not None, "section": section_name})
        assessment_results.append({"outcome": outcome, "covered_by": assessment_name})
    all_covered = bool(outcomes) and all(item["covered"] for item in section_results) and all(
        item["covered_by"] for item in assessment_results
    )
    return {
        "outcomes_to_sections": section_results,
        "outcomes_to_assessment": assessment_results,
        "all_outcomes_covered": all_covered,
    }


def gate_results(
    metrics: dict[str, float | int],
    structure: dict[str, object],
    sources: dict[str, object],
    anti_leak: dict[str, object],
    runnable_shell: dict[str, object],
    lab_runnability: dict[str, object],
    anti_fabrication: dict[str, object],
    practice_mcq: dict[str, object],
    alignment: dict[str, object],
    skip_source_check: bool,
    source_h1: dict[str, object] | None = None,
    body_words_floor: int = 5000,
) -> dict[str, bool | None]:
    quiz_count = int(structure["quiz_count"])
    gates: dict[str, bool | None] = {
        "gate_no_source_h1": not source_h1["violation"] if source_h1 is not None else True,
        "density_mean_wpp_30": float(metrics["mean_wpp"]) >= 30,
        "density_median_wpp_28": float(metrics["median_wpp"]) >= 28,
        "density_short_rate_20pct": float(metrics["short_paragraph_rate"]) <= 0.20,
        "density_max_consecutive_short_2": int(metrics["max_consecutive_short_run"]) <= 2,
        "body_words_floor_met": int(metrics["body_words"]) >= int(body_words_floor),
        "sentence_length_12_28": 12 <= float(metrics["mean_sentence_length"]) <= 28,
        "structure_sections_present": bool(structure["has_learning_outcomes"])
        and 3 <= int(structure["learning_outcome_count"]) <= 5
        and bool(structure["has_why_matters"])
        and bool(structure["next_module_link"]),
        "structure_order_correct": bool(structure["section_order_correct"]),
        "structure_did_you_know_4": int(structure["did_you_know_count"]) == 4,
        "structure_common_mistakes_6_8": 6 <= int(structure["common_mistakes_rows"]) <= 8,
        "structure_quiz_6_8_with_details": 6 <= quiz_count <= 8
        and int(structure["quiz_with_details"]) == quiz_count,
        "structure_hands_on_checkboxes": int(structure["hands_on_checkboxes"]) >= 3,
        "sources_min_10": int(sources["count"]) >= 10,
        "sources_all_reachable": None
        if skip_source_check
        else not any(int(sources["url_status"].get(key, 0)) for key in ("404", "fetch_failed")),  # type: ignore[union-attr]
        "anti_leak": not anti_leak["forbidden_tokens"]
        and not anti_leak["has_emoji"]
        and not anti_leak["has_47"],
        "runnable_no_kubectl_alias": not runnable_shell["kubectl_alias_violations"],
        "lab_image_binary_match": not lab_runnability["image_binary_violations"],
        "anti_fabrication_no_unsourced_anecdote": not anti_fabrication["unsourced_anecdotes"],
        "practice_mcq_four_options_with_distractors": None
        if not practice_mcq["applies"]
        else not practice_mcq["violations"],
        "outcomes_aligned": bool(alignment["all_outcomes_covered"]),
    }
    return gates


def classify_tier(metrics: dict[str, float | int], gates: dict[str, bool | None]) -> tuple[str, list[str]]:
    failed = [key for key, value in gates.items() if value is False]
    if int(metrics["body_words"]) < 3000:
        return "T3", failed
    if not failed:
        return "T0", []
    density_keys = {
        "density_mean_wpp_30",
        "density_median_wpp_28",
        "density_short_rate_20pct",
        "density_max_consecutive_short_2",
        "sentence_length_12_28",
        "body_words_floor_met",
    }
    structure_failed = [key for key in failed if key.startswith("structure_")]
    density_failed = [key for key in failed if key in density_keys]
    lab_failed = [key for key in failed if key == "lab_image_binary_match"]
    other_failed = [
        key for key in failed if key not in density_keys and not key.startswith("structure_") and key not in lab_failed
    ]
    if density_failed and structure_failed:
        return "T3", failed
    if structure_failed and not density_failed and not lab_failed and not other_failed and len(structure_failed) <= 2:
        return "T1", failed
    if density_failed and not structure_failed and not other_failed:
        return "T2", failed
    # Lab-runnability failures are blocking but localized, so lab-only failures classify with T2.
    if lab_failed and not density_failed and not structure_failed and not other_failed:
        return "T2", failed
    return "T3", failed


def verify(path: str | Path, skip_source_check: bool = False, max_workers: int = 8) -> dict[str, object]:
    module_path = Path(path)
    text = _read(module_path)
    frontmatter, _ = _strip_frontmatter(text)
    metrics = density_metrics(text)
    structure = structure_metrics(text)
    sources = sources_metrics(text, skip_source_check, max_workers)
    assets = protected_assets(text)
    anti = anti_leak_metrics(text)
    runnable_shell = runnable_shell_metrics(text)
    lab_runnability = lab_runnability_metrics(text)
    anti_fabrication = anti_fabrication_metrics(text)
    practice_mcq = practice_mcq_metrics(module_path, text)
    alignment = alignment_metrics(text)
    source_h1 = source_h1_metrics(text)
    body_words_floor = _body_words_floor_for_module(module_path)
    gates = gate_results(
        metrics,
        structure,
        sources,
        anti,
        runnable_shell,
        lab_runnability,
        anti_fabrication,
        practice_mcq,
        alignment,
        skip_source_check,
        source_h1,
        body_words_floor=body_words_floor,
    )
    tier, reasons = classify_tier(metrics, gates)
    passed = all(value is not False for value in gates.values())
    diagnostics = [str(source_h1["message"])] if source_h1["message"] else []
    try:
        display_path = str(module_path.relative_to(REPO_ROOT))
    except ValueError:
        display_path = str(module_path)
    return {
        "path": display_path,
        "title": str(frontmatter.get("title", "")),
        "tier": tier,
        "tier_reasons": reasons,
        "metrics": metrics,
        "structure": structure,
        "sources": sources,
        "protected_assets": assets,
        "anti_leak": anti,
        "runnable_shell": runnable_shell,
        "lab_runnability": lab_runnability,
        "anti_fabrication": anti_fabrication,
        "practice_mcq": practice_mcq,
        "alignment": alignment,
        "source_h1": source_h1,
        "diagnostics": diagnostics,
        "gates": gates,
        "passed": passed,
        "frontmatter": frontmatter,
    }


def _frontmatter_revision_pending(path: Path) -> bool:
    frontmatter, _ = _strip_frontmatter(_read(path))
    return frontmatter.get("revision_pending") is True


def _collect_paths(args: argparse.Namespace) -> list[Path]:
    paths = [Path(path) for path in args.paths]
    if args.glob:
        paths.extend(Path(path) for path in globlib.glob(args.glob, recursive=True))
    if args.all_revision_pending:
        paths.extend(
            path
            for path in (REPO_ROOT / "src/content/docs").glob("**/*.md")
            if _frontmatter_revision_pending(path)
        )
    seen: dict[Path, None] = {}
    for path in paths:
        seen.setdefault(path, None)
    return list(seen)


def _write_records(records: Iterable[dict[str, object]], out: Path | None, tier_only: bool) -> None:
    handle = out.open("w", encoding="utf-8") if out else sys.stdout
    try:
        for record in records:
            if tier_only:
                handle.write(f"{record['path']}: {record['tier']}\n")
            else:
                handle.write(json.dumps(record, ensure_ascii=False, sort_keys=True) + "\n")
    finally:
        if out:
            handle.close()


def _print_summary(records: list[dict[str, object]]) -> None:
    tiers = Counter(str(record["tier"]) for record in records)
    failures = Counter(
        reason
        for record in records
        for reason in record.get("tier_reasons", [])  # type: ignore[union-attr]
    )
    print("summary:")
    print("tiers:", json.dumps(dict(sorted(tiers.items())), sort_keys=True))
    print("failure_gates:", json.dumps(dict(sorted(failures.items())), sort_keys=True))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Verify KubeDojo modules against the #388 contract.")
    parser.add_argument("paths", nargs="*", help="Markdown module paths")
    parser.add_argument("-g", "--glob", help="Glob pattern for markdown modules")
    parser.add_argument("-A", "--all-revision-pending", action="store_true", help="Scan revision_pending modules")
    parser.add_argument("-o", "--out", type=Path, help="Write JSONL output to this path")
    parser.add_argument("-s", "--summary", action="store_true", help="Print aggregate tier and gate counts")
    parser.add_argument("-q", "--quiet", action="store_true", help="Suppress per-module progress")
    parser.add_argument("--skip-source-check", action="store_true", help="Skip live source reachability checks")
    parser.add_argument("--max-workers", type=int, default=8, help="Max source-check worker threads")
    parser.add_argument("--tier-only", action="store_true", help='Print "path: tier" for fast triage')
    parser.add_argument(
        "--snapshot",
        action="store_true",
        help=(
            "Capture stdout from allowlisted kubectl/helm/kind/k3d commands in each module's "
            "bash code blocks and write dated snapshot files under "
            "calibration/v1/verifier-snapshots/<module-key>/. Default off; existing CI unaffected."
        ),
    )
    args = parser.parse_args(argv)

    paths = _collect_paths(args)
    if not paths:
        parser.error("provide paths, --glob, or --all-revision-pending")
    records: list[dict[str, object]] = []
    for path in paths:
        if not args.quiet and args.out:
            print(f"verifying {path}", file=sys.stderr)
        records.append(verify(path, skip_source_check=args.skip_source_check, max_workers=args.max_workers))
        if args.snapshot:
            _run_snapshot(path, quiet=args.quiet)
    _write_records(records, args.out, args.tier_only)
    if args.summary:
        _print_summary(records)
    return 0


def _run_snapshot(path: Path, *, quiet: bool) -> None:
    # Ensure repo root is on sys.path (verify_module strips "" and its own dir at import time).
    _root = str(REPO_ROOT)
    if _root not in sys.path:
        sys.path.insert(0, _root)
    from scripts.quality import (
        verifier_snapshots,  # local import to keep default path fast
    )

    snap = verifier_snapshots.snapshot_module(path)
    if snap and not quiet:
        print(f"snapshot → {snap}", file=sys.stderr)


if __name__ == "__main__":
    raise SystemExit(main())
