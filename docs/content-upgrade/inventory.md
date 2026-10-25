# Content inventory ledger

`content_inventory.py` is a deterministic, read-only inventory CLI. From the
repository root it defaults to `src/content/docs`; tests and isolated audits may
pass `--docs-root PATH`. It accepts an optional evidence receipt with
`--evidence PATH` and always writes one JSON report to stdout:

```bash
.venv/bin/python scripts/quality/content_inventory.py --evidence evidence.json
```

Each `pages[]` record contains the docs-relative `path`, `locale` (`en` or
`uk`), `type` (`hub`, `module`, `chapter`, `lab`, or `page`), normalized
`section`, `source_digest` (`sha256:<hex>`), counterpart fields, and the
frontmatter `slug` as `source_route`. `route_validation` is always
`not_checked`: this tool does not claim that a route rendered or resolved in
Astro. A missing `slug` is reported as a null source route rather than inferred.

An evidence file has a `pages` list or path-keyed object. Each receipt needs
`path`, `page_digest`, `disposition` (`retain`, `revise`, or `expand`),
`reviewer_refs`, `evidence_refs`, and `independent_statuses`. Status values are
`pending`, `pass`, `fail`, `unknown`, or `not_applicable`. The CLI fills omitted
layers with `unknown`; it never derives a pass from a file,
heading, frontmatter flag, or inventory presence. A pass must include an
evidence reference. Both reference lists must be nonempty for every disposition,
including pending or unknown layers. A `current` receipt means only that its
digest and schema were checked; its reviewer and evidence references/statuses
remain supplied assertions, not independently verified source or reviewer
evidence.

`new_pages` are current paths absent from a valid supplied receipt set;
`missing_pages` are receipt paths absent from disk; `stale_receipts` have a
digest mismatch; `invalid_receipts` fail receipt validation. Missing, invalid,
and stale receipts are emitted as unreviewed with unknown statuses. Without a
usable evidence input, the inventory remains deterministic but does not label
pages as new or missing. The command does not write ledgers, caches, state, or
content files.

## Program coverage ledger

`docs/content-upgrade/page-reviews.json` is the tracked program input; its
`kubedojo.page_reviews.v1` label identifies the dataset, while inventory validation
still uses the `pages` receipt format above. The separate coverage reporter counts
current supplied dispositions, not exhaustive claim clearance. Optional
`acceptance_refs` is a nonempty list of nonempty explicit lead acceptance links;
inventory itself ignores this extra field. Coverage may count a supplied acceptance
only with retain, those references and passing applicable evidence; it never grants
source, book or human-review acceptance. The existing acceptance contract governs.
