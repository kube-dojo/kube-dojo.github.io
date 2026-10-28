# Authored Phoenix audit — a planning artifact, not a real deployment

The supplied scenario has three Puppet-managed VMs, Docker/Engine swarm mode, a conversion script, API/workers, PostgreSQL, Redis and a dashboard. Installed versions, contracts, failure observations and recovery targets are missing. No Mesos or Cloud Foundry installation is asserted for Phoenix. This artifact practices comparison rather than reporting implementation or a measured learning result.

## Requirements and evidence to collect

1. Availability and recovery: product owner must set tolerated outage/data loss. Operator must inventory durable state, backups and restoration procedure, then observe an authorized host-loss/restoration test. No recovery result exists here.
2. Updates and access: release owner must specify rollback and availability criteria; inspect the actual service definitions, credentials and write paths. Test only after agreeing on a disposable pilot and expected observations.
3. Support and ownership: record Engine, Puppet and conversion-script versions/maintainers, contracts, incident owners and required integrations. Their names do not establish support sufficiency or conflict.

## Component decisions, all provisional

| Component | Evidence available | Missing evidence and decision boundary |
|---|---|---|
| Engine swarm mode | Docker documents a production runtime; distinguish Classic Swarm. | Need intended Engine version, required integration/update/recovery tests. Retain provisionally pending the common comparison. |
| Puppet | Official architecture says agents apply a compiled catalog. | Inspect actual catalog and writers. Retain host management if it meets requirements; do not infer that it changes application replica fields. |
| Image build | Kubernetes FAQ separates image builds from removed built-in dockershim. External cri-dockerd is a separate integration. | Inventory actual images, target runtime/CRI API and dependencies; compatibility remains untested. Retain the build workflow only subject to those checks. |
| Converted Compose definitions | Docker documents production configuration; conversion is not proof of required behavior. | Identify the actual script, resources and owners; test update/data/access/recovery requirements. Change, retain or migrate only with evidence. |
| Database | No backup/restore/failover evidence supplied. | Compare current, managed and self-managed options against consistency, restore, support, cost and ownership requirements. No automatic preference. |

## Primary claim audit and transfer

- Apache Attic: https://attic.apache.org/projects/mesos.html records Mesos retirement August2025/Attic completion October2025. It does not establish Phoenix inventory, Marathon retirement, distribution contracts or a migration deadline. A Mesos-dependent candidate needs its actual support arrangement before disposition.
- Mesos architecture: https://mesos.apache.org/documentation/architecture/ documents resource offers to framework schedulers and tasks through executors. The archived Marathon README https://github.com/d2iq-archive/marathon/blob/90619da70d79a2ecf19368a21c6a695ea981bd74/README.md describes the framework separately. Neither explains industry migration or predicts careers.
- Docker Compose: https://docs.docker.com/compose/how-tos/production/ documents production/single-server use. “Cannot be used in production” is unsupported. Host-loss/data-recovery requirements and observations remain missing; meeting them could justify retention, while a demonstrated unmet requirement could justify a change.
- Cloud Foundry transfer: https://docs.cloudfoundry.org/concepts/diego/diego-architecture.html describes Tasks and Long-Running Processes; https://docs.cloudfoundry.org/devguide/deploy-apps/deploy-app.html describes cf push. For a hypothetical database/custom-controller workload, investigate the intended distribution/version and support. Neither guide supplies a universal mismatch or users' migration cause.
- Runtime: https://kubernetes.io/blog/2022/02/17/dockershim-faq/ distinguishes removed built-in integration from image building/external adapter. https://v1-35.docs.kubernetes.io/docs/concepts/containers/cri/ states the v1 API requirement for1.26and later. The proposed environment still needs actual image/workload/runtime verification.

## Ownership and rollout proposal

Assign host configuration to the documented Puppet workflow, and identify which automation actually submits each API object or field. Identify its controller separately. If two workflows assert a different image or replica value, agree on the intended owner and inspect the actual write method. Server-Side Apply field-manager conflicts are conditional protection, not a guarantee for every write. See https://v1-35.docs.kubernetes.io/docs/reference/using-api/server-side-apply/ and the Ansible module/official controller records in the supplied catalog.

If a pilot is justified, agree on its workload, dependencies, impact, owner, rollback and stop/go observations before changing anything. A Kubernetes candidate must address a demonstrated gap and assign infrastructure, workload, upgrades, access, data and verification responsibilities; a managed offering must be checked against its actual agreement. The candidate can be rejected or retained as a proposal when evidence is missing.

The final Compose decision remains provisional. A successful startup alone cannot establish the specified production behavior, and the absence of a specified recovery target prevents a defensible pass/fail. Retain the documented workflow for investigation, inspect production settings and data ownership, and collect agreed failure/recovery evidence before deciding. This completes the written audit task; it does not execute a migration or manufacture the missing operational observations.
