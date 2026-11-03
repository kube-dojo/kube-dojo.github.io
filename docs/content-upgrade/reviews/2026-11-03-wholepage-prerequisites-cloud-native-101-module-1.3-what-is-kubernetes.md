# Reviews of prerequisites/cloud-native-101/module-1.3-what-is-kubernetes.md under OO-KD-REREVIEW-1102

Verbatim reviewer output, unedited. Reviewer for both: Claude Sonnet 5.5 (claude-sonnet-5-5), outside the OpenAI/Codex author family (gpt-6.1-terra). These are scoped verdicts; none is lead acceptance. The kubectl lab was not run by either reviewer (no cluster on the review host).

## kd-wp-cn13-r1: call 1 of 2, whole-page review

- reviewed head: `f139a684080195c79e692a99a59bf851be9d3a77`
- run nonce: `4664e81cb04840b490c1603960af9008`
- verdict: `incorrect` (confidence 0.8)

### Explanation (verbatim)

DIGEST: sha256sum of src/content/docs/prerequisites/cloud-native-101/module-1.3-what-is-kubernetes.md is 0c93da89924ad0a5a20f568c43058fa9eaf0d9fb6fbc2fd79d7e396cc36622a5, which matches the supplied digest. The checkout HEAD is f139a6840, not 1632266a8, but the page bytes are identical. I read all 659 lines.

DISPOSITION: revise, confidence 0.8. One BLOCKING under-explanation in the lab setup, and the lab floor is missed. The conceptual teaching is strong.

D SCORES (module):
- D1 Outcomes 5: four measurable Evaluate/Diagnose/Predict/Assess outcomes, each with matching teaching and practice.
- D2 Scaffolding 4: build-up is sound (problem, definition, architecture, resources, request flow, trade-offs). 'Pods' is used at lines 62 and 68 before it is defined at line 208, and 'endpoints' (line 296) is never defined.
- D3 Active Learning 5: four predict-then-reveal prompts, four decision cards and a lab.
- D4 Real-World 4: hypothetical scenarios are labelled, and there is a common-mistakes table and an anti-pattern table.
- D5 Assessment 5: six scenario quizzes explain the why and agree with the lesson. I found no contradiction between quiz answers and the lesson.
- D6 Cognitive Load 4: diagrams carry explanatory text. The same four control-plane components are covered three times (restaurant analogy, paragraphs, table), and the lab setup script is heavy for a beginner.
- D7 Engagement 4: strong hook and analogies; line 62's 'Stop and think' contains no question.
- D8 Practitioner Depth 4: decision matrix, managed vs self-managed trade-offs, and when Kubernetes does not apply.
Total 35/40. D floors are met.

L SCORES (lab):
- L1 Scenario design 4.
- L2 Progressive difficulty 4: read-only inspection, then a Pod, then describe, then cleanup.
- L3 Understanding over memorization 4: solution guides tie each output to the architecture.
- L4 Hints and feedback 3: there are solution guides and prediction cards, but no tiered hints and no expected-output shapes. The setup has a silent dead end (see B1).
- L5 Transfer 4.
Total 19/25. The L4 floor is missed and the total is under 21.

SOURCE_STATUS: partly supported.
- Claims judged: about 16 material claims (excluding generic Kubernetes definitions).
- Supported by pages I opened: 7.
- Unknown (fetch truncated or content not reached): 5.
- Unsupported: 0.
- Reasonable but unsourced or overstated: 4, including the Auto-scaling row.

Supported claims, checked against fetched text:
- Components page: scheduler binds unbound Pods; kube-controller-manager runs controllers; kubelet ensures Pods and containers run; kube-proxy maintains Service network rules; etcd is the store for API server data.
- GKE Autopilot manages nodes and node provisioning, while customers declare workload needs.
- Docker restart policies only restart containers and do not relocate them across hosts.
- Compose provides service-name DNS on its default network.
- Pods docs: the smallest deployable unit, with shared network and storage, and not usually created directly.
- Taint docs: NoExecute eviction semantics and tolerationSeconds.
- 10-years blog: first commit on June 6, 2014. This was quoted from the blog opening.

UNKNOWN (fetch truncated at 100 KB or text not reached):
- 7-spoke logo history.
- 'helmsman' etymology.
- Borg/Omega lineage.
- Default 300 s not-ready/unreachable toleration.
- Node-controller heartbeat/grace period text.
- Compose secrets page and CNCF journey report: not opened.
The page hedges node-failure timing ('eventually', 'configured grace period', 'subject to their tolerations'), so I treat the timing claims as acceptably qualified.

The committed source catalogs (2026-10-30 and 2026-10-31) hold only a frontmatter-only entry (S011) for this page. They contain no claim ledger, so I could not use them as claim evidence. All semantic checks above were mine, not supplied.

LAB_EXECUTION: not run. The host has no cluster or container runtime, and no one executed these kubectl commands. I judged them as prose and design only.

BLOCKING FINDING (1):
B1 (lines 536-538, 489, 539-547): the lab script requires KUBEDOJO_LAB_CONTEXT, but nothing tells an absolute beginner how to find the context name, what 'verified' means, or how to export it. Line 489 says only 'independently confirm that the selected context is a dedicated disposable cluster'. The only guidance is the code comment 'export KUBEDOJO_LAB_CONTEXT with the verified context name first'. The variable is not defined in the prerequisite Your First Cluster module (grep found no match there; it appears only in an unrelated CKA page). If the variable is unset, the script silently skips namespace creation, EXAMPLE_READY stays 'no', and every later kubectl call prints 'Setup incomplete; stop' with no instruction on what to fix. The learner is stranded. Smallest fix: add 2-3 lines before the script saying to run `kubectl config get-contexts`, to confirm the CURRENT context is the lab cluster from Your First Cluster (for kind, `kind-<cluster name>`), and to run `export KUBEDOJO_LAB_CONTEXT=<that name>`. Add one sentence that 'Setup incomplete; stop' means the variable is unset or the context check failed.

NON-BLOCKING FINDINGS:
N1 (line 354): the table row '| Auto-scaling | No | Yes |' is unqualified. Kubernetes autoscaling is opt-in and needs the HPA plus a metrics source, and cluster autoscaling is a separate piece. Line 368 itself says 'when configured well'. Qualify the cell, for example 'Yes, once configured (HPA, metrics)'. 'Rolling updates | Automatic' is similarly strong.
N2 (line 62): the 'Stop and think' callout contains no question; it states the answer inline. Phrase it as a question, or demote it to ordinary prose.
N3 (lines 164 and 174-188): the restaurant analogy, the four component paragraphs, and the two component tables re-state the same components, after the airport analogy has already mapped the control plane. This is mild repetition. Drop the restaurant box or the first table. Not blocking, because nothing the learner needs is missing.
N4 (lines 539 and 585): the kubectl shell function stays defined after cleanup sets EXAMPLE_READY=no, so any later kubectl in that terminal refuses. Add 'then close this terminal'.
N5 (lines 509-519): the task 2 solution guide does not say that on kind or kubeadm the kube-system listing also shows etcd and the API server, scheduler and controller-manager Pods, whereas managed clusters hide the control plane. That is a missed link to the architecture and managed-vs-self sections.
N6 (line 296): 'endpoints' is used without definition, and 'haunted' is informal. Cosmetic.

OMITTED-CLAIM DISCOVERY:
- Line 376: 'Cloud-managed Kubernetes is the usual starting point for production teams' is unsourced, but hedged by 'usual'.
- Lines 378 and 383: kubeadm conformance, k3s, kind, minikube and Docker Desktop characterizations are unsourced and low volatility. Only the Kubernetes docs links appear, and none specifically for k3s or kind.
- Line 432: 'hosted by CNCF' and 'Google founders drew on Borg and Omega'. I could not verify the Borg/Omega claim; it is common knowledge.
No prices, quotas or version-volatile claims are stated without a hedge. nginx:1.27 is a pinned tag used only as an example.

SAFETY: acceptable. The lab uses a disposable-cluster guard, a dedicated generated namespace, scoped cleanup with explicit --context, and a warning not to broaden deletion. No sudo, credential or public-exposure advice.

URLS ACTUALLY OPENED (via WebFetch): kubernetes.io/blog/2024/06/06/10-years-of-kubernetes/ (partial: first-commit sentence only); kubernetes.io/docs/concepts/architecture/nodes/ (truncated before the heartbeat/eviction sections); docs.cloud.google.com/kubernetes-engine/docs/concepts/autopilot-overview; kubernetes.io/docs/concepts/overview/components/; docs.docker.com/engine/containers/start-containers-automatically/; kubernetes.io/docs/concepts/scheduling-eviction/taint-and-toleration/ (partial); kubernetes.io/docs/concepts/workloads/pods/ (partial); docs.docker.com/compose/how-tos/networking/. curl was unavailable, so I could not read the truncated tails.

PROVENANCE: reviewer Claude Code, Anthropic family, model claude-sonnet-5-5, Claude Agent SDK harness. Review kind: whole-page review, call 1 of 2. Checks I performed: sha256sum; full read of the page, review contract and completion plan; grep of the catalogs and prerequisite pages; the web fetches listed above. Checks supplied and not re-run: the catalogs' metadata, and prior review history, which I treated as unverified. Limits: no lab execution; several web fetches truncated; I did not open Compose secrets, the CNCF report, or the EKS, AKS and GKE overview pages.

### Findings (verbatim JSON)

```json
[
 {
  "id": "B1-lab-context-undefined",
  "title": "Lab setup requires KUBEDOJO_LAB_CONTEXT but never tells the beginner how to obtain or export it",
  "body": "The Pod-creation task script reads KUBEDOJO_LAB_CONTEXT, which is defined nowhere in the page or in the Your First Cluster prerequisite. The only instruction is a code comment. A learner on the Zero to Terminal route is told to 'independently confirm' the cluster is disposable but not how. If the variable is unset, the script silently skips namespace creation and every later kubectl call prints 'Setup incomplete; stop', with no recovery path.",
  "priority": "P2",
  "confidence": 0.8,
  "category": "docs",
  "location": {
   "path": "src/content/docs/prerequisites/cloud-native-101/module-1.3-what-is-kubernetes.md",
   "start_line": 536,
   "end_line": 545,
   "claim_type": "present"
  },
  "verbatim": "# In a fresh Bash terminal, export KUBEDOJO_LAB_CONTEXT with the verified context name first.",
  "why_wrong": "UNDER-EXPLANATION: a skipped step that the lab cannot proceed without. The beginner cannot find the context name or the export syntax from the page, and the failure message gives no remedy.",
  "smallest_fix": "Before the script, add: run `kubectl config get-contexts`, confirm the current context is the disposable lab cluster from Your First Cluster (for kind, `kind-<cluster name>`), then `export KUBEDOJO_LAB_CONTEXT=<that name>`. Add one sentence explaining that 'Setup incomplete; stop' means the variable is unset or the context check failed.",
  "sources": [
   "none"
  ]
 },
 {
  "id": "N1-autoscaling-table-overclaim",
  "title": "Comparison table states Kubernetes auto-scaling as an unqualified Yes",
  "body": "Autoscaling in Kubernetes is opt-in and requires configuring the HPA and a metrics source (plus cluster autoscaling for nodes). The page itself says autoscaling reduces waste 'when configured well'. The unqualified table cell contradicts that hedge.",
  "priority": "P3",
  "confidence": 0.6,
  "category": "correctness",
  "location": {
   "path": "src/content/docs/prerequisites/cloud-native-101/module-1.3-what-is-kubernetes.md",
   "start_line": 354,
   "end_line": 356,
   "claim_type": "present"
  },
  "verbatim": "| Auto-scaling | No | Yes |",
  "why_wrong": "Unsupported specificity: a beginner may infer Kubernetes scales on its own with no setup.",
  "smallest_fix": "Change the Kubernetes cell to 'Yes, once configured (HPA, metrics)' and consider the same qualifier for the rolling-updates row.",
  "sources": [
   "none"
  ]
 },
 {
  "id": "N3-duplicate-component-explanations",
  "title": "Same four control-plane components are explained by analogy, prose and a table back to back",
  "body": "A restaurant analogy re-maps the components that the airport analogy and diagram already mapped, and the component tables repeat the preceding paragraphs nearly verbatim.",
  "priority": "P3",
  "confidence": 0.5,
  "category": "style",
  "location": {
   "path": "src/content/docs/prerequisites/cloud-native-101/module-1.3-what-is-kubernetes.md",
   "start_line": 164,
   "end_line": 188,
   "claim_type": "present"
  },
  "verbatim": "> **Restaurant analogy**: Picture a busy restaurant kitchen.",
  "why_wrong": "Mild BLOAT: the learner loses nothing a stated outcome needs if one of the three treatments is removed. Non-blocking because no needed content is missing.",
  "smallest_fix": "Remove the restaurant analogy box or the first component table.",
  "sources": [
   "none"
  ]
 }
]
```

## kd-wp-cn13-r2: call 2 of 2, delta review

- reviewed head: `dae8ff4b311c92c2e556d1b01c5862aaf1246d27`
- run nonce: `f168fa0a7eef40eb883193f803242ff6`
- verdict: `correct` (confidence 0.8)

### Explanation (verbatim)

DELTA REVIEW, call 2 of 2 (not acceptance). TASK 1: HEAD is dae8ff4b311c92c2e556d1b01c5862aaf1246d27. The diff against f139a684 touches one file with 21 additions and 9 deletions. The page sha256 at HEAD is 1f06c2ec50a31a25a35cafe46d0fa6258205f912a0167d193a9874b731c19bd9, which matches the expected value. Word count rose from 8971 to 9140 (+169, about 1.9%): no bloat. Removing the restaurant box offsets part of the additions.

B1: CLOSED. The new paragraph at line 539 comes before the script (lines 543-556) in reading order. It gives `kubectl config get-contexts`, which is the right command (kubectl config get-contexts reference page: it lists contexts from the kubeconfig). It then says to confirm the current context is the disposable cluster and to export the variable, with a concrete example. A learner reading top to bottom therefore exports the variable before pasting the script. The script guard is unchanged: the diff does not touch lines 543-556, and I read it. The recovery paragraph (line 541) names the unset variable, the failed context check and the failed namespace creation, and gives a next step (fresh terminal, verify, export). The pointer to 'clean up any owned namespace as instructed below' is safe: the cleanup block only acts when EXAMPLE_OWNED is yes, so it is a no-op before setup succeeded. The example name is consistent with Your First Cluster: grep finds `kind-dojo-basics` and `dojo-basics` in module-1.1-first-cluster.md lines 206-224, 339, 545 and 770, including the line 545 advice to use names such as `kind-dojo-basics`.

One residual remains (non-blocking, F1). Module 1.1 points KUBECONFIG at a private temp file in a dedicated lesson shell (lines 291-330). It tells the learner to close that shell and to run lesson_delete or lesson_finish at the end. A learner who followed 1.1 literally and then opens a 'fresh Bash terminal', as this page instructs, will not see `kind-dojo-basics` in `kubectl config get-contexts`. The page gives no hint about this. It is a narrow path, since the setup text also allows any disposable cluster, and the other prerequisite labs share the same 'fresh terminal' convention. So I do not treat it as a blocker.

N1: CLOSED. The auto-scaling cell now reads 'Yes, once configured (HPA and metrics)'. The HPA page (opened) says the HPA is an API resource plus a controller, and that metrics.k8s.io 'is usually provided by an add-on named Metrics Server, which needs to be launched separately'. Rolling updates now reads 'Automatic for Deployments using the rolling update strategy'. The Deployment page (opened at offset 100000) says that RollingUpdate is the default strategy type.
N2: CLOSED in form. The callout now asks a question. It states the answer immediately after the question, which weakens the retrieval prompt, but it is coherent and not a defect.
N3: CLOSED. The restaurant box is removed. Grep for restaurant, kitchen, front desk and floor manager finds no remaining hits. The only analogy hits are the airport analogy (lines 72-96), which is separate and was untouched. There are no dangling 'above', 'earlier' or 'as we saw' references to the removed box. The component paragraphs and tables stay as they were; the redundancy is only reduced, which is acceptable.
N4: CLOSED. The line after cleanup says to close the terminal to remove the temporary kubectl shell function. This is accurate: the script defines the function at line 547 and cleanup only sets EXAMPLE_READY=no, so closing the terminal discards the function.
N5: CLOSED. The task 2 solution guide now names the API server, scheduler, controller manager and, when local, etcd on kubeadm clusters, and says a managed control plane may not appear. The kubeadm init page (opened) lists static Pod manifests for etcd, kube-apiserver, kube-controller-manager and kube-scheduler. The static Pod page (opened) shows mirror Pods in the API server, but its kube-system detail was truncated, so the kube-system placement for kubeadm is UNKNOWN from my sources; it is well established in general and low-risk. The GKE cluster architecture page (opened) says GKE manages the control plane lifecycle; it does not say outright whether control plane Pods are hidden from the user, so 'may not appear' rests on general knowledge.
N6: CLOSED. 'Haunted' is replaced with 'a network fault'. The page now defines endpoints as the network addresses of its backends. The EndpointSlice page (opened) says EndpointSlices track the IP addresses of backend endpoints, normally associated with a Service.

L4: MOSTLY CLOSED. The added Hint lines give output shapes without answering the tasks. They are accurate for `kubectl get nodes` (name, status, roles), `get pods -n kube-system` (names and status), `get namespaces` (names and status) and `describe pod` (Node, State and Events sections). The namespaces hint about which policies a namespace needs for isolation fits the lesson, since the solution guide names RBAC, network policy, quotas and admission. The solution guides for tasks 4 and 6 gained expected-output shapes. There are still no tiered hints, and the guard's context-check failure prints no message, so the recovery text cannot say which cause applied; the next step is the same for all three causes, so this is minor.

DELTA-INTRODUCED DEFECTS: none blocking. I found no dangling references to removed text. Grep of src for fragment links into this page found none. No headings were removed, because the restaurant box was a callout. No new links were added; the Sources section is unchanged. The new claims in the diff are consistent with the sources I opened. The PR body table could not be read: `gh` with `--repo` is refused at the review boundary. I therefore verified the added claims independently against the primary pages instead.

URLS OPENED: kubernetes.io HPA concept page; Deployment concept page, twice, the second at offset 100000; kubeadm init reference; static Pod task page; EndpointSlice concept page; kubectl config get-contexts reference; GKE cluster architecture page.

SCORES, from a full read with the call-1 labels. D 35/40, margin +2 over the 33 floor: D1 outcomes 5, D2 scaffolding 4, D3 active learning 5, D4 real-world 4, D5 assessment 5, D6 cognitive load 4, D7 engagement 4, D8 practitioner depth 4. Every D is at or above 4, so the floor is met with no margin on any individual dimension. L 21/25 as prose judgement, margin 0 over the 21 floor: L1 scenario design 4, L2 progressive difficulty 4, L3 understanding over memorization 4, L4 hints and feedback 4 (up from 3, the lowest allowed), L5 transfer 5. Every L is at least 4. The margin is thin and I do not inflate it. The F1 residual would pull L4 back towards 3 for a learner on the private-kubeconfig path.

BLOCKING: none. NON-BLOCKING: F1 (private-kubeconfig path from module 1.1 is not mentioned), no tiered hints, the answer stated inline in 'Stop and think'. Accepted call-1 residuals stand: trivia not re-verified, 300 s toleration and grace period not re-checked, no citation seed.

PROVENANCE: reviewer is Claude Sonnet 5.5 (claude-sonnet-5-5, Anthropic family), outside the author's OpenAI/Codex family, run in Claude Code. CHECKS PERFORMED: git diff and hash, whole-page read of the lab section and greps. SUPPLIED AND NOT INDEPENDENTLY CHECKED: the PR body, which I could not read. LIMITS: the kubectl lab was not run, since the host has no cluster; I judged it as prose and design only. A static Pod 'kube-system' statement is UNKNOWN from my sources.

### Findings (verbatim JSON)

```json
[
 {
  "id": "F1",
  "title": "Fresh-terminal context lookup cannot find the Your First Cluster context",
  "body": "The new setup text tells the learner to open a fresh Bash terminal and run get-contexts, and it names `kind-dojo-basics` as the example from Your First Cluster. That module points KUBECONFIG at a private temp file inside a dedicated lesson shell (module-1.1-first-cluster.md lines 291-330). It also tells the learner to close that shell and to run lesson_delete and lesson_finish at the end. A learner who followed it literally will not see that context in a new terminal. The default kubeconfig was deliberately left unchanged. The page does not say so, and gives no step for this case.",
  "priority": "P3",
  "confidence": 0.7,
  "category": "docs",
  "location": {
   "path": "src/content/docs/prerequisites/cloud-native-101/module-1.3-what-is-kubernetes.md",
   "start_line": 539,
   "end_line": 539,
   "claim_type": "present"
  },
  "verbatim": "In a fresh Bash terminal, run `kubectl config get-contexts` and confirm that the current context points to your dedicated disposable cluster from Your First Cluster. The example cluster named `dojo-basics` uses `kind-dojo-basics`;",
  "why_wrong": "The example context exists only in the private kubeconfig of the lesson shell from Your First Cluster, so a literal 'fresh terminal' lookup can come up empty and leave the beginner without a next step. This is a narrow path. Other disposable clusters work, and the sibling prerequisite labs share the same fresh-terminal convention, so it is non-blocking.",
  "smallest_fix": "Add one sentence: if you created the cluster in the Your First Cluster lesson shell, run these commands in that shell or export its KUBECONFIG first, because a new terminal will not see the private kubeconfig.",
  "sources": [
   "none"
  ]
 }
]
```
