---
title: "Module 5: Multi-Tasking Mastery - Worktrees and Stashing"
prerequisites: "Module 4 of Git Deep Dive"
next_module: "[Module 6: The Digital Detective](../module-6-troubleshooting/)"
revision_pending: false
sidebar:
  order: 5
---

> **Complexity**: `[MEDIUM]`
>
> **Time to Complete**: 80–110 minutes (unmeasured planning estimate for reading and local practice)
>
> **Prerequisites**: Module 4 of Git Deep Dive

---

## What You'll Be Able to Do

By the end of this module, you will be able to:

- Implement `git worktree` to manage concurrent development efforts across multiple branches without disrupting your primary working directory.
- Diagnose and resolve orphaned or disconnected worktrees using lifecycle commands like `prune` and `remove`.
- Evaluate the precise technical trade-offs between `git stash`, `git worktree`, and multiple repository clones to select the optimal context-switching strategy for a given scenario.
- Execute advanced stash operations, including isolating untracked files, applying specific stashes from the stack, and recovering stashed changes into isolated branches.
- Design a resilient local development workflow that prevents uncommitted state loss during critical, time-sensitive production interruptions.

## Why This Module Matters

Hypothetical scenario: it is late afternoon at a regional payments company during a planned Kubernetes platform upgrade. A senior engineer is halfway through refactoring an ingress controller deployment, with modified YAML files, half-written Go tests for a custom admission webhook, and a local cluster tuned to reproduce a routing edge case. Then security pages the team: a vulnerable production image has to be replaced immediately, before the next merchant settlement window opens. The change itself is tiny, but the operational risk is not tiny at all, because a broken hotfix could block payment authorization and put revenue at risk during a narrow production window.

In that hypothetical, the engineer reaches for `git stash`, switches to the production branch, makes the image update, and pushes the hotfix. That first part looks successful, but the return trip is painful. The stash does not include a newly created manifest because the file is still untracked, and `git stash pop` collides with the same deployment block that the emergency patch changed. The fix prevents customer-visible impact, yet the team pays for the rushed context switch with hours of conflict resolution, repeated local cluster resets, and a delayed review of the original ingress refactor.

This module is about preventing that class of avoidable disruption. Git branches are cheap, but a normal clone gives you only one working directory, and real engineering work rarely arrives one task at a time. You will learn when a stash is the right short-term scratchpad, when a linked worktree is the safer architecture, and when a second clone is still justified. By the end, you should be able to leave unfinished work exactly where it is, handle an interruption in a clean directory, and return without relying on memory or luck.

## The Context Switch Problem

A standard Git clone has two pieces that matter during daily development: the repository database and the working tree. The repository database stores objects, refs, branch names, remote-tracking state, and configuration. The working tree is the visible directory where your editor, tests, linters, and local tools interact with files. In the simplest setup, those two pieces feel inseparable because the `.git` directory sits beside the files you edit, but Git treats them as distinct layers.

When you run `git switch` or `git checkout`, Git rewrites the working tree to match the target commit. That rewrite is safe only when your current directory can be moved to the new branch without overwriting uncommitted work. If you have modified tracked files, staged changes, or untracked files that collide with paths on the target branch, Git may refuse the switch. If the paths do not collide, Git may allow the switch and carry your dirty state forward, which is often worse because unfinished feature work can accidentally ride into a hotfix branch.

The practical lesson is that a branch is not the same thing as a workspace. A branch names a line of history; a workspace is a directory, an index, editor state, test artifacts, environment variables, and your own mental context. Many early Git users learned branches first and assumed they solved context switching by themselves. Branches solve the history problem, but they do not give you two independent working directories unless you create a second clone or a linked worktree.

Compare two possible workarounds. One is to clone the repository again for a new task, release check, or urgent review. Another is to save uncommitted work in a stash, switch branches, handle the interruption, switch back, and restore it. Both are options rather than universal defaults: consider which repository state and runtime resources each approach actually separates before choosing one.

Multiple clones give you separate repository-local refs, configuration, working trees, and indexes. That can be useful when repository-level settings must differ, but a clone does not automatically isolate global credential helpers, hooks selected by global configuration, or runtime services. Local clones may also share object storage through hardlinks or explicit alternates. The cost is another repository to maintain: each clone needs its own fetches, and a local branch in one does not automatically exist in another. Choose the required boundary deliberately; a clone is not a hermetic test environment.

There is also a coordination cost that does not show up in disk usage. In a multi-clone workflow, each directory can quietly develop its own local branches, remotes, ignored files, hook state, and unpushed commits. When a teammate asks which directory contains the fix, the answer may depend on memory rather than repository state. Linked worktrees remain attached to one repository database, and `git worktree list` inventories registered worktrees, including records whose directories are missing.

Stash has the opposite shape. It is lightweight and local, but it stores a patch-like snapshot whose context is easy to forget. A stash entry records the state of tracked modifications, and with the right flags it can include untracked or ignored files, but it does not preserve your open terminals, local database state, running cluster, or exact mental stack. It is a temporary shelf, not a parallel desk. The longer a stash sits while the branch underneath it changes, the more likely the return path turns into conflict recovery.

That distinction is why the right question is not "Is stash bad?" but "What kind of state am I saving?" If the state is a two-line formatting cleanup before a pull, stash is appropriate. If the state includes half a feature, a failing test, a running cluster, and a branch that may be interrupted for a day, stash is hiding too much context behind a single stack entry. A senior workflow makes that difference explicit before the interruption starts.

**Pause and predict:** What do you think happens if you run `git stash` while a new file exists in your directory but has never been added with `git add`? Write kept or stashed before opening the answer.

<details>
<summary>Check your prediction</summary>

By default, `git stash` saves tracked modifications and staged changes, but it leaves untracked files alone. That behavior surprises engineers because a dirty `git status` can contain both tracked and untracked state, while the plain stash command captures only part of it. If the untracked file does not collide with the branch you switch to, it remains visible in the new branch. If it does collide, Git may block the branch switch or force you to decide what to do at the worst possible moment.

</details>

## Mastering Git Stash for Micro-Interruptions

Stash is still worth mastering because not every interruption deserves a new directory. If you are about to pull upstream changes, run a formatter, or briefly inspect another branch, a named stash can be faster than making a worktree. The key is to treat stash as a precise tool for micro-interruptions, not as a general-purpose storage locker for unfinished projects. Good stash usage starts with context, includes the right files, and restores with a reversible command.

Never run a bare `git stash` when the work matters. The default message usually says something like `WIP on branch-name`, which is enough for the next thirty seconds and nearly useless after lunch. Use `git stash push -m` so future you can connect the entry to a real task, file, or experiment. The message is cheap insurance because the stash stack is indexed by position, and those positions shift as new entries are added or removed.

```bash
# Bad practice
git stash

# Good practice
git stash push -m "Mid-refactor of deployment.yaml resource limits"
```

When your work includes new files, add the `-u` or `--include-untracked` flag. This is common in infrastructure repositories because a feature might introduce a new Kubernetes manifest, a values file, a migration, or a test fixture before it is ready for staging. Using `-u` tells Git to stash tracked modifications and untracked files together, which makes the saved state more complete. It does not include ignored files such as build outputs unless you use the stronger `-a` flag.

```bash
# Stashes tracked modifications AND untracked new files
git stash push -u -m "Added new redis-deployment.yaml and modified configmap"
```

The `-a` or `--all` flag includes ignored files too. That can help when you intentionally need to clear ignored artifacts from a directory, but those files also become Git objects in the saved state. Choose `-u` when you need untracked source files while leaving ignored caches and build directories in place; use `-a` only when including those ignored files is intentional.

Every stash entry goes onto a stack, with the newest entry at `stash@{0}`. You can inspect the stack before applying anything, and you should do that whenever more than one entry exists. The command below is not just a convenience; it is a guard against applying the wrong patch to the wrong branch. A stash message that looked obvious yesterday may be ambiguous after two incident calls and a review rotation.

```bash
git stash list
```

The output will look something like this:

```text
stash@{0}: On feature-auth: Added new redis-deployment.yaml and modified configmap
stash@{1}: On main: Mid-refactor of deployment.yaml resource limits
```

Before applying a stash, inspect it as a patch. The `show -p --include-untracked` options let you review tracked and saved untracked content without changing your working directory. Plain `show -p` omits untracked content unless configured otherwise. This distinction matters when stashes contain migrations or manifests with similar names across environments: inspect the complete saved content before restoring it.

```bash
git stash show -p --include-untracked stash@{1}
```

**Pause and predict:** What do you expect if you apply `stash@{1}` rather than pop it? Write whether the stash stack changes before opening the answer; then compare your prediction with `git stash list`.

<details>
<summary>Check your prediction</summary>

Use `git stash apply` when you want to retain the saved entry during restoration. It attempts to put changes into the current working tree while leaving the entry on the stack. If it conflicts, stop and inspect `git status`; there is no `git stash --abort`. Preserve any unrelated edits before resolving or discarding the failed replay. The saved stash remains available for recovery from a clean directory. Add `--index` when you also intend to restore the original staged state; conflicts can prevent that restoration.

</details>

```bash
# Applies the most recent stash
git stash apply

# Applies a specific stash from the stack
git stash apply stash@{1}
```

`git stash pop` is convenient, but convenience is not the same as safety. Pop applies the stash and, when the application succeeds, drops the entry from the stack. That behavior is fine for trivial edits, but it becomes risky when you are tired, on the wrong branch, or dealing with configuration files whose conflicts are subtle. For critical infrastructure work, apply first, inspect and test the result, and only then drop the stash intentionally.

```bash
# Drop a specific stash
git stash drop stash@{1}

# Clear the entire stash stack (use with extreme caution)
git stash clear
```

For an old or conflict-prone stash, consider `git stash branch` from a clean working tree. It creates a branch at the original base, restores the working tree and index, and drops the entry on success when you supply a `stash@{…}` reference or omit the stash argument (which selects the latest entry). Passing a raw stash commit ID does not drop an entry from the list. This reconstructs the patch's original context. It cannot switch successfully through unresolved conflicts from a previous apply; preserve that state and use a separate clean worktree if needed. Commit the recovered work before normal integration.

```bash
git stash branch recovered-auth-work stash@{0}
```

Here is a small practice workflow for the untracked-file trap. Use a fresh temporary directory and a fictional repository-local identity; signing is disabled only in this disposable repository. Setting `core.excludesFile` to `/dev/null` prevents global ignore patterns from affecting this practice. The new `draft-config.txt` contains harmless placeholder content. Never use real credentials in stash practice: stashed files become Git objects, including files captured with `-u` or `-a`.

```bash
stash_practice_root=$(mktemp -d)
cd "$stash_practice_root"
mkdir stash-practice && cd stash-practice
git init -b main
git config user.name "Practice Learner"
git config user.email "learner@example.invalid"
git config commit.gpgsign false
git config core.excludesFile /dev/null
```

Create an initial commit so the repository has a clean baseline. Git stash depends on a repository with commits because it needs a `HEAD` commit as the reference point for the saved changes. In a brand-new repository with no commit, many normal history operations do not yet have a stable anchor.

```bash
echo "v1" > config.txt
git add config.txt
git commit -m "Initial commit"
```

Now create one tracked modification and one untracked file. This gives you a realistic dirty state: part of the work is visible as a modification to a tracked file, and part of it is visible only as a new path. That mixed state is where many stash mistakes start, because a quick glance at `git status` may not translate into the right stash flags.

```bash
echo "v2" > config.txt
echo "example-local-value" > draft-config.txt
```

Stash both pieces together with `-u`. After this command, the working tree should return to a clean state and the untracked file should disappear from the directory because it has been saved inside the stash entry. This is the behavior you want before switching into a review or a tiny branch inspection.

```bash
git stash push -u -m "WIP on tracked and draft config"
```

Inspect the stash stack and the complete saved patch before restoring. The explicit `--include-untracked` flag shows `draft-config.txt` as well as the tracked change to `config.txt`. Check both contents so you can distinguish a saved file from a file merely left behind in the working directory.

```bash
git stash list
git stash show -p --include-untracked stash@{0}
```

Finally, restore with `apply`. Confirm that `config.txt` contains `v2`, `draft-config.txt` has returned, and the entry remains in `git stash list`. This separates restoration from deletion. Keep the stash until you have checked the contents; the cleanup below intentionally deletes the entire disposable practice repository, including its saved entry.

```bash
git stash apply stash@{0}
git status --short
cat config.txt draft-config.txt
git stash list
```

When you are finished experimenting, remove only the generated disposable root and its contents. Do not use this command for a real worktree or repository:

```bash
cd / && rm -rf -- "${stash_practice_root:?}"
```

## The Power of Git Worktrees

If stash is a temporary shelf, a worktree is a separate desk connected to the same filing cabinet. Git introduced linked worktrees so one repository database can support multiple working directories, each with its own checked-out branch and index. The main advantage is that you do not have to clean, stash, or commit unfinished work before opening a clean directory for another task. Your feature branch can remain dirty in one terminal while a hotfix branch is clean in another.

Linked worktrees share the object database and ordinary refs, including branch and remote-tracking refs; `HEAD` and certain special refs remain per-worktree. A linked worktree stores checked-out files plus small administrative metadata rather than duplicating repository history. Fetching in one updates shared remote-tracking refs, but does not update the other worktrees' checked-out files. This gives you independent file views with a shared repository inventory.

The isolation is not absolute, and that distinction matters. Each worktree has its own working directory and index, so staged changes and uncommitted file edits do not bleed between them. However, global services such as a single local database, fixed ports, shared Docker networks, and editor-wide settings can still collide. A team running two Kubernetes test environments from two worktrees must still choose separate namespaces, ports, or clusters. Worktrees solve Git workspace contention; they do not automatically isolate every tool outside Git.

The index isolation is one of the most underrated benefits. Staging is local to the worktree, so you can have a carefully staged patch in the feature directory while the hotfix directory has a completely different staged patch. This matters for review quality because `git diff --cached` remains focused on the task in front of you. A stash records the index separately, but restoring without `--index` can lose the staged and unstaged split.

Use a named branch for temporary work: create `hotfix/image-patch`, commit the fix, and push it when you need backup or review. Removing the linked directory leaves its branch and commits available. A branch name may later be deleted, so preserve the relevant commit or pull-request reference rather than treating a temporary directory name as a permanent audit trail.

When you run `git clone`, you create the main worktree. Inside that directory, the `.git` directory stores objects, refs, configuration, and, once linked worktrees are added, their administrative metadata. The diagram marks the directory created for linked worktrees as conditional.

```mermaid
flowchart TD
    subgraph MainWorktree ["Main Worktree: /projects/k8s-operator"]
        deploy["deploy/"] ~~~ src["src/"]
        src ~~~ gomod["go.mod"]
        gomod ~~~ dotgit[".git/  <-- The actual repository database"]
        
        dotgit --> objects["objects/"]
        dotgit --> refs["refs/"]
        dotgit -.-> worktrees["worktrees/  <-- Created on add; linked-worktree administrative data"]
    end
```

When you add a linked worktree, Git creates a new directory with normal project files, but the `.git` entry inside that directory is a file rather than a full repository directory. That file points back to metadata under the main repository's `.git/worktrees/` directory. The linked worktree gets its own `HEAD`, its own index, and its own administrative state, while the actual object database remains shared.

```mermaid
flowchart TD
    subgraph LinkedWorktree ["Linked Worktree: /projects/k8s-operator-hotfix"]
        deploy["deploy/"] ~~~ src["src/"]
        src ~~~ gomod["go.mod"]
        gomod ~~~ dotgit[".git FILE points to private metadata<br/>under /projects/k8s-operator/.git/worktrees/"]
    end
```

The standard creation command is `git worktree add`. You provide a path for the new directory and the branch or commit you want checked out there. In many interruption workflows, you also create a new branch at the same time with `-b`. That lets you leave a dirty feature branch untouched, create a clean hotfix branch from `main`, and start working in a sibling directory.

```bash
# Usage: git worktree add <path> <branch>

# Create a new directory alongside your current one,
# create a new branch called 'hotfix-cve',
# and check it out starting from 'main'
git worktree add -b hotfix-cve ../k8s-operator-hotfix main
```

Illustrative output; your commit ID and subject will differ:

```text
Preparing worktree (new branch 'hotfix-cve')
HEAD is now at 8f3a9b2 Update ingress documentation
```

At this point you have two separate directories connected to one repository database. Your original directory can contain uncommitted feature work, while `../k8s-operator-hotfix` starts clean on the hotfix branch. You can open a new terminal, run tests, commit, and push from the hotfix worktree. When the emergency ends, you remove the temporary worktree and return to the original terminal without replaying a stash or reconstructing your thought process.

By default, Git refuses to check out a branch already checked out in another worktree. This prevents competing updates to one branch pointer. Force options can override the protection, so treat it as a guardrail rather than an absolute invariant. Prefer a new branch name or a deliberately detached worktree for the same starting point; named branches make new work easier to retain.

**Pause and predict:** What do you expect if you try to create a worktree for a branch already checked out in another worktree? Write the result before opening the answer.

<details>
<summary>Check your prediction</summary>

By default the command fails. In a Git 2.56 run, the message was `fatal: 'hotfix-cve' is already used by worktree at '…'`. Imagine two terminals both claiming to own `feature/auth-refresh`, each with a different index and different uncommitted files. The default guard prevents competing checkouts; if you see this error, list your worktrees before forcing anything.

</details>

```bash
git worktree list
```

The output gives you the path, commit, and branch or detached state for each worktree. Before deleting branches or cleaning directories, inspect this inventory and each relevant directory's status. The paths and IDs below are illustrative; listing worktrees does not establish that their edits or unpushed commits have been preserved.

```text
/projects/k8s-operator         8f3a9b2 [feature-auth]
/projects/k8s-operator-hotfix  2c9b4e1 [hotfix-cve]
```

When you finish with a worktree, remove it through Git. The command deletes the directory and cleans the matching metadata under the main repository. Git will refuse to remove a worktree that contains uncommitted changes unless you force it, which is another useful guardrail. If the worktree contains commits that have not been pushed or merged, pause and decide whether to keep the branch before removing the directory.

```bash
# Removes the linked directory and its metadata; keeps its branch and commits
git worktree remove ../k8s-operator-hotfix
```

The common failure mode is deleting the directory with the operating system, for example with `rm -rf`, instead of using `git worktree remove`. The files disappear, but the main repository can retain metadata saying that the branch is in use. That record can block another checkout until manually pruned or eventually removed by automatic garbage collection after expiry.

```bash
git worktree prune
```

`git worktree prune` removes stale administrative records, not lost files. Inspect `git worktree prune -n -v` first, and confirm the directory was deleted rather than temporarily unmounted. Lock portable worktrees before they become unavailable. If a directory was moved, use `git worktree repair <new-path>` to reconnect it instead. Normal cleanup uses `git worktree remove`, which protects dirty directories without requiring force.

## Kubernetes Interruption Workflow

Worktrees become especially valuable in Kubernetes repositories because the source files are only part of the local state. A change to a Deployment may be tied to a running cluster, a port-forward, generated manifests, and a failing integration test. Stashing the source files does not reset those external systems, and carrying dirty YAML into a production hotfix branch can produce misleading tests. A separate worktree gives the hotfix a clean file view while allowing you to decide separately how to isolate the cluster.

Suppose you are developing a reliability upgrade for a Deployment. Git itself does not require Kubernetes tooling, but platform repositories often mix Git operations with manifest validation.

For a local test, the unfinished feature might include probes, resource requests, and image changes. Those are exactly the fields an emergency hotfix might also need to touch. If you stash the feature, switch to `main`, update the image, and return later, you are betting that the same manifest regions did not drift in incompatible ways. If you create a worktree from `main`, the hotfix starts from the production file while the feature file stays physically open in the original directory. That physical separation is useful when your editor has multiple tabs open, your terminal history is full of feature-specific commands, and your local notes refer to paths in the original directory.

The worktree does not automatically give you a second Kubernetes cluster, so design that part deliberately. For a deeper controller change, you might use a separate cluster or a separate namespace so hotfix validation does not share resources with the feature branch. The Git decision and the runtime-environment decision are related, but they are not the same decision.

Consider recording this separation in a runbook: "Create a worktree from the verified production base, choose the required runtime isolation, validate the hotfix diff, and remove the worktree after preserving the fix." This is a workflow recommendation, not a measured incident-response improvement. Its purpose is to make the source and runtime boundaries explicit before an interruption; `main` is suitable only when it represents the production base you intend to patch.

Exercise scenario: a realistic operator team can use this split during incident response. Alice is building automated backup support for a database operator, with many modified Go files, new CustomResourceDefinition manifests, and a local cluster configured to test backup scheduling. Production then reports a leader-election crash. The stash approach asks Alice to package a complex feature as a patch, change branch context, run a different investigation in the same directory, and later reapply the patch over a branch that may have moved. The worktree approach asks Alice to open a clean sibling directory from `main`, fix the leader-election code there, and leave the backup work untouched.

The difference is not merely comfort. During an incident, reducing accidental coupling is an operational control. A clean hotfix worktree makes it easier to see which files changed, easier to run focused tests, and easier to produce a reviewable commit. The original feature directory remains dirty, but that dirtiness is contained. When the incident ends, Alice does not need to remember whether a local manifest belonged to the feature or the hotfix; the directory boundary preserves that answer.

## Patterns & Anti-Patterns

The first durable pattern is the sibling-directory worktree. Keep the main clone in a stable location and create temporary worktrees beside it with names that explain their purpose, such as `../operator-hotfix-leader-election` or `../site-review-pr-812`. The path name becomes operational documentation when `git worktree list` is printed during a busy day. This pattern scales well because every worktree shares fetched refs, while the directory name communicates why it exists.

This naming discipline sounds minor until a team has several temporary directories open during a release week. A directory named `../tmp2` tells you nothing about whether it can be deleted, while `../operator-hotfix-leader-election` tells you the branch purpose before you even run Git. When the name, branch, pull request, and test namespace line up, cleanup becomes a simple verification step instead of an archeology project.

The second pattern is apply-before-drop for stash recovery. Use `git stash apply`, run `git status`, inspect the diff, and run a small validation before dropping the stash. That extra minute protects you from deleting the only copy of a patch that was applied in the wrong place. It also creates a natural checkpoint: once the restored work is committed or deliberately abandoned, the stash can be removed with confidence.

The third pattern is branch-from-stash for old work. If a stash is more than a short interruption old, assume its original context matters. `git stash branch` reconstructs that context better than a direct apply against a branch that has evolved. This pattern turns a risky patch replay into a normal branch integration problem, which is easier to review and easier to undo.

The fourth pattern is environment naming that follows the worktree. If a worktree exists for `hotfix/image-patch`, give its local namespace, database, or cluster a matching name when practical. The exact command depends on the tool, but the principle is stable: directory isolation should be paired with runtime isolation when tests mutate external state. Otherwise two worktrees can still compete for port bindings, test databases, or Kubernetes resources.

The most common anti-pattern is treating stash as a filing cabinet. A stack of unnamed WIP entries is not a backlog; it is deferred confusion. Teams fall into this because stash is fast and because Git makes it easy to hide mess temporarily. The better alternative is to make a WIP commit on a branch when the work is meaningful, or create a worktree when another task needs a clean directory.

Another anti-pattern is force-removing worktrees as routine cleanup. `git worktree remove -f` exists for exceptional cases, but regular use trains you to ignore Git's warning that uncommitted changes exist. If a temporary worktree has valuable edits, commit them, stash them with a message, or consciously discard them after inspection. The safest cleanup path is boring: list, status, remove.

A subtler anti-pattern is assuming that worktrees replace branches. They do not. A worktree is a directory attached to a branch, detached commit, or new branch. The branch still carries history, review identity, and push behavior. If you use detached worktrees casually, you can create commits that are easy to lose because no branch name points at them. For normal team work, create a named branch with `-b` and push it like any other branch.

The last anti-pattern is using worktrees to avoid committing for too long. Worktrees let you keep tasks separate, but they do not remove the need for small commits and reviewable history. If three worktrees each contain days of uncommitted work, you have traded one crowded directory for three hidden risk piles. Commit meaningful checkpoints, push branches that need backup or review, and remove temporary directories when their purpose ends.

## Decision Framework

Choose the tool by asking what isolation you need and how long the interruption will last. For simple dirty edits, a named stash can be appropriate. For a separate file view and index, use a worktree. For per-worktree settings, consider `extensions.worktreeConfig` and `git config --worktree`; for independent repository-local refs, consider another clone. In either case, configure credentials, hooks and runtime services separately when those boundaries matter; directory creation alone does not provide that isolation.

**Pause and predict:** Which approach would you choose here and why? Your colleague asks you to review a pull request that changes two files, you have no uncommitted work, and you expect the review to take ten minutes. Write stash, worktree, or branch switch before opening the answer.

<details>
<summary>Check your prediction</summary>

If your working tree is clean and the review is tiny, switching branches in the current directory is reasonable. A worktree is still a good option when you want to preserve editor context, keep your current branch visible, or run tests without disturbing local artifacts. The important point is that worktrees are not mandatory for every branch switch; they are valuable when the cost of mixing contexts exceeds the cost of another directory.

</details>

| Scenario | Recommended Strategy | Technical Rationale |
| :--- | :--- | :--- |
| **Pulling latest changes** with a small dirty edit. | Named stash, if needed | Inspect and save the intended files first. Pull and later stash application can both conflict; with a clean tree no stash is needed. |
| **Emergency production hotfix** while mid-feature. | `git worktree` | The hotfix requires a clean state and may take hours. You need a strong guarantee that feature code will not leak into the hotfix. |
| **Reviewing a colleague's massive pull request** while working on your own code. | `git worktree` | Reviews often require running code, editing configuration, and executing tests. A separate directory keeps review experiments away from feature work. |
| **Testing another Kubernetes version** with different repository settings. | Per-worktree config or `git clone` | Worktree-specific config can separate settings; a clone also separates refs. Both require deliberate runtime and credential isolation. |
| **Trying a speculative refactor that you might throw away.** | `git branch` in the current tree | If your tree is clean, a normal branch and a WIP commit may be enough. Stash is unnecessary when you can preserve the experiment in history. |

One way to operationalize the framework is to set team conventions. For incident response, consider a worktree. For a small pull-before-push interruption, consider a named stash. If a reproduction needs a fresh clone, configure credentials and hooks at the intended scope as well. Document the chosen boundaries so teammates can identify which local directory and runtime resources belong to the task.

The framework should also account for the cost of return. A context-switch tool is successful only if returning to the original task is boring. Stash has a low start cost but can have a high return cost when patches conflict or messages are vague. A worktree has a slightly higher start cost because it creates a directory and often a branch, but its return cost is usually just changing terminals. A clone has the highest start and maintenance cost, so reserve it for cases where shared repository state would itself be a problem.

## Did You Know?

1. Git 2.5 (July 2015) introduced linked worktrees experimentally as a replacement for `contrib/workdir/git-new-workdir`. The old helper is historical context; the practice below uses `git worktree`.
2. A stash entry is built from internal commits that record the working tree and the index; it is not just a loose diff file tucked away on disk.
3. Without force, Git rejects a second checkout of the same branch in another worktree, protecting its pointer from competing directory updates.
4. The `git worktree prune` command removes stale metadata when a linked worktree directory was deleted outside Git, but it is not a substitute for normal `git worktree remove` cleanup.

## Common Mistakes

| Mistake | Why It Happens | How to Fix It |
| :--- | :--- | :--- |
| **Losing new files in a stash** | Running `git stash` without `-u` leaves newly created untracked files in the working directory, so they follow you into the next branch. | Use `git stash push -u -m "clear context"` when the dirty state includes new source files. |
| **Stash stack amnesia** | Bare `git stash` creates generic messages that do not explain why the entry exists once more work has happened. | Always use `git stash push -m "specific task and file context"` and inspect with `git stash list`. |
| **Orphaned worktree directories** | Deleting a worktree folder with `rm -rf` removes files but can leave metadata marking the branch as in use. | Prefer `git worktree remove <path>`; inspect and prune stale records, or repair a moved worktree. |
| **Popping onto the wrong branch** | `git stash pop` applies and then deletes the entry after a clean application, leaving little room to reconsider. | Default to `git stash apply`, verify the result, and then run `git stash drop` deliberately. |
| **Trying to check out a branch in use** | By default Git rejects a branch already checked out in another worktree. | Run `git worktree list`, switch or remove the other worktree, or create a new branch for the second directory. |
| **Ignoring environment bleed** | Worktrees isolate Git files and indexes, but shared ports, databases, clusters, and credentials can still collide. | Pair worktree isolation with separate namespaces, ports, clusters, or local configuration when tests mutate external state. |
| **Using detached worktrees casually** | Checking out a commit without a branch can make new commits harder to find and push. | Use `git worktree add -b <branch> <path> <start-point>` for normal team work. |

## Quiz

<details>
<summary>Question 1: You are deep into modifying a Helm chart for a reliability upgrade when an urgent production image patch must be made on `main`. Your current directory has uncommitted YAML and generated test fixtures. What workflow should you choose, and why?</summary>

Use `git worktree add -b hotfix/image-patch ../project-hotfix main` and make the production patch in that new directory. The hotfix needs a clean working tree, and your feature has enough uncommitted state that a stash would become a risky patch replay. A worktree keeps the hotfix commit reviewable because only hotfix files are visible there. It also lets you return to the original directory without reapplying anything.
</details>

<details>
<summary>Question 2: You stashed work before helping a colleague, then returned two days later after the target branch had changed heavily. A direct apply produces painful conflicts. What should you try next, and what problem does it solve?</summary>

First inspect and preserve the conflicted working tree; a direct `git stash branch` cannot switch through unresolved index entries. One recovery route is `git worktree add --detach ../stash-recovery HEAD`, followed by `git -C ../stash-recovery stash branch recovered-work stash@{0}` using the entry you inspected. The clean directory lets Git restore the stash at its original base without deleting the failed replay. Successful branch recovery drops the shared stash entry, so commit the recovered work and inspect both directories before cleanup.
</details>

<details>
<summary>Question 3: A teammate deleted `../testing-env` with the file manager. Now Git refuses to check out `test-deployment`, saying it "is already used by worktree at" that path. How do you diagnose and repair the state?</summary>

Run `git worktree list` and `git worktree prune -n -v`. Confirm the path was actually deleted, rather than moved or temporarily unmounted, then run `git worktree prune`. Prune removes stale metadata; it cannot recover deleted uncommitted files. Use `repair <new-path>` for a moved directory and lock portable worktrees before disconnection. Future cleanup should use `git worktree remove` so Git can protect dirty files and update metadata together.
</details>

<details>
<summary>Question 4: You created a new Python script but did not run `git add`. After `git stash` and a branch switch, the script is still present in the new branch. Why did that happen, and how would you avoid it?</summary>

Plain `git stash` does not include untracked files. The new script had no index entry, so Git left it in the working directory during the stash operation. If the target branch did not have a tracked file at the same path, the file remained visible after the switch. Use `git stash push -u -m "message"` when new source files are part of the temporary state.
</details>

<details>
<summary>Question 5: You need to compare behavior against a different Kubernetes version and also use different credentials and hooks. A teammate suggests a worktree because it saves disk space. What concern should you raise?</summary>

A worktree isolates the working directory and index, but it still shares the repository database and may share global Git configuration, hooks strategy, credentials, editor settings, and local services. Per-worktree configuration can separate settings; a clone can separate refs and repository-local configuration. Neither automatically isolates credentials or runtime services. The right decision depends on what must be isolated.
</details>

<details>
<summary>Question 6: You have three stashes and suspect `stash@{1}` contains database migration work. Your current branch is clean, but applying the wrong stash would waste time. What should you do before restoring it?</summary>

Run `git stash list`, then `git stash show -p --include-untracked stash@{1}`. These inspection commands leave your working files unchanged. The explicit flag includes saved untracked files, which plain `show -p` normally omits. Confirm the intended files and contents, apply the inspected entry, and verify the result before dropping it. Add `--index` if restoring its staging state matters.
</details>

<details>
<summary>Question 7: Your team uses worktrees for every incident, but two incident worktrees keep failing tests because both try to bind the same local port and use the same namespace in a shared cluster. Did Git worktrees fail here?</summary>

No. Git worktrees solved the source-directory and index isolation problem, but they did not isolate external runtime resources. Shared ports, shared databases, shared clusters, and shared namespaces can still collide across directories. The fix is to pair each worktree with environment isolation such as separate namespaces, dynamic ports, or separate clusters. Treat worktree creation as one part of the incident workspace, not the whole workspace.
</details>

## Hands-On Exercise: The Mid-Flight Hotfix

In this local Git simulation, you will leave a reliability upgrade uncommitted, create a clean hotfix worktree from `main`, commit an image-tag edit there, and return. You need Git, a POSIX shell, `mktemp`, and file utilities including `mkdir`, `cat`, `sed`, and `mv`; the commands were tested with Git 2.56. Kubernetes tools, a cluster, and network access are not required. The `fleet-api` images and health endpoint are fictional placeholders: this exercise proves file/history separation, not image availability, manifest acceptance, security remediation, or application health.

Start in a temporary directory so the practice repository can be deleted when you are done. The first repository represents your normal development workspace. It begins with a stable production Deployment so there is a clean `main` branch to patch during the interruption.

```bash
worktree_practice_root=$(mktemp -d)
cd "$worktree_practice_root"
mkdir k8s-fleet-manager && cd k8s-fleet-manager
git init -b main
git config user.name "Practice Learner"
git config user.email "learner@example.invalid"
git config commit.gpgsign false
```

Create the stable base state. This manifest is intentionally minimal so the difference between production and unfinished feature work is easy to see. Commit it before starting the feature branch because the hotfix worktree needs a real `main` commit as its starting point.

```bash
cat << 'EOF' > deployment.yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: fleet-api
spec:
  replicas: 2
  selector:
    matchLabels:
      app: fleet-api
  template:
    metadata:
      labels:
        app: fleet-api
    spec:
      containers:
      - name: api
        image: fleet-api:v1.0.0
EOF
git add deployment.yaml
git commit -m "Initial production release v1.0.0"
```

Create and check out a new feature branch. This branch represents a normal medium-sized change, not an emergency. You are going to leave it dirty on purpose so you can see that worktrees do not require a clean starting directory.

```bash
git checkout -b feature/reliability-upgrade
```

Begin the unfinished reliability work by replacing the Deployment with a more complex version. Do not commit these changes. The dirty working tree is the point of the exercise, because it models the moment when an interruption arrives while you are mid-thought.

```bash
cat << 'EOF' > deployment.yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: fleet-api
spec:
  replicas: 2
  selector:
    matchLabels:
      app: fleet-api
  template:
    metadata:
      labels:
        app: fleet-api
    spec:
      containers:
      - name: api
        image: fleet-api:v1.1.0-rc1
        resources:
          requests:
            memory: "64Mi"
            cpu: "250m"
          limits:
            memory: "128Mi"
            cpu: "500m"
        livenessProbe:
          httpGet:
            path: /healthz
            port: 8080
          initialDelaySeconds: 3
          periodSeconds: 3
EOF
```

Your interruption is a production bug in `fleet-api:v1.0.0`. You need to patch the image version to `v1.0.1` on `main`, but you cannot lose the reliability upgrade and you do not want to apply a stash later. Use the checklist below as your success path.

- [ ] Create a new worktree named `fleet-manager-hotfix` in the parent directory, creating a new branch `hotfix/image-patch` based on `main`.
- [ ] Navigate to the new worktree directory.
- [ ] Verify that `deployment.yaml` in this new directory is the clean original production version with `fleet-api:v1.0.0`.
- [ ] Update the image tag in the hotfix directory to `fleet-api:v1.0.1`.
- [ ] Commit the hotfix in the hotfix worktree.
- [ ] Safely remove the hotfix worktree using Git commands rather than deleting the directory directly.
- [ ] Return to your original directory and verify your reliability upgrades are still exactly as you left them.

<details>
<summary>Hints: choose the boundary, then inspect it</summary>

1. Keep the dirty feature directory in place; the interruption needs files from the committed `main`, not from your index.
2. Use `git worktree add -b <new-branch> <sibling-path> main`. If Git says a branch is already checked out, inspect `git worktree list` rather than forcing it.
3. In the hotfix directory, inspect `git status --short` and the image before editing. If removal refuses a dirty directory, preserve and inspect those edits instead of adding `-f`.

</details>

<details>
<summary>Solution</summary>

Create the worktree while leaving your dirty feature directory exactly as it is. This command makes a sibling directory, creates a new branch, and starts that branch from `main`.

```bash
git worktree add -b hotfix/image-patch ../fleet-manager-hotfix main
```

Move into the new directory and inspect the manifest. It should show the original `v1.0.0` image and none of the resource or probe changes from the feature branch.

```bash
cd ../fleet-manager-hotfix
cat deployment.yaml
```

Apply and commit the hotfix. Write the changed manifest to a temporary file before replacing the original.

```bash
sed 's/fleet-api:v1\.0\.0/fleet-api:v1.0.1/' deployment.yaml > deployment.yaml.tmp && mv deployment.yaml.tmp deployment.yaml

git add deployment.yaml
git commit -m "Hotfix: update API image to v1.0.1"
```

Clean up through Git. Move out of the hotfix directory first, then remove the linked worktree so Git deletes both the directory and its metadata.

```bash
cd ../k8s-fleet-manager
git worktree remove ../fleet-manager-hotfix
```

Verify that the original feature work is still present and uncommitted. You should see the resource requests, limits, liveness probe, and release-candidate image exactly where you left them.

```bash
cat deployment.yaml
git status
git show hotfix/image-patch:deployment.yaml
git worktree list
git stash list
```
</details>

Read the checks as separate questions. In the feature directory, `git status` asks whether unfinished work is still local. Reading the hotfix branch's committed manifest asks what the emergency commit contains. `git worktree list` asks whether the temporary checkout remains registered. A clean hotfix directory alone cannot establish that the original feature edits survived, because its status describes a different index and working tree.

Before cleanup, explain which command answers each question and predict its result. Expect the original file to remain modified, the committed hotfix image to be `v1.0.1`, and the removed sibling path to be absent from the inventory. If a result disagrees, keep the directories and branch while you investigate. Successful directory removal does not mean the branch was pushed or its work reviewed; preserving history and removing a checkout are separate decisions.

Use these cards to retrieve and transfer the module's ideas. Read each mistaken expectation, identify the failure layer, and then open the reveal.

**Card A: The plain stash captured the new file.** An engineer expects a never-added manifest to disappear from the working tree after `git stash`, with no `-u` flag. They expect every dirty path to move onto the stack.

<details>
<summary>Check your prediction</summary>

Failure layer: tracked state versus untracked files. Next action: look for the new file still in the directory. Plain `git stash` saves tracked and staged edits only. Use `-u` only when you meant to shelve untracked files too.

</details>

**Card B: `apply` dropped the stash.** `git stash apply stash@{1}` put the patch into the tree. The next `git stash list` is expected to be missing that entry, the way `pop` behaves after a clean apply.

<details>
<summary>Check your prediction</summary>

Failure layer: restore versus delete. Next action: expect the entry to remain. Drop it only after the tree is tested. `pop` is the command that removes a successful entry.

</details>

**Card C: The second worktree reused the branch.** `feature/auth-refresh` is already checked out. A second `git worktree add` uses that same branch name so both directories share one pointer.

<details>
<summary>Check your prediction</summary>

Failure layer: one checkout per branch name. Next action: expect the command to fail. Create a new branch name, or detach on purpose, and list worktrees before forcing anything.

</details>

**Card D: The ten-minute review required a worktree.** The tree is clean. The pull request changes two files. The review should take about ten minutes. A new directory is treated as the only safe move.

<details>
<summary>Check your prediction</summary>

Failure layer: interruption cost. Next action: switch branches in the current directory. Use a worktree when you must keep the current context, not because every review is an emergency.

</details>

Success criteria:

- [ ] The hotfix commit exists on `hotfix/image-patch`.
- [ ] The hotfix worktree was removed with `git worktree remove`.
- [ ] `git worktree list` no longer shows `fleet-manager-hotfix`.
- [ ] The original `feature/reliability-upgrade` directory still has uncommitted reliability changes.
- [ ] No stash entry was required to survive the interruption.

**Transfer challenge:** Keep the dirty feature work and create another named worktree from `main` for a documentation-only review. Explain which committed image it sees, why its index is independent, and which ports or clusters would still be shared. Inspect the review directory before removing it with Git. Keep the original practice repository until you have inspected the retained hotfix commit; remove the temporary parent only when you intentionally want to discard all practice history.

**Lifecycle stretch:** Create another clean review worktree, then move its directory with `mv`. Predict which path `git worktree list` will report before repairing the connection with `git worktree repair <new-path>`. Verify the inventory and status from both directories, then remove the review worktree through Git. Explain why pruning its record would be the wrong response while the moved files still exist. This extends the interruption workflow into diagnosing a filesystem change rather than repeating branch creation.

After checking the results and deciding to discard all practice history and unfinished feature edits, remove only the generated hotfix-practice parent with `cd / && rm -rf -- "${worktree_practice_root:?}"`. The variable must still identify the temporary root created for this exercise; the guard rejects an unset or empty value, not an incorrectly reassigned nonempty path.

## Sources

Git behavior was checked against the [Git 2.56 documentation snapshot](https://github.com/git/git/tree/a018953688f1b10bddf91bff8747068f5f4746a4/Documentation); the 2.5 links provide historical context.

- [Git documentation: git-worktree](https://git-scm.com/docs/git-worktree)
- [Git documentation: git-clone](https://git-scm.com/docs/git-clone)
- [Git documentation: git-stash](https://git-scm.com/docs/git-stash)
- [Git documentation: git-switch](https://git-scm.com/docs/git-switch)
- [Git documentation: git-checkout](https://git-scm.com/docs/git-checkout)
- [Git documentation: git-branch](https://git-scm.com/docs/git-branch)
- [Git documentation: git-config](https://git-scm.com/docs/git-config)
- [Git documentation: gitcredentials](https://git-scm.com/docs/gitcredentials)
- [Git documentation: git-fetch](https://git-scm.com/docs/git-fetch)
- [Git documentation: git-init](https://git-scm.com/docs/git-init)
- [Git documentation: git-clean](https://git-scm.com/docs/git-clean)
- [Git documentation: gitrepository-layout](https://git-scm.com/docs/gitrepository-layout)
- [Git 2.5 release notes](https://github.com/git/git/blob/v2.5.0/Documentation/RelNotes/2.5.0.txt)
- [Git 2.5 worktree documentation](https://github.com/git/git/blob/v2.5.0/Documentation/git-worktree.txt)
- [Pro Git book: Stashing and Cleaning](https://git-scm.com/book/en/v2/Git-Tools-Stashing-and-Cleaning)
- [Pro Git book: Advanced Merging](https://git-scm.com/book/en/v2/Git-Tools-Advanced-Merging)
- [Pro Git book: Branches in a Nutshell](https://git-scm.com/book/en/v2/Git-Branching-Branches-in-a-Nutshell)
- [Kubernetes documentation: Deployments](https://kubernetes.io/docs/concepts/workloads/controllers/deployment/)
- [Kubernetes documentation: Liveness, readiness, and startup probes](https://kubernetes.io/docs/tasks/configure-pod-container/configure-liveness-readiness-startup-probes/)
- [Kubernetes documentation: Namespaces](https://kubernetes.io/docs/concepts/overview/working-with-objects/namespaces/)
- [Kubernetes documentation: Resource management](https://kubernetes.io/docs/concepts/configuration/manage-resources-containers/)
- [POSIX shell language](https://pubs.opengroup.org/onlinepubs/9799919799/utilities/V3_chap02.html)
- [POSIX sed](https://pubs.opengroup.org/onlinepubs/9799919799/utilities/sed.html)
- [POSIX mv](https://pubs.opengroup.org/onlinepubs/9799919799/utilities/mv.html)
- [POSIX rm](https://pubs.opengroup.org/onlinepubs/9799919799/utilities/rm.html)
- [GNU coreutils: mktemp manual source](https://github.com/coreutils/coreutils/blob/9e804edddb8a0c9d45da87519ae6274c35793ce0/doc/coreutils.texi#L14370)

## Next Module

Continue to [Module 6: The Digital Detective](../module-6-troubleshooting/) to learn how to diagnose broken history, failed merges, and repository states that do not match your expectations.
