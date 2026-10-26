# T01-P04: packages, cloud and first server

Owner #2278; sources/practice/assessment #2275/#2276/#2277. Checked 2026-10-26 at base `f79efd0782b9d9746f9e33971ae3669d57c338df`. Terra completed full reads (0.9:1–732;0.10:1–533;0.11:1–576); Astra implemented scoped corrections, with lead source/diagnostic integration. All three pages remain **revise**, D1–D8 unassessed. Closed #2572/#2574 timing receipts remain useful history, not current acceptance.

## Findings and corrections

| Page | Correction and checked evidence |
|---|---|
| 0.9 Packages | An unable-to-locate error does not prove an empty package index. Inspect configured sources and update results. Release-to-htop version attribution was unverified after package-page fetch failures; keep the displayed versions explicitly simulated and diagnose executable/package/origin evidence. [Ubuntu apt manual](https://manpages.ubuntu.com/manpages/noble/man8/apt.8.html), update: downloads metadata from configured sources. |
| 0.10 Cloud | Stopping compute does not stop every charge. Keep retained resources and provider rules explicit; use a fresh workspace instead of opening a fixed home notes file. [AWS EC2 stop/start](https://docs.aws.amazon.com/AWSEC2/latest/UserGuide/how-ec2-instance-stop-start-works.html), persistent resources and costs: EBS volumes and associated Elastic IPs persist and can incur charges. No current price or eligibility promise. |
| 0.11 First server | Replace all bare host-port publications with explicit loopback; align explanation, repairs, quiz, URL and success criteria. [Docker port publishing](https://docs.docker.com/engine/network/port-publishing/), publishing/default bind: all host addresses by default, loopback option, pre-28.0.0 same-L2 caveat and custom-routing limits. Require an authorized local context; no absolute isolation claim. |
| 0.11 Setup/files/teardown | Prefer preconfigured Docker; mark installation illustrative and limit privileged setup to an authorized disposable VM with teardown. [Docker Linux post-install](https://docs.docker.com/engine/install/linux-postinstall/), docker-group warning: root-level privileges. A fresh host workspace protects index.html, failed container creation does not authorize deleting a collision, and cloud cleanup inventories owned retained billable resources. |
| 0.11 Diagnostic consistency | A welcome page is an HTTP observation, corroborated by container/port and distinctive content checks. Refusal/timeouts and inside-versus-outside tests narrow hypotheses rather than prove a specific rejecting host/firewall or complete health. |

Source URLs above were fetched and relevant passages read by the lead. These are selective support checks, not whole-page source/history acceptance. No invented package matrix, packet capture, zero-charge result or learner measurement is supplied.

## Execution and remaining evidence

Eight local macOS workspace/fixture checks passed after final integration: fresh setup, existing directory/file/symlink stops, fixed-home-file preservation and saved-buffer fixture writes. Docker mapping consistency is static inspection, not an executed Docker/network test. Bash `-e` models the instructed manual stop. No editor, package installation, service/group change, Docker daemon/container, SSH, cloud provisioning or hosted lab was executed.

All176 pipeline tests and enabled structural gates pass. Full source reachability passes for0.10/0.11;0.9 recorded one fetch failure, with reachability explicitly skipped for its enabled-gate result. Reachability is not source support, and that failure is not asserted resolved. Complete claim maps, independent rubric/assessment and documented-environment practical proof remain with #2275/#2277/#2276; the batch remains unchecked. Exact-head cross-provider review/CI, merged build/public smoke and delivery receipts remain separate gates. Continue to T01-P05 with these blockers visible rather than promoting unavailable runtime evidence.
