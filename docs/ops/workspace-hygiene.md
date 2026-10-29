# Workspace hygiene and packet closeout

Use the ignored primary-checkout registry `.agent/workspace-hygiene.json` to
record ownership and next actions. Its `worktrees` object maps absolute paths
to `owner`, `purpose`, `branch`, `head`, `state`, `next_action`, and `pr`
(number or null). States are `active`, `blocked`, `ready_to_retire`, and
`archived`. A blocked record also needs a concrete `reason`; its next action
must name a check and a date or milestone. Do not infer legacy ownership.

Before creating a worktree, record its intended path, owner, purpose, branch,
starting head, state and next action; use a null PR until known. Confirm its
actual branch and head immediately after creation and keep the record current.
Before creating task-owned temporary or evidence paths, register their owner,
purpose, retention (`retain`, `archive`, or `discard`) and next action in the
`artifacts` object. A directory entry may cover a named evidence group; inventory
its exact members before cleanup. Associate it with its packet and revision.
Retention is a decision record, not deletion authority. Prefer managed session
storage for reusable helpers instead of accumulating unowned `/tmp` copies.

From the primary checkout run:

```sh
.venv/bin/python scripts/ops/workspace_hygiene.py --check --github
```

Run it before creating the next packet, after merge and before declaring a
packet complete, before a pause or handoff, and periodically during long runs.
Resolve drift or record a concrete blocked hold with owner and next check.
Unavailable registry, inventory or required GitHub evidence is an unknown to
resolve, never a pass. Before further work, reconcile a newly registered path
that was not successfully created; do not leave a phantom active record.

The CLI checks registered metadata, Git worktree inventory and recorded PR
state/head with `--github`. It does not discover every artifact, establish
ownership or inactivity, verify preservation, or authorize deletion. A valid
blocked hold can make its metadata check pass while closeout remains unfinished.
The lead must revisit those holds at their recorded milestone.

Before authorized closeout, reconcile the packet's PR and issue state, local
and remote branches, and applicable leases or locks. Verify live heads, tracked
and untracked changes, unpushed commits, current activity and path identity.
An upstream disappearing is not merge proof. Inspect ignored files, nested
repositories and temporary paths; preserve exact heads and required source,
review, runtime and failed-attempt evidence before retiring them. Use verifiable
backups appropriate to the scope, with restore prerequisites recorded; a new
full repository copy for every packet is unnecessary.

Close or update the scoped issue only when its own acceptance criteria pass.
Reconcile stale PR, branch and lease pointers; do not close a larger parent or
source issue merely because one delivery packet merged. Conversely, an open
parent or source issue alone does not retain a fully delivered scoped packet's
worktree. A hygiene request grants no merge or publication authority by itself.

When the user requests active Git/workspace hygiene, routine task-owned
closeout is in scope after the safety evidence above is verified. This grants
no unrelated destructive action. Never force away dirty, unpushed, active,
locked, unmatched or unknown work. Follow the applicable READY checklist and
higher-priority restrictions. Record retained, removed and skipped paths,
branches and evidence locations; unresolved closeout needs an owner, concrete
reason and next check before the packet is reported complete.
