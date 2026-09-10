# Dual-repo: curriculum site + Killercoda labs

KubeDojo has two GitHub repositories. An epic driver treats them as one
program with two git roots. Never mix trees in one PR.

| | Curriculum | Labs |
| --- | --- | --- |
| Remote | `kube-dojo/kube-dojo.github.io` | `kube-dojo/kubedojo-labs` |
| Local (typical) | this checkout | sibling `../kubedojo-labs` or `$KUBEDOJO_LABS` |
| Learner surface | https://kube-dojo.github.io/ | https://killercoda.com/kubedojo/scenario/`<id>` |
| Worktrees | `.worktrees/<name>` | `kubedojo-labs/.worktrees/<name>` |
| Default line budget | ≤200 / <20 files | **explicit per-issue budget** (a coherent scenario tree exceeds 200 lines; reviewer must endorse) |

Confirm the labs path with `git -C <labs> rev-parse --show-toplevel` before
dispatch. Do not assume a hard-coded machine path in briefs.

## Layout (labs)

Scenario directories are **flat at the labs repo root**
(`linux-2.1-namespaces/`, `cka-2.1-pods/`, `prereq-0.8-servers-ssh/`).
The labs README nested tree is aspirational — do not "fix" it into
subfolders as part of a content packet.

Each scenario:

```
<id>/
  index.json      # title, details (steps), backend image
  intro.md setup.sh finish.md
  stepN/text.md  stepN/verify.sh  [stepN/solution.sh]
```

`verify.sh` must be deterministic. `setup.sh` must be idempotent.
Universal-user convention: `verify.sh` resolves `USER_HOME` via `id ubuntu`;
solutions must not hardcode `/root/...` and must `sudo` for privileged
commands (labs `#15`).

Test locally:

```bash
# from the labs repo / worktree
bash scripts/test-scenario.sh <id>
# or the CI helper
bash scripts/ci/run-lane.sh
```

The Ubuntu CI harness is **unprivileged docker** unless labs `#1` has
landed a privileged lane. Namespace / cgroup / capability scenarios may
pass locally in a privileged container and still fail the Ubuntu job —
that is a **labs `#1` residual**, not proof the scenario is wrong. Record
the class explicitly; do not "fix" by deleting the lab.

## Curriculum ↔ labs URLs

Main-repo frontmatter / buttons:

```yaml
lab:
  url: "https://killercoda.com/kubedojo/scenario/<id>"
```

`scripts/ci/check_lab_urls.py` requires that exact host/path shape. A 200
on `killercoda.com/playgrounds/scenario/kubernetes` is the **wrong**
target (generic playground). Slug mismatches (module says `prereq-0.8-servers-ssh`
while the tree only has `prereq-0.7-servers-ssh`) are G04 inventory work:
inspect semantic alignment before rewriting links.

`scripts/lab_pipeline.py` in the main repo coordinates receipts; it is
not a second lab platform. Do not create a replacement for Killercoda.

## Evidence classes (never collapse these)

| Claim | What counts | What does not |
| --- | --- | --- |
| Scenario exists | `index.json` at exact id on a revision | README count, local fixture |
| Local execution | `verify.sh` receipts (root and ubuntu-sudo when required) | Reading `text.md` |
| CI harness | GitHub Actions on that head, per lane | Ubuntu-only green ≠ Kubernetes acceptance |
| Hosted publication | Killercoda page shows the real title | git merge, HTTP 200 on a generic playground |
| Interactive hosted smoke | Operator/platform session that ran the steps | Page publication |
| Curriculum alignment | Module outcomes ↔ scenario steps + reset + env | URL string match alone |

## Content-upgrade wiring (#2272 / G04)

When driving epic
[#2272](https://github.com/kube-dojo/kube-dojo.github.io/issues/2272):

- Main **#2276** owns reproducible lab validation **and** Killercoda
  coordination.
- Labs **#2** owns the scenario portfolio and exact-path execution packets.
- Labs **#1** owns automated scenario testing / CI (including a privileged
  Kubernetes/namespace lane if still missing).
- English-first scheduling does not close labs `#2` early.

Priority-1 lab work is unsafe or unverified behavior, not "write more
scenarios." Missing exact ids are packets under labs `#2`; they need
semantic + deployed evidence, not a manifest tally.

Do **not** provision billable cloud (AWS VPC NAT, public IPv4, …) without
present-tense operator GO. Record `probe not executed` honestly.

## Hygiene

Reap merged labs worktrees in the labs repo the same way as curriculum
worktrees. Stale `feat/linux-2.*` trees after merge are disk defects.
Keep issue comments on **both** #2276 and labs #2 when a packet lands so
neither board looks idle.
