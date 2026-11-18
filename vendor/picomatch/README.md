# Patched picomatch (GHSA-fc5q-39xc-vjpf)

`learn-ukrainian-picomatch-4.0.7-lu.1.tgz` is picomatch 4.0.7 with one fix, packed as
`@learn-ukrainian/picomatch@4.0.7-lu.1`. It is a byte copy of the tarball the
learn-ukrainian project vendors for the same advisory (its `site/vendor/picomatch/`).
`package.json` installs it as `picomatch` and points every `picomatch` in the tree at it
with the override `"picomatch": "$picomatch"`. `package-lock.json` pins its sha512
integrity, so `npm ci` refuses any other bytes.

## Why

GHSA-fc5q-39xc-vjpf (CVE-2026-112366, high) covers every published picomatch release up
to 4.0.7: a repeated extglob such as `+(*a)` compiles to a regular expression that
backtracks exponentially. No fixed release exists and upstream has not merged any of the
open fix proposals, so this copy carries the fix. It replaces both the 4.x copy and the
2.3.2 copy that anymatch used to pull in; anymatch and micromatch only call functions 4.x
still provides.

## The fix

`picomatch-4.0.7-lu.1.patch` changes `lib/parse.js` and `package.json` only. In
`analyzeRepeatedExtglob`, a `+(...)` or `*(...)` extglob is now treated as risky, and so
compiled as literal text (the treatment upstream already gives `*(*|x)`), unless:

- it has one branch of fixed width: literal characters, `?` and bracket expressions only,
  so every repetition consumes the same number of characters; or
- it has several branches that are all non-empty literals forming a uniquely decodable
  set (Sardinas-Patterson test), so no input can be split into branches in two ways.
  The test must see the text the regex matches, so a branch may hold only characters
  the tokenizer emits as exactly themselves: ASCII letters and digits and
  `space _ . ~ # % & ' / : ; < = > -`. Under case-insensitive matching (`nocase`, or `i`
  in `flags`) the branches are compared lower-cased.

A single fixed-width branch must not contain a backslash: the tokenizer gives escapes
regex meaning (`\w`) and collapses backslash runs so that a following `?` can become a
quantifier, so the analysis does not try to model them. Repeated extglobs whose body holds
`*`, `+`, a nested extglob, braces, quotes, a backslash or an ambiguous alternation
(`+(a|ab|b)`) now match only their literal text. Upstream's own test suite passes except
for 76 assertions, all of that kind. A numeric `maxExtglobRecursion` no longer relaxes the
guard; `maxExtglobRecursion: false` still turns it off.

## Supply-chain gate

`scripts/security/check_install_scripts.py` gate 3 fails on any dependency that does not
resolve from the npm registry. This tarball is its one exception: the
`ALLOWLIST_NON_REGISTRY` entry for `node_modules/picomatch` passes only when the lockfile
name, version, `resolved` path and sha512 integrity all equal the values above. A rebuilt
or swapped tarball, a bumped version or any other path still fails the gate, so changing
this copy means updating that entry in a reviewed commit.

## Rebuild and verify

```bash
npm pack picomatch@4.0.7   # integrity sha512-qcJu88Q2IWqJsDD529JKMdwGm/dvInW4HvQnRwiH9JtihJvzGOscDtHE3x1pBKeUOTysQ8kVmLnJ2kJu7yhcGA==
tar xzf picomatch-4.0.7.tgz
patch -p1 < vendor/picomatch/picomatch-4.0.7-lu.1.patch
chmod -R u=rwX,go=rX package
(cd package && npm pack --pack-destination ..)
```

The result is byte-identical to the committed tarball (sha256
`37659379a731a0ef8f1dfbcadbd71a84d33ee3f5596a16e7c419933332b35202`): integrity
`sha512-HV+6IOKo6ObdzotW27KfsDLfpmVnT17SViHn20M/hKLLWv9QuzjNCeap7qtv8Cq+Htk3T2Q1bNwVCbeBjZLP9Q==`,
the value of the `node_modules/picomatch` entry in `package-lock.json` and in the gate's
allowlist. When you change the patch, bump the `-lu.N` suffix, rebuild, and update the
lockfile and the allowlist entry together.

## Removal condition

Remove this copy when either holds:

- a picomatch release newer than 4.0.7 fixes GHSA-fc5q-39xc-vjpf (the advisory then names
  a first patched version): point the `picomatch` dependency in `package.json` at that
  registry release, keeping the override so the 2.x consumers get it too; or
- the advisory is withdrawn: drop the `picomatch` dependency and override from
  `package.json`.

Then regenerate `package-lock.json`, delete the `node_modules/picomatch` entry from
`ALLOWLIST_NON_REGISTRY` in `scripts/security/check_install_scripts.py`, and delete this
directory.
