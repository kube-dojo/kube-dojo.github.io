---
title: "Privacy, Safety, and Trust"
slug: ai/foundations/module-1.5-privacy-safety-and-trust
sidebar:
  order: 5
---

> **Complexity**: `[MEDIUM]`
>
> **Time to Complete**: 45-60 min
>
> **Prerequisites**: AI foundations, basic command-line literacy, and a beginner-level understanding of cloud or Kubernetes workflows

---

## What You'll Be Able to Do

- Design privacy boundaries for AI workflows by separating public, internal, confidential, and regulated data before any prompt reaches a model.
- Evaluate trust levels for AI outputs by matching the task's blast radius to evidence, review, and human accountability requirements.
- Diagnose safety risks in AI-assisted work, including data exposure, prompt injection, hallucinated advice, hidden bias, and over-automation.
- Implement a sanitization and review workflow that reduces sensitive-data leakage before using local, private, or approved enterprise AI tools.
- Compare local, private, and approved enterprise AI options when deciding whether a task belongs in an external model, internal gateway, or manual process.

## Why This Module Matters

Hypothetical scenario: an engineer is debugging a failed deployment late in the day, and an AI assistant offers to summarize the logs if the engineer pastes the whole bundle into a chat box. The log bundle includes customer identifiers, internal service names, a private endpoint, and a stack trace that reveals library versions. The engineer is not trying to leak anything; they are trying to move quickly. Privacy failures often begin exactly there, at the point where convenience feels like care but removes the boundaries that normally protect a system.

The operational stakes are bigger than passwords. A prompt can contain personal data, commercial strategy, unreleased product plans, architecture details, security posture, incident timelines, and metadata about what a team is investigating. Even when no single line looks like a secret, the combined context can describe how the organization works. A model provider, a logging system, a browser extension, an analytics layer, or a misconfigured internal retrieval store may retain more than the learner intended to share.

Trust is the second half of the problem. AI output can sound fluent while being incomplete, stale, overconfident, or wrong for the local environment. In infrastructure work, a polished answer can still recommend a risky Kubernetes manifest, an obsolete policy, or a command that changes production state without review. The safer habit is not to reject AI tools. The safer habit is to decide what data the tool may see, what authority the output may have, and what verification must happen before a human acts on it.

In this module you will turn that habit into a practical workflow. You will classify data before prompting, choose between local and approved AI paths, apply a trust model to different tasks, and build a small sanitization review that keeps sensitive context out of an external prompt. The examples stay close to cloud-native work because KubeDojo learners often use AI to explain manifests, summarize logs, review YAML, and plan Kubernetes 1.35+ operations.

## Start With A Simple Principle

The easiest AI tools are also the easiest tools to use without thinking. A browser tab accepts whatever you paste, produces an answer in seconds, and usually hides the infrastructure behind a friendly interface. That interface can make a risky act feel casual. If you would hesitate to paste the same material into a public issue tracker, shared chat room, or unknown software-as-a-service form, you should pause before pasting it into an AI tool as well.

That pause is not bureaucracy. It is the functional boundary between experimentation and professional engineering. When you send a prompt to a model, you are not only sending the words you typed. You may be sending file names, error paths, usernames, cluster names, namespace conventions, customer traces, cloud regions, image tags, dependency versions, and the reason your team is investigating them. Those details can be more useful to an attacker than a single obvious secret because they describe how to reason about the environment.

Think of prompting like giving a contractor a temporary badge. The contractor may be skilled, but you still decide which room they can enter, what documents they may see, and who checks the work before it affects production. The same distinction applies to AI systems. A public model may be fine for rewriting a paragraph about public documentation. It is a poor default for analyzing a private incident bundle unless the data path, retention policy, contract, and internal approval have already been settled.

The first design move is to classify the data before you classify the tool. Public information can usually go to a broader set of tools because the privacy consequence is small. Internal information may require an approved enterprise account, a contractual data-processing agreement, or a gateway that logs access. Confidential and regulated information often belongs in a private environment, a local model, a tightly scoped retrieval system, or a manual workflow where the data never leaves the governed boundary.

Pause and predict: what do you think happens if an engineer removes passwords from a log bundle but leaves service names, customer IDs, private IP ranges, and the production namespace? The prompt no longer contains a classic credential, but it still reveals a precise operational map. In a real review, you would treat that as sensitive context because it can help someone infer architecture, business relationships, incident impact, or internal naming standards.

The protected boundary also includes the model's output. If the model sees sensitive context, its answer may restate that context, include it in generated notes, or embed it in a ticket that has wider access than the original data. A careless workflow can therefore leak information twice: once when the prompt leaves the team, and again when the response is copied into a place where more people can read it. Safe AI use requires controlling both directions.

For highly sensitive work, local inference is one practical option. A local model does not automatically solve every safety problem, because you still need access control, patching, logging, and output review. It does, however, change the data movement problem. If the prompt stays on a developer workstation, in a private Kubernetes namespace, or inside a controlled virtual private cloud, the organization can reduce third-party exposure while still receiving assistance on summarization, extraction, or first-pass review.

The following preserved example shows a local model path for sensitive manifest review. The commands are intentionally full and copy-pasteable, and the prompt text uses a bracketed placeholder instead of real customer or infrastructure data. In a production-grade version, you would also pin the image, control network egress, restrict local files mounted into the container, and document who is allowed to use the model for which data classes.

```bash
# Deploy a local instance to ensure data sovereignty
docker run -d -v ollama:/root/.ollama -p 11434:11434 --name ollama ollama/ollama

# Pull a model before the first API call (required on a fresh setup)
docker exec ollama ollama pull llama3.2

# Execute an inference call where the prompt never leaves your local network
curl http://localhost:11434/api/generate -d '{
  "model": "llama3.2",
  "prompt": "Review this internal k8s manifest for security misconfigurations: [MANIFEST_CONTENT]",
  "stream": false
}'
```

Local does not mean automatically trustworthy. The model may still hallucinate a Kubernetes field, miss a dangerous permission, or recommend a pattern that conflicts with your organization's policy. It can also create a new internal risk if every developer downloads different models and keeps unreviewed copies of sensitive prompts on personal machines. The principle is therefore not "local is safe"; the principle is "choose the smallest data exposure that can still support the task, then verify the result."

## Practical Boundaries for Data, Context, and Metadata

Practical privacy starts with a boundary map. Before a prompt is written, ask which category the data belongs to, who owns it, and what would happen if it appeared in a vendor log, browser history, shared transcript, or future support ticket. The point is not to slow every learner with legal analysis. The point is to make the default path explicit enough that people do not invent their own rules during pressure.

The most obvious boundary is direct sensitive data. Do not casually paste secrets, credentials, customer data, private contracts, unreleased strategy documents, or production incident data into an AI tool without approval. Kubernetes examples deserve special care because manifests and logs can combine application names, service accounts, namespaces, hostnames, annotations, image registries, and policy settings. A redacted `Secret` value does not make the whole manifest public.

The less obvious boundary is contextual leakage. A stack trace may reveal the version of a vulnerable dependency. A prompt about an identity provider migration may reveal a security roadmap. A log line may include a rare internal identifier that can be joined with another dataset. An architecture diagram may show which services are critical, which ones are legacy, and where access control is thin. None of those details is a password, but each can reduce the effort required to attack or profile the system.

Metadata is a third boundary. Even if the content is sanitized, the pattern of requests can be revealing. Repeated prompts about a competitor's API, a specific cloud region, a merger-related domain, or a regulatory regime can signal what the organization is planning. Enterprise AI gateways often exist partly to centralize policy, logging, anonymization, and routing so individual employees do not leak strategy through scattered personal accounts and browser extensions.

Before running this, what output do you expect if the incident file includes customer names after a manual redaction pass? A local model will still summarize what it sees, so the risk depends on whether the file stays inside the approved boundary. If the same command were pointed at a public chat tool, the lack of passwords would not be enough. The safer workflow is to scrub first, route to the right environment, and treat the result as advisory.

The following is an illustrative example only — it assumes a running Ollama server and an on-disk incident file that are not created elsewhere in this module.

```text
# Example: Using a local inference engine to analyze sensitive logs
# This keeps all data within your VPC or local machine, bypassing cloud privacy risks.
ollama run llama3:8b "Summarize this internal post-mortem and identify the root cause: $(cat production_incident_log.txt)"
```

The command preserves the original lesson's point, but a professional team should wrap it with guardrails. The script could refuse to run unless the file is stored under an approved incident directory, scan for obvious personal data, write an audit entry, and remind the user that the generated summary must not be pasted into broad channels. A small wrapper is often more effective than a long policy because it changes the path people actually use.

Boundaries are also different for training, logging, and inference. A provider may say that prompts are not used to train foundation models, while still retaining request logs for abuse monitoring or debugging. Another provider may offer zero data retention only for selected endpoints, accounts, or contractual tiers. A third may let administrators opt out of model improvement while keeping transcripts for a period. Engineers do not need to memorize every clause, but they do need to know that "not trained on our data" is not the same as "not retained anywhere."

For regulated data, the responsible question is not only "can the model answer this?" but "is this model part of the approved processing chain?" Personal data, protected health information, financial records, employment records, and contractual material may have specific obligations around purpose limitation, retention, access, deletion, and sub-processors. If the AI provider is not covered by the organization's approval process, the tool may create a data transfer that the team cannot defend later.

A useful boundary practice is minimum necessary context. If the task is to explain an error code, the model may need the error code and the relevant public documentation link, not the full customer session. If the task is to review a Kubernetes Deployment pattern, the model may need a synthetic manifest that preserves structure without real image names, domains, or annotations. If the task is to draft a customer email, the model may need the tone and topic, not the customer's private history.

## Privacy Questions To Ask Before Prompting

Good privacy questions are concrete enough to change behavior. "Is this safe?" is too vague because it invites opinions and optimism. Better questions trace the data path: where does this data go, who can retain it, whether it is used for training, logging, analytics, or support, and whether the task belongs in a local tool, a private environment, or an approved enterprise system instead. Those questions turn privacy from a mood into an engineering decision.

Start with destination. A browser chat, an API endpoint, an IDE extension, a retrieval system, and a local model can all call themselves AI tools while moving data differently. The interface is not the infrastructure. A tool embedded in an editor may send selected code, surrounding files, terminal output, or telemetry depending on its configuration. A web tool may keep transcripts under a user account. A private gateway may proxy requests and apply policy before data reaches a model vendor.

Next ask about retention. Retention is the practical difference between a temporary computation and a durable record. A prompt that is retained in logs, analytics systems, support tooling, or training pipelines creates a longer-lived exposure than a prompt that is processed and discarded under a contractual no-retention configuration. Even when retention is legitimate, it should be visible. Teams cannot manage what they do not know exists.

Then ask about purpose. Data collected for abuse monitoring is different from data collected for product improvement, and both differ from data used to tune a customer-specific model. A learner may not control those purposes directly, but a professional workflow should route prompts only through tools whose purposes have been approved for that data class. When the purpose is unclear, assume the tool is not appropriate for confidential or regulated information until someone accountable confirms otherwise.

Privacy also includes identity and access. If a shared AI workspace contains transcripts, who can search them later? If a retrieval-augmented system indexes internal documents, does it enforce document-level permissions at query time? If an administrator can export logs, are those logs covered by the same controls as the source system? The model's answer may be generated in seconds, but the transcript and indexed context can become a long-lived internal data store.

The preserved Python example below demonstrates a simple sanitization step using Microsoft Presidio. It masks names and locations while preserving enough structure for a model to help with wording or classification. This is not a complete privacy program, because real systems must consider custom identifiers, rare combinations, policy exceptions, and review. It is a practical starting point for understanding how automated scrubbing can reduce accidental exposure before a request leaves the boundary.

```python
# Example: Using a privacy library to scrub data before API submission
from presidio_analyzer import AnalyzerEngine
from presidio_anonymizer import AnonymizerEngine

analyzer = AnalyzerEngine()
anonymizer = AnonymizerEngine()

raw_prompt = "Contact Jane Smith (ID: 9912) regarding the Berlin deployment."
results = analyzer.analyze(text=raw_prompt, entities=["PERSON", "LOCATION"], language='en')

# Anonymize ensures the LLM sees the context but not the identity
anonymized = anonymizer.anonymize(text=raw_prompt, analyzer_results=results)
sanitized_prompt = anonymized.text
print(sanitized_prompt)
# Output: "Contact <PERSON> (ID: 9912) regarding the <LOCATION> deployment."
```

Notice what the example does not solve. The identifier remains visible, and the phrase "Berlin deployment" may still be sensitive if only a small group works on that project. A determined analyst could sometimes re-identify a person from role, location, timing, and project name even after obvious names are removed. Sanitization therefore belongs in a layered process: automated detection, human judgment for context, approved routing, and conservative storage.

Which approach would you choose here and why: sanitize the original incident log, replace it with a synthetic example, or keep the task entirely inside a private incident system? For a public learning exercise, synthetic data is usually best because the model only needs structure. For a live incident, a private approved tool may be appropriate if it is covered by policy. For regulated customer material, the right answer may be manual analysis by authorized people rather than any external prompt.

The strongest privacy workflows make the safe path easier than the unsafe path. A command-line wrapper can redact common patterns, attach a data-class label, and route low-risk prompts to a public model while blocking high-risk prompts from leaving the environment. An internal portal can provide approved prompt templates and explain why some fields are excluded. A review checklist can require teams to record which data class was used before they publish an AI-generated summary.

## Trust Questions and Safety Beyond Moderation

Trust is not a single yes-or-no property of a model. It is a relationship between a tool, a task, the data used, the evidence available, and the cost of being wrong. The same model can be useful for rephrasing public notes and unacceptable for interpreting a private contract. A smaller local model can be better for privacy while worse for factual precision. A powerful hosted model can be strong at reasoning while still requiring review before a production change.

Before using an AI answer, ask whether the output is advisory or authoritative. Advisory output helps a human think, draft, compare, or search. Authoritative output changes a system of record, advises a customer, approves a policy, modifies infrastructure, or decides what someone is allowed to do. Most AI outputs should begin as advisory. Turning them into authoritative action requires evidence, review, and a named human or process that accepts accountability.

Safety is broader than content moderation. Many learners hear "AI safety" and think only about harmful text, but operational safety includes data exposure, incorrect advice, workflow over-automation, hidden bias, omission, and false confidence. A model can refuse a dangerous prompt and still produce a subtly wrong Kubernetes recommendation. It can pass a toxicity filter and still invent a field that Kubernetes 1.35+ will ignore. Moderation reduces one class of harm; it does not verify correctness or fit.

Prompt injection is another safety concern. In a retrieval or agent workflow, the model may read untrusted content that tries to override the user's instructions. A malicious document can say to ignore previous guidance, reveal hidden context, or call a tool in a harmful way. The safe design treats model input as untrusted and model output as untrusted until validated. This is familiar to engineers: it is the same mindset used for web input, shell arguments, and data crossing service boundaries.

The preserved YAML policy sketch below shows how an AI gateway can make trust decisions enforceable. It is written as pseudo-configuration, not a product-specific schema, but the shape matters. Inbound filters reduce what the model may see. Outbound filters reduce what users may receive or act on. The gateway becomes a control point where privacy, safety, and trust are implemented as behavior rather than a page of advice.

```yaml
# Example LLM Gateway Trust Policy (Pseudo-config)
inbound_filters:
  - type: pii_masking
    entities: [EMAIL, CREDIT_CARD, IP_ADDRESS, SECRET_KEY]
    action: redact
    replacement_token: "[REDACTED]"
  - type: prompt_injection_detection
    threshold: 0.85
    on_match: block_and_log
outbound_filters:
  - type: toxicity_filter
    action: flag
  - type: hallucination_check
    strategy: cross_reference_rag_source
```

The most important line in that sketch is not a specific filter. It is the idea that trust decisions should be enforced before and after the model call. If a team depends only on each individual remembering every rule, the rules will fail during outages, deadlines, and routine fatigue. A gateway, wrapper, or approved workflow can block obviously risky inputs, attach audit context, and require extra review for high-blast-radius outputs.

Hallucination deserves a precise definition. In this module, a hallucination is not merely a silly answer. It is a fluent response that lacks sufficient grounding in the facts needed for the task. The model may invent a Kubernetes field, cite a policy that does not apply, assume a default that changed between versions, or fill a missing fact with a plausible guess. Because the answer sounds coherent, humans may review it less carefully than a rough draft from a junior teammate.

Verification must therefore match the task. For a study explanation, you can compare the answer with vendor documentation and ask follow-up questions. For a Kubernetes manifest, you can run schema validation, policy checks, `kubectl diff` against a test cluster, and peer review. For security guidance, you need authoritative sources and a qualified reviewer. For legal, financial, medical, or regulated advice, the model should not be the authority; it can help organize questions for the professional who owns the decision.

Bias and omission are safety issues too. A model may reflect the distribution of public examples, which can overrepresent common platforms, English-language documentation, or popular cloud defaults. It may omit constraints that are obvious inside your organization, such as data residency, union agreements, retention schedules, or internal policy exceptions. The output can be syntactically polished while still narrowing the options in a way that disadvantages users or ignores obligations.

Over-automation is the final trust trap. A learner may start by asking for explanations, then progress to generated scripts, then allow an agent to run commands. Each step increases blast radius. In a cloud-native environment, a single generated command can delete resources, change permissions, expose a service, or rotate credentials incorrectly. Automation should earn trust through small reversible steps, dry runs, tests, approvals, and observability before it is allowed near production state.

## A Simple Trust Model for AI Workflows

A practical trust model starts by ranking the task rather than ranking the tool. Low-trust-required tasks include brainstorming, tone changes, outline generation, and summarizing public material. Medium-trust-required tasks include explanations, study help, coding ideas, and first-pass reviews where a human will verify the result. High-trust-required tasks include production changes, security guidance, legal or financial interpretation, sensitive data handling, and anything that affects customers, access, money, or compliance.

As the trust requirement rises, three bars rise together. The privacy bar rises because high-risk tasks often involve sensitive context. The evidence bar rises because a wrong answer costs more. The human-review bar rises because accountability cannot be delegated to a statistical system. A low-risk prompt can be informal. A high-risk prompt should have a documented data path, known retention behavior, source grounding, and a clear approval step before action.

Use blast radius as the first shortcut. If the output is wrong, who or what is harmed? A bad title suggestion wastes minutes. A bad incident summary can mislead leadership. A bad Kubernetes RBAC recommendation can grant broad access. A bad contract interpretation can create financial exposure. Trust is not about whether the model seems intelligent. Trust is about the cost of mistaken confidence in the specific context where the output will be used.

Use reversibility as the second shortcut. Some AI-assisted actions are easy to undo, such as editing a draft or reorganizing study notes. Others are hard to undo, such as publishing a misleading statement, deleting resources, disclosing personal data, or sending confidential text to an unapproved processor. When reversibility is low, the workflow needs more friction. Friction can be a second reviewer, a dry run, a policy engine, an approval ticket, or a decision to avoid AI for that step.

Use evidence as the third shortcut. The model's own explanation is not enough evidence for high-risk work. Evidence may include links to primary documentation, test output, schema validation, source citations, audit logs, or comparison with an approved policy. In Kubernetes, evidence might mean checking the official API reference, running admission policy tests, and confirming behavior in a non-production cluster. In privacy work, evidence might mean the contract, data processing agreement, and retention configuration.

The model can still be valuable when trust is low. For example, it can generate a checklist of questions for a privacy review, draft a synthetic manifest for a lesson, or summarize public documentation so the learner knows what to verify next. Treating output as advisory does not mean ignoring it. It means preserving human judgment and requiring external grounding before the output becomes action.

The model can also be valuable when trust is high, but only inside a stronger system. A private AI assistant can help a security team triage internal findings if it is connected to approved data, enforces access control, logs usage, and routes recommendations through review. A coding assistant can help refactor infrastructure code if changes go through tests, policy checks, peer review, and staged rollout. The model contributes speed; the surrounding workflow contributes control.

For learners, the everyday habit is simple: name the task's trust tier before prompting. Say, "This is low trust because it rewrites public notes," or "This is high trust because it touches production access." That sentence forces you to name the blast radius and the verification path. It also makes review easier because teammates can challenge the classification before the tool sees data or the output changes a system.

## When AI Use Is The Wrong Choice

Sometimes the disciplined answer is not "use a better model." Sometimes the disciplined answer is "do this locally," "do this manually," "use an approved internal system," or "do not externalize this information at all." That is not anti-AI. It is the same engineering instinct that keeps secrets out of public repositories, prevents debug endpoints from reaching the internet, and requires production changes to pass review.

AI use is often the wrong choice when the model does not need the sensitive data to help. If you want a general explanation of a Kubernetes concept, use public examples and documentation rather than private manifests. If you want to improve the tone of a customer email, replace names, account details, and incident specifics with placeholders. If the sensitive substance is essential, route the task through an approved private path or keep it with authorized humans.

AI use is also wrong when the answer must be authoritative and there is no verification path. A model can help draft questions for counsel, but it should not be treated as counsel. It can help summarize a public compliance guide, but it should not decide whether a private contract satisfies a legal obligation. It can suggest tests for a security control, but it should not be the only reviewer of that control. Authority belongs to accountable people and governed processes.

Another wrong-choice signal is hidden scope expansion. A user asks for help summarizing a public document, then adds an internal incident timeline, then asks the model to produce a customer statement. Each step changes the data class and the trust tier. A safe workflow notices the change and stops for a new decision. The tool that was appropriate for public notes may no longer be appropriate for incident communications or customer commitments.

Wrong-choice decisions should be recorded without shame. If a team makes refusal feel like obstruction, employees will route around the policy. A better culture says: "This task needs an approved internal environment," or "Use synthetic data for the learning prompt," or "This is a manual review because the data cannot leave the system." Clear alternatives reduce shadow AI because people still have a path to get work done.

Kubernetes learners can practice this discipline with manifests. A public example Deployment is fine for learning. A production manifest with internal registry paths, labels, annotations, and service accounts is not automatically safe just because secret values are base64-encoded or omitted. For Kubernetes 1.35+ work, the right AI path depends on what the manifest reveals, what the model will do with it, and whether generated changes can be tested before they reach a cluster.

## Patterns & Anti-Patterns

### Patterns

Classify before prompting is the first durable pattern. It works because the data class determines the rest of the workflow: tool choice, routing, retention expectations, review, and storage. Teams that classify after receiving an answer are already too late, because the data has moved. In practice, classification can be simple: public, internal, confidential, regulated, and production-sensitive. The labels matter less than the shared behavior attached to each label.

Sanitize and synthesize is the second pattern. Sanitization removes or masks sensitive elements from a real artifact, while synthesis creates a structurally similar example that contains no real data. Sanitization is useful when the real shape of the problem matters, such as error messages or manifest structure. Synthesis is better for teaching, documentation, prompt templates, and policy discussion. The scaling consideration is maintenance: teams need examples and scrubbing rules that evolve with the systems they operate.

Route by trust tier is the third pattern. Low-risk prompts can use broad tools if policy allows. Medium-risk prompts should use approved accounts, source grounding, and human review. High-risk prompts should move through private systems, gateways, strict access control, and explicit accountability. This pattern scales because it does not ask every person to remember every vendor clause. It asks them to choose a tier, and then the platform applies the appropriate controls.

Validate before action is the fourth pattern. The model may generate useful drafts, but the system should validate facts, syntax, permissions, and blast radius before anything changes. In infrastructure work, that means schema checks, policy engines, dry runs, peer review, and staged rollout. In writing work, it means source comparison and audience review. In privacy work, it means checking whether sensitive material survived the sanitization step.

### Anti-Patterns

The first anti-pattern is treating consumer tools like private infrastructure. Teams fall into it because the interface is fast and familiar, and because the data feels harmless in the moment. The better alternative is to provide an approved route that is nearly as convenient, with clear labels for what data may be used. A policy that only says "do not use that" without offering a working path often produces hidden workarounds.

The second anti-pattern is confusing moderation with safety. A tool that refuses some harmful requests is not automatically safe for contracts, production logs, or security decisions. Moderation answers a narrow content question, while operational safety asks about exposure, correctness, access, accountability, and downstream action. The better alternative is a layered review model where moderation is one control among several, not the definition of trust.

The third anti-pattern is asking the model to be the reviewer of its own risky output. A generated policy, manifest, or incident statement may include a confident explanation of why it is safe. That explanation is useful input, but it is not independent evidence. The better alternative is to check the output against primary documentation, local tests, policy engines, and human reviewers who can challenge assumptions rather than simply restate the model's reasoning.

The fourth anti-pattern is saving transcripts where broader audiences can search them later. A prompt may be acceptable for a narrow support case but inappropriate in a shared workspace, ticket, or knowledge base. Teams fall into this pattern because AI outputs are easy to copy and paste. The better alternative is to redact before publishing, store transcripts according to the original data class, and avoid turning private context into searchable institutional memory.

## Decision Framework

Use this framework before an AI tool sees the data. First, name the task: drafting, explaining, summarizing, coding, debugging, reviewing, deciding, or acting. Second, name the data class: public, internal, confidential, regulated, or production-sensitive. Third, name the trust tier: low, medium, or high. Fourth, choose the route: public tool, approved enterprise tool, private gateway, local model, or no AI. Fifth, define verification before you read the answer.

If the task uses public data and the output is low impact, a public or broadly approved tool may be reasonable. The verification can be light, such as checking that the answer matches the public source. If the task uses internal data and the output informs a decision, use an approved enterprise path and verify the answer against source material. If the task uses confidential or regulated data, prefer a private or local path, and confirm that retention, access, and audit behavior match policy.

If the output will change infrastructure, raise the trust tier even when the input data seems harmless. A public Kubernetes example can still lead to a harmful generated command if the learner runs it against the wrong context. Production action requires environment checks, dry runs, review, and rollback planning. A model may help write the first draft, but the workflow must prevent unreviewed output from becoming a cluster change.

If the answer will be communicated outside the team, also raise the trust tier. A generated incident summary, customer message, security note, or compliance interpretation carries reputational and contractual consequences. Verify facts, remove sensitive details, and have an accountable reviewer approve the final text. The model can help organize language, but it should not decide what the organization claims.

The final decision question is whether the model needs the real data. If it does not, use synthetic or minimized input. If it does, ask whether the approved route exists. If no approved route exists and the data is sensitive, the task should remain manual or local until the organization creates a governed path. This decision may feel slower than pasting into a chat box, but it prevents a small convenience from becoming a durable exposure.

## Did You Know?

- The NIST AI Risk Management Framework 1.0 was released in 2023 and organizes trustworthy AI work around governance, mapping, measurement, and management.
- The OWASP Top 10 for LLM Applications includes prompt injection and sensitive information disclosure because model behavior and application security have to be evaluated together.
- The European Union's General Data Protection Regulation has applied since 2018, which means AI data handling may intersect with long-standing privacy obligations rather than a brand-new concern.
- Kubernetes Secrets are only base64-encoded by default, so teams must configure stronger controls such as encryption at rest and RBAC instead of treating the object format as sufficient protection.

## Common Mistakes

| Mistake | Why It Happens | How to Fix It |
|---|---|---|
| Pasting full incident logs into a public AI tool | The outage feels urgent, and removing obvious passwords looks like enough protection | Minimize the log, scrub identifiers, and use a local or approved incident workflow before involving a model |
| Treating "not used for training" as "not retained" | Vendor privacy language can sound broader than it is | Check retention, logging, abuse monitoring, support access, and contractual settings for the specific tool path |
| Trusting polished output because it sounds expert | Fluent explanations reduce the reader's skepticism | Require source grounding, tests, peer review, or professional approval based on the task's blast radius |
| Using real customer examples for prompt engineering | Real data makes examples feel more realistic and useful | Create synthetic examples that preserve structure without carrying private identities, contracts, or incidents |
| Letting AI-generated commands run without review | Automation turns advice into action faster than people notice | Use dry runs, test environments, policy checks, and human approval before production changes |
| Indexing documents into RAG without access control | Search feels like a convenience feature, so authorization is treated as separate | Enforce document-level permissions during retrieval and audit who can query sensitive collections |
| Publishing AI transcripts into broad workspaces | Generated summaries are easy to copy into tickets and channels | Store outputs according to the highest data class present in the prompt or response |

## Quiz

<details><summary>Question 1: Your team is rushing to resolve a production outage, and a teammate wants to paste the full incident log, including customer details and internal service names, into a public AI chat tool for quick analysis. What should you do first?</summary>

Do not paste the full log into the public tool. The right first step is to classify the data, minimize what the model needs, and choose a local, private, or approved enterprise route if sensitive incident context is required. Customer identifiers and internal service names are sensitive even when passwords have been removed. The output should also be treated as advisory, because a fluent root-cause summary still needs evidence from logs, metrics, and responders.
</details>

<details><summary>Question 2: A product manager says an AI tool is fine for reviewing an unreleased partner contract because it has moderation and refuses harmful prompts. What is wrong with that reasoning?</summary>

Moderation does not answer the privacy and trust questions that matter for a private contract. A refusal system may reduce harmful content, but it does not prove that the contract can be shared, retained, logged, or used for the purpose requested. Contract interpretation is also high trust because a wrong answer can affect financial or legal exposure. The safer path is to use an approved review process and treat any AI assistance as drafting support for accountable reviewers.
</details>

<details><summary>Question 3: An engineer asks a model to rewrite a public team announcement and later asks it to generate a Kubernetes RBAC change for production. How should the trust model differ?</summary>

The announcement rewrite is low trust because the input is public and mistakes are easy to review. The production RBAC change is high trust because it can change who has access to cluster resources. That second task needs stronger privacy controls, source grounding, schema validation, policy checks, and human review before action. The same model may assist both tasks, but the workflow around the second task must be much stricter.
</details>

<details><summary>Question 4: A developer removes API keys from a manifest before sending it to an AI tool, but leaves namespace names, internal registry paths, service accounts, and annotations. What risk remains?</summary>

The manifest still exposes contextual information about the organization's architecture and operating model. Namespaces, registry paths, service accounts, and annotations can reveal ownership, deployment patterns, internal controls, and the shape of production systems. Removing explicit keys is necessary but not sufficient. The developer should minimize or synthesize the manifest, then route it through an approved path if real internal structure is required.
</details>

<details><summary>Question 5: A private RAG assistant indexes internal design documents, but users can ask broad questions across the whole collection. What should you diagnose before trusting the assistant?</summary>

You should diagnose whether retrieval enforces the same document-level permissions that protect the source material. A private model is not enough if the retrieval layer can surface documents to users who could not otherwise read them. You should also check logging, transcript storage, and whether answers quote or summarize restricted content. Trust depends on the complete data path, not only on where the model is hosted.
</details>

<details><summary>Question 6: Your AI assistant suggests a Kubernetes 1.35+ manifest change and explains confidently that it is safe. What verification should happen before applying it?</summary>

The explanation is not independent evidence, so the change needs validation outside the model. Check the relevant Kubernetes documentation, run schema or policy validation, use a non-production environment, inspect the diff, and get human review if the change affects access, networking, storage, or production behavior. A confident answer can still include a hallucinated field or unsafe default. The trust tier is high because the output can change infrastructure.
</details>

<details><summary>Question 7: A learner wants to use AI to explain a private incident, but the model only needs the structure of the timeline to teach the concept. What input should they provide?</summary>

They should provide a synthetic or heavily minimized example rather than the real incident. If the learning objective is structure, the model does not need customer names, service names, timestamps, or internal business details. Synthetic input preserves the teaching value while reducing privacy and metadata exposure. If real incident content is essential, the task should move to an approved private workflow with proper retention and access controls.
</details>

## Hands-On Exercise

Exercise scenario: you are asked to review whether three AI-assisted tasks are safe to run through an external model. The tasks are a public documentation summary, a sanitized Kubernetes manifest review, and a production incident summary. Your goal is to build a repeatable decision workflow rather than rely on instinct. Work through the checklist below using notes, a local text file, or your team's normal review template.

### Setup

Create a scratch document named `ai-trust-review.md` and add three headings: `Task`, `Data Class`, and `Verification Plan`. You do not need to install any tooling for this exercise, but you may use the preserved local-model and sanitization examples earlier in the module as reference designs. Keep the examples synthetic; do not use real customer records, secrets, production logs, or private contracts.

### Tasks

- [ ] Classify each task as public, internal, confidential, regulated, or production-sensitive, and write one sentence explaining the classification.
- [ ] Assign each task a low, medium, or high trust tier, then name the blast radius if the model output is wrong.
- [ ] Decide whether each task belongs in a public tool, approved enterprise tool, private gateway, local model, or no-AI workflow.
- [ ] Write a minimum-necessary prompt for the Kubernetes manifest review that removes real names while preserving enough structure for useful feedback.
- [ ] Define the verification evidence required before anyone acts on the model's output, such as source documentation, tests, policy checks, or human approval.
- [ ] Review your plan for transcript storage and decide where the prompt and answer may be saved after the task is complete.

<details><summary>Solution guidance</summary>

The public documentation summary should usually be low trust if it uses public sources and the output is only study material. The sanitized Kubernetes manifest review is usually medium trust if it is synthetic or minimized, but it becomes high trust if the generated change will be applied to production. The production incident summary is production-sensitive and may include confidential or regulated data, so it should use a private approved path or remain manual. In every case, the final answer should name the data path, retention expectation, verification evidence, and accountable reviewer.
</details>

### Success Criteria

- [ ] Your review separates data class from trust tier instead of treating privacy and correctness as the same question.
- [ ] Your Kubernetes prompt uses synthetic names or placeholders and avoids real service names, customer identifiers, registry paths, and secrets.
- [ ] Your verification plan requires stronger evidence for high-blast-radius outputs than for low-risk drafting tasks.
- [ ] Your storage decision keeps prompts and responses under controls appropriate for the most sensitive data included.
- [ ] Your final recommendation includes at least one case where AI use is limited, routed privately, or rejected because the data should not leave the governed boundary.

## Sources

- [NIST AI Risk Management Framework](https://www.nist.gov/itl/ai-risk-management-framework)
- [OWASP Top 10 for LLM Applications](https://owasp.org/www-project-top-10-for-large-language-model-applications/)
- [OECD AI Principles](https://oecd.ai/en/ai-principles)
- [Microsoft Presidio documentation](https://microsoft.github.io/presidio/)
- [Kubernetes Secrets documentation](https://kubernetes.io/docs/concepts/configuration/secret/)
- [Kubernetes encryption at rest documentation](https://kubernetes.io/docs/tasks/administer-cluster/encrypt-data/)
- [Kubernetes RBAC documentation](https://kubernetes.io/docs/reference/access-authn-authz/rbac/)
- [Cloud Native Security Whitepaper](https://www.cncf.io/reports/cloud-native-security-whitepaper/)
- [Kubernetes admission controllers documentation](https://kubernetes.io/docs/reference/access-authn-authz/admission-controllers/)
- [Anthropic privacy and security documentation](https://platform.claude.com/docs/en/build-with-claude/privacy-and-security)

## Next Module

Continue to [Using AI for Learning, Writing, Research, and Coding](../module-1.6-using-ai-for-learning-writing-research-and-coding/) to practice choosing the right AI workflow for study, writing, research, and coding tasks.
