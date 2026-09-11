---
title: "How to Verify AI Output"
slug: ai/foundations/module-1.4-how-to-verify-ai-output
sidebar:
  order: 4
revision_pending: false
---

> **Complexity**: `[MEDIUM]`
>
> **Time to Complete**: 60-75 min
>
> **Prerequisites**: Modules 1.1-1.3, basic command-line comfort, and a willingness to test fluent answers against evidence

---

## Learning Outcomes

By the end of this module, you should be able to:

- Evaluate the risk level of AI output and choose a verification rigor that matches the cost of being wrong.
- Identify claims, assumptions, and the source of truth needed before treating AI output as reliable evidence.
- Implement an evidence-based verification workflow for AI-generated technical explanations, commands, and configuration changes.
- Diagnose hallucinated flags, deprecated fields, unsafe selectors, and destructive commands before they reach a real environment.
- Design guardrails for low-risk, medium-risk, and high-risk AI use so acceleration does not replace engineering judgment.

## Why This Module Matters

Hypothetical scenario: a teammate asks an AI tool for a quick fix during an incident. The answer is calm, specific, and formatted like a runbook. It suggests a Kubernetes command, explains why the command should work, and adds a confident warning that the change is safe. The team is tired, the service is noisy, and the answer looks much better than an empty terminal. If nobody verifies the command against the live cluster, the team may turn a draft into an outage.

That scenario is intentionally ordinary. The danger in AI-assisted work is rarely a visibly absurd answer. The danger is a response that is close enough to familiar practice that it passes a tired human's first glance. A model can combine real terminology, outdated syntax, plausible flags, and a correct-looking explanation into one polished artifact. Verification is the discipline that separates useful draft material from operational authority.

This module teaches a verification habit you can reuse across writing, study, coding, Kubernetes 1.35+ operations, infrastructure-as-code, and security review. You will learn to classify risk, isolate claims, pick a source of truth, test the output, and decide what can be used, revised, or discarded. The goal is not to distrust every response forever. The goal is to make trust earned, proportional, and anchored to evidence outside the generated text.

## The Core Rule: Ask What Happens If It Is Wrong

The most important AI habit is not writing a clever prompt. The most important habit is keeping judgment outside the model. A generated answer can be useful, but it should not become the source of truth merely because it is fluent. Before you ask whether an answer sounds good, ask what would happen if the answer were wrong. That question turns verification from a vague ideal into an engineering decision.

Low-risk output can tolerate lightweight checks because the cost of failure is low and the action is reversible. If a model rewrites your maintenance email, you should check meaning, tone, timing, and missing details. You do not need a formal review board for every sentence. You do need to make sure the rewrite did not change the maintenance window, soften a required warning, or invent a promise the team cannot keep.

Medium-risk output needs evidence because it may shape decisions, learning, or implementation. Study notes, code suggestions, workflow advice, architecture explanations, and troubleshooting hypotheses all belong here unless they touch production directly. The generated text may be a useful starting point, but it must be compared with docs, code, logs, tests, examples, or another source that is closer to reality than the model's training patterns.

High-risk output needs strong verification because the failure may be expensive, unsafe, or hard to reverse. Legal, medical, financial, security, production, and destructive command guidance should never be accepted on style alone. A command that opens port 22 to `0.0.0.0/0`, deletes resources through a broad selector, or changes identity policy may look ordinary in a code block. The blast radius is what matters.

Think of verification like choosing how carefully to cross a road. In an empty hallway, you glance and keep moving. On a quiet neighborhood street, you look both ways. At a busy intersection, you wait for the signal, watch the cars, and avoid stepping out just because another person says it is fine. AI output deserves the same proportional response. The check should match the consequence.

The practical categories are reversible and irreversible failure. A hallucinated phrase in a draft announcement is usually reversible because you can edit and resend a correction. A bad firewall rule, a broken database migration, or an unsafe cleanup command can create a real incident before anyone notices. The first step in verification is therefore a cost-of-failure assessment. If the answer is wrong, who notices, how quickly, and what has already changed by then?

Pause and predict: suppose an AI tool suggests changing a Kubernetes manifest from `readOnlyRootFilesystem: true` to `false` so a container can write a cache file. What evidence would you need before accepting the suggestion, and what could go wrong if the suggestion were copied into production without review? A strong answer should mention the application requirement, the security context, the writable path, the least-privilege alternative, and the policy or admission controls that apply in your cluster.

The same risk lens changes how you read every response. You stop asking whether the answer is impressive and start asking which claims need proof. A model can draft an explanation, propose a command, or suggest a manifest, but the generated artifact is not evidence by itself. Evidence comes from the live system, the current documentation, the repository, the test suite, the schema, the policy, the log line, or the human decision record.

This is why verification moves the engineer's role from writer to editor and auditor. AI can accelerate the first draft of a plan, but you remain responsible for intent, constraints, and consequences. High-seniority practitioners spend less time admiring syntax and more time asking whether the proposed action matches the system's safety boundaries. Treat generated output like untrusted user input: useful, structured, and sometimes exactly right, but not allowed to cross a trust boundary without validation.

## Build A Verification Ladder

A verification ladder helps you avoid two common extremes. One extreme is accepting every generated answer because it sounds authoritative. The other is treating every answer like a court filing and wasting time on checks that do not change the outcome. The ladder gives you a middle path: classify the risk first, then choose a verification method that matches the task.

The low-risk rung covers brainstorming, rewriting, tone adjustment, formatting, summarization of your own text, and rough ideation. Verification here is mostly about intent and distortion. Did the rewrite preserve the facts? Did the summary omit a condition? Did the tone create a promise or blame that was not in the original? You can move quickly because the source material is yours and the result is easy to inspect.

The medium-risk rung covers study notes, technical explanations, code snippets, workflow advice, design comparisons, and non-destructive operational guidance. Verification here is about grounding. You should identify the factual claims, compare them with a source of truth, and run safe examples where possible. The model may be right, but the reason you trust the output should be the evidence, not the response's polish.

The high-risk rung covers production changes, destructive shell commands, security guidance, identity policy, financial decisions, health advice, compliance interpretations, and anything that could harm users or systems. Verification here is a process, not a glance. You want primary sources, explicit evidence, dry runs, peer review, rollback planning, and a bias toward reversible changes. If the action cannot be safely previewed, slow down and change the workflow before acting.

| Risk Level | Typical Output | Verification Target | Reasonable Action |
|---|---|---|---|
| Low | Draft email, tone rewrite, summary of your own note | Meaning, intent, missing details | Read carefully and edit before sending |
| Medium | Technical explanation, code suggestion, study notes | Docs, tests, logs, code, schemas | Verify claims and run safe checks |
| High | Production change, security advice, deletion command | Primary docs, live dry run, peer review | Require evidence, approval, and rollback |

For technical work, moving up the ladder means moving from passive reading to systematic triangulation. A model might suggest Kubernetes syntax that was valid in an older API version, a Terraform argument from a provider release you do not use, or a command-line flag that exists in a different tool. The verification task is not to ask the model whether it is confident. The task is to compare the generated claim against the tool, version, and environment that will actually execute it.

The following example demonstrates the core habit. If a model suggests a command, do not only inspect whether the command looks familiar. Ask the local tool whether the flag exists, run a dry plan when the tool supports it, and inspect the proposed change before allowing state to move. Small deterministic checks can catch large probabilistic mistakes.

```bash
# Verify if the AI-suggested flag actually exists in your current CLI version
kubectl get pods --help | grep -- "--suggested-flag"

# Or, run a dry-run to see the impact without making changes
terraform plan -out=check.tfplan
# Then inspect the plan specifically for destructive actions (e.g., deletions)
terraform show -json check.tfplan | jq '.resource_changes[] | select(.change.actions[] == "delete")'
```

The command block is not a universal recipe. It is a pattern. First, ask the real tool about its interface. Second, ask the infrastructure tool for a planned change rather than applying it immediately. Third, inspect for destructive actions explicitly. The model may have generated the command, but the command earns trust only when deterministic tooling confirms what would happen.

Execution sandboxes are especially useful for medium-to-high-risk output. Instead of allowing a generated script to alter state, run it with a dry-run mode, against a temporary directory, in a disposable namespace, or with read-only credentials. If the script cannot be made previewable, that is itself a finding. A workflow that cannot be inspected before action is a poor match for generated suggestions.

```bash
# Example: Verifying an AI-suggested resource cleanup script
# 1. Capture the output but disable the destructive action
./ai-generated-cleanup.sh --dry-run > proposed_changes.log

# 2. Use 'grep' or 'wc' to check for unexpected scale
# If you expect 5 deletions and see 500, the AI logic is flawed
grep "Deleting" proposed_changes.log | wc -l

# 3. Perform a server-side dry-run for manifests to catch Admission Controller errors
kubectl apply -f ai-suggested-config.yaml --dry-run=server
```

Notice how the ladder keeps the model useful without giving it authority. You still get speed from the first draft, the cleanup idea, or the manifest skeleton. You also keep the verification outside the generated text. The model proposes; the environment, docs, tests, validators, and reviewers dispose. That separation is the difference between AI assistance and AI-shaped wishful thinking.

## Turn Answers Into Claims And Sources Of Truth

Verification becomes much easier when you stop treating the response as one large object. Break it into claims. A claim is any statement that could be true or false, any assumption that affects the result, or any instruction that changes what someone will do. The sentence "this field is supported in Kubernetes 1.35+" is a claim. The statement "this command is safe because it only deletes completed jobs" is a claim. The implied idea that a namespace selector is narrow enough is also a claim.

Once you have the claims, choose the source of truth for each one. Official documentation is a good source for public API behavior. The actual codebase is the source for local helper functions and project conventions. Logs, metrics, and event streams are the source for what happened in a system. A local CLI help page can be the source for installed command flags. A dry run or test suite can be the source for whether a proposed change behaves as intended.

The source of truth should be closer to the decision than the model is. If you are verifying a Kubernetes manifest, the live cluster schema may matter more than a generic blog post. If you are verifying a repository-specific command, the repository scripts and current branch matter more than a public example. If you are verifying a policy decision, the team's written policy or decision record matters more than a generated best-practice paragraph.

The practical workflow is simple enough to memorize: identify the claim, classify the risk, choose the source of truth, check the answer against that source, and only then act. The simplicity is intentional. Under pressure, complicated verification frameworks get skipped. A short loop can become muscle memory, and muscle memory is what protects you when the response is fluent and the clock is loud.

For Kubernetes-specific output, the source of truth often includes the cluster's discovery API and admission path. Static memory of Kubernetes concepts is not enough because clusters have versions, feature gates, custom resources, admission controllers, and policy engines. A manifest that looks reasonable in a generic answer may fail validation, violate local policy, or behave differently because your cluster has additional controllers installed.

```bash
# Validate the AI-generated manifest against the live cluster schema
kubectl apply -f ai-generated-resource.yaml --dry-run=server --validate=true

# Cross-reference the suggested fields with the live API documentation
# to verify the AI isn't hallucinating non-existent parameters
kubectl explain pod.spec.containers.securityContext | grep -A 5 "readOnlyRootFilesystem"
```

That example verifies two different claims. The server-side dry run checks whether the manifest is acceptable to the cluster's API path without persisting the resource. The `kubectl explain` command checks whether a field exists where the answer claimed it exists. Neither command proves that the configuration is a good design, but both commands reduce the risk that a plausible answer hides a basic schema mistake.

Before running this, what output do you expect if the generated manifest contains a field in the wrong location? A strong prediction is that the server-side dry run should fail with a validation or decoding error, while `kubectl explain` should not show the field at the path the model proposed. Making the prediction first matters because it keeps you from treating any output as success merely because a command printed something technical.

Some generated answers mix several claim types in one paragraph, so you may need multiple checks. A troubleshooting answer might claim that a pod restarted, that the restart came from memory pressure, that the fix is increasing limits, and that no code change is required. Those claims map to different sources: `kubectl describe`, events, metrics, container exit reasons, repository changes, and maybe application logs. A single agreeable paragraph cannot settle all of them.

It helps to write a small verification note when the result matters. Use three columns: AI claim, source of truth, and result. That note does not need to be formal. It can be a scratchpad during incident work or a short comment in a pull request. The act of writing the source forces a useful question: am I checking against reality, or am I merely asking another language model to sound equally confident?

Asking a second model can be useful for critique, alternative hypotheses, or spotting missing assumptions. It is not the same as verification. Two models may share training patterns, common documentation examples, or the same misleading prompt. Agreement between generated answers is a signal worth considering, but it is weaker than evidence from the actual system. Treat model-to-model comparison as brainstorming unless it is followed by an external check.

The following wrapper is useful when you want the model to make its own assumptions visible before you verify them. It does not replace evidence. It helps you extract claims, version assumptions, and edge cases from the answer so your human verification has better handles.

```markdown
[Verification Wrapper]: After answering my query, please provide:
1. The specific API version assumptions (e.g., policy/v1 vs v1beta1).
2. Two edge cases or environment constraints where this solution would fail.
3. The official documentation link or RFC number that governs this behavior.
4. A "confidence score" (1-10) for the factual accuracy of any code snippets.
```

Use that wrapper carefully. A generated documentation link may still be wrong, stale, or irrelevant. A generated confidence score is not a calibrated probability unless the surrounding system has been specifically evaluated for that behavior. The wrapper is valuable because it exposes what to check, not because it certifies the answer.

## Verify Technical Output With Deterministic Checks

Technical verification works best when you convert generated language into deterministic checks. A model is probabilistic, but a parser, validator, unit test, dry run, schema query, and help command are more constrained. The point is not that deterministic tools are perfect. The point is that they fail in more inspectable ways and are grounded in the version of the tool, code, or cluster you are actually using.

Start with interface verification. If a command uses a flag you do not recognize, ask the installed tool for help. If a library call uses a parameter that looks new, check the package docs or introspect the installed version. If a manifest uses an unfamiliar field, query the API schema. Many AI mistakes are not deep reasoning failures. They are version drift, copied syntax from a nearby tool, or a plausible field name that never existed.

Then verify scope. Destructive commands often fail because their selector, path, namespace, account, or filter is broader than intended. A cleanup command with a missing label selector can delete far more than a human expected. A file deletion command with an unquoted variable can expand unpredictably. A Terraform expression can target resources outside the intended module. Scope verification asks, "What exact objects would this touch?"

Finally verify consequence. A command can be syntactically valid and correctly scoped while still being a poor decision. Increasing a memory limit might hide a leak. Disabling a security setting might make an application work while violating policy. Rolling back a deployment might restore service while discarding a database migration dependency. Consequence verification asks whether the action fits the operational objective, not merely whether the syntax passes.

| Verification Layer | Question | Tooling Examples | What It Catches |
|---|---|---|---|
| Interface | Does this flag, field, or function exist here? | `--help`, `kubectl explain`, package docs | Hallucinated parameters and version drift |
| Scope | What objects or paths would be affected? | dry runs, selectors, `find -print`, plan output | Broad selectors and unintended targets |
| Consequence | Is the proposed action appropriate? | tests, metrics, review, rollback plan | Valid but harmful changes |
| Accountability | Who approved the risk? | pull request, change ticket, incident log | Unowned decisions and weak audit trail |

Kubernetes manifests are a good example because they combine all four layers. A generated manifest may use a valid API version, but the fields may be misplaced. It may pass schema validation, but select the wrong pods. It may select the right pods, but break traffic because a NetworkPolicy omitted DNS or health checks. It may be technically correct, but unacceptable because the change bypasses the team's approval process.

Infrastructure-as-code needs the same habit. A Terraform plan is more trustworthy than a generated prose explanation of what Terraform will do, but even the plan requires review. You should inspect creation, update, replacement, and deletion actions. You should compare the plan against the intended change. You should notice when the output is larger than expected, because unexpected scale often reveals a wrong module path, provider configuration, or variable value.

For generated code, tests provide a strong first check, but they are not complete verification. A unit test can catch obvious behavior errors while missing security, performance, concurrency, and integration concerns. If the model generated a regex, test positive and negative examples. If it generated a migration, test rollback and data preservation. If it generated a script, test empty input, multiple matches, strange filenames, and permission errors.

Which approach would you choose here and why: asking the model to explain a generated command one more time, or running the command in a harmless preview mode and comparing the output with your expectation? The preview is usually stronger because it observes tool behavior directly. The explanation can help you understand, but it cannot substitute for the evidence produced by the tool that will actually run.

There is one more subtle check: compare the answer against local conventions. A command may be technically valid and still wrong for your team. Maybe the repository requires a wrapper script, a specific namespace, a staging branch, a policy label, or a change-management ticket. The model will not infer those conventions unless they are in context. Your verification should include project rules, not just public documentation.

Treat all generated technical output like a pull request from a fast junior contributor. You do not reject it because it came from a junior contributor, and you do not merge it because it is formatted well. You review the diff, run the tests, check the risk, and ask for changes when assumptions are missing. The productivity gain survives because review is narrower than blank-page creation.

## Calibrate Verification To Workflow Risk

Verification is easiest when it is built into the workflow before pressure arrives. If every AI-assisted action requires a brand-new judgment call, people will skip steps during incidents, deadlines, or late-night maintenance. A good workflow makes the common checks obvious. It gives low-risk work a light path, medium-risk work a structured path, and high-risk work a guarded path with approvals and rollback.

For writing and communication, the workflow can stay simple. Keep the original text nearby, compare meaning, confirm names and dates, and remove invented promises. If the message affects customers, compliance, security, or incident communication, raise the risk level. The model may help with clarity, but the owner must verify that the final message is accurate, complete, and aligned with the team's decision.

For study and documentation, require source anchoring. Generated study notes should point back to official docs, course material, source code, or observed behavior. If you plan to share notes with new hires, treat them as medium risk because the notes can shape future decisions. A confident simplification that omits an exception may become team folklore. Verification prevents helpful summaries from becoming unsupported doctrine.

For operational changes, put the guardrails in tooling. Prefer read-only credentials for analysis. Require server-side dry runs for Kubernetes manifests when practical. Require infrastructure plans before apply operations. Require peer review for production changes. Record the evidence used to accept or reject the generated suggestion. These guardrails matter because the model's output quality will vary, but the workflow can remain stable.

For security-sensitive work, verification must include threat modeling. A generated answer may fix the symptom while widening the attack surface. For example, changing a security context, opening a network rule, weakening authentication, or broadening identity permissions can make an application work by removing the control that was protecting the system. Security verification asks whether the proposed fix preserves the control objective, not only whether the immediate error disappears.

One practical pattern is to assign every generated artifact a status. "Disposable" means the output is only a thinking aid and should not be preserved. "Draft" means it can be edited and checked by a human. "Evidence-backed" means key claims have been verified against sources. "Actionable" means the output has passed the checks required for its risk level. The status label prevents a brainstorming response from quietly becoming a deployment plan.

The label also helps teams communicate. Instead of saying "the AI says this is safe," an engineer can say, "This is a draft cleanup script. I verified the flags against local help, ran dry-run output, and confirmed the selector touches only the expected objects. It still needs peer review before production." That sentence makes evidence and remaining risk visible. It also keeps accountability with the team.

Verification should also handle refusal to act. Sometimes the right result is not a better command but a decision that the output should not be used. Maybe the model invented a field, missed a policy, gave advice outside your expertise, or asked for access that the workflow should not grant. Discarding output is not wasted effort. It is the expected result of a verification process that has real standards.

The habit becomes stronger when you log what failed. If the model often invents flags for a tool, add a standard help-check step. If it often misses local naming conventions, add a context template. If it often overstates certainty in incident summaries, require evidence labels. Verification is not only a gate at the end. It is feedback that improves how you prompt, review, and design AI-assisted workflows.

## Worked Example: Verify A Troubleshooting Answer

Exercise scenario: a staging deployment starts failing readiness checks after a configuration change. An AI tool receives a short prompt that says, "The API pods are unhealthy after the release. What should I do?" It responds that the likely cause is a missing environment variable and suggests editing the deployment immediately. The answer is plausible because missing environment variables are common, but the prompt did not include pod events, container logs, rollout history, or the changed manifest.

The first verification move is to label the answer as a hypothesis rather than a conclusion. The claim is not "the model found the problem." The claim is "a missing environment variable could explain the symptom." That distinction matters because it changes what you check next. You do not edit the deployment to match the hypothesis. You gather the evidence that would make the hypothesis true or false.

For this scenario, the source-of-truth packet should include rollout status, recent events, pod logs, the deployment diff, and the readiness probe configuration. If events show image pull failures, the missing-variable hypothesis is probably a distraction. If logs show the application exiting with a configuration error and the deployment diff removed a required variable, the hypothesis becomes stronger. The same generated sentence can be weak or useful depending on whether evidence supports it.

The second move is to check for version and environment assumptions. The model might suggest a `kubectl` field path, a probe setting, or a patch command that is close to correct but wrong for the current object shape. A live schema query and a server-side dry run help here. They do not prove root cause, but they prevent you from turning a troubleshooting hypothesis into a syntactically invalid or policy-violating change.

The third move is to separate diagnosis from remediation. Even if the missing variable is real, the safest next action may not be a direct edit in staging. The team may prefer a pull request that restores the variable in source control, a rollback to the previous image, or a temporary patch followed by a permanent fix. Verification should therefore ask both "is this diagnosis supported?" and "is this action the right way to correct it?"

This worked example also shows why active learning matters. Before you inspect the logs, predict what evidence would support each explanation. Missing variables should produce application-level errors or failed startup messages. Bad image references should appear in pull events. Readiness probe path mistakes should show probe failures against a specific endpoint. Making these predictions ahead of time reduces confirmation bias because you are not merely hunting for text that resembles the generated answer.

If you were writing a claim-source-result note for this case, it might contain three rows. One row would map "readiness failure caused by missing variable" to logs and the deployment diff. Another row would map "suggested patch uses a valid field" to `kubectl explain` and server-side dry run. A third row would map "direct edit is acceptable" to team workflow, ownership, and rollback policy. The model's answer becomes one input to a reviewable decision instead of a substitute for the decision.

The final outcome may be that the answer was partially useful. Maybe it named a real failure mode but guessed the wrong object. Maybe it suggested a valid command but skipped the team's source-control rule. Maybe it correctly identified the missing variable, while the right remediation was a pull request rather than a live patch. Verification does not require the output to be entirely right or entirely wrong. It requires you to preserve the useful parts and block the unsupported parts.

## Patterns & Anti-Patterns

Good verification patterns have one shared property: they move truth outside the generated answer. The model may still assist with drafting, decomposition, summarization, and critique, but the final confidence comes from sources, tools, tests, and accountable review. This separation lets you benefit from generation without pretending generation is the same thing as evidence.

| Pattern | When To Use It | Why It Works | Scaling Consideration |
|---|---|---|---|
| Claim-source-result note | Medium-risk explanations, study notes, and pull requests | It forces every important claim to name evidence | Turn the note into a template for repeated workflows |
| Dry-run first | Manifests, infrastructure plans, cleanup scripts, migrations | It previews scope before state changes | Automate dry-run capture in CI or change tickets |
| Live schema check | Kubernetes and API-driven configuration | It grounds syntax in the actual environment | Pair with version labels and policy checks |
| Human approval gate | High-risk production, security, and identity changes | It keeps accountability with qualified reviewers | Define who can approve which risk level before incidents |

The claim-source-result pattern is a good default because it works across many domains. In documentation, the source may be an official page. In debugging, it may be a log line. In code, it may be a test. In policy, it may be a written standard. The format is simple enough to use in a scratchpad, but explicit enough to expose unsupported claims.

Dry-run first is the operational pattern that prevents many painful mistakes. It does not guarantee safety, but it changes the conversation from "this looks safe" to "here is what the tool says it would affect." That evidence is reviewable. If the preview is unexpectedly broad, the generated command has failed before it can damage anything.

Live schema checks matter because generated answers often blur versions and environments. A model may know that a field exists somewhere, but not whether it exists in your cluster, provider, or installed package. Asking the live API or installed tool grounds the answer in the execution target. This is especially important for Kubernetes 1.35+ clusters with admission controllers, custom resources, and local policy constraints.

Human approval gates are not a sign that AI has failed. They are how serious systems handle serious consequences. A generated security change, production rollback, or identity policy update should have an owner, a reviewer, and a rollback plan. AI can reduce the time needed to prepare the change, but it should not erase the accountability that makes the change acceptable.

Anti-patterns collapse generation and verification into the same step. They often feel efficient because they reduce friction in the moment. The cost arrives later, when a plausible response turns into a wrong command, a misleading document, or an unsupported operational decision. The better alternative is usually a small external check, not a larger prompt.

| Anti-Pattern | What Goes Wrong | Better Alternative |
|---|---|---|
| Trusting polished language | Fluency hides missing evidence and stale assumptions | Require claim-source-result for medium and high risk |
| Asking the same model to verify itself | The critique may repeat the same unsupported pattern | Check docs, code, logs, schemas, tests, or reviewers |
| Skipping dry runs under time pressure | Destructive scope errors reach real systems | Make preview commands part of the incident checklist |
| Treating public examples as local truth | Local versions, policies, and conventions differ | Verify against installed tools and the live environment |
| Using AI output directly in production | A draft crosses a trust boundary without approval | Require risk classification and approval before action |
| Letting generated notes become team folklore | Simplifications turn into false institutional memory | Attach sources and expiration dates to reference material |

The main scaling lesson is that verification should become boring. If every check feels heroic, the workflow is too fragile. Templates, preflight scripts, CI validators, policy checks, and review checklists make the right thing easier to repeat. That is how a team keeps AI assistance fast without turning every response into an exception.

## Decision Framework

Use this framework when an AI output appears useful and you need to decide what to do next. It intentionally starts with consequence rather than confidence. A response can be confident and still wrong, while an uncertain response may contain a useful hypothesis. Consequence determines the minimum verification path.

```text
+-------------------------------+
| AI output arrives              |
+-------------------------------+
              |
              v
+-------------------------------+
| What if this is wrong?         |
+-------------------------------+
      | low            | medium/high
      v                v
+----------------+  +---------------------------+
| Check intent   |  | Identify claims and risk   |
| and meaning    |  | choose source of truth     |
+----------------+  +---------------------------+
      |                |
      v                v
+----------------+  +---------------------------+
| Edit or discard|  | Run docs/tests/dry-run     |
| before use     |  | schema/log/code checks     |
+----------------+  +---------------------------+
                       |
                       v
                 +---------------------------+
                 | Need approval or rollback?|
                 +---------------------------+
                       |
                       v
                 +---------------------------+
                 | Act only after evidence   |
                 | matches required rigor    |
                 +---------------------------+
```

The first branch is low risk. If the output is a tone rewrite, brainstorm list, or summary of text you supplied, check meaning and move on. Do not overbuild the process. The second branch covers anything that teaches, configures, troubleshoots, deletes, deploys, grants access, or changes user-facing behavior. That branch requires evidence because the answer can shape real decisions.

Use the following decision matrix when the risk is not obvious. The same artifact can move between columns depending on context. A generated command in a temporary lab is lower risk than the same command in production. A study note for yourself is lower risk than a page that becomes onboarding reference for new engineers. Risk belongs to the workflow, not just the text.

| If The Output Will... | Treat It As | Minimum Verification |
|---|---|---|
| Improve wording without changing facts | Low risk | Compare with the original and check intent |
| Explain a technical concept for learning | Medium risk | Compare with official docs and known examples |
| Suggest code or commands for local testing | Medium risk | Run tests, help checks, and safe previews |
| Change shared infrastructure | High risk | Dry run, peer review, rollback, source evidence |
| Affect security, compliance, money, or health | High risk | Primary sources, qualified human review, documented approval |

If you are still unsure, raise the risk level by one rung. This conservative rule is not about fear. It is about avoiding hidden coupling. A small-looking technical change can have large consequences when it sits inside production, identity, networking, data retention, or customer communication. Extra verification is cheaper than recovering from a change that should never have crossed the boundary.

The framework also tells you when AI output is disposable. If you cannot identify the claims, cannot find an appropriate source, cannot preview the action, or cannot explain the consequence, do not promote the output to action. Ask for a smaller artifact, gather missing evidence, or discard the suggestion. A model that cannot produce a verifiable answer for a high-risk task should not be negotiated into authority.

## Did You Know?

- **NIST published AI RMF 1.0 in January 2023**: the framework separates trustworthy AI work into govern, map, measure, and manage functions, which is a useful reminder that risk handling starts before a model response is generated.

- **Kubernetes server-side dry run reached stable status years before many teams made it routine**: the feature exists so clients can ask the API path what would happen without persisting a change, which is exactly the kind of deterministic check AI-assisted manifest work needs.

- **OWASP lists misinformation as a generative-AI application risk**: the security concern is not only malicious input, but also overreliance on plausible output that can produce unsafe decisions.

- **A second model is not a primary source**: model agreement may help you discover alternatives, but docs, code, logs, tests, schemas, and qualified reviewers are stronger evidence for technical action.

## Common Mistakes

| Mistake | Why It Happens | How to Fix It |
|---|---|---|
| Trusting polished language | Fluent answers feel like expertise, especially under time pressure | Classify risk first, then require evidence for medium and high-risk claims |
| Treating AI output as the source of truth | The generated answer is easier to read than docs, logs, or code | Name the source of truth before acting and compare the answer against it |
| Verifying by asking the same question again | Another generated answer feels like confirmation | Use a deterministic check, primary source, or reviewer outside the model loop |
| Skipping scope checks on commands | The command looks familiar, so selectors and paths get ignored | Preview affected objects with dry runs, plans, `find -print`, or read-only queries |
| Ignoring version drift | The answer uses real syntax from another release, provider, or tool | Check installed help output, live schemas, package docs, and cluster version behavior |
| Letting study notes become authority | Helpful summaries get reused without their original context | Attach sources, mark uncertainty, and re-check before sharing as reference material |
| Removing controls to make an error disappear | The model optimizes for immediate success, not policy intent | Verify the control objective and look for a least-privilege fix |
| Forgetting rollback and ownership | Fast drafts make actions feel temporary and low commitment | Require an owner, success criteria, rollback plan, and approval for high-risk changes |

## Quiz

1. **Your team uses AI to rewrite an internal email announcing a maintenance window. The message sounds clearer than your draft, but you are about to send it to hundreds of employees. What should you verify before sending, and why is this still considered low risk?**

   <details>
   <summary>Answer</summary>

   Check that the rewrite preserves the maintenance time, expected duration, affected systems, and any required action for readers. This is low risk because the task is wording and tone rather than production behavior, and the original source material is available for comparison. The verification target is meaning, not external technical truth. If the rewrite invents a promise, changes the time, or removes a warning, edit or discard it before sending.

   </details>

2. **An AI tool suggests a shell command to delete old files from a server, and the command looks plausible at first glance. What verification steps should you take before running it?**

   <details>
   <summary>Answer</summary>

   Treat the command as high risk because deletion changes state and may be hard to reverse. Verify the path, filename pattern, quoting, flags, and exact objects that would be affected. Replace the destructive action with a read-only preview such as `find ... -print` or a dry-run mode when available. Run the destructive command only after the preview matches your expectation and the rollback or restore path is clear.

   </details>

3. **You ask AI for a quick explanation of why a deployment failed, and it gives a confident answer about a Kubernetes configuration problem. What is the right next step if you classify this as medium risk?**

   <details>
   <summary>Answer</summary>

   Break the explanation into claims and compare them with evidence from the actual deployment. Useful sources include events, pod status, logs, the changed manifest, rollout history, and official Kubernetes documentation for any fields involved. A medium-risk troubleshooting answer can be a good hypothesis, but it should not become the conclusion until the evidence supports it. If the model names a field or behavior, verify that field against `kubectl explain` or the relevant docs.

   </details>

4. **A colleague says they already verified an AI-generated troubleshooting answer by pasting the same prompt into a second model and getting a similar response. Why is that not enough?**

   <details>
   <summary>Answer</summary>

   Model agreement can be useful for brainstorming, but it is not the same as checking against reality. Two systems may share common examples, repeat the same unstated assumption, or both lack access to your logs and code. Real verification uses a source of truth such as official docs, command output, repository state, tests, or a qualified reviewer. The second model may help you identify what to check, but it cannot replace the check.

   </details>

5. **AI suggests a new firewall rule to quickly fix remote access for your production environment. The change would expose port 22 to `0.0.0.0/0`. How should you think about the risk, and what level of verification is appropriate?**

   <details>
   <summary>Answer</summary>

   This is high risk because it changes security exposure for a production environment. The right response is not to accept the rule because it restores access, but to verify the operational need, threat impact, and least-privilege alternative. You should require primary guidance, peer review, approval, and a rollback plan before any change. A narrower source range, temporary access path, or separate break-glass process may satisfy the need without removing the control.

   </details>

6. **You receive an AI-generated CLI example that uses a flag you do not recognize. The syntax looks professional, and you are under time pressure. What workflow should you apply before using it?**

   <details>
   <summary>Answer</summary>

   Identify the flag claim, classify the task risk, choose the installed CLI help or official docs as the source of truth, and check the answer before acting. If the flag exists, verify that it means what the answer claimed in your tool version. If the flag does not exist or behaves differently, discard or revise the command. Professional formatting is not evidence, especially for command-line interfaces that change across releases.

   </details>

7. **Your team asks AI for study notes summarizing a technical system you are learning. The notes seem helpful, but you plan to share them with new hires as a reference. What should you verify before treating them as reliable?**

   <details>
   <summary>Answer</summary>

   Treat the notes as medium risk because they may shape future understanding and decisions. Compare key claims with official docs, source code, architecture records, or observed behavior in the real system. Look for missing conditions, version assumptions, unsupported simplifications, and tradeoffs the notes skipped. If the notes become reference material, attach sources and mark areas that require re-checking when the system changes.

   </details>

## Hands-On Exercise

The goal of this exercise is to practice a repeatable verification workflow by checking low-risk, medium-risk, and high-risk AI outputs against evidence before acting on them. You will work in a temporary lab directory so the commands are safe, then you will write a short claim-source-result note. The exercise is deliberately small because the habit matters more than the tool. If you can do this in a scratch directory, you can scale the same thinking to pull requests, Kubernetes manifests, Terraform plans, and incident summaries.

Setup note: run the commands from a normal shell on a machine with standard Unix tools. Some help commands differ slightly between GNU and macOS environments, so the examples include fallbacks where useful. Do not use a shell alias for `kubectl` in reusable scripts or copied examples; aliases often do not expand in non-interactive shells. For this exercise, the Kubernetes examples in the module are conceptual, while the local file commands are the commands you will actually run.

- [ ] Create a temporary lab directory and a small set of sample files to work with.

  ```bash
  LAB_DIR="$(mktemp -d)"
  mkdir -p "$LAB_DIR"/logs
  touch "$LAB_DIR"/logs/app.log "$LAB_DIR"/logs/api.log "$LAB_DIR"/logs/old.log
  ls -la "$LAB_DIR"/logs
  ```

- [ ] Ask an AI tool to rewrite a short maintenance email for clarity. Compare the rewrite against your original and mark any changes in meaning, tone, or missing details.

  Use these verification commands to keep the original facts visible while you review the generated rewrite for altered timing, softened warnings, or invented promises.

  ```bash
  printf '%s\n' "Original email:" 
  printf '%s\n' "Maintenance starts at 18:00 UTC, expected duration 20 minutes, dashboards may be briefly unavailable."
  ```

- [ ] Ask the AI tool for a command that lists files in the `logs` directory sorted by name. Do not run the suggestion yet. First verify that the command is safe and read-only.

  Use these verification commands to inspect your current directory and the temporary lab path before trusting any generated listing command.

  ```bash
  pwd
  ls -la "$LAB_DIR"
  ls -la "$LAB_DIR"/logs
  ```

- [ ] Check each part of the AI-suggested listing command against local help output or built-in documentation. Confirm that every flag exists and means what the AI output claimed.

  Use these verification commands to compare the generated flags with local documentation, accepting small platform differences while rejecting unsupported claims.

  ```bash
  ls --help 2>/dev/null | head -n 20 || ls -G
  man ls | col -b | head -n 30 2>/dev/null
  ```

- [ ] Run the verified read-only command and compare the output with what you expected from the directory contents.

  Use this verification command only after the earlier checks pass, then compare the sorted output with the files you created during setup.

  ```bash
  ls -1 "$LAB_DIR"/logs | sort
  ```

- [ ] Ask the AI tool for an explanation of what a command like `find "$LAB_DIR"/logs -name '*.log'` does. Identify the claims in the explanation, then verify them by running a safe example.

  Use these verification commands to test the explanation against real output, especially claims about filename matching and file counts.

  ```bash
  find "$LAB_DIR"/logs -name '*.log'
  find "$LAB_DIR"/logs -type f | wc -l
  ```

- [ ] Ask the AI tool for a command to delete `old.log`. Treat this as high risk even in a temporary directory. Verify the path, the filename, and whether the action is reversible before running anything destructive.

  Use these verification commands to prove the target path and filename before any destructive action, because a deletion command deserves stronger evidence.

  ```bash
  realpath "$LAB_DIR"/logs/old.log 2>/dev/null || readlink "$LAB_DIR"/logs/old.log
  ls -la "$LAB_DIR"/logs
  find "$LAB_DIR"/logs -maxdepth 1 -name 'old.log' -print
  ```

- [ ] Perform a dry-run mindset check by replacing the destructive action with a read-only preview first. Confirm that only the intended file would be affected.

  Use these verification commands to preview the exact object and the exact deletion command, while still keeping the shell in read-only mode.

  ```bash
  find "$LAB_DIR"/logs -maxdepth 1 -name 'old.log' -print
  printf '%s\n' rm "$LAB_DIR"/logs/old.log
  ```

- [ ] Delete the file only after the preview matches your expectation, then verify the result.

  Use these verification commands after the preview matches your expectation, then confirm the target is gone and no other log file was removed.

  ```bash
  rm "$LAB_DIR"/logs/old.log
  ls -la "$LAB_DIR"/logs
  find "$LAB_DIR"/logs -maxdepth 1 -name 'old.log' -print
  ```

- [ ] Write a short note with three columns: `AI claim`, `source of truth`, and `result`. Record one example each for low-risk, medium-risk, and high-risk verification from this exercise.

  <details>
  <summary>Solution guidance</summary>

  A strong note should show that each output was treated according to risk. For the email rewrite, the source of truth is the original message and your intended communication. For the listing command, the source of truth is the local filesystem plus `ls` documentation. For the deletion command, the source of truth is the previewed path and the exact file match. The important distinction is that the generated answer never verifies itself.

  </details>

Use this success checklist to confirm that the exercise practiced proportional verification instead of merely running commands in sequence.

- [ ] The low-risk rewrite was checked for meaning and intent, not just style.
- [ ] At least one AI-suggested command was verified against local help output before execution.
- [ ] A technical explanation from AI was checked against real command output.
- [ ] A destructive action was previewed before it was run.
- [ ] The final notes clearly separate AI suggestions from evidence-based conclusions.

## Sources

- [NIST AI Risk Management Framework (AI RMF 1.0)](https://www.nist.gov/publications/artificial-intelligence-risk-management-framework-ai-rmf-10)
- [NIST Artificial Intelligence Risk Management Framework: Generative Artificial Intelligence Profile](https://www.nist.gov/publications/artificial-intelligence-risk-management-framework-generative-artificial-intelligence)
- [OWASP LLM09:2025 Misinformation](https://genai.owasp.org/llmrisk/llm092025-misinformation/)
- [Kubernetes: Declarative Management of Kubernetes Objects Using Configuration Files](https://kubernetes.io/docs/tasks/manage-kubernetes-objects/declarative-config/)
- [Kubernetes: kubectl apply reference](https://kubernetes.io/docs/reference/kubectl/generated/kubectl_apply/)
- [Kubernetes: kubectl explain reference](https://kubernetes.io/docs/reference/kubectl/generated/kubectl_explain/)
- [Kubernetes API reference](https://kubernetes.io/docs/reference/kubernetes-api/)
- [Terraform CLI: plan command](https://developer.hashicorp.com/terraform/cli/commands/plan)
- [Terraform CLI: show command](https://developer.hashicorp.com/terraform/cli/commands/show)
- [jq manual](https://jqlang.github.io/jq/manual/)

## Next Module

Continue to [Privacy, Safety, and Trust](../module-1.5-privacy-safety-and-trust/) to learn how verification connects to data handling, safety boundaries, and responsible AI use.
