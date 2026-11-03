# Record source and deployment evidence

Use this after a hub's reviewed revision has landed. Follow the existing
[evidence layers](evidence-and-acceptance.md) and
[review contract](../review-contract.md). These tools record evidence; the lead
still owns page acceptance. Run from the checkout containing the committed page.
Use its primary checkout's `.venv/bin/python` when working in a linked worktree.
All CLI options are available through `--help`.

## 1. Author proposes claims; prepare the verifier packet

The page author proposes **all material claims**, including technical assertions
inside table descriptions. Each claim has an exact page quote, inclusive
one-based line span, kind and candidate sources. Internal assertions about titles,
links, lesson coverage, planning times and arithmetic use committed Git objects.
External assertions require captured upstream sources, not the page's own text.
An independent verifier must also inspect the full page for omitted claims.

Author proposal file shape:

```json
{
  "author": {
    "identity": "gpt-6.1-terra",
    "family": "openai",
    "evidence_ref": "docs/content-upgrade/page-reviews.json#work"
  },
  "claims": [{
    "claim_id": "C001",
    "claim_text": "exact quote from the committed page",
    "line_start": 7,
    "line_end": 7,
    "kind": "internal",
    "candidate_sources": [{"path": "src/content/docs/prerequisites/kubernetes-basics/index.md"}]
  }]
}
```

The lead confirms the author identity against the durable work evidence. The
current ledger has no structured author-family field, so the tool requires this
explicit evidence reference rather than guessing the family from prose.
For `external` claims, replace each candidate with `{"capture":"capture.json"}`.
Capture through the existing fetcher before preparing the seed:

```sh
.venv/bin/python -m scripts.quality.build_source_receipt capture \
  https://kubernetes.io/docs/concepts/workloads/pods/ \
  --output docs/content-upgrade/reviews/kb-pods-capture.json
```

Capture uses `scripts.fetch_citation._fetch_once` and its text extractor. It
retains the raw response bytes as base64, their SHA-256, extracted text, URL and
retrieval date. The snapshot digest covers **raw response bytes**, not extracted
text. Off-allowlist domains require a grant request; do not widen the allowlist.
Git snapshots hash exact blob bytes. Seeds use the existing `claims[].claim_id`
and schema-version-2 shape, with extra binding and candidate-source fields.

Commit only the canonical seed. Each external source retains its retrieval URI,
final URL, retrieval date, content type, raw-byte snapshot digest, capture method
and extracted `text`. HTML with a `<main>` region keeps that entire region's
text, excluding site navigation. Other inputs keep the full extracted text.
There is no character cutoff. `text_extraction` records `html-main-v1` or
`full-v1`. The verifier reads and quotes this retained text.

The Kubernetes Basics pilot measured 243,426 seed bytes, down from 7,791,841,
and 827,533 packet bytes for 29 claims and 19 sources, including ten external
captures. Its retained external text is 217,317 bytes. This measures that pilot,
not a size ceiling for other pages; no source text is silently truncated.

Raw bytes stay in the original capture and in a separate verifier evidence
directory supplied as `--captures-dir`. Neither captures nor packets are
committed. The seed command validates the capture's raw digest and full text,
then retains a capture file keyed by URI and snapshot digest in that directory.
Keep this directory with the packet and verifier run. The receipt command
requires it for external sources and rechecks raw bytes, extraction and all
source metadata against the seed. Older captures from the same tool lack
`status` and `truncated` fields because their producer checked these before
writing. New captures record both; non-200 or truncated captures are refused.

```sh
.venv/bin/python -m scripts.quality.build_source_receipt seed \
  --page src/content/docs/prerequisites/kubernetes-basics/index.md \
  --claims claims.json --captures-dir evidence/kb-captures \
  --output docs/citation-seeds/prerequisites-kubernetes-basics-index.json
.venv/bin/python -m scripts.quality.build_source_receipt packet \
  --seed docs/citation-seeds/prerequisites-kubernetes-basics-index.json \
  --output docs/content-upgrade/reviews/kb-packet.json
```

Outputs must be new files. Keep earlier attempts and negative verdicts. After a
page or seed change, prepare a new packet and obtain a new recorded verdict.
The packet includes full page text, claim spans and captured source text. Give
it to the independent verifier, **Anthropic Claude for the OpenAI-authored pilot**.
The author and builder cannot supply the verifier's judgments.

Legacy seeds containing `body_base64` are refused with a regeneration message.
Regenerate the seed and packet from retained proposals and captures, then get
new verdicts bound to their new digests. The `kubedojo.source_verdicts.v1`
schema and receipt schema are unchanged. A previous packet or verdict cannot
be reused after seed bytes change.

## 2. Independent verifier writes JSON; lead builds and checks the receipt

Verifier-output schema, shown with example values:

```json
{
  "schema": "kubedojo.source_verdicts.v1",
  "page_digest": "sha256:<64 lowercase hex digits>",
  "seed_digest": "sha256:<64 lowercase hex digits>",
  "packet_digest": "sha256:<SHA-256 of exact packet file bytes>",
  "coverage_complete": true,
  "verifier": {"identity": "independent-verifier-task", "family": "anthropic"},
  "run": {"identity": "recorded-run-id", "status": "complete"},
  "claims": [{
    "claim_id": "C001",
    "verdict": "SUPPORTED",
    "source": {
      "retrieval_uri": "git-object://<blob SHA from packet>",
      "snapshot_digest": "sha256:<snapshot SHA-256 from packet>",
      "quote": "exact contextual source quote",
      "locator": "source lines or section"
    },
    "rationale": "Why the source supports the entire claim in context."
  }]
}
```

Every shown field is required. Digests, identities, claim IDs, quotes, locators
and rationales are nonempty strings; `coverage_complete` is boolean and `claims`
is a nonempty array with exactly one entry per seed claim ID. Verdict is one of
`SUPPORTED`, `UNSUPPORTED`, `CONTRADICTED`, `UNREADABLE`. A positive source must
be one of that claim's captured candidates, with matching digest and literal
quote. Supported canonical families are `openai`, `anthropic`, `google`, `xai`,
`meta`, `deepseek`; known harness aliases normalize to their family. Unknown or
equal author/verifier families block. The run must be complete and its identity
must refer to the retained verifier run; a family label alone is not attestation.
For claims requiring several sources, an optional `additional_sources` array
uses the same shape and binding checks as `source`.

```sh
.venv/bin/python -m scripts.quality.build_source_receipt receipt \
  --seed docs/citation-seeds/prerequisites-kubernetes-basics-index.json \
  --packet docs/content-upgrade/reviews/kb-packet.json \
  --captures-dir evidence/kb-captures \
  --verdicts docs/content-upgrade/reviews/kb-verdicts.json \
  --output docs/content-upgrade/reviews/kb-source-acceptance.json
.venv/bin/python -m scripts.quality.build_source_receipt check \
  --seed docs/citation-seeds/prerequisites-kubernetes-basics-index.json \
  --receipt docs/content-upgrade/reviews/kb-source-acceptance.json
```

Missing claims, omissions, negative/unreadable judgments, incomplete runs or stale
page/seed/packet/source bindings refuse receipt creation. Unsupported or
contradicted claims require a page fix or the page stays unaccepted. `check`
overlays the candidate on a temporary copy of the live ledger, runs `bind_page`,
and reports acceptance/reasons plus the ledger digest without editing it.
It also checks claim spans, source references and digests, independent family,
positive judgments and literal quotes against retained seed text or exact Git
blob bytes. It needs no capture directory. Its output explicitly says that it
does **not** reverify external raw bytes; that requires the retained captures
and a receipt rebuild. Neither a digest nor a matching quote establishes
semantic support without the independent verifier's recorded judgment.

## 3. Lead records live deployed smoke, then adopts the evidence

Fetch the deployed commit if it is not already local. After Pages succeeds:

```sh
.venv/bin/python -m scripts.quality.record_deployed_smoke \
  --page src/content/docs/prerequisites/kubernetes-basics/index.md \
  --expect 'Kubernetes Basics' --expect 'module-1.1-first-cluster/' \
  --output docs/content-upgrade/reviews/kb-deployed-smoke.json
```

The recorder checks the latest successful Pages deployment and its workflow run,
compares the page bytes at its head, derives the live route, requires HTTP 200
and every exact HTML string, and rechecks deployment identity after retrieval.
Missing objects, non-successful deployments, mismatches and failed checks refuse
the record. It uses no local build evidence.

The lead's separate data PR embeds the receipt as `source_acceptance`, records
`technical_source` and `deployed_smoke` only when justified, and links both named
review artifacts and the independent verifier run in acceptance refs. The seed
must be adopted at the canonical filename used above. The lead alone decides
`lab_execution: not_applicable` and puts its page-specific justification in lead
acceptance refs. Neither tool edits `page-reviews.json`, assigns lab status,
publishes pages or grants whole-page acceptance. Repeat for cloud-native-101
with its own page path, claims, canonical seed filename and new output names.
