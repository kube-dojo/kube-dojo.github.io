#!/usr/bin/env python3
"""Supply-chain DETECTION tripwire — issue #1812 (Miasma-class worm defense).

`.npmrc` sets `ignore-scripts=true` (PREVENTION: dependency lifecycle scripts do
not execute on install). This is DETECTION: it scans the dependency tree and FAILS
if a dependency can run install-time code that has not been explicitly audited —
so a freshly-introduced hook (the Miasma worm republishes packages with forged
provenance) is surfaced for human review instead of sitting silent until someone
runs `npm install` on a machine without the guard.

Authoritative source = `package-lock.json`, NOT the installed `node_modules`:
  - The lockfile lists EVERY dependency, including OS-gated optional ones that are
    not installed on this machine (e.g. `fsevents` on Linux) — node_modules misses
    those (cross-family review, codex/deepseek).
  - npm's `hasInstallScript` flag is TRUE for preinstall/install/postinstall AND
    for implicit node-gyp builds (`binding.gyp` with no declared script) — reading
    `package.json.scripts` alone misses the latter (e.g. `fsevents`).
  - The lockfile PATH (`node_modules/<name>`) is the resolved identity, so a
    package that lies about its `name` in package.json cannot spoof the allow-list,
    and a package with a null/empty name cannot evade the scan (review: all three).

Three gates (any violation => exit 1):
  1. INSTALL HOOKS: every `hasInstallScript` package must be in ALLOWLIST_INSTALL.
  2. ALLOW-LIST ABUSE: an allow-listed package's *declared* install hooks must be a
     subset of EXPECTED_HOOKS — so a compromised esbuild/sharp that adds a rogue
     preinstall is still caught.
  3. NON-REGISTRY SOURCE: any dep resolved from git/local/tarball is flagged — those
     bypass registry signing and DO run `prepare` on install (the `prepare` surface
     that npm's `hasInstallScript` does not cover; registry deps do not run `prepare`
     on `npm ci`). The only exceptions are the exact entries in
     ALLOWLIST_NON_REGISTRY: the lockfile entry at that exact path must equal the
     pinned entry (name, version, resolved, integrity and every other key).

Adding to any allow-list is a security decision — review it in its own commit.

Exit 0 = clean. Exit 1 = unaudited install-time code found (or lockfile missing).
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

# Packages permitted to carry an install script (lockfile `hasInstallScript`).
# Keep minimal and reviewed. Identity is the lockfile path, not the declared name.
# Honoured ONLY at the top level (`node_modules/<name>`); a legitimate nested copy
# must be opted in by its full path in ALLOWLIST_INSTALL_PATHS below.
ALLOWLIST_INSTALL: set[str] = {"esbuild", "fsevents", "sharp"}

# Specific NESTED install-hook packages that are explicitly audited, keyed by FULL
# lockfile path. The top-level-only rule deliberately refuses to trust an allow-listed
# leaf name at a nested path (a worm could nest a rogue `esbuild`), so each legitimate
# nested copy is opted in here one exact path at a time. Entries still pass the
# alias-masquerade and EXPECTED_HOOKS subset checks below.
#   - node_modules/astro/node_modules/sharp: astro pins sharp 0.34.5 nested (the
#     top-level sharp is 0.35.1 with no install script). Audited: resolved from the npm
#     registry with a pinned sha512 integrity, no `name` alias, genuine `sharp` (native
#     image library that legitimately builds its binary via the `install` hook).
ALLOWLIST_INSTALL_PATHS: set[str] = {
    "node_modules/astro/node_modules/sharp",
}

# For an allow-listed package, its DECLARED install-lifecycle hooks must be a subset
# of these. fsevents builds via binding.gyp with no explicit script => empty set.
EXPECTED_HOOKS: dict[str, set[str]] = {
    "esbuild": {"postinstall"},
    "sharp": {"install"},
    "fsevents": set(),
}

# Gate-3 exceptions: non-registry entries that are explicitly audited, keyed by FULL
# lockfile path. The lockfile entry at that path must EQUAL the pinned entry below,
# every key and value, nothing missing and nothing added (so no extra `bin`,
# `hasInstallScript` or other install metadata, and no registry or empty `resolved`
# swapped in). Anything else at that path is reported as [non-registry-pin]; the
# same entry at any other path is an ordinary [non-registry] finding. `integrity` pins
# the tarball bytes: this script compares the recorded value, and `npm ci` enforces
# it on install (EINTEGRITY for a swapped tarball).
#   - node_modules/picomatch: patched picomatch 4.0.7 for GHSA-fc5q-39xc-vjpf, built
#     from `npm pack picomatch@4.0.7` + vendor/picomatch/picomatch-4.0.7-lu.1.patch
#     (rebuild recipe in vendor/picomatch/README.md). No scripts, no bin. REMOVE this
#     entry, with vendor/picomatch/, when a picomatch release above 4.0.7 fixes
#     GHSA-fc5q-39xc-vjpf, or the advisory is withdrawn.
ALLOWLIST_NON_REGISTRY: dict[str, dict[str, object]] = {
    "node_modules/picomatch": {
        "name": "@learn-ukrainian/picomatch",
        "version": "4.0.7-lu.1",
        "resolved": "file:vendor/picomatch/learn-ukrainian-picomatch-4.0.7-lu.1.tgz",
        "integrity": (
            "sha512-HV+6IOKo6ObdzotW27KfsDLfpmVnT17SViHn20M/hKLLWv9QuzjNCeap7qtv8Cq+"
            "Htk3T2Q1bNwVCbeBjZLP9Q=="
        ),
        "license": "MIT",
        "engines": {"node": ">=12"},
    },
}

INSTALL_LIFECYCLE = ("preinstall", "install", "postinstall")
REGISTRY_PREFIX = "https://registry.npmjs.org/"

REPO_ROOT = Path(__file__).resolve().parents[2]


def name_from_lock_path(path: str) -> str:
    """Resolved package identity = the segment after the last `node_modules/`.
    Handles scopes: `node_modules/@astrojs/starlight` -> `@astrojs/starlight`."""
    return path.split("node_modules/")[-1]


def pinned_entry_mismatch(path: str, meta: dict) -> list[str] | None:
    """For a path in ALLOWLIST_NON_REGISTRY: the sorted keys whose values differ from
    the pinned entry (missing and extra keys included), [] on an exact match.
    None when the path has no pinned entry."""
    expected = ALLOWLIST_NON_REGISTRY.get(path)
    if expected is None:
        return None
    keys = expected.keys() | meta.keys()
    return sorted(k for k in keys if meta.get(k, ...) != expected.get(k, ...))


def declared_install_hooks(pkg_dir: Path) -> set[str] | None:
    """Read declared install hooks from <pkg_dir>/package.json. None if not present.
    pkg_dir is the package's ACTUAL location (lockfile.parent / lockfile path), so a
    nested copy is read at its real path — not collapsed to the top-level name."""
    pkg_json = pkg_dir / "package.json"
    if not pkg_json.is_file():
        return None
    try:
        scripts = json.loads(pkg_json.read_text(encoding="utf-8")).get("scripts") or {}
    except (ValueError, OSError):
        return set()
    if not isinstance(scripts, dict):
        return set()
    return {h for h in INSTALL_LIFECYCLE if h in scripts}


def main(argv: list[str]) -> int:
    lockfile = Path(argv[1]) if len(argv) > 1 else REPO_ROOT / "package-lock.json"
    if not lockfile.is_file():
        print(f"ERROR: lockfile not found: {lockfile}", file=sys.stderr)
        return 1

    try:
        packages = json.loads(lockfile.read_text(encoding="utf-8")).get("packages", {})
    except (ValueError, OSError) as exc:
        print(f"ERROR: cannot parse {lockfile}: {exc}", file=sys.stderr)
        return 1

    install_hook_pkgs: list[str] = []
    violations: list[str] = []

    for path, meta in packages.items():
        if not path:  # root package
            continue

        # Local/linked deps (`file:` / workspace symlink) run `prepare` on install and
        # bypass registry signing. We have none — flag any that appear (review: codex R3
        # demonstrated a `file:` dep slipping past the registry gate).
        if meta.get("link"):
            violations.append(
                f"[local-link] {path} — linked/local dependency "
                f"(resolved={meta.get('resolved') or '?'}); runs `prepare`, unsigned"
            )
            continue

        leaf = name_from_lock_path(path)

        # Gate 1 + 2: install scripts. Identity is the FULL lockfile path, NOT the
        # leaf name. A nested `node_modules/x/node_modules/esbuild` must not inherit
        # esbuild's allow-list entry — so an allow-listed name is only honoured when
        # it is the top-level dependency (review: codex R2 demonstrated that bypass).
        if meta.get("hasInstallScript"):
            install_hook_pkgs.append(path.removeprefix("node_modules/"))
            is_top_level = path == f"node_modules/{leaf}"
            lock_name = meta.get("name")
            # Allowed if it is a top-level allow-listed name, OR its exact nested path
            # is explicitly audited. Everything else (incl. a nested allow-listed leaf
            # that is NOT path-allow-listed) is a violation.
            allowed = (leaf in ALLOWLIST_INSTALL and is_top_level) or path in ALLOWLIST_INSTALL_PATHS
            if not allowed:
                violations.append(
                    f"[install-hook] {path} — declares an install script and is not a "
                    f"top-level audited dependency (allow-list {sorted(ALLOWLIST_INSTALL)}, "
                    f"top-level only) nor an audited nested path "
                    f"(ALLOWLIST_INSTALL_PATHS)"
                )
            elif lock_name and lock_name != leaf:
                # `esbuild: npm:evil@x` installs `evil` at node_modules/esbuild but the
                # lockfile records the REAL name — reject the alias masquerade so it
                # cannot borrow an allow-listed identity (review: codex R3).
                violations.append(
                    f"[alias-masquerade] {path} — lockfile name {lock_name!r} != install "
                    f"path {leaf!r} (npm alias borrowing an allow-listed name)"
                )
            else:
                # Read hooks from the package's ACTUAL location, not node_modules/<leaf>.
                actual = declared_install_hooks(lockfile.parent / path)
                expected = EXPECTED_HOOKS.get(leaf, set())
                if actual is not None and not actual <= expected:
                    violations.append(
                        f"[allow-list-abuse] {path} — allow-listed but declares "
                        f"unexpected hook(s) {sorted(actual - expected)} "
                        f"(expected ⊆ {sorted(expected) or '∅'})"
                    )
                # actual is None only for a top-level allow-listed dep not installed on
                # this runner (e.g. fsevents on Linux). The lockfile `name` is verified
                # above and `integrity` pins the tarball, so a swap/alias surfaces in the
                # lockfile diff; PREVENTION (.npmrc ignore-scripts) blocks execution
                # regardless. Residual: a same-name rogue hook added to an uninstalled
                # OS-gated dep is caught only by lockfile-integrity diff review.

        # Gate 3: non-registry source (git/local/tarball — runs `prepare`, unsigned).
        # An audited path must equal its pinned entry exactly, whatever its source.
        mismatch = pinned_entry_mismatch(path, meta)
        resolved = meta.get("resolved")
        if mismatch is not None:
            if mismatch:
                violations.append(
                    f"[non-registry-pin] {path} — lockfile entry differs from the audited "
                    f"pinned entry in {mismatch} (ALLOWLIST_NON_REGISTRY requires an exact "
                    f"match)"
                )
        elif resolved is not None and not isinstance(resolved, str):
            violations.append(
                f"[non-registry] {path} — malformed `resolved` ({type(resolved).__name__}); "
                f"cannot prove a registry source"
            )
        elif resolved and not resolved.startswith(REGISTRY_PREFIX):
            violations.append(
                f"[non-registry] {path} — resolved from a non-registry source "
                f"({resolved[:60]}); these run `prepare` on install and bypass "
                f"registry signing"
            )

    print(
        f"Scanned {lockfile.name}: {len(install_hook_pkgs)} package(s) with install "
        f"scripts ({', '.join(sorted(install_hook_pkgs)) or 'none'})."
    )

    if violations:
        print(
            f"\n  SUPPLY-CHAIN TRIPWIRE: {len(violations)} finding(s) — "
            f"unaudited install-time code:",
            file=sys.stderr,
        )
        for v in violations:
            print(f"    {v}", file=sys.stderr)
        print(
            "\n  This is how Miasma-class worms execute. Review the package(s) and "
            "the lockfile diff.\n  If legitimate, update ALLOWLIST_INSTALL / "
            "EXPECTED_HOOKS / ALLOWLIST_NON_REGISTRY in this file in a reviewed commit.",
            file=sys.stderr,
        )
        return 1

    print("OK — no unaudited dependency install-time code.")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
