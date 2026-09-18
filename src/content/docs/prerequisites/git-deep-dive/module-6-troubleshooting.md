---
title: "Module 6: The Digital Detective — Troubleshooting and Search"
description: "Master advanced Git search, forensics, and troubleshooting techniques to diagnose broken Kubernetes deployments."
sidebar:
  order: 6
revision_pending: false
---

> **Complexity**: `[MEDIUM]`
>
> **Time to Complete**: 90–120 minutes (long-form read + hands-on exercise)
>
> **Prerequisites**: Module 5 of Git Deep Dive

---

## Learning Outcomes

After completing this module, you will be able to:

- **Diagnose** the exact commit that introduced a subtle Kubernetes configuration regression by combining `git bisect run` with a deterministic validation script.
- **Evaluate** the true lineage of suspicious code blocks across whitespace-only rewrites, file movement, and refactors by applying advanced `git blame` options.
- **Compare** historical diff search, snapshot search, and filtered log queries so you can choose the right troubleshooting tool for a live incident.
- **Design** targeted audit trails for Kubernetes manifests that answer who changed what, when it changed, and why the change mattered.
- **Implement** a repeatable Git troubleshooting workflow that moves from broken cluster symptoms to evidence-backed remediation.

## Why This Module Matters

Hypothetical scenario: at 3:14 AM on a holiday retail weekend, a payment platform that had been stable for months started dropping a measurable slice of checkout traffic with `503 Service Unavailable` responses. The Kubernetes control plane was healthy, the nodes were ready, and the application images had passed their normal checks, yet the customer-facing path was failing often enough that revenue dashboards turned into incident evidence. The latest revert did not help, because the release also contained compliance patches that could not be rolled back casually, and the only visible clue was that the `payment-gateway` manifests had been touched by several teams across hundreds of commits.

In that kind of incident, Git is no longer a place where finished work is stored. It becomes a queryable timeline of operational decisions, and the team that can interrogate that timeline calmly has a different outage experience from the team that scrolls through pull requests in panic. A single YAML line can route traffic to the wrong port, remove a readiness gate, weaken a `NetworkPolicy`, or hide a resource limit change behind a formatting commit. The practical skill is not memorizing more commands; it is learning how to turn an unreliable symptom into a narrow historical question that Git can answer.

This module teaches that investigative workflow using the same tools you already have installed. You will use binary search to find the first bad commit, automate that search so human judgment does not contaminate the result, trace line authorship through refactors, search deleted history with Pickaxe queries, scan current and historical snapshots with `git grep`, and assemble an audit trail that an incident commander or compliance reviewer can trust. For Kubernetes examples, assume a current cluster target of Kubernetes 1.35 or newer, and use the full `kubectl` command in runnable examples so every command can be copied into a script without depending on an interactive shell alias.

The lesson also changes how you think about time during troubleshooting. A live cluster shows the present, dashboards show recent symptoms, and Git shows the sequence of intended state changes that led there. The strongest investigators move between those views deliberately instead of letting one view dominate the story. If the cluster says a service is broken, Git can tell you when the intended service definition changed; if Git says nothing changed, the cluster can reveal deployment drift, controller lag, or an out-of-band edit. Treating those timelines as separate but comparable records keeps the investigation grounded.

## Section 1: Turning Symptoms into a Search Space with `git bisect`

When a system fails but you do not know when the failure was introduced, reviewing commits one by one is a slow way to create false confidence. If there are five hundred commits between a known working release tag and the current broken state, a linear review asks engineers to keep a fragile mental model across many unrelated changes. The more urgent the incident feels, the more tempting it becomes to blame the last visible change, even though the actual regression may have landed days earlier and only surfaced when traffic patterns changed.

`git bisect` exists because this problem has a mathematical shape. You provide Git with two anchors: one commit that is definitely bad and one commit that is definitely good. Git then checks out a midpoint commit and asks you to classify it. Each answer discards roughly half of the remaining history, just like finding a word in a dictionary by opening near the middle instead of reading every page from the front. The result is not magic; it is disciplined narrowing of a search space that would otherwise overwhelm human attention.

The key operational decision is choosing anchors that describe the bug honestly. A good commit must be a state where the specific behavior under investigation truly worked, not merely a date when nobody remembers complaints. A bad commit must be a state where the exact failure reproduces, not a general feeling that `main` is unhealthy. If the anchors are sloppy, the binary search still runs, but it answers the wrong question with impressive speed.

Good anchors often come from operational records rather than memory. A release tag tied to a successful deployment, a commit recorded by a GitOps controller, or a build artifact linked to a passing smoke test is better than "sometime before lunch." Bad anchors should be equally concrete: the commit currently deployed to a failing environment, the branch tip whose rendered manifests fail validation, or the exact revision that reproduces a unit test failure. When you cannot establish both sides, spend time improving observability before starting bisection, because a precise algorithm cannot repair imprecise evidence.

```mermaid
flowchart TD
    subgraph S1 [Step 1: Test Midpoint C4]
        direction LR
        C1[C1: Good] --- C2[C2: ?] --- C3[C3: ?] --- C4{C4: Test} --- C5[C5: ?] --- C6[C6: ?] --- C7[C7: Bad]
    end

    subgraph S2 [Step 2: C4 is BAD, Test Midpoint C2]
        direction LR
        C1_2[C1: Good] --- C2_2{C2: Test} --- C3_2[C3: ?] --- C4_2[C4: Bad]
    end

    subgraph S3 [Step 3: C2 is GOOD, Test Midpoint C3]
        direction LR
        C2_3[C2: Good] --- C3_3{C3: Test} --- C4_3[C4: Bad]
    end
    
    S1 -->|Result: BAD| S2
    S2 -->|Result: GOOD| S3
    S3 -->|Result: GOOD| R[Conclusion: C4 is the first bad commit]
```

Imagine a `Deployment` manifest that suddenly fails server-side validation after a sequence of infrastructure-as-code changes. The cluster is available, the API server is responding, and your working theory is that a schema field, indentation block, or API version changed at some point after the last release. Before you begin, create a clean local state, because bisection repeatedly checks out historical commits and Git must be free to move your working tree without destroying uncommitted work.

```bash
git bisect start
```

That command begins the session, but it does not yet know your boundaries. The current commit is normally the bad side when you are investigating a live regression from the tip of your branch. You can be explicit and mark `HEAD` as bad, or omit the hash when you are already checked out at the broken state.

```bash
git bisect bad
```

The other boundary is the most recent known-good state. In a mature release process, this might be a version tag, a production deployment commit, or the merge commit for a previous release train. In this example, `v1.2.0` represents the point where the manifest deployed successfully.

```bash
git bisect good v1.2.0
```

After those anchors are set, Git checks out a midpoint commit and reports roughly how many revisions remain. The repository is now in a detached `HEAD` state, which is expected during bisection. You are not on your normal branch; you are visiting a historical snapshot so you can classify it as good or bad for this one behavior.

```bash
Bisecting: 125 revisions left to test after this (roughly 7 steps)
[a1b2c3d4e5f6g7h8i9j0k1l2m3n4o5p6q7r8s9t0] Update resource requests
```

**Pause and predict:** If you run a Kubernetes validation against this checked-out commit and it succeeds, what should you tell Git next, and what does that answer mean for the remaining history?

<details>
<summary>Check your prediction</summary>

The correct answer is `git bisect good`, because success proves the regression was introduced after the current midpoint. Git can then ignore the older half of the range and continue searching only in the newer half.

</details>

Write the bisect subcommand before you continue. The validation command below checks the manifest. It does not mark the midpoint.

```bash
kubectl apply --dry-run=server -f deployment.yaml
```

If the same validation fails with the exact symptom you are investigating, mark the midpoint as bad instead. Be precise here: a failure caused by missing local dependencies is not the same as the Kubernetes schema regression you are hunting. Manual bisection works only when each classification reflects the target behavior, not any possible inconvenience at that historical commit.

```bash
git bisect bad
```

After several rounds, Git prints the first bad commit. That phrase matters: it is not merely a commit where the bug exists, but the earliest commit in the selected history range where the bad behavior appears after a known-good predecessor. That commit becomes your main evidence artifact for deeper investigation, review, or rollback planning.

```bash
b9c8d7e6f5g4h3i2j1k0l9m8n7o6p5q4r3s2t1u0 is the first bad commit
commit b9c8d7e6f5g4h3i2j1k0l9m8n7o6p5q4r3s2t1u0
Author: Alex Engineer <alex@example.com>
Date:   Tue Oct 24 14:32:11 2025 -0400

    chore: update apiVersion for HorizontalPodAutoscaler
```

Always end the session deliberately. During an incident, engineers often celebrate the culprit and forget that the repository is still checked out somewhere in the past. `git bisect reset` returns you to the branch and commit where the session began, which prevents later commands from accidentally running against historical code.

```bash
git bisect reset
```

Hypothetical scenario: a platform team managing tenant onboarding uses this workflow when default `NetworkPolicy` objects stop rendering from a Helm chart. The pipeline is green, the chart still installs, and a visual diff of recent pull requests does not reveal the missing indentation inside a helper template. A manual bisection using `helm template` as the classification test can narrow more than two hundred commits to a single chart refactor in eight checks, which gives the incident channel a specific commit, author, and rationale instead of another hour of speculative review.

The team learned an important secondary lesson from that incident: bisection is most useful when the test can be run against historical code without requiring the whole production system. Rendering a chart, validating a manifest, running a focused unit test, or starting a small local service gives Git something repeatable to classify. If the only way to observe the bug is to wait for production traffic, the first task is to design a smaller reproduction. That reproduction becomes the bridge between operational symptoms and historical proof.

## Section 2: Automating the Investigation with `git bisect run`

Manual bisection teaches the concept, but automation is where the tool becomes trustworthy under pressure. Humans are slow classifiers, especially when each midpoint requires building an artifact, rendering manifests, starting a local test cluster, or reading noisy validation output. Worse, fatigue creates inconsistent answers: an engineer may mark a commit bad because the setup was annoying, or mark it good because a flaky test happened to pass once. `git bisect run` removes that inconsistency by letting a script classify each checked-out commit through exit codes.

The exit-code contract is simple and strict. When your command exits `0`, Git marks the commit good. When it exits from `1` through `124`, or `126` through `127`, Git marks the commit bad. Exit `125` has a special meaning: the commit cannot be tested for this question, so Git should skip it and choose a nearby candidate without treating it as proof of the bug. That distinction is the difference between a robust forensic run and an automated path to the wrong answer.

Suppose a `StatefulSet` manifest began failing Kubernetes API server validation after many changes to storage templates. A useful bisect script should perform only the smallest test that proves or disproves the target behavior at the currently checked-out commit. The script below validates one manifest and converts the `kubectl` result into the classification Git expects. Place it outside the repository, such as `/tmp/test-manifest.sh`, so historical checkouts cannot delete or modify the script while bisection is running.

```bash
#!/usr/bin/env bash
# Location: /tmp/test-manifest.sh

# We do NOT use 'set -e' because we want to capture the failure exit code manually,
# rather than having the script abort immediately.

echo "Testing commit: $(git rev-parse --short HEAD)"

# Run a dry-run apply against the API server to validate the YAML schema
kubectl apply -f k8s/production/statefulset.yaml --dry-run=server > /dev/null 2>&1

# Capture the exit code of the kubectl command
EXIT_CODE=$?

# Evaluate the exit code and communicate with git bisect
if [ $EXIT_CODE -eq 0 ]; then
    echo "Validation passed. Returning GOOD."
    exit 0 # Tells Git this commit is Good
else
    echo "Validation failed. Returning BAD."
    exit 1 # Tells Git this commit is Bad
fi
```

Make the script executable before starting the run. This is a mundane step, but it is worth doing explicitly because a permission error during bisection is not evidence that the target commit is bad. When your test harness is not executable, you have an environment problem, not a Kubernetes regression.

```bash
chmod +x /tmp/test-manifest.sh
```

With the script ready, define the boundaries and let Git drive the loop. The bisection session checks out commits, runs the script, reads the exit code, and chooses the next midpoint without asking for manual labels. Your job shifts from repeatedly typing `good` or `bad` to verifying that the test itself is a faithful model of the production symptom.

```bash
# 1. Initialize
git bisect start

# 2. Define the current broken state
git bisect bad HEAD

# 3. Define the last known working release
git bisect good v2.4.0

# 4. Hand over control to the script
git bisect run /tmp/test-manifest.sh
```

During the run, the output may feel fast and impersonal, which is exactly the point. Git is not forming opinions about likely authors, commit messages, or suspicious-looking diffs. It is repeatedly asking one question: does this checked-out tree pass the test? That discipline is why automated bisection is useful during emotional incidents.

```text
running /tmp/test-manifest.sh
Testing commit: 7a8b9c0
Validation passed. Returning GOOD.
Bisecting: 67 revisions left to test after this (roughly 6 steps)
...
running /tmp/test-manifest.sh
Testing commit: 1d2e3f4
Validation failed. Returning BAD.
Bisecting: 33 revisions left to test after this (roughly 5 steps)
...
f8e7d6c5b4a3c2d1e0f9a8b7c6d5e4f3a2b1c0d9 is the first bad commit
```

Before running this against a real repository, ask yourself what output you expect from the known-good tag and the known-bad `HEAD`. If the script cannot clearly distinguish those two anchors before bisection begins, it will not become more reliable in the middle of history. A quick preflight against both endpoints often catches missing cluster context, stale credentials, or tests that are too broad for the regression you are isolating.

The most common failure mode is treating every non-zero result as the target bug. Consider a range where one historical commit temporarily broke the `Makefile`, while your actual investigation concerns ingress routing. If `make test` fails at that commit and your script exits `1`, Git marks the commit bad for the routing bug even though routing was never tested. That false classification can eliminate the half of history containing the real regression.

```bash
#!/usr/bin/env bash
# /tmp/robust-test.sh

# Step 1: Attempt to compile the binary
make build
if [ $? -ne 0 ]; then
    echo "Compilation failed! This commit is untestable."
    # Exit 125 tells git bisect: "Skip this commit and find another midpoint"
    exit 125 
fi

# Step 2: Run the actual test for the bug
./bin/app-tester --run-integration
if [ $? -eq 0 ]; then
    exit 0 # Good
else
    exit 1 # Bad
fi
```

Exit `125` is not a way to ignore inconvenient evidence; it is a way to preserve the meaning of the evidence. Use it when the commit cannot answer the question because the test harness cannot run. Do not use it when the application runs and exhibits the bug, because that would hide a real bad commit from the search.

A useful production-grade bisect script usually has three layers. First, it prepares only the dependencies needed for the test, avoiding broad rebuilds when a narrow manifest render is enough. Second, it checks whether the test environment itself is valid and exits `125` if it is not. Third, it runs one deterministic assertion that maps directly to the incident symptom. That structure makes the final first-bad commit easier to defend in a post-incident review.

It is also worth logging the commit under test, the command being run, and the reason for each exit code. Those messages may feel verbose while the command is streaming, but they become valuable when someone asks why a specific midpoint was skipped or why a commit was marked bad. Keep the log human-readable and avoid hiding all output behind `/dev/null` until the script is stable. Once the classification is proven, you can quiet noisy tools while still printing the key evidence line for each commit.

For Kubernetes validation, prefer tests that do not mutate shared environments. A server-side dry run can catch schema and admission failures without persisting objects, while a local render plus a static policy check can run even when a cluster is unavailable. If the regression concerns runtime behavior, consider a disposable local cluster or namespace created by the script and destroyed afterward. The principle is the same in every case: each historical checkout must produce the artifact being tested, and the test must observe that artifact rather than a stale deployment.

## Section 3: Reading Lineage with `git blame` Instead of Blaming People

Finding the first bad commit answers when a regression entered the selected range, but it does not always explain the surrounding intent. You still need to know whether a suspicious line was a typo, a deliberate tradeoff, a copied block from another service, or the residue of a mass formatting change. `git blame` is valuable because it annotates each current line with the commit that last changed it, but the name of the command can mislead teams into treating it as a tool for personal accusation. Use it as a lineage reader, not as a way to embarrass an author.

The raw form is intentionally simple. It prints a revision, author, date, and line content for every line in the file. On a small manifest, that may be enough. On a large generated chart, a raw blame is a wall of noise, especially if the suspicious block is only a few lines inside a template with hundreds of unrelated lines.

```bash
git blame k8s/deployment.yaml
```

Output:

```text
^e2f3g4h (Alice     2024-01-10 09:00:00 -0400   1) apiVersion: apps/v1
^e2f3g4h (Alice     2024-01-10 09:00:00 -0400   2) kind: Deployment
b9c8d7e6 (Bob       2024-02-15 14:30:00 -0400   3) metadata:
b9c8d7e6 (Bob       2024-02-15 14:30:00 -0400   4)   name: payment-gateway
... (800 more lines)
```

Targeted blame is the practical version. If a readiness probe, `resources` block, or `securityContext` stanza looks suspicious, restrict the command to that range instead of making yourself parse the entire file. You can select fixed lines when you know them, or use a regular expression plus an offset when the file shifts often.

```bash
git blame -L 45,50 k8s/deployment.yaml
```

The regular-expression form is especially helpful in Kubernetes manifests because the same concepts appear repeatedly across containers, init containers, sidecars, and templates. The command below finds the first `resources:` line and annotates it plus the next ten lines, which is often enough to cover requests and limits without manually counting from the top of the file.

```bash
git blame -L '/resources:/',+10 k8s/deployment.yaml
```

Whitespace-only rewrites are where naive blame becomes actively misleading. A formatter commit can make every line appear to have been authored by a CI user or a cleanup branch, hiding the original design decision you are trying to evaluate. The `-w` option tells Git to ignore whitespace changes while resolving blame, so it can look past indentation-only changes and report the commit that changed the actual text.

```bash
git blame -w k8s/deployment.yaml
```

Large repositories often make this policy durable with `.git-blame-ignore-revs`. If the team performed a repository-wide YAML reformat, you can place that commit hash in the ignore file and configure Git to skip it during blame. This keeps future investigations focused on meaningful authorship instead of repeatedly rediscovering the same formatting event.

```bash
git config blame.ignoreRevsFile .git-blame-ignore-revs
```

Movement is the second trap. A standard blame follows the current file path, so it may credit the person who moved a block into a new file rather than the person who designed the block. That distinction matters when a Helm helper, storage stanza, or security policy was copied during a refactor and later becomes suspicious during an outage.

```bash
git blame -C k8s/charts/payment/_ingress.tpl
```

The `-C` option asks Git to detect copied or moved lines. Repeating it makes the search more aggressive across commits and files, which costs more time on very large repositories but can recover authorship through complicated refactors. Use the expensive form when the answer is operationally important enough to justify the extra work.

```bash
# Standard blame shows the refactoring commit:
c8d7e6f5 (Bob       2024-03-01 10:00:00 -0400 12) {{ include "mychart.labels" . | nindent 4 }}

# Blame with -C -C pierces the veil to find the true author:
a1b2c3d4 (Alice     2023-11-15 09:15:00 -0400 12) {{ include "mychart.labels" . | nindent 4 }}
```

**Pause and predict:** You are auditing a `securityContext` block that appears to allow a container to run with more privilege than expected. Standard blame names a Jenkins user, and the commit message says it converted YAML indentation from four spaces to two. Which approach would you choose here and why?

<details>
<summary>Check your prediction</summary>

A defensible answer combines `git blame -w` with `-C` when movement is possible, because whitespace ignores the formatter while copy detection follows the block through refactors.

</details>

Write the flags before you continue. The next paragraph is about what to do after you have a commit id. It does not choose those flags.

The outcome you want from blame is a better next question. Once you identify the original commit, read the commit message, inspect the surrounding diff, and look for the linked issue or pull request. A suspicious line may have been a legitimate emergency workaround that never received a cleanup issue, or it may reveal a misunderstanding that deserves a test. Blame gives you coordinates in history; engineering judgment decides what to do with them.

Blame also benefits from path awareness. If a file was renamed, a plain command against the current path can miss context that lived under an older name, while log commands with `--follow` or copy-detection options can provide clues about the rename boundary. In review conversations, present blame output with humility: "this line last changed here" is a fact, but "this person caused the outage" is a much larger claim. The goal is to recover design intent, not to reduce a complex system failure to a name beside a line.

## Section 4: Searching Ghost Changes with Pickaxe Queries

Sometimes the line you need to investigate no longer exists. A configuration value may have been removed from a manifest, a policy exception may have disappeared and reappeared, or a secret-like placeholder may have been committed and then deleted. `git blame` cannot annotate a line that is absent from the current file, and `git grep` searches snapshots rather than the lifecycle of a string. For deleted or fluctuating text, you need `git log -S` and `git log -G`, commonly known as Pickaxe searches.

The `-S` option searches historical diffs for commits where the number of occurrences of a string changed. That detail is important because it is not asking whether a commit contains the string somewhere; it is asking whether the commit added or removed an occurrence. If an environment variable vanished from a `Deployment`, `-S` can show the add commit and the remove commit even when the current file contains nothing.

```bash
git log -S "DB_MAX_CONNECTIONS" --oneline
```

Output:

```text
f9a8b7c Remove legacy database connection limits
a1b2c3d Add explicit connection limits for stability
```

That result gives you a concise timeline, but an incident investigator usually needs the patch as well. Pairing Pickaxe with `--patch` or following up with `git show` reveals the exact context. The goal is not only to know who removed `DB_MAX_CONNECTIONS`, but to understand whether the removal was part of a planned connection-pooling change, an accidental cleanup, or a risky attempt to reduce resource pressure.

The `-G` option answers a broader question. Instead of counting occurrences of one exact string, it searches diff lines with a regular expression. This is useful when the value changes over time or the exact text is unknown. CPU limits, memory quantities, port numbers, hostnames, and API versions are often better searched by pattern than by one literal value.

`git log -G` and `git log -S` use POSIX extended regular expressions (ERE), not PCRE, so use `[[:space:]]` instead of `\s` for whitespace.

```bash
git log -G "cpu:[[:space:]]*[0-9]+m" --oneline -p
```

Output snippet:

```diff
commit e4d3c2b1
Author: SRE Team <sre@example.com>
Date:   Mon Nov 05 11:20:00 2024 -0400

    feat: scale up frontend resources for holiday traffic

diff --git a/k8s/frontend-deployment.yaml b/k8s/frontend-deployment.yaml
--- a/k8s/frontend-deployment.yaml
+++ b/k8s/frontend-deployment.yaml
@@ -45,7 +45,7 @@
         resources:
           requests:
             cpu: 100m
           limits:
-            cpu: 200m
+            cpu: 500m
```

**Pause and predict:** If `git grep "DB_MAX_CONNECTIONS"` returns no matches, does that prove the repository never contained the variable?

<details>
<summary>Check your prediction</summary>

It does not. It proves only that the currently searched snapshot lacks the string. A Pickaxe query against history is the right tool when the suspected evidence may have been added and removed before you looked. A snapshot search answers whether the text exists in this tree. A Pickaxe search answers which commits changed the presence of that text.

</details>

Write yes or no before you continue. Two search questions can sound alike during an incident, and chasing the wrong evidence costs time you do not have. The next section does not grade this prediction.

| Command | What it Searches | Use Case |
| :--- | :--- | :--- |
| **`git log -S "password"`** | Searches the *history of changes* (diffs) across all commits. | "Find me the commit where this string was added or removed." |
| **`git grep "password"`** | Searches the *current snapshot* (the files) of the specified commit. | "Does this string exist in the codebase right now?" |

Security investigations make this difference concrete. If an AWS example key such as `AKIAIOSFODNN7EXAMPLE` was committed in a tutorial manifest and removed later, `git grep` may return nothing from the current tree. `git log -S "AKIAIOSFODNN7EXAMPLE"` can still reveal the add and remove commits, which lets the team evaluate exposure, credential rotation needs, and whether similar patterns exist elsewhere in history. Treat historical secrets as incidents even when the current branch is clean.

Pickaxe queries become even more powerful when you combine them with path limits and date filters. If a deprecated API version appears in old Kubernetes overlays, searching the entire repository history may return too much noise. Adding `-- k8s/prod/` or narrowing the date range makes the result closer to the operational question you need answered. Start broad when you are not sure where the evidence lives, then narrow only after you see enough matches to understand the shape of the history.

## Section 5: Scanning Snapshots Quickly with `git grep`

When the evidence exists in the current tree, `git grep` is usually the right search tool. It understands the repository, searches tracked content efficiently, and avoids many irrelevant directories that a generic recursive `grep` command may stumble through. In infrastructure repositories, that matters because generated output, dependency directories, virtual environments, and build artifacts can be large enough to make ordinary search slow and noisy.

`git grep` also searches arbitrary Git tree objects without checking them out. That ability is valuable when a teammate asks you to review a branch, when you need to compare a release tag with `main`, or when you want to search a remote tracking branch while keeping your local changes untouched. You are searching Git's stored snapshots directly rather than rearranging your working directory.

Suppose a teammate says they added a `PodDisruptionBudget` on their feature branch but cannot remember the path. You do not need to stash your work, switch branches, and risk disrupting your local context. Search the remote branch object directly.

```bash
git grep "kind: PodDisruptionBudget" origin/feature-ha-setup
```

Output:

```text
origin/feature-ha-setup:k8s/infra/pdb-frontend.yaml:kind: PodDisruptionBudget
```

`git grep` also supports boolean expressions. If you are auditing services and need to find manifests that include both `kind: Service` and `type: LoadBalancer`, an ordinary search for either string is too broad. Combining expressions lets you turn a noisy text scan into a practical infrastructure query.

```bash
git grep -e "kind: Service" --and -e "type: LoadBalancer"
```

You can push the idea further by asking Git for every commit and searching those trees, although this should be used deliberately on large repositories. The command below searches all reachable commits for a deprecated Kubernetes API version, which is useful during upgrade readiness work when you need to find old branches or historical manifests that still mention a removed API.

```bash
git grep "apiVersion: policy/v1beta1" $(git rev-list --all)
```

**Pause and predict:** Which approach would you choose here and why: a current release readiness check for deprecated APIs, or a historical compliance investigation into when deprecated APIs were introduced?

<details>
<summary>Check your prediction</summary>

For the current release, search the relevant branch or tag with `git grep`. For introduction history, use `git log -S` or `-G` so the result points to commits rather than merely showing present-day files.

</details>

Write the command family before you continue. The next paragraph pairs repository search with cluster checks. It does not choose between a present-day scan and a history scan.

In Kubernetes work, pair `git grep` with cluster checks when you need both intended state and observed state. A repository can show what should be deployed, while `kubectl get` and `kubectl describe` show what the API server currently knows. Use the full command in shared documentation, scripts, and copied examples so the evidence-gathering sequence does not depend on a local alias that only exists in one engineer's interactive shell.

```bash
kubectl get deploy,svc,pdb -n payments
kubectl describe deploy payment-gateway -n payments
```

Do not confuse repository search with cluster truth. A manifest branch may contain a `PodDisruptionBudget`, while the cluster lacks it because the branch was never applied, a GitOps controller is paused, or an overlay excludes the file. Strong troubleshooting usually alternates between Git evidence and Kubernetes evidence until the two timelines line up.

The reverse is also true: a cluster can contain resources that the current repository no longer describes. Someone may have applied a hotfix manually, an old controller may have left orphaned objects behind, or a migration may have moved ownership to another repository. When Git search and cluster inspection disagree, resist the urge to declare one side wrong immediately. Instead, ask which reconciliation mechanism should connect them, then inspect that mechanism's logs, commit references, and applied revision metadata.

## Section 6: Building Audit Trails with Filtered History

Troubleshooting often ends with a broader accountability question: what changed in the production manifests during the period when risk increased? Git's log filters let you answer that question without exporting the whole repository history into a spreadsheet first. You can filter by author, date, path, and output format, then combine those filters into a report that is narrow enough for an auditor or incident lead to read.

Author and date filters are straightforward when the question is about a person or team. The command below asks for commits by a contractor account since the beginning of a month. In real environments, remember that author names are not identity proof by themselves; they are useful Git metadata that should be correlated with pull request review, signed commits, deployment logs, or access-control records when the stakes are high.

```bash
git log --author="contractor.name" --since="2024-10-01" --oneline
```

Path filters keep the report focused on the files that matter. If the production incident concerns `config/settings.yaml`, the application source commits are distracting even if they happened in the same week. The double dash separates revision options from paths, which prevents ambiguous names from being interpreted as branches or flags.

```bash
git log --oneline -- config/settings.yaml
```

For a compliance report, commit messages are rarely enough. You often need the changed file list so reviewers can see which manifests were modified, added, or deleted. `--name-status` appends that file-level detail to each matching commit, which turns a vague timeline into an actionable audit trail.

```bash
git log \
  --since="2023-12-20" \
  --until="2024-01-02" \
  --name-status \
  -- k8s/prod/
```

Output:

```text
commit d4c3b2a1
Author: DevOps Bot <bot@example.com>
Date:   Wed Dec 27 03:00:00 2023 -0400

    Automated image tag update for frontend

M       k8s/prod/frontend-deployment.yaml
A       k8s/prod/frontend-configmap.yaml
```

If the report needs to flow into a SIEM, spreadsheet, or incident database, format it directly from Git rather than hand-copying terminal output. The `--pretty=format` placeholders below produce a simple comma-separated view with short hash, author name, author date, and subject. For richer automation, prefer a delimiter that cannot appear in commit subjects, but this form is easy to read during a module exercise.

```bash
git log --since="2024-01-01" --pretty=format:"%h,%an,%ad,%s" --date=short -- k8s/
```

Output:

```text
a1b2c3d,Alice Engineer,2024-01-15,Update ingress rules
e4f5g6h,Bob Developer,2024-01-12,Fix typo in deployment
```

A strong audit trail usually includes the question, the command, the boundaries, and the interpretation. For example, "all commits touching `k8s/prod/` during the holiday change freeze" is stronger than "recent manifest changes" because it defines a path and a date range. If the team later challenges the result, you can rerun the exact command and discuss whether the boundary was right instead of arguing from memory.

Hypothetical scenario: after a platform outage caused by a missing readiness probe, the team initially argues about whether the change bypassed review. A filtered log for the production overlay shows that the probe was removed in a small commit labeled as an image tag update, and `--name-status` reveals that the same commit changed an overlay patch file. The evidence shifts the conversation from personal suspicion to process repair: image automation needs a narrower write path, and review rules need to flag manifest field removal separately from image changes.

Filtered history is most persuasive when it is paired with boundaries that match the operational policy. If the organization has a change freeze from one date to another, use those exact dates. If the freeze applies only to production overlays, filter only those paths. If automation is allowed to update image tags but not probes, include file names and patches so the distinction is visible. A report that mirrors the policy language is easier for reviewers to evaluate than a broad dump of nearby commits.

## Patterns & Anti-Patterns

The strongest Git troubleshooting workflows combine a narrow symptom, a deterministic test, and a historical query that matches the shape of the evidence. A team should not start with every command it knows. It should start by deciding whether the evidence exists now, existed in the past, or needs to be proven through repeated historical checkouts.

| Pattern | When to Use It | Why It Works | Scaling Consideration |
| :--- | :--- | :--- | :--- |
| Bisect with a single failing assertion | The system was good at one known point and bad at another. | It converts many commits into a logarithmic search with reproducible labels. | Keep the script narrow, and preflight it against both anchors before the run. |
| Targeted blame after finding a suspicious line | You need context for a current line in a manifest or template. | It connects text to the commit that last changed it, then lets you inspect intent. | Use `-w`, `-C`, and ignore-revs files when formatting or movement obscures authorship. |
| Pickaxe for vanished or fluctuating text | A variable, policy exception, limit, or secret-like string is gone now. | It searches diffs, so deleted evidence still leaves a historical trail. | Prefer `-G` for patterns and `-S` for exact lifecycle changes. |
| Filtered log for incident reports | Stakeholders need a timeline of specific paths, people, or dates. | It turns commit history into a bounded report rather than a narrative guess. | Store the exact command with the report so reviewers can reproduce the boundary. |

Anti-patterns usually come from using a familiar command for the wrong evidence type. `git grep` is excellent for present snapshots, but it is the wrong tool for deleted code. `git blame` is useful for current lines, but misleading after a mass reformat unless you account for whitespace. `git bisect run` is powerful, but dangerous when the script confuses "the test could not run" with "the bug exists."

| Anti-pattern | What Goes Wrong | Better Alternative |
| :--- | :--- | :--- |
| Searching current files for deleted evidence | The result is empty, and the team wrongly concludes the value never existed. | Use `git log -S` or `git log -G` to search historical diffs. |
| Curling live production inside a bisect script | Every historical checkout tests the same deployed system, so the labels are meaningless. | Build or render from the checked-out commit and test an isolated local artifact. |
| Treating blame output as personal proof | The apparent author may be a formatter, mover, or automation account. | Read the commit, use movement and whitespace options, and correlate with review context. |
| Writing broad validation scripts | Flaky or unrelated failures mark commits bad and corrupt the search. | Separate setup failures from target failures, and exit `125` when a commit is untestable. |

## Decision Framework

Choose the tool by asking where the evidence lives. If the symptom reproduces only when you check out historical commits and run a test, use bisection. If the suspicious line exists now, use targeted blame. If the text is missing now but may have existed before, use Pickaxe. If the question is who touched a path during a window, use filtered log queries.

```text
                 +------------------------------+
                 | What evidence do you have?   |
                 +---------------+--------------+
                                 |
             +-------------------+-------------------+
             |                                       |
     Current line exists?                    Line/value missing now?
             |                                       |
     +-------+-------+                       +-------+-------+
     | git blame -L |                       | git log -S/-G |
     +-------+-------+                       +-------+-------+
             |                                       |
     Need true author through moves?         Need exact patch context?
             |                                       |
     Use -w, -C, ignore revs                 Add -p or run git show
             |
             +-------------------+
                                 |
                  Behavior changed over time?
                                 |
                         +-------+-------+
                         | git bisect    |
                         | git bisect run|
                         +-------+-------+
                                 |
                         Need stakeholder timeline?
                                 |
                         +-------+-------+
                         | git log filters|
                         | --name-status  |
                         +---------------+
```

| Investigation Question | Primary Tool | Confirmation Step |
| :--- | :--- | :--- |
| "Which commit introduced this reproducible failure?" | `git bisect run` | Inspect `git show` for the first bad commit and rerun the test around its parent. |
| "Who last changed this current manifest line?" | `git blame -L` | Use `-w` or `-C` if formatting or movement may hide the original author. |
| "When was this deleted variable removed?" | `git log -S` | Add `--patch` or inspect the removal commit directly. |
| "Which manifests changed during the freeze?" | `git log --since --until --name-status -- path/` | Compare the Git timeline with deployment and review records. |
| "Does a teammate's branch contain this resource?" | `git grep pattern branch` | Confirm whether that branch was deployed or merged. |

The framework is intentionally simple because incident response rewards repeatable decisions. Do not start with the most impressive command; start with the question that eliminates the most uncertainty. When the answer shifts the evidence type, change tools rather than forcing one command to do every job.

In practice, investigations loop through this framework more than once. A Pickaxe search may reveal a removal commit, then blame may explain the current replacement line, then a filtered log may show that both commits happened during a freeze. That loop is healthy as long as each step narrows or validates the story. Write down the command that produced each claim, because reproducibility is what separates a forensic timeline from an incident-room anecdote.

## Did You Know?

1. **The Pickaxe name is old Git culture**: `git log -S` is commonly called Pickaxe because it digs through patch history for string additions and removals rather than searching only the current checkout.
2. **`git bisect visualize` can show your current search state**: during a complicated bisection, `git bisect visualize` or `git bisect view` opens a viewer such as `gitk` so you can inspect commits marked good, bad, and untested.
3. **Reverse blame can search deletion history**: `git blame --reverse START..END file` can help identify where a line disappeared across a bounded range, which is useful when normal blame cannot see removed text.
4. **Kubernetes dry-run modes changed operational habits**: server-side dry runs (available since roughly Kubernetes 1.18, including modern 1.35+ clusters) let teams validate manifests against the API server without persisting objects, which makes Git bisection safer when a reachable cluster is available.

## Common Mistakes

| Mistake | Why It Happens | How to Fix It |
| :--- | :--- | :--- |
| Forgetting `git bisect reset` | After finding the bug, engineers celebrate and leave the repository in a detached historical checkout. | Run `git bisect reset` immediately after recording the first bad commit so later work returns to the original branch. |
| Testing dirty working trees | Uncommitted changes make Git unable to move safely between historical commits. | Commit, stash, or discard unrelated local changes before starting the bisection session. |
| Using `git grep` to find deleted code | The command searches snapshots, so removed text is invisible in the current tree. | Use `git log -S` for exact strings or `git log -G` for regular-expression changes in historical diffs. |
| Trusting blame on reformatted files | A formatter commit can appear to author every line even though it changed only whitespace. | Use `git blame -w`, configure `.git-blame-ignore-revs`, and inspect the underlying commit before drawing conclusions. |
| Writing bisect scripts that exit `1` on compile errors | The script treats an untestable commit as proof of the target regression. | Detect setup or build failures separately and exit `125` when the commit cannot answer the investigation question. |
| Curling live production during bisection | Historical checkouts do not affect the already deployed production system. | Build, render, or deploy an isolated artifact from the checked-out commit before testing behavior. |
| Blaming the wrong branch | The local checkout may be stale or pointed at a feature branch without the relevant history. | Confirm the target branch first, or pass the intended revision explicitly to Git commands. |

## Quiz

<details><summary><strong>Question 1</strong>: You are running an automated <code>git bisect run ./test.sh</code> to locate a routing bug in Kubernetes ingress manifests. One midpoint commit cannot build because of an unrelated Makefile syntax error. What must the script do, and why?</summary>

**Answer**: The script must detect that the build failure prevents the routing test from running and exit with code `125`. That code tells Git the commit is untestable for this investigation, so Git should skip it instead of marking it bad. If the script exits `1`, Git treats the unrelated Makefile problem as evidence of the routing regression and may discard the half of history that contains the true culprit. The important reasoning is that bisection labels must describe the target behavior, not every possible historical failure.
</details>

<details><summary><strong>Question 2</strong>: A security scan shows a `NetworkPolicy` exception exists now, but you suspect it was temporarily removed last month and then restored. Which Git search should you use to prove or disprove that lifecycle?</summary>

**Answer**: Use `git log -S "specific-policy-string"` when you can identify exact text from the exception, or `git log -G "regex-pattern"` if the shape is known but values changed. These commands search historical diffs, so they can reveal commits where the text was removed and later re-added. `git grep` would only tell you whether the current snapshot contains the exception, which cannot prove the temporary removal. After finding candidate commits, inspect their patches and review context before concluding intent.
</details>

<details><summary><strong>Question 3</strong>: `git blame` says a junior engineer wrote a dangerous storage stanza yesterday, but they claim they only moved the manifest during a repository reorganization. How do you verify the claim?</summary>

**Answer**: Run targeted blame with copy or movement detection, such as `git blame -C` on the current file and the suspicious line range. If the block was moved from another file, Git can look past the reorganization commit and show the earlier author and commit that introduced the text. If the move happened across several steps, repeated `-C` options can make the search more aggressive. You should then inspect the original commit because authorship alone does not explain whether the stanza was correct for its original context.
</details>

<details><summary><strong>Question 4</strong>: Your API is broken at `HEAD` and stable at tag `v2.0`. You automate bisection with a script that curls the live production health endpoint at `https://api.production.com/health`. Why will this not find the Git regression?</summary>

**Answer**: Bisection changes the local repository checkout, but it does not redeploy each historical commit to production. The script would keep testing the same live system regardless of which commit Git checked out, so every classification would describe current production rather than the historical tree. A valid script must build, render, or run an isolated artifact from the currently checked-out commit and test that artifact. For Kubernetes manifests, that might mean rendering the chart and running a server-side dry run against a safe validation cluster.
</details>

<details><summary><strong>Question 5</strong>: You need to investigate an AWS example key, `AKIAIOSFODNN7EXAMPLE`, that may have been committed and later removed. `git grep` returns nothing. What does that result prove, and what command should come next?</summary>

**Answer**: The empty `git grep` result proves only that the searched snapshot does not currently contain the string. It does not prove the string never existed in repository history. The next command should be `git log -S "AKIAIOSFODNN7EXAMPLE"` so Git searches diffs where the occurrence count changed. If matches appear, inspect the add and remove commits to determine exposure, remediation timing, and whether similar examples exist elsewhere.
</details>

<details><summary><strong>Question 6</strong>: An auditor asks for all commits by `platform-team` that modified files in `k8s/networking/`, including whether each file was added, modified, or deleted. What command produces that report?</summary>

**Answer**: Use `git log --author="platform-team" --name-status -- k8s/networking/`. The author filter narrows the result to the named identity, while the pathspec after `--` limits the report to the networking directory. `--name-status` adds the file-level change type, which is the detail the auditor requested. For a real compliance packet, record the exact command and time window so the report can be reproduced.
</details>

<details><summary><strong>Question 7</strong>: A teammate says their remote branch contains a new `PodDisruptionBudget`, but you have local work you do not want to stash. How can you find the file path without checking out their branch?</summary>

**Answer**: Run `git grep "kind: PodDisruptionBudget" origin/their-branch`, replacing the branch name with the actual remote tracking branch. `git grep` can search Git tree objects directly, so it does not need to change your working directory. The result includes the branch, file path, and matching line, which is enough to start review. You should still confirm whether that branch was deployed before treating it as cluster truth.
</details>

## Hands-On Exercise: The Case of the Broken Manifest

In this exercise, you will create a fresh repository with simulated history, introduce a subtle Kubernetes-style bug, bury it under routine commits, and use automated bisection plus targeted blame to find the evidence. The lab is intentionally local and safe: it does not require a cluster, and the validation script checks the manifest text so you can focus on the Git investigation mechanics before applying the same pattern to server-side Kubernetes validation.

### Step 1: Scenario Setup

First, generate a repository with a deep enough history to make manual review unattractive. The initial manifest uses `containerPort: 80`, which matches the default Nginx container behavior in this simplified scenario. Later, one commit changes the port to `8080`, and many routine commits hide that change from casual inspection.

```bash
mkdir k8s-forensics-lab && cd k8s-forensics-lab
git init

# Create the initial, perfectly working manifest
cat << 'EOF' > deployment.yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: web-server
spec:
  replicas: 3
  selector:
    matchLabels:
      app: web
  template:
    metadata:
      labels:
        app: web
    spec:
      containers:
      - name: nginx
        image: nginx:1.27.0
        ports:
        - containerPort: 80
EOF
git add deployment.yaml
git commit -m "Initial commit: working deployment"
git tag v1.0

# Simulate 20 good, benign commits
for i in {1..20}; do
  echo "# Comment $i" >> deployment.yaml
  git commit -am "chore: minor update $i"
done

# INTRODUCE THE BUG (Typo in containerPort: 80 -> 8080)
sed -i.bak 's/containerPort: 80/containerPort: 8080/' deployment.yaml
rm deployment.yaml.bak
git commit -am "fix: adjust port configuration for new ingress"

# Simulate 30 more commits completely burying the bug
for i in {21..50}; do
  echo "# Comment $i" >> deployment.yaml
  git commit -am "chore: minor update $i"
done
```

### Step 2: Verify the Problem

Inspect the current file to confirm the broken state exists at `HEAD`. This is your bad anchor. In a real Kubernetes workflow, this step might be a failed `kubectl apply --dry-run=server` or a failing integration test, but here a direct text check keeps the exercise portable.

```bash
cat deployment.yaml | grep containerPort
```

Expected output:

```text
containerPort: 8080
```

### Step 3: Author the Validation Script

Create a script that distinguishes the good state from the bad state. The `$` anchor matters because it prevents `8080` from being accepted as though it contained the correct value. This script is deliberately small, which makes its exit-code behavior easy to reason about during bisection.

```bash
#!/usr/bin/env bash
# Location: /tmp/test-port.sh

# Check if the deployment contains the correct exact string 'containerPort: 80'
# The '$' anchors the search to the end of the line, ensuring '8080' fails.
grep "containerPort: 80$" deployment.yaml > /dev/null

# grep exits 0 if the string is found (Good commit), 1 if not found (Bad commit)
exit $?
```

Make the test script executable:

```bash
chmod +x /tmp/test-port.sh
```

### Step 4: Execute the Automated Bisect

Now instruct Git to hunt down the bug. Read each command before running it and connect it to the bisection model: start the session, mark the bad endpoint, mark the good endpoint, then hand classification to the script.

- [ ] Initialize the bisect process: `git bisect start`
- [ ] Mark the current broken state: `git bisect bad HEAD`
- [ ] Mark the known good release tag: `git bisect good v1.0`
- [ ] Hand over execution to the automation script: `git bisect run /tmp/test-port.sh`

<details>
<summary><strong>View Expected Output</strong></summary>

```bash
running /tmp/test-port.sh
Bisecting: 12 revisions left to test after this (roughly 4 steps)
[some-hash] chore: minor update 26
...
running /tmp/test-port.sh
[hash] is the first bad commit
commit [hash]
Author: Your Name <your.email@example.com>
Date:   [Date]

    fix: adjust port configuration for new ingress
```

Git has successfully found the exact commit that mutated the port, traversing 50 commits and executing 5 tests in a fraction of a second.
</details>

### Step 5: Clean Up and Interrogate the Code

The first bad commit tells you when the regression entered the history, but targeted blame helps you connect the current line to the historical evidence. Reset the bisection session first, then blame only the port line instead of asking Git to annotate the whole manifest.

- [ ] Terminate the forensic session and return to reality: `git bisect reset`
- [ ] Use targeted blame against the port line: `git blame -L '/containerPort/',+1 deployment.yaml`
- [ ] Inspect the first bad commit with `git show --stat --patch <hash>` and confirm the diff changed only the expected line.
- [ ] Record the command sequence and the first bad commit hash as your incident evidence.

```bash
git blame -L '/containerPort/',+1 deployment.yaml
```

<details>
<summary><strong>Solution Explanation</strong></summary>

The `git blame` command targets the regular expression `/containerPort/` and renders only that line. You will see the specific commit hash, committer identity, and timestamp associated with the port change. By chaining automated bisection with targeted line blame, you move from "the manifest is wrong" to "this commit changed this line and here is the evidence." That is the practical standard for incident forensics.
</details>

**Card A: A passing midpoint is marked bad.** The dry-run succeeds on the checked-out commit. The bisect is told `bad` anyway, because the regression is "somewhere in this history."

<details>
<summary>Check your prediction</summary>

Failure layer: which half still contains the bug. Next action: `git bisect good`. Success means the regression is newer than this commit, so the older half can be ignored.

</details>

**Card B: Whitespace blame is trusted.** `securityContext` looks too privileged. Blame names a Jenkins user whose message only says the YAML indent changed from four spaces to two.

<details>
<summary>Check your prediction</summary>

Failure layer: the formatter commit, not the author of the privilege. Next action: rerun with `git blame -w`, and add `-C` if the block may have moved. Then read the commit that still owns the meaning.

</details>

**Card C: No grep hits means the variable never existed.** `git grep "DB_MAX_CONNECTIONS"` is empty on the current tree. The incident note says the setting was removed last week.

<details>
<summary>Check your prediction</summary>

Failure layer: this snapshot versus history. Next action: do not close the search. Use a Pickaxe query (`git log -S` or `-G`) for commits that added or removed the string.

</details>

**Card D: A release check is run as history.** The question is whether the branch you are about to ship still contains `policy/v1beta1`. The command chosen is `git log -S`.

<details>
<summary>Check your prediction</summary>

Failure layer: present files versus introduction commits. Next action: `git grep` on the release branch or tag for a current readiness check. Use `git log -S` when the question is when the API was introduced.

</details>

### Success Criteria

- [ ] You created a local repository with a known-good `v1.0` tag and a bad `HEAD`.
- [ ] Your `/tmp/test-port.sh` script exits `0` for the correct port and non-zero for the bad port.
- [ ] `git bisect run /tmp/test-port.sh` identified the commit message `fix: adjust port configuration for new ingress`.
- [ ] You ran `git bisect reset` after the investigation.
- [ ] You used targeted `git blame` to annotate only the `containerPort` line.

## Sources

- [Git documentation: git-bisect](https://git-scm.com/docs/git-bisect)
- [Git documentation: git-blame](https://git-scm.com/docs/git-blame)
- [Git documentation: git-log](https://git-scm.com/docs/git-log)
- [Git documentation: git-grep](https://git-scm.com/docs/git-grep)
- [Git documentation: git-show](https://git-scm.com/docs/git-show)
- [Git documentation: git-rev-list](https://git-scm.com/docs/git-rev-list)
- [Git documentation: git-config](https://git-scm.com/docs/git-config)
- [Git book: Debugging with Git](https://git-scm.com/book/en/v2/Git-Tools-Debugging-with-Git)
- [Kubernetes documentation: kubectl](https://kubernetes.io/docs/reference/kubectl/)
- [Kubernetes documentation: kubectl apply](https://kubernetes.io/docs/reference/kubectl/generated/kubectl_apply/)
- [Kubernetes documentation: API overview](https://kubernetes.io/docs/reference/using-api/)
- [Kubernetes documentation: server-side apply](https://kubernetes.io/docs/reference/using-api/server-side-apply/)

## Next Module

Now that you can dissect history to locate regressions and build forensic audit trails, look outward to collaboration workflows. Learn how to synchronize local work with external servers, handle complex merge conflicts, and manage upstream changes safely in [Module 7: Professional Collaboration - Remotes and PRs](../module-7-remotes-prs/).
