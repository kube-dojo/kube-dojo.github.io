---
title: "Git Deep Dive"
sidebar:
  order: 0
---

**Master the tool that every engineer uses daily but few truly understand.**

You already know `git add`, `git commit`, `git push`. This course takes you from "I can save my work" to "I understand the machine and can handle any situation."

Every module uses Kubernetes manifests, Helm charts, and real infrastructure files — not `hello.txt`.

---

## Modules

| # | Module | Time | What You'll Master |
|---|--------|------|--------------------|
| 1 | [Module 1: The Ghost in the Machine — Git Internals](module-1-git-internals/) | 100–140 min | .git directory, objects, SHA hashing, the DAG |
| 2 | [Module 2: The Art of the Branch — Advanced Merging](module-2-advanced-merging/) | 100–130 min | FF vs 3-way merges, conflict resolution, branching strategies |
| 3 | [Module 3: History as a Choice — Interactive Rebasing](module-3-interactive-rebasing/) | 90–120 min | Interactive rebase, squash, fixup, the Golden Rule |
| 4 | [Module 4: The Safety Net — Undo and Recovery](module-4-undo-recovery/) | 80–110 min | reset, reflog, revert — never lose code again |
| 5 | [Module 5: Multi-Tasking Mastery — Worktrees and Stashing](module-5-worktrees-stashing/) | 80–110 min | Worktrees, stash, parallel branch work |
| 6 | [Module 6: The Digital Detective — Troubleshooting and Search](module-6-troubleshooting/) | 90–120 min | bisect, blame, pickaxe search, history forensics |
| 7 | [Module 7: Professional Collaboration — Remotes and PRs](module-7-remotes-prs/) | 90–120 min | Remotes, PRs, fetch vs pull, atomic commits |
| 8 | [Module 8: Efficiency at Scale — Sparse Checkout and LFS](module-8-scale/) | 90–120 min | Sparse checkout, LFS, shallow clones, monorepos |
| 9 | [Module 9: Automation and Customization — Hooks and Rerere](module-9-hooks-rerere/) | 90–120 min | Hooks, rerere, aliases, team config |
| 10 | [Module 10: Bridge to GitOps — The Infrastructure Source](module-10-gitops-bridge/) | 80–110 min | Git as source of truth, directory patterns, ArgoCD/Flux |

These are planning estimates copied from the ten module headers, not measured learner completion times. Their arithmetic gives an aggregate range of **890–1200 minutes (about 14 hours 50 minutes–20 hours)**; individual setup, reading, and practice time will vary.

---

## Prerequisites

- [Zero to Terminal](../zero-to-terminal/) — especially Module 0.6 (Git Basics)
- Basic comfort with the command line (`cd`, `ls`, `cat`, `nano`)

## After This Course

You're ready for:
- [Modern DevOps](../modern-devops/) — the next step on the prerequisites route; CI/CD and GitOps build directly on this course
- [CKA Certification](../../k8s/cka/) — git skills used throughout exam prep
- [Linux](/linux/) — optional deeper systems knowledge if you skipped the Linux fork earlier