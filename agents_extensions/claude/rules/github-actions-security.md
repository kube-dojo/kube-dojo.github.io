# GitHub Actions Security

Defensive rules for `.github/workflows/**` and `.github/actions/**`. Enforced by `zizmor.yml`.

## 1. Pin every `uses:` to a full commit SHA

Format: `uses: owner/repo@<40-char SHA>  # vX.Y.Z`

Why: tags are mutable. The 2026-05-19 actions-cool incident moved every tag of two actions to imposter commits in attacker-controlled forks; only SHA-pinned consumers were unaffected. Same attack class hit `tj-actions/changed-files` in 2025-03 (CVE-2025-30066, ~23,000 repos; tags retroactively moved to a malicious commit that dumped CI/CD secrets into workflow logs). Org-agnostic — applies to `actions/*` (GitHub's own org) just as much as third-party.

The version comment matters: it tells Dependabot what tag this SHA tracks, so Dependabot updates can flow.

## 2. Resolve SHAs from the upstream repo, not from a blog post

```bash
curl -s "https://api.github.com/repos/<owner>/<repo>/git/refs/tags/<tag>" \
  | python3 -c "import json,sys; print(json.load(sys.stdin)['object']['sha'])"
```

Or with auth: `gh api /repos/<owner>/<repo>/git/refs/tags/<tag> --jq '.object.sha'`.

## 3. `persist-credentials: false` on every `actions/checkout`

Unless the workflow needs to `git push` (almost never the case for this repo's workflows), set `persist-credentials: false` on the checkout step. Prevents the `GITHUB_TOKEN` from sitting in `.git/config` for subsequent steps to exfiltrate.

## 4. Permissions scoped to the job, not the workflow

Workflow-level `permissions:` apply to all jobs. Privileged scopes (`pages: write`, `id-token: write`, `contents: write`, `packages: write`) must live on the specific job that needs them.

## 5. Dependabot `cooldown` is mandatory

`.github/dependabot.yml` MUST set `cooldown: { default-days: 7 }` (or stricter) on every `package-ecosystem` entry, especially `github-actions`. The cooldown delays Dependabot from proposing a move to a newly-published tag for N days — the exact window the security community needs to detect and disclose a tag-mutation attack. The 2026-05-19 actions-cool incident was public within hours; a 7-day cooldown would have prevented Dependabot consumers from ever auto-adopting the poisoned tags.

zizmor's `dependabot-cooldown` audit will fail the build on any ecosystem without it.

## 6. Reviewing a Dependabot github-actions PR

Even with cooldown, the PR can still be the attack delivery vector if a poisoned tag survives the cooldown window. Before merging:

```bash
# Verify the new SHA actually points to the claimed tag in the upstream repo
gh api /repos/<owner>/<repo>/git/refs/tags/<tag> --jq '.object.sha'
# Should match the SHA in the PR diff. If not, do not merge.
```

**Do not enable auto-merge on `github-actions` Dependabot PRs.** They are the single highest-impact PR class in this repo (CI runs with broad permissions).

## 7. New workflow checklist

When adding a `.github/workflows/*.yml` or `.github/actions/*/action.yml`:

1. Every `uses:` is SHA-pinned with version comment.
2. `permissions:` block is present and starts from `contents: read` minimum.
3. Privileged scopes are job-level, not workflow-level.
4. `actions/checkout` has `persist-credentials: false` unless the workflow pushes commits.
5. Run `uvx zizmor --offline --strict-collection .github/` locally — must be clean. `--strict-collection` is required; without it, an unparseable workflow silently passes.
6. CI's `zizmor` workflow (which scans `.github/` with `--strict-collection`) will re-run on the PR and block on findings.

## References

- The Hacker News, 2026-05-19: https://thehackernews.com/2026/05/github-actions-supply-chain-attack.html (actions-cool incident).
- zizmor audits: https://docs.zizmor.sh/audits/
- Memory: `feedback_actions_pin_to_sha.md`
