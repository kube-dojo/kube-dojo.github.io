# Namespace publication and execution evidence

This status correction under #3680 records completed publication checks for page SHA-256 `f4a194ad83a8e1d31fb8b65e5327ce4cb19147e8a7fde28619085dd7913cf188`, published from merged commit `aca3a6940976a1f66c7b965a6d7c785b7528f8fc` by [PR #3730](https://github.com/kube-dojo/kube-dojo.github.io/pull/3730). It changes no lesson, source receipt, score or acceptance decision. The page remains `revise`.

## Completed publication checks

- The exact merged primary checkout built successfully with Node 22: 2,181 pages. The full merged tree and all five changed blobs matched the independently reviewed revision `71e3ba3c7b3c71470918a53b208be184f60951e9`.
- [GitHub Pages run 41122334748](https://github.com/kube-dojo/kube-dojo.github.io/actions/runs/41122334748) completed successfully for that merged commit; deployment completed at 20:29:05 UTC on October 30, 2026.
- At 20:30:33 UTC, the [published lesson](https://kube-dojo.github.io/prerequisites/kubernetes-basics/module-1.7-namespaces-labels/), learner news, next YAML lesson, Ukrainian counterpart and pinned changelog history returned HTTP 200. Eight expected-text checks and four superseded-phrase absence checks passed; retrieved history bytes matched the merged file.
- A subsequent native Chrome check opened all 36 lesson disclosures, found none empty, inspected the corrected label and quota text, and followed English/Ukrainian/English navigation, the next YAML lesson and learner news. Diagram controls rendered; this check did not repeat the earlier complete modal inspection. The actual local dashboard at `http://127.0.0.1:8768/` showed the lesson current/revise and Prerequisites 13/51 accepted.

The retained local records are `.agent/session231/namespace-claim-precision/merged/build/report.json`, `merged/tree-binding.json`, `merged/publication-http/report.json` and `merged/native-publication.md`. They support `page_presence: pass` and `deployed_smoke: pass` for the specified page and deployment. They do not demonstrate learner comprehension or Ukrainian content fidelity.

## Execution evidence and its limits

All 31 fences remained byte-identical across the scoped corrections. Preserved main-exercise macOS/Linux observations cover the 13 exercise fences and actual Kubernetes 1.35 resources, including Ready Pod/endpoint membership changes, CPU defaults and owned-namespace cleanup. Separate Linux reference checks cover seven Bash fences, four complete manifests through server dry-run, quota/LimitRange admission, selector results and an intentional quota rejection. Four reference manifests use illustrative images and were not run as workloads; selector fixtures remained Pending. No traffic-distribution or network-isolation test is established. The private fixtures were subsequently removed with preservation records and unchanged user kubeconfig hashes.

These scoped runs are now recorded rather than hidden behind a pending publication status. `lab_execution` remains `unknown` until the complete applicable practice scope is reconciled; the note does not turn partial observations into a blanket execution pass.

## Remaining acceptance gates

The [original Source4 result](https://github.com/kube-dojo/kube-dojo.github.io/issues/3680#issuecomment-6530423578) remains NEEDS_CHANGES with a failed freshness check. [Source5 failed before model review](https://github.com/kube-dojo/kube-dojo.github.io/issues/3680#issuecomment-6533774920): provider schema rejection, zero of 506 required chunks read, no verdict, score or receipt. Five whole-page attempts are spent; no sixth is authorized. Technical-source status stays `unknown`, editorial review stays `pending`, and no canonical acceptance is recorded. The existing scoped correction concern has used two of five PR-review invocations; reviewing this metadata correction consumes its third, separately from the exhausted whole-page counter.
