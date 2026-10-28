# T01-P12e: branching choices and configured GitOps revisions

Owner #2278; factual/editorial #2275 and assessment #2277. This bounded correction replaces universal workflow rankings and inevitable-failure claims with release, review and promotion decisions. It updates the branching outcome, worked decision, patterns and quiz answers together. Existing merge-base, strategy and diff-limit corrections remain; all 43 fenced bodies are unchanged.

## Primary-source verification — 2026-10-28

- [Git workflow manual](https://git-scm.com/docs/gitworkflows), Description, Graduation and Topic branches: Git documents multiple integration/maintenance branches and warns smaller projects rarely need its entire workflow. This is not a claim that all teams should copy it.
- [GitFlow author](https://nvie.com/posts/a-successful-git-branching-model/), 2020 reflection and the original branch descriptions: applicability differs between continuous delivery and explicitly versioned or multiply supported software. The page does not establish universal conflict or deployment outcomes.
- [GitHub flow](https://docs.github.com/en/get-started/using-github/github-flow), Introduction and Following GitHub flow: branch, change, pull request, review and merge; checks/protection depend on configuration. Immediate production deployment is not a required step in this guide.
- [Trunk-based development](https://trunkbaseddevelopment.com/), Introduction and smaller/scaled team variants: one shared trunk with direct-commit or short-lived review-branch approaches. This supports a workflow definition, not a mathematical guarantee against conflicts or a team-performance ranking.
- [Argo CD tracking strategies](https://argo-cd.readthedocs.io/en/stable/user-guide/tracking_strategies/), introduction, HEAD/Branch Tracking, Tag Tracking and Commit Pinning: selected manifests depend on the tracked reference; automatic sync is optional and parameter overrides can affect desired manifests. `main` is not mandatory.

The lead opened the primary pages and retained five actual captures with retrieval identities and hashes under local session228 evidence; the first three reuse verified session227 captures. The worked example and quiz are hypothetical configuration reasoning, not an Argo CD execution receipt. A production pin does not advance merely because an unrelated branch advances; actual sync and workload behavior need separate verification.

## Acceptance limits

The row remains `revise`, retaining prior review references. No full-page source clearance, numeric rubric approval, lab execution, Ukrainian fidelity or learner effect is asserted. Schema versus object-reference/runtime validation, time guidance, remaining P12 claims and full practice acceptance stay open. Exact-head independent review, branch CI, merged primary build and deployed browser verification are delivery gates recorded separately with their actual revisions.
