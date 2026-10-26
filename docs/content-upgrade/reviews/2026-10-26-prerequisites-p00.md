# T01-P00: beginner Kubernetes editorial residuals

Owner #2278; reviewed against base `2b57fdac1a0159e4af2ac7469cebb99546b14ab7` on 2026-10-26. This is a scoped correction of N5, N6, remaining N7 and Kubernetes-hub N8 from [the prior independent review](https://github.com/kube-dojo/kube-dojo.github.io/pull/3536#issuecomment-6389933630), not a new full-page review or acceptance. Preserve the [full-page findings](2026-10-24-prerequisites.md) and their subsequent correction history.

## Findings and disposition

Paths are relative to `src/content/docs/`; locations below describe the base revision.

| Finding | Evidence | Correction |
|---|---|---|
| N5 | Kubernetes introduction line109 describes what the teaching commands do instead of asking the learner to reason | Ask whether a client connection error proves application containers stopped, and what other evidence is needed |
| N6 | Introduction line166 uses unexplained `k`, despite its full-command convention | Use `kubectl` |
| N7 | Deployments line37 says “violently recover” and “aggressively protects user availability” | Explain replica/template intent and diagnosis with readiness, application health and capacity limits |
| N8 | Kubernetes Basics hub line10 promises secure sensitive-data handling and confident operation | Name practiced skills and explicitly retain Secret access/storage responsibilities |

All three supplied page dispositions remain **revise**: the named residuals are corrected, while exhaustive source, editorial, assessment and applicable practical evidence remain incomplete. No D1–D8 scores or acceptance assertion is supplied. The cloud-native hub is unchanged.

## Source checks

Checked the versioned official Kubernetes 1.35 documentation on 2026-10-26 for the changed claims:

- [Deployment desired state and controller](https://v1-35.docs.kubernetes.io/docs/concepts/workloads/controllers/deployment/), opening paragraphs and Creating a Deployment: replica/template intent, ReplicaSet responsibility and rollout observation support the bounded replacement paragraph.
- [Deployment status](https://v1-35.docs.kubernetes.io/docs/concepts/workloads/controllers/deployment/#deployment-status): readiness and insufficient capacity can affect progress; controllers do not guarantee service availability.
- [Secrets caution](https://v1-35.docs.kubernetes.io/docs/concepts/configuration/secret/#caution): independent Secret creation separates sensitive data from application code/images; encryption at rest and least-privilege access remain necessary protections.
- [Control-plane components](https://v1-35.docs.kubernetes.io/docs/concepts/overview/components/#control-plane-components): the API server exposes the Kubernetes API. A client connection error alone does not establish that application containers stopped.

These checks support the changed claims only; they do not clear every assertion in the full pages. The hub's concrete practice description is supported by its eight linked lessons, including the existing guarded Deployment example and cleanup exercise.

## Verification and limits

- Both modules pass enabled structural gates with URL reachability probes skipped; this is not source completeness or pedagogical acceptance.
- Every fenced block is byte-for-byte equal to the base: 17 in the introduction and 25 in Deployments, including guard, cleanup, YAML and diagrams. No code was changed or newly executed against a cluster.
- Worktree pipeline suite: 176 tests passed. No Python files changed; Ruff is not applicable. Diff/receipt integrity and exact-head independent review remain delivery gates.
- The pre-submit primary build tests the stated main base, not this unmerged worktree. Proposed content requires branch CI; publication/render checks must be recorded after delivery.
- Preserve [#2306](https://github.com/kube-dojo/kube-dojo.github.io/pull/2306)'s exact historical kind1.35 execution receipt; no new real-cluster, hosted-lab, Ukrainian or learner-study evidence is claimed.
