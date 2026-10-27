# Authored assessment sample — Module 1.1

This is an authored validation example for source SHA-256 `b2e88df4d83b0b564c40fda29afb1394a8ca93a4a036b34b8af6d0630c6ef5f7`, not learner feedback, a runtime experiment, or an acceptance verdict. The source update makes the two cost sentences conditional and repairs the separate reflection cards; this sample already treats costs as an inference and does not presume saved Git intent.

## Architecture review comment

Our microservices need a way to place containers on suitable machines and recover when a process or node fails. We also need safe rollouts and a shared API that records what should be running, so operators and automation can coordinate. Container images solve packaging; they do not by themselves answer those operational questions.

**My inference:** a script or proprietary scheduler can become more expensive to maintain if our teams and failure modes grow, because we would have to design, test, and support the placement, recovery, and rollout behaviors ourselves. That cost is conditional on our actual requirements and staffing; neither the history nor a single case study establishes that building one is always more expensive.

Docker Swarm deserves consideration because its service orchestration is integrated with Docker Engine. Docker documents declarative services, scaling, networking, and desired-state reconciliation in [Swarm mode, “Desired state reconciliation”](https://docs.docker.com/engine/swarm/#desired-state-reconciliation). We should check whether its available integrations and provider support meet our specific needs instead of assuming that Engine integration makes it unusable outside one cloud. Mesos took another route: its [“Mesos Architecture” documentation](https://mesos.apache.org/documentation/architecture/), describes offers to framework schedulers, allowing different frameworks to decide how to use resources. We would need to evaluate the necessary frameworks and support for our workload; [Apache retired Mesos in 2025](https://attic.apache.org/projects/mesos.html), so a new deployment would also need a maintenance plan.

Kubernetes offers a declarative API and controllers that reconcile actual state toward desired state. The [Kubernetes 1.35 controller documentation, “Controller pattern”](https://v1-35.docs.kubernetes.io/docs/concepts/architecture/controller/) explains that controllers observe cluster state and act to move it toward a desired state. This is a documented design lesson: record intent and assign a controller to respond to differences, rather than relying only on repeated imperative commands by an operator. It does not guarantee successful recovery when capacity or dependencies are unavailable. API extension, community governance, documented integrations, and managed services such as [Amazon EKS](https://aws.amazon.com/blogs/aws/amazon-eks-now-generally-available/) are evaluation inputs, not guarantees of portability or zero operating work. A custom system could leave us responsible for maintaining integrations and finding support outside that ecosystem.

The [CNCF Spotify case study, “Challenge” and “Solution”](https://www.cncf.io/case-studies/spotify/) reports that the team wanted a larger community and ran Kubernetes alongside Helios during migration. At publication the move was still under way; this is one organization's reported experience, not a universal cost comparison.

I recommend comparing managed Kubernetes and Swarm against our required integrations and testing failure recovery and rollout behavior before selecting either. The counterargument is operational complexity: for a handful of services with modest availability needs and no requirements for those integrations, a simpler managed application platform or Swarm may be a better first choice. Before committing, we need local evidence of recovery and rollback outcomes, actual support and exit options, and estimates for upgrades, security, monitoring, and staff training for each candidate.

## Mapping and limitations

- Operational problem, imperative versus declarative behavior, and conditional maintenance inference: first two paragraphs and Kubernetes paragraph.
- Two historical contenders with capabilities and evaluation boundaries: Swarm and Mesos paragraph; retirement is cited separately.
- Kubernetes strengths, ecosystem risk, controller lesson, limit, and small-workload boundary: final three paragraphs.
- Reported migration state and two or more primary citations with identifiable supported claims: Spotify and cited product/project documentation; the maintenance inference is explicitly labeled.
- Recommendation, counterargument, and local evidence needed: final paragraph.
- Possible ambiguity: the opening directs exactly three problem sentences and two cost sentences, whereas the success checklist does not restate those counts. This sample follows the requested counts. No human learner performance is inferred from this authored artifact.
