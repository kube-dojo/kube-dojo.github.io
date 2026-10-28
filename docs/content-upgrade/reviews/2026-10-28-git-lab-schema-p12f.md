# T01-P12f: runnable merge practice and schema/reference boundaries

Owner #2278; factual/source #2275, practical #2276 and assessment #2277. Exact execution of the prior hands-on commands stopped at the readiness-probe Perl substitution with exit255. The corrected delimiter preserves the intended probe. Setup now creates a fresh directory with a local fictional Git identity and local signing setting; it leaves existing repositories and global Git settings untouched.

## Primary sources and actual checks — 2026-10-28

- [Kubeconform v0.8.0 README](https://github.com/yannh/kubeconform/blob/v0.8.0/Readme.md), Limits, Usage and Overriding schemas location: OpenAPI-derived schema checks exclude further server validation; schema locations may be remote or local; schema version selection and HTTP cache are explicit options. A cache is not evidence that every needed schema is present.
- [Kubernetes ConfigMaps](https://kubernetes.io/docs/concepts/configuration/configmap/#configmaps-and-pods), ConfigMaps and Pods and Using Configmaps as environment variables: the `envFrom.configMapRef` selects a ConfigMap by name for the Pod, in the same namespace. This supports the file relationship check, not a claim that a target object exists or the application works.
- The lead retained actual primary captures, an upstream release asset/digest and original failed-run commands. An explicitly intervened continuation is preserved separately from successful repaired-source runs. After integration of #3602, the actual hands-on commands ran using Git2.56.0 and kubeconform0.8.0: only ConfigMap conflicted, the Deployment auto-merged to the shown solution, strict Kubernetes1.35.0 schema checks passed, and five replicas, the probe, strict mode and matching local reference names were inspected.
- The source's absent-reference control also passed schema validation, while an additional wrong-type control failed. A separate process with networking denied validated both final objects using captured local schemas. Default-schema checks contacted remote schema storage; no cluster was contacted or resources applied. These results are local execution evidence, not server, admission or runtime acceptance.

## Scope and remaining work

The body, pattern/decision guidance and lab distinguish rendering, schema shape, name/namespace relationships and runtime evidence. The lab is a synthetic local exercise. The prior branching section, complete quiz and merge-diff corrections are preserved; five PhilosophyDesign acceptances and all other page rows remain unchanged. The selected row remains `revise`, including lab execution `unknown` for the whole lesson: this receipt covers one hands-on exercise, not every runnable example.

Exact-head cross-provider review/CI and merged build/Pages/browser publication remain separate delivery gates. Full P12 source coverage, rubric, other applicable practice and time consistency remain open. No whole-page, Ukrainian or learner-effect acceptance is asserted.
