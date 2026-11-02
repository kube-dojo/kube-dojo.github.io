# Content Writing Long — fixture expansion plan

## Current state

- `kubedojo-rbac-module.yaml` — long Kubernetes RBAC module-writing task that rewards TTT pedagogy, operator decisions, misconceptions, runnable checks, and Bloom L3 treatment over upstream-doc paraphrase.

## Target

- Target count: 5 fixtures.
- Current count: 1 fixture.
- Add 4 fixtures covering multiple topics and length variants.
- Keep the lane focused on long-form instructional writing, not short answer generation or generic documentation.

## Variety dimensions

- Topic 1: Kubernetes RBAC, using the existing module fixture as the baseline.
- Topic 2: Kubernetes scheduling or storage, with a scenario that requires diagnosis and operator tradeoffs.
- Topic 3: cloud platform or AWS operations, with explicit source-fidelity and safety constraints.
- Topic 4: security or supply-chain hardening, with concrete commands, warnings, and verification steps.
- Length variants: include short-long, medium-long, full module, and constrained rewrite lengths so verbosity and completeness can be calibrated separately.

## Acceptance criteria per fixture

- Passing answers cover the stated outcomes with explanations, worked examples, operator decisions, and checks that support learner practice.
- Strong answers score `judge_score>=7`, teach through decisions and checks, and avoid padding, fabricated facts, or upstream-doc paraphrase.
- Any fixture with deterministic content gates must pass those gates before qualitative judge scoring is accepted.

## Open questions

- Should each topic have its own rubric profile, or should the existing long-writing rubric be reused with fixture-specific required terms?
- What ground-truth sources are allowed for cloud and security topics, and how many citations should be mandatory?
- Who reviews long-writing fixtures for pedagogy quality before they become stable calibration cases?

## Refs

- #1413
- Memory: `feedback_single_fixture_v1_calibration.md`
