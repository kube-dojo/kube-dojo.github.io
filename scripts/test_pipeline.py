"""Integration tests for the v1 quality pipeline.

Tests deterministic checks, state transitions, and pipeline logic
WITHOUT calling LLM APIs. Uses known-good modules as fixtures.

Run:  python scripts/test_pipeline.py
      python scripts/test_pipeline.py -v          # verbose
      python scripts/test_pipeline.py TestChecks   # single class
"""

from __future__ import annotations

import copy
import importlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
import textwrap
import threading
import unittest
from argparse import Namespace
from concurrent.futures import ThreadPoolExecutor
from contextlib import ExitStack
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import ClassVar
from unittest.mock import patch

import yaml

REPO_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(REPO_ROOT / "scripts"))

structural = importlib.import_module("checks.structural")
CheckResult = structural.CheckResult
GEMINI_WRITER_MODEL = importlib.import_module("dispatch").GEMINI_WRITER_MODEL


class _CalibrationIsolatedCase(unittest.TestCase):
    """Guard review-entering fixtures, without blocking unrelated CLI tests."""

    def run(self, result=None):
        import v1_pipeline as p

        with ExitStack() as stack:
            stack.enter_context(patch.dict(os.environ, {"SECOND_REVIEWER_SAMPLE_RATE": "0"}))
            stack.enter_context(patch.object(p.random, "random", return_value=0.0))
            guards = [stack.enter_context(patch.object(p, name, side_effect=AssertionError(f"unexpected {name}")))
                      for name in ("dispatch_auto", "dispatch_agy", "dispatch_claude", "dispatch_codex")]
            guards.append(stack.enter_context(patch("subprocess.Popen", side_effect=AssertionError("unexpected process"))))

            def assert_guards_unused():
                for guard in guards:
                    guard.assert_not_called()

            self.addCleanup(assert_guards_unused)
            return super().run(result)


def sample_fact_ledger() -> dict:
    """Reusable schema-valid fact ledger fixture."""
    return {
        "as_of_date": "2026-04-12",
        "topic": "Test Module",
        "claims": [
            {
                "id": "C1",
                "claim": "Kubernetes current stable is v1.35",
                "status": "SUPPORTED",
                "current_truth": "Kubernetes current stable is v1.35",
                "sources": [{"url": "https://kubernetes.io/releases/", "source_date": "2026-04-12"}],
                "conflict_summary": None,
                "unverified_reason": None,
            }
        ],
    }


class TestPrMergeHelper(unittest.TestCase):
    def test_merge_when_green_waits_then_direct_squash_merges(self):
        from lib import pr_merge

        calls = []

        def fake_run_gh(args, repo):
            calls.append(args)
            if args[:3] == ["pr", "view", "123"] and "statusCheckRollup" in args[-1]:
                if len([c for c in calls if c[:3] == ["pr", "view", "123"]]) == 1:
                    payload = {
                        "state": "OPEN",
                        "statusCheckRollup": [{"status": "IN_PROGRESS"}],
                    }
                else:
                    payload = {
                        "state": "OPEN",
                        "statusCheckRollup": [{"conclusion": "SUCCESS"}],
                    }
                return subprocess.CompletedProcess(args, 0, json.dumps(payload), "")
            if args == ["pr", "merge", "123", "--squash", "--delete-branch"]:
                return subprocess.CompletedProcess(args, 0, "", "")
            if args == ["pr", "view", "123", "--json", "mergeCommit"]:
                payload = {"mergeCommit": {"oid": "abc123"}}
                return subprocess.CompletedProcess(args, 0, json.dumps(payload), "")
            raise AssertionError(f"unexpected gh call: {args}")

        sleeps = []
        with patch.object(pr_merge, "_run_gh", side_effect=fake_run_gh):
            sha = pr_merge.merge_when_green(
                123,
                repo=REPO_ROOT,
                poll_interval=1,
                sleep_fn=sleeps.append,
            )

        self.assertEqual(sha, "abc123")
        self.assertEqual(sleeps, [1])
        self.assertIn(["pr", "merge", "123", "--squash", "--delete-branch"], calls)
        self.assertNotIn("--auto", " ".join(" ".join(call) for call in calls))


class TestGitVerifyHelper(unittest.TestCase):
    def test_verify_pushed_to_remote_accepts_matching_sha(self):
        from lib.git_verify import verify_pushed_to_remote

        def fake_run(_cmd, **_kwargs):
            return subprocess.CompletedProcess(
                _cmd,
                0,
                "abc123\trefs/heads/feature/test\n",
                "",
            )

        with patch("lib.git_verify.subprocess.run", side_effect=fake_run):
            ok, remote_sha, error = verify_pushed_to_remote(
                "feature/test",
                "abc123",
                repo=REPO_ROOT,
            )

        self.assertTrue(ok)
        self.assertEqual(remote_sha, "abc123")
        self.assertIsNone(error)

    def test_verify_pushed_to_remote_rejects_stale_sha(self):
        from lib.git_verify import verify_pushed_to_remote

        def fake_run(_cmd, **_kwargs):
            return subprocess.CompletedProcess(
                _cmd,
                0,
                "old456\trefs/heads/feature/test\n",
                "",
            )

        with patch("lib.git_verify.subprocess.run", side_effect=fake_run):
            ok, remote_sha, error = verify_pushed_to_remote(
                "feature/test",
                "new123",
                repo=REPO_ROOT,
            )

        self.assertFalse(ok)
        self.assertEqual(remote_sha, "old456")
        self.assertIn("expected new123", error or "")


class TestCodexPushVerification(unittest.TestCase):
    def test_runner_marks_codex_danger_success_failed_when_origin_stale(self):
        from agent_runtime import runner
        from agent_runtime.adapters.base import InvocationPlan
        from agent_runtime.result import ParseResult

        class FakeAdapter:
            default_model = "gpt-test"
            supported_modes = frozenset({"danger"})

            def build_invocation(self, **kwargs):
                return InvocationPlan(cmd=["fake-codex"], cwd=kwargs["cwd"])

            def liveness_signal_paths(self, _plan):
                return ()

            def parse_response(self, **_kwargs):
                return ParseResult(ok=True, response="push: done")

        class FakeProc:
            returncode = 0
            stdin = None

            def poll(self):
                return 0

            def kill(self):
                return None

            def wait(self, timeout=None):
                return 0

        class FakeWatchdogState:
            stdout_lines: ClassVar[list[str]] = ["push: done"]
            stderr_lines: ClassVar[list[str]] = []

        stale_error = "Codex danger-mode dispatch left origin stale"
        with patch.object(runner, "_load_adapter", return_value=FakeAdapter()), \
             patch.object(runner, "has_headroom", return_value=(True, "")), \
             patch.object(runner, "build_agent_env", return_value={}), \
             patch.object(runner.subprocess, "Popen", return_value=FakeProc()), \
             patch.object(runner, "start_watchdog", return_value=(FakeWatchdogState(), [])), \
             patch.object(runner, "stop_watchdog"), \
             patch.object(runner, "write_record"), \
             patch.object(runner, "_git_head_sha", side_effect=["old", "new"]), \
             patch.object(runner, "verify_current_branch_pushed", return_value=(False, stale_error)):
            result = runner.invoke(
                "codex",
                "commit and push",
                mode="danger",
                cwd=REPO_ROOT,
                model="gpt-test",
                skip_headroom_check=True,
            )

        self.assertFalse(result.ok)
        self.assertIn(stale_error, result.stderr_excerpt or "")
        self.assertEqual(result.usage_record["outcome"], "error")


class TestRequireFileChangeGuard(unittest.TestCase):
    """The require_file_change_on_write guard (#2099 agy no-write flake)."""

    @staticmethod
    def _fake_adapter(require_flag: bool):
        from agent_runtime.adapters.base import InvocationPlan
        from agent_runtime.result import ParseResult

        class FakeAdapter:
            default_model = "agy-test"
            supported_modes = frozenset({"workspace-write", "danger"})
            require_file_change_on_write = require_flag

            def build_invocation(self, **kwargs):
                return InvocationPlan(cmd=["fake-agy"], cwd=kwargs["cwd"])

            def liveness_signal_paths(self, _plan):
                return ()

            def parse_response(self, **_kwargs):
                # CLI exited 0 with output => parses ok, even though the
                # no-write flake means nothing landed on disk.
                return ParseResult(ok=True, response="wrote the module")

        return FakeAdapter()

    @staticmethod
    def _fake_proc():
        class FakeProc:
            returncode = 0
            stdin = None

            def poll(self):
                return 0

            def kill(self):
                return None

            def wait(self, timeout=None):
                return 0

        return FakeProc()

    @staticmethod
    def _fake_watchdog_state():
        class FakeWatchdogState:
            stdout_lines: ClassVar[list[str]] = ["wrote the module"]
            stderr_lines: ClassVar[list[str]] = []

        return FakeWatchdogState()

    def _invoke(self, *, require_flag, head_seq, porcelain_seq,
                mode="workspace-write", push_verify=(True, None)):
        from agent_runtime import runner

        with patch.object(runner, "_load_adapter",
                          return_value=self._fake_adapter(require_flag)), \
             patch.object(runner, "has_headroom", return_value=(True, "")), \
             patch.object(runner, "build_agent_env", return_value={}), \
             patch.object(runner.subprocess, "Popen",
                          return_value=self._fake_proc()), \
             patch.object(runner, "start_watchdog",
                          return_value=(self._fake_watchdog_state(), [])), \
             patch.object(runner, "stop_watchdog"), \
             patch.object(runner, "write_record"), \
             patch.object(runner, "verify_current_branch_pushed",
                          return_value=push_verify), \
             patch.object(runner, "_git_head_sha", side_effect=head_seq), \
             patch.object(runner, "_git_status_porcelain", side_effect=porcelain_seq):
            return runner.invoke(
                "agy",
                "write the module",
                mode=mode,
                cwd=REPO_ROOT,
                model="agy-test",
                skip_headroom_check=True,
            )

    def test_no_file_change_marks_error(self):
        """ok parse + zero worktree change => retryable error."""
        # before + guard-after HEAD; before + guard-after porcelain.
        result = self._invoke(
            require_flag=True,
            head_seq=["sha0", "sha0"],
            porcelain_seq=["", ""],
        )
        self.assertFalse(result.ok)
        self.assertEqual(result.usage_record["outcome"], "error")
        self.assertIn("no file change", (result.stderr_excerpt or "").lower())
        self.assertIn("#2099", result.stderr_excerpt or "")

    def test_file_change_present_stays_ok(self):
        """A real porcelain change clears the guard."""
        result = self._invoke(
            require_flag=True,
            head_seq=["sha0", "sha0"],
            porcelain_seq=["", "?? uk/new-module.md\n"],
        )
        self.assertTrue(result.ok)
        self.assertEqual(result.usage_record["outcome"], "ok")

    def test_guard_off_when_adapter_opts_out(self):
        """No flag => empty worktree is NOT downgraded (legacy behavior)."""
        # With the flag off in workspace-write mode, neither HEAD nor porcelain
        # is snapshotted (danger path is not taken either), so both mocks see
        # zero calls; the extra seq item is just an unused cushion.
        result = self._invoke(
            require_flag=False,
            head_seq=["sha0"],
            porcelain_seq=[],
        )
        self.assertTrue(result.ok)
        self.assertEqual(result.usage_record["outcome"], "ok")

    def test_git_unmeasurable_does_not_punish(self):
        """If git status can't be read (None), the guard must not fire."""
        result = self._invoke(
            require_flag=True,
            head_seq=["sha0", "sha0"],
            porcelain_seq=[None, None],
        )
        self.assertTrue(result.ok)
        self.assertEqual(result.usage_record["outcome"], "ok")

    def test_danger_mode_no_write_marks_error(self):
        """The production path is danger mode (dispatch_smart forces agy to
        danger). A no-write danger run must also flip to error, exercising the
        guard alongside — not instead of — the danger push-verify block."""
        # HEAD: before, push-verify-after, file-guard-after (all identical, so
        # push-verify sees no commit and never calls verify_current_branch_pushed).
        result = self._invoke(
            require_flag=True,
            mode="danger",
            head_seq=["sha0", "sha0", "sha0"],
            porcelain_seq=["", ""],  # before, file-guard-after
        )
        self.assertFalse(result.ok)
        self.assertEqual(result.usage_record["outcome"], "error")
        self.assertIn("#2099", result.stderr_excerpt or "")

    def test_push_verify_error_wins_over_file_guard(self):
        """When agy DOES commit in danger mode but the push fails, the
        push-verify error must win: the file guard is short-circuited
        (push_verify_error is not None) so the excerpt is push-related, never
        the #2099 no-write note."""
        # HEAD moves (sha0 -> sha1) => push-verify block fires and, because the
        # push is stale, sets push_verify_error. The file guard is then skipped,
        # so no file-guard HEAD/porcelain-after reads happen.
        result = self._invoke(
            require_flag=True,
            mode="danger",
            head_seq=["sha0", "sha1"],  # before, push-verify-after (changed)
            porcelain_seq=[""],  # before only; file guard never runs
            push_verify=(False, "origin stale: expected sha1"),
        )
        self.assertFalse(result.ok)
        self.assertEqual(result.usage_record["outcome"], "error")
        self.assertIn("origin stale", result.stderr_excerpt or "")
        self.assertNotIn("#2099", result.stderr_excerpt or "")


# ---------------------------------------------------------------------------
# Fixtures: known-good and known-bad module content
# ---------------------------------------------------------------------------

GOOD_MODULE = textwrap.dedent("""\
---
title: "Test Module — Good"
slug: prerequisites/test/module-0.1-good
sidebar:
  order: 1
---

## Learning Outcomes

After completing this module, you will be able to:

- **Debug** container networking issues using standard Linux tools
- **Design** a pod networking strategy for a multi-tenant cluster
- **Evaluate** trade-offs between different CNI plugins

## Why This Module Matters

In 2023, a major e-commerce platform lost $12M in revenue during a
12-hour outage caused by a misconfigured network policy. The root cause
was a single engineer who didn't understand how pod-to-pod networking
works at the Linux kernel level.

This module gives you that understanding so you never make the same mistake.

## Core Concepts

Kubernetes networking follows four fundamental rules:

1. Every pod gets its own IP address
2. Pods on any node can communicate with pods on any other node
3. Agents on a node can communicate with all pods on that node
4. No NAT between pods

> **Pause and predict**: What would happen if rule #2 were violated?
> Think about service discovery, DNS resolution, and east-west traffic.

### Network Namespaces

Each pod runs in its own network namespace. This provides isolation:

```bash
# List network namespaces
ip netns list

# Execute command in a namespace
ip netns exec <ns> ip addr show
```

The container runtime creates a veth pair — one end in the pod namespace,
the other in the host namespace, connected to a bridge.

| Component | Purpose | Example |
|-----------|---------|---------|
| veth pair | Connects pod ns to host | vethXXXX |
| bridge | Connects all pods on node | cbr0, cni0 |
| iptables | Service routing | KUBE-SERVICES chain |
| IPAM | IP allocation | host-local, calico-ipam |

### CNI Plugins

The Container Network Interface (CNI) standardizes network setup:

```yaml
apiVersion: v1
kind: Pod
metadata:
  name: network-test
spec:
  containers:
  - name: netshoot
    image: nicolaka/netshoot
    command: ["sleep", "infinity"]
```

> **Stop and think**: If you had 500 nodes, which CNI would you choose —
> Calico, Cilium, or Flannel? What factors would influence your decision?

### Debugging Network Issues

```bash
# Check pod connectivity
kubectl exec -it netshoot -- ping 10.244.1.5

# Trace network path
kubectl exec -it netshoot -- traceroute 10.244.1.5

# Check DNS resolution
kubectl exec -it netshoot -- nslookup kubernetes.default
```

## Did You Know?

- The Linux kernel processes over 1 million packets per second on modern hardware
- Cilium uses eBPF to bypass iptables entirely, reducing latency by 40%
- Kubernetes Service IPs don't actually exist on any interface — they're virtual
- The maximum number of Services per cluster is 2^16 (65,536) due to port range limits

## Common Mistakes

| Mistake | Why It Happens | Fix |
|---------|---------------|-----|
| NetworkPolicy allows all traffic | Default is allow-all | Add deny-all default policy |
| DNS resolution fails in pods | CoreDNS not running | Check kube-system pods |
| Pod can't reach external IPs | Missing SNAT/masquerade | Check iptables POSTROUTING |
| Service returns connection refused | Wrong targetPort | Match container port exactly |
| Inter-namespace traffic blocked | Overly strict NetworkPolicy | Check namespace selectors |
| Pods get duplicate IPs | IPAM range overlap | Audit --pod-cidr on each node |

## Quiz

<details>
<summary>Q1: Your production cluster has 200 nodes. Users report intermittent 5xx errors from a service backed by 50 pod replicas. Logs show connection timeouts to upstream pods. What's the most likely network-layer cause?</summary>

The most likely cause is iptables rule saturation. With 50 replicas, kube-proxy
creates extensive iptables chains for load balancing. At 200 nodes with many
services, the iptables rules can exceed 20,000 entries, causing noticeable
latency in packet processing. The fix is to switch kube-proxy to IPVS mode,
which uses hash tables instead of linear chain traversal.

</details>

<details>
<summary>Q2: A developer deploys a NetworkPolicy that selects pods with label app=api but the policy seems to have no effect. Traffic that should be blocked still flows. What should you check first?</summary>

First verify that your CNI plugin supports NetworkPolicy enforcement. Flannel,
for example, does NOT enforce NetworkPolicies — it only provides networking.
You need Calico, Cilium, or another policy-capable CNI. Second, check that
the policy is in the same namespace as the target pods. NetworkPolicies are
namespace-scoped and won't affect pods in other namespaces.

</details>

<details>
<summary>Q3: After upgrading your CNI from Flannel to Calico, all existing pods lose network connectivity. New pods work fine. Why?</summary>

Existing pods still have their veth pairs configured by Flannel's CNI binary.
The network configuration inside those pods (IP address, routes, DNS) was set
at pod creation time. Calico doesn't retroactively reconfigure running pods.
The fix is to perform a rolling restart of all workloads so pods get recreated
with Calico's networking. Use `kubectl rollout restart` for each deployment.

</details>

<details>
<summary>Q4: You configure a Service with externalTrafficPolicy: Local but some nodes return 503 errors for that Service. Other nodes work fine. What's happening?</summary>

With externalTrafficPolicy: Local, traffic is only forwarded to pods on the
same node that received the traffic. Nodes that don't have a pod for that
Service will return 503. This is by design — it preserves client source IP
and avoids extra network hops. The fix is either to ensure pods are scheduled
on all nodes (via DaemonSet or pod anti-affinity spread), or accept that some
nodes won't serve that Service and configure your load balancer's health checks
to route around them.

</details>

<details>
<summary>Q5: Explain why a headless Service (clusterIP: None) is necessary for StatefulSets but not for Deployments.</summary>

StatefulSets need stable network identities — each pod must be individually
addressable (e.g., mysql-0.mysql.default.svc.cluster.local). A headless Service
creates individual DNS A records for each pod instead of a single virtual IP.
Deployments don't need this because their pods are interchangeable — a regular
Service with a ClusterIP and round-robin load balancing is appropriate. The
headless Service also ensures that clients can discover all StatefulSet members
for consensus protocols like Raft or Paxos.

</details>

## Hands-On Exercise

### Task 1: Create a Network Debug Pod

Deploy a netshoot pod for network debugging:

```bash
kubectl run netshoot --image=nicolaka/netshoot --command -- sleep infinity
kubectl wait --for=condition=Ready pod/netshoot
```

<details>
<summary>Verify</summary>

```bash
kubectl exec netshoot -- ip addr show
# Should show eth0 with a pod CIDR IP
```

</details>

### Task 2: Test Pod-to-Pod Connectivity

Create two pods and verify they can communicate:

```bash
kubectl run server --image=nginx --port=80
kubectl run client --image=nicolaka/netshoot --command -- sleep infinity
```

<details>
<summary>Solution</summary>

```bash
SERVER_IP=$(kubectl get pod server -o jsonpath='{.status.podIP}')
kubectl exec client -- curl -s $SERVER_IP
# Should return nginx welcome page
```

</details>

### Task 3: Apply a NetworkPolicy

Create a deny-all policy and verify it blocks traffic:

```yaml
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: deny-all
spec:
  podSelector: {}
  policyTypes:
  - Ingress
  - Egress
```

<details>
<summary>Solution</summary>

```bash
kubectl apply -f deny-all.yaml
kubectl exec client -- curl -s --max-time 3 $SERVER_IP
# Should timeout — all traffic blocked
```

</details>

### Success Checklist

- [ ] Network debug pod running
- [ ] Pod-to-pod connectivity verified
- [ ] NetworkPolicy applied and blocking traffic

## Next Module

Continue to [Module 0.2: DNS in Kubernetes](/prerequisites/test/module-0.2-dns/) where
we explore how CoreDNS resolves Service names and how to debug DNS issues.
""")

DAMAGED_REWRITE_DRAFT = textwrap.dedent("""\
---
title: "Test Module — Damaged"
slug: prerequisites/test/module-0.1-damaged
sidebar:
  order: 1
---

## Learning Outcomes

- Recall that Kubernetes networking exists

## Core Concepts

This damaged rewrite dropped the code samples, tables, prompts, and quiz blocks
that the baseline module contained.
""")


BAD_MODULE_NO_FRONTMATTER = "# No frontmatter\n\nSome content here."

BAD_MODULE_NO_OUTCOMES = textwrap.dedent("""\
---
title: "Missing Outcomes"
sidebar:
  order: 1
---

## Introduction

Some content but no Learning Outcomes section and no quiz.
""")

BAD_MODULE_EMOJIS = textwrap.dedent("""\
---
title: "Has Emojis"
sidebar:
  order: 1
---

## Learning Outcomes

- Learn stuff 🎉

## Quiz

<details><summary>Q1</summary>Answer</details>
<details><summary>Q2</summary>Answer</details>
<details><summary>Q3</summary>Answer</details>
<details><summary>Q4</summary>Answer</details>

> **Pause and predict**: What happens next?
> **Stop and think**: Why?
""")

BAD_MODULE_DEPRECATED_API = textwrap.dedent("""\
---
title: "Deprecated APIs"
sidebar:
  order: 1
---

## Learning Outcomes

- Understand APIs

Use apiVersion: extensions/v1beta1 for your Deployments.

## Quiz

<details><summary>Q1</summary>Answer</details>
<details><summary>Q2</summary>Answer</details>
<details><summary>Q3</summary>Answer</details>
<details><summary>Q4</summary>Answer</details>

> **Pause and predict**: What happens?
> **Stop and think**: Why?
""")


# ---------------------------------------------------------------------------
# Test: Deterministic structural checks
# ---------------------------------------------------------------------------

class TestStructuralChecks(unittest.TestCase):
    """Test structural checks against known content."""

    def _make_path(self, name: str = "module-0.1-test.md",
                   prefix: str = "prerequisites/test") -> Path:
        """Create a fake path for check context."""
        return Path(f"src/content/docs/{prefix}/{name}")

    def _errors(self, results: list[CheckResult]) -> list[CheckResult]:
        return [r for r in results if not r.passed and r.severity == "ERROR"]

    def _warnings(self, results: list[CheckResult]) -> list[CheckResult]:
        return [r for r in results if not r.passed and r.severity == "WARNING"]

    def test_good_module_passes_all_checks(self):
        """A well-formed module should have zero ERROR-level failures."""
        path = self._make_path()
        results = structural.run_all(GOOD_MODULE, path)
        errors = self._errors(results)
        self.assertEqual(errors, [], f"Good module has errors: {errors}")

    def test_no_frontmatter_fails(self):
        path = self._make_path()
        results = structural.run_all(BAD_MODULE_NO_FRONTMATTER, path)
        errors = self._errors(results)
        fm_errors = [e for e in errors if "FRONTMATTER" in e.check]
        self.assertGreater(len(fm_errors), 0, "Should flag missing frontmatter")

    def test_missing_outcomes_fails(self):
        path = self._make_path()
        results = structural.run_all(BAD_MODULE_NO_OUTCOMES, path)
        errors = self._errors(results)
        outcome_errors = [e for e in errors if "OUTCOMES" in e.check]
        self.assertGreater(len(outcome_errors), 0, "Should flag missing Learning Outcomes")

    def test_emoji_detection(self):
        path = self._make_path()
        results = structural.run_all(BAD_MODULE_EMOJIS, path)
        errors = self._errors(results)
        emoji_errors = [e for e in errors if "EMOJI" in e.check]
        self.assertGreater(len(emoji_errors), 0, "Should flag emojis")

    def test_deprecated_api_in_prose_is_warning(self):
        """Deprecated APIs in prose should be flagged as WARNING (not ERROR)."""
        path = self._make_path()
        results = structural.run_all(BAD_MODULE_DEPRECATED_API, path)
        warnings = self._warnings(results)
        api_warnings = [w for w in warnings if "K8S_API" in w.check]
        self.assertGreater(len(api_warnings), 0,
                           "Should warn about deprecated extensions/v1beta1 in prose")

    def test_deprecated_api_in_code_block_ignored(self):
        """Deprecated APIs inside code blocks should not be flagged."""
        path = self._make_path()
        # Same API but inside a fenced code block
        content = textwrap.dedent("""\
        ---
        title: "APIs in Code"
        sidebar:
          order: 1
        ---
        ## Learning Outcomes
        - Understand APIs

        ```yaml
        apiVersion: extensions/v1beta1
        kind: Deployment
        ```

        ## Quiz
        <details><summary>Q1</summary>Answer</details>
        <details><summary>Q2</summary>Answer</details>
        <details><summary>Q3</summary>Answer</details>
        <details><summary>Q4</summary>Answer</details>
        > **Pause and predict**: What happens?
        > **Stop and think**: Why?
        """)
        results = structural.run_all(content, path)
        api_results = [r for r in results if "K8S_API" in r.check]
        # Should pass — API is only in code block
        for r in api_results:
            self.assertTrue(r.passed, f"API in code block should not be flagged: {r.message}")

    def test_line_count_is_warning_not_error(self):
        """LINE_COUNT was demoted to WARNING — should never be ERROR."""
        path = self._make_path()
        results = structural.run_all(BAD_MODULE_NO_OUTCOMES, path)
        line_results = [r for r in results if "LINE_COUNT" in r.check]
        for r in line_results:
            if not r.passed:
                self.assertEqual(r.severity, "WARNING",
                                 "LINE_COUNT should be WARNING, not ERROR")

    def test_slug_warning_for_dotted_filename(self):
        """Files with dots in stem should get a slug warning."""
        path = self._make_path("module-1.1-test.md", "k8s/cka/part1")
        content = textwrap.dedent("""\
        ---
        title: "No Slug"
        sidebar:
          order: 1
        ---
        ## Content
        """)
        results = structural.check_frontmatter(content, path)
        slug_warnings = [r for r in results if "slug" in r.message.lower() and not r.passed]
        self.assertGreater(len(slug_warnings), 0, "Should warn about missing slug")


# ---------------------------------------------------------------------------
# Test: Deterministic checks on real modules from disk
# ---------------------------------------------------------------------------

class TestRealModules(unittest.TestCase):
    """Run deterministic checks against actual modules in the repo.

    Picks one known-good module per track and verifies zero errors.
    """

    KNOWN_GOOD: ClassVar[list[str]] = [
        "prerequisites/zero-to-terminal/module-0.1-what-is-a-computer",
        "cloud/advanced-operations/module-8.1-multi-account",
        "k8s/cka/part1-cluster-architecture/module-1.1-control-plane",
        "k8s/ckad/part1-design-build/module-1.3-multi-container-pods",
    ]

    def test_known_good_modules_pass_checks(self):
        """Each known-good module should have zero deterministic errors."""
        content_root = REPO_ROOT / "src" / "content" / "docs"
        for key in self.KNOWN_GOOD:
            path = content_root / f"{key}.md"
            if not path.exists():
                self.skipTest(f"Module not found: {key}")
            content = path.read_text()
            results = structural.run_all(content, path)
            errors = [r for r in results if not r.passed and r.severity == "ERROR"]
            self.assertEqual(errors, [],
                             f"{key} has {len(errors)} errors: "
                             f"{[e.message for e in errors]}")


# ---------------------------------------------------------------------------
# Test: State management
# ---------------------------------------------------------------------------

class TestStateManagement(unittest.TestCase):
    """Test pipeline state load/save/transitions."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.state_file = Path(self.tmpdir) / "state.yaml"

    def tearDown(self):
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def _patch_state_file(self):
        """Patch STATE_FILE to use temp dir."""
        return patch("v1_pipeline.STATE_FILE", self.state_file)

    def test_load_empty_state(self):
        """Loading nonexistent state returns empty modules dict."""
        import v1_pipeline as p
        with self._patch_state_file():
            state = p.load_state()
            self.assertIn("modules", state)
            self.assertEqual(len(state["modules"]), 0)

    def test_save_and_reload(self):
        """State survives save/load cycle."""
        import v1_pipeline as p
        with self._patch_state_file():
            state = {"modules": {
                "test/module-1": {
                    "phase": "done",
                    "scores": [5, 5, 5, 5, 5, 5, 5, 5],
                    "sum": 40,
                    "passes": True,
                    "last_run": "2026-04-06T00:00:00",
                    "errors": [],
                }
            }}
            p.save_state(state)
            loaded = p.load_state()
            self.assertEqual(loaded["modules"]["test/module-1"]["sum"], 40)
            self.assertTrue(loaded["modules"]["test/module-1"]["passes"])

    def test_get_module_state_initializes(self):
        """get_module_state creates a default entry for new modules."""
        import v1_pipeline as p
        state = {"modules": {}}
        ms = p.get_module_state(state, "new/module")
        self.assertEqual(ms["phase"], "pending")
        self.assertFalse(ms["passes"])
        self.assertIsNone(ms["scores"])

    def test_module_key_from_path(self):
        """Module keys are derived correctly from file paths."""
        import v1_pipeline as p
        path = p.CONTENT_ROOT / "k8s" / "cka" / "part1-cluster-architecture" / "module-1.1-control-plane.md"
        key = p.module_key_from_path(path)
        self.assertEqual(key, "k8s/cka/part1-cluster-architecture/module-1.1-control-plane")

    def test_find_module_path_rejects_traversal(self):
        """Path traversal in module keys should be rejected."""
        import v1_pipeline as p
        result = p.find_module_path("../../etc/passwd")
        self.assertIsNone(result)

    def test_parallel_worker_state_merges_do_not_clobber_other_modules(self):
        """Parallel run-section workers should save isolated module snapshots."""
        import v1_pipeline as p

        content_root = Path(self.tmpdir) / "docs"
        module_a = content_root / "track" / "module-1.1-a.md"
        module_b = content_root / "track" / "module-1.2-b.md"
        module_a.parent.mkdir(parents=True, exist_ok=True)
        module_a.write_text("---\ntitle: A\n---\n\nBody\n")
        module_b.write_text("---\ntitle: B\n---\n\nBody\n")

        shared_state = {"modules": {}}
        observed_local_keys: dict[str, set[str]] = {}
        results: dict[str, bool] = {}
        barrier = threading.Barrier(2)
        previous_state_lock = p._PARALLEL_RUN_SECTION_STATE_LOCK
        previous_git_lock = p._PARALLEL_RUN_SECTION_GIT_LOCK

        def fake_run_module(module_path, state, max_retries=4, models=None,
                            dry_run=False, refresh_fact_ledger=False,
                            write_only=False):
            key = p.module_key_from_path(module_path)
            ms = p.get_module_state(state, key)
            ms["errors"] = []
            ms["phase"] = "review"
            ms["passes"] = True
            barrier.wait(timeout=5)
            for counter in range(1, 6):
                ms["counter"] = counter
                p.save_state(state)
            observed_local_keys[key] = set(state["modules"].keys())
            return True

        with ExitStack() as stack:
            stack.enter_context(patch.multiple(p, CONTENT_ROOT=content_root, STATE_FILE=self.state_file))
            with patch("v1_pipeline.run_module", side_effect=fake_run_module):
                p._PARALLEL_RUN_SECTION_STATE_LOCK = threading.Lock()
                p._PARALLEL_RUN_SECTION_GIT_LOCK = threading.Lock()
                try:
                    with ThreadPoolExecutor(max_workers=2) as executor:
                        futures = {p.module_key_from_path(path): executor.submit(
                            p._run_module_in_parallel, path, shared_state, max_retries=2,
                        ) for path in (module_a, module_b)}
                        results = {key: future.result() for key, future in futures.items()}
                finally:
                    p._PARALLEL_RUN_SECTION_STATE_LOCK = previous_state_lock
                    p._PARALLEL_RUN_SECTION_GIT_LOCK = previous_git_lock

        key_a = "track/module-1.1-a"
        key_b = "track/module-1.2-b"
        self.assertEqual(observed_local_keys[key_a], {key_a})
        self.assertEqual(observed_local_keys[key_b], {key_b})
        self.assertTrue(results[key_a])
        self.assertTrue(results[key_b])
        self.assertEqual(shared_state["modules"][key_a]["counter"], 5)
        self.assertEqual(shared_state["modules"][key_b]["counter"], 5)

        loaded = yaml.safe_load(self.state_file.read_text())
        self.assertEqual(set(loaded["modules"]), {key_a, key_b})
        self.assertEqual(loaded["modules"][key_a]["counter"], 5)
        self.assertEqual(loaded["modules"][key_b]["counter"], 5)

    def test_load_rubric_profile_uses_frontmatter_track(self):
        """Rubric profile lookup prefers an explicit frontmatter track."""
        import v1_pipeline as p
        with tempfile.TemporaryDirectory() as tmpdir:
            module_path = Path(tmpdir) / "module.md"
            module_path.write_text(textwrap.dedent("""\
            ---
            title: "Track Lookup Test"
            slug: sandbox/test/module-0.1
            track: cka
            ---
            Test body.
            """))
            profile = p.load_rubric_profile_for_module(module_path)
            self.assertEqual(profile["name"], "cka")
            self.assertEqual(profile["severity_gate"]["severe_failed_checks"], 5)


# ---------------------------------------------------------------------------
# Test: Review audit log
# ---------------------------------------------------------------------------

class TestReviewAuditLog(_CalibrationIsolatedCase):
    """Test per-module review audit helpers and integration points."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.repo_root = Path(self.tmpdir)
        self.content_root = self.repo_root / "src" / "content" / "docs"
        self.content_root.mkdir(parents=True, exist_ok=True)
        self.module_path = self.content_root / "test" / "module-0.1-test.md"
        self.module_path.parent.mkdir(parents=True, exist_ok=True)
        self.module_path.write_text(GOOD_MODULE)
        self.state_file = self.repo_root / ".pipeline" / "state.yaml"
        self.review_dir = self.repo_root / ".pipeline" / "reviews"
        self.module_key = "test/module-0.1-test"

    def tearDown(self):
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def _patch_paths(self, p):
        return patch.multiple(
            p,
            REPO_ROOT=self.repo_root,
            CONTENT_ROOT=self.content_root,
            STATE_FILE=self.state_file,
            REVIEW_AUDIT_DIR=self.review_dir,
            KNOWLEDGE_CARD_DIR=self.repo_root / ".pipeline" / "knowledge-cards",
            FACT_LEDGER_DIR=self.repo_root / ".pipeline" / "fact-ledgers",
        )

    def _write_state(self, phase="review", reviewer="gemini", severity="clean", errors=None):
        self.state_file.parent.mkdir(parents=True, exist_ok=True)
        state = {
            "modules": {
                self.module_key: {
                    "phase": phase,
                    "reviewer": reviewer,
                    "severity": severity,
                    "errors": errors or [],
                }
            }
        }
        self.state_file.write_text(yaml.dump(state, sort_keys=False))

    def test_append_review_audit_creates_new_file(self):
        import v1_pipeline as p

        self._write_state(phase="review", reviewer="gemini", severity="targeted")

        with self._patch_paths(p):
            audit_path = p.append_review_audit(
                self.module_path,
                "WRITE",
                writer=GEMINI_WRITER_MODEL,
                mode="write",
                duration=2.5,
                plan="Initial write plan",
                output_chars=1234,
            )

        content = audit_path.read_text()
        self.assertTrue(audit_path.exists())
        self.assertIn("# Review Audit: test/module-0.1-test", content)
        self.assertIn("**Current phase**: review", content)
        self.assertIn("**Current reviewer**: gemini", content)
        self.assertIn("**Current severity**: targeted", content)
        self.assertIn("**Total passes**: 1", content)
        self.assertIn("`WRITE`", content)
        self.assertIn(f"**Writer**: {GEMINI_WRITER_MODEL}", content)

    def test_second_append_prepends_and_preserves_existing_entries(self):
        import v1_pipeline as p

        self._write_state(phase="review", reviewer="gemini", severity="targeted")

        with self._patch_paths(p):
            p.append_review_audit(
                self.module_path,
                "WRITE",
                writer="writer-a",
                mode="write",
                duration=1,
                plan="first plan",
                output_chars=100,
            )
            p.append_review_audit(
                self.module_path,
                "REVIEW",
                verdict="APPROVE",
                reviewer="claude-sonnet-4-6",
                attempt="1/5",
                severity="clean",
                duration=4,
                checks=[{"id": cid, "passed": True} for cid in p.CHECK_IDS],
                feedback="Looks good.",
            )
            content = p.review_audit_path_for_key(self.module_key).read_text()
            self.assertLess(content.index("`REVIEW`"), content.index("`WRITE`"))
            self.assertIn("writer-a", content)
            self.assertIn("claude-sonnet-4-6", content)
            self.assertIn("**Total passes**: 2", content)

    def test_header_updates_on_each_append(self):
        import v1_pipeline as p

        with self._patch_paths(p):
            self._write_state(phase="write", reviewer="gemini", severity="targeted")
            p.append_review_audit(
                self.module_path,
                "WRITE",
                writer=GEMINI_WRITER_MODEL,
                mode="write",
                duration=1,
                plan="first",
                output_chars=10,
            )

            self._write_state(phase="done", reviewer="claude", severity="clean")
            p.append_review_audit(
                self.module_path,
                "DONE",
                reviewer="claude",
                pass_sum="all binary checks passed",
            )
            content = p.review_audit_path_for_key(self.module_key).read_text()
            self.assertIn("**Current phase**: done", content)
            self.assertIn("**Current reviewer**: claude", content)
            self.assertIn("**Current severity**: clean", content)
            self.assertIn("**Total passes**: 2", content)
            self.assertRegex(content, r"\*\*First pass\*\*: [0-9TZ:\-]+")
            self.assertRegex(content, r"\*\*Last pass\*\*: [0-9TZ:\-]+")

    def test_concurrent_appends_do_not_corrupt_file(self):
        import v1_pipeline as p

        self._write_state(phase="review", reviewer="gemini", severity="targeted")

        with self._patch_paths(p):
            def worker(i: int):
                p.append_review_audit(
                    self.module_path,
                    "WRITE",
                    writer=f"writer-{i}",
                    mode="write",
                    duration=i + 1,
                    plan=f"plan-{i}",
                    output_chars=100 + i,
                )

            threads = [threading.Thread(target=worker, args=(i,)) for i in range(5)]
            for thread in threads:
                thread.start()
            for thread in threads:
                thread.join()
            content = p.review_audit_path_for_key(self.module_key).read_text()
            self.assertEqual(content.count("## "), 5)
            self.assertIn("**Total passes**: 5", content)
            for i in range(5):
                self.assertIn(f"writer-{i}", content)

    def test_dry_run_creates_no_audit_file(self):
        import v1_pipeline as p

        state = {"modules": {}}
        with self._patch_paths(p), \
             patch.object(p, "dispatch_auto") as mock_dispatch:
            result = p.run_module(self.module_path, state, dry_run=True)
            self.assertFalse(result)
            self.assertEqual(mock_dispatch.call_count, 0)
            self.assertFalse(p.review_audit_path_for_key(self.module_key).exists())

    def test_full_pipeline_pass_produces_complete_audit(self):
        import v1_pipeline as p

        state = {"modules": {}}
        review_ok = {
            "verdict": "APPROVE",
            "checks": [{"id": cid, "passed": True} for cid in p.CHECK_IDS],
            "edits": [],
            "feedback": "Approved.",
        }
        git_ok = subprocess.CompletedProcess(["git"], 0, "", "")

        with self._patch_paths(p), \
             patch.object(p, "step_write", return_value=GOOD_MODULE), \
             patch.object(p, "step_review", return_value=review_ok), \
             patch.object(p, "ensure_fact_ledger", return_value=sample_fact_ledger()), \
             patch.object(p, "step_content_aware_fact_ledger", return_value=None), \
             patch.object(p, "step_check_integrity", return_value=(True, [])), \
             patch.object(p, "step_check", return_value=(True, [])), \
             patch.object(p, "_git_stage_and_commit", return_value=(git_ok, git_ok)) as mock_git:
            ok = p.run_module(self.module_path, state)
            self.assertTrue(ok)
            audit_path = p.review_audit_path_for_key(self.module_key)
            content = audit_path.read_text()
            self.assertIn("`WRITE`", content)
            self.assertIn("`REVIEW`", content)
            self.assertIn("`CHECK_PASS`", content)
            self.assertIn("`DONE`", content)
            self.assertLess(content.index("`DONE`"), content.index("`CHECK_PASS`"))
            self.assertLess(content.index("`CHECK_PASS`"), content.index("`REVIEW`"))
            self.assertLess(content.index("`REVIEW`"), content.index("`WRITE`"))
            add_paths = mock_git.call_args[0][0]
            self.assertIn(str(self.module_path), add_paths)
            self.assertIn(str(audit_path), add_paths)

    def test_check_retries_in_function_without_returning_false(self):
        import v1_pipeline as p

        state = {
            "modules": {
                self.module_key: {
                    "phase": "check",
                    "reviewer": "gemini",
                    "severity": "clean",
                    "errors": [],
                }
            }
        }
        self.module_path.with_suffix(".staging.md").write_text(GOOD_MODULE)
        transient_failure = [CheckResult("LINE_COUNT", False, "temporary check failure")]
        git_ok = subprocess.CompletedProcess(["git"], 0, "", "")

        with self._patch_paths(p), \
             patch.object(p, "ensure_fact_ledger", return_value=sample_fact_ledger()), \
             patch.object(
                 p,
                 "step_check",
                 side_effect=[(False, transient_failure), (True, [])],
             ) as mock_check, \
             patch.object(p, "_git_stage_and_commit", return_value=(git_ok, git_ok)):
            ok = p.run_module(self.module_path, state, max_retries=1)

        ms = state["modules"][self.module_key]
        self.assertTrue(ok)
        self.assertEqual(mock_check.call_count, 2)
        self.assertEqual(ms["phase"], "done")
        self.assertEqual(ms.get("check_failures"), 0)
        self.assertNotIn("Deterministic checks failed after review", ms["errors"])

    def test_reset_stuck_writes_reset_audit_and_commits_batch(self):
        import v1_pipeline as p

        state = {
            "modules": {
                self.module_key: {
                    "phase": "check",
                    "reviewer": "gemini",
                    "severity": "targeted",
                    "errors": [
                        "Deterministic checks failed after review",
                        "Review rejected 5 times",
                    ],
                }
            }
        }
        self.state_file.parent.mkdir(parents=True, exist_ok=True)
        self.state_file.write_text(yaml.dump(state, sort_keys=False))
        git_ok = subprocess.CompletedProcess(["git"], 0, "", "")

        with self._patch_paths(p), \
             patch.object(p, "_git_stage_and_commit", return_value=(git_ok, git_ok)) as mock_git:
            p.cmd_reset_stuck(Namespace())
            audit_path = p.review_audit_path_for_key(self.module_key)
            content = audit_path.read_text()
            self.assertIn("`RESET`", content)
            self.assertIn("**New phase**: pending", content)
            self.assertIn("Deterministic checks failed after review", content)
            self.assertIn("Review rejected 5 times", content)
            add_paths = mock_git.call_args[0][0]
            self.assertEqual(add_paths, [str(audit_path)])

    def test_reset_stuck_clears_stale_resume_metadata_on_fresh_restart(self):
        import v1_pipeline as p

        staging_path = self.module_path.with_suffix(".staging.md")
        staging_path.write_text("stale staged draft")
        state = {
            "modules": {
                self.module_key: {
                    "phase": "check",
                    "severity": "targeted",
                    "checks_failed": [{"id": "LAB", "evidence": "old failure"}],
                    "plan": "TARGETED FIX. Old plan from previous run.",
                    "targeted_fix": True,
                    "paused_reason": "rate limit",
                    "errors": ["Deterministic checks failed after review"],
                }
            }
        }
        self.state_file.parent.mkdir(parents=True, exist_ok=True)
        self.state_file.write_text(yaml.dump(state, sort_keys=False))
        git_ok = subprocess.CompletedProcess(["git"], 0, "", "")

        with self._patch_paths(p), \
             patch.object(p, "_git_stage_and_commit", return_value=(git_ok, git_ok)):
            p.cmd_reset_stuck(Namespace())

        reloaded = yaml.safe_load(self.state_file.read_text())
        ms = reloaded["modules"][self.module_key]
        self.assertEqual(ms["phase"], "write")
        self.assertNotIn("plan", ms)
        self.assertNotIn("targeted_fix", ms)
        self.assertNotIn("paused_reason", ms)
        self.assertFalse(staging_path.exists(), "Fresh restart should drop stale staged draft")


# ---------------------------------------------------------------------------
# Test: Pipeline step_check (deterministic gate)
# ---------------------------------------------------------------------------

class TestStepCheck(unittest.TestCase):
    """Test the CHECK step that gates file writes."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.module_path = Path(self.tmpdir) / "module-0.1-test.md"
        self.module_path.write_text(GOOD_MODULE)

    def tearDown(self):
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_good_content_passes_check(self):
        import v1_pipeline as p
        passed, results = p.step_check(GOOD_MODULE, self.module_path)
        self.assertTrue(passed, f"Good module should pass CHECK. Errors: "
                        f"{[r.message for r in results if not r.passed and r.severity == 'ERROR']}")

    def test_truncated_content_fails(self):
        """Content significantly shorter than original should fail truncation guard."""
        import v1_pipeline as p
        truncated = GOOD_MODULE[:len(GOOD_MODULE) // 3]  # ~33% of original
        passed, _results = p.step_check(truncated, self.module_path)
        self.assertFalse(passed, "Truncated content should fail CHECK")

    def test_missing_frontmatter_fails(self):
        import v1_pipeline as p
        passed, _results = p.step_check("No frontmatter here", self.module_path)
        self.assertFalse(passed, "Content without frontmatter should fail")

    def test_broken_yaml_frontmatter_fails(self):
        import v1_pipeline as p
        broken = "---\ntitle: [invalid yaml\n---\nBody"
        passed, _results = p.step_check(broken, self.module_path)
        self.assertFalse(passed, "Broken YAML frontmatter should fail")

    def test_frontmatter_missing_title_fails(self):
        import v1_pipeline as p
        no_title = "---\nsidebar:\n  order: 1\n---\n## Content"
        passed, _results = p.step_check(no_title, self.module_path)
        self.assertFalse(passed, "Frontmatter without title should fail")


# ---------------------------------------------------------------------------
# Test: Pipeline state transitions (mocked LLM)
# ---------------------------------------------------------------------------

class TestPipelineTransitions(_CalibrationIsolatedCase):
    """Test run_module state transitions with mocked LLM calls."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.state_file = Path(self.tmpdir) / "state.yaml"
        self.module_path = Path(self.tmpdir) / "module-0.1-test.md"
        self.module_path.write_text(GOOD_MODULE)

    def tearDown(self):
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def _mock_write_success(self, *args, **kwargs):
        """Mock Gemini write that returns valid improved content."""
        return True, GOOD_MODULE

    def _mock_review_approve(self, *args, **kwargs):
        """Mock review that approves (binary gate #223)."""
        import v1_pipeline as p

        check_ids = p.CHECK_IDS
        return True, json.dumps({
            "verdict": "APPROVE",
            "severity": "clean",
            "checks": [{"id": cid, "passed": True} for cid in check_ids],
            "edits": [],
            "feedback": "",
        })

    def _mock_review_reject(self, *args, **kwargs):
        """Mock review that rejects with 1 fixable quiz issue."""
        import v1_pipeline as p

        check_ids = p.CHECK_IDS
        checks = [{"id": cid, "passed": True} for cid in check_ids]
        checks[1] = {"id": "QUIZ", "passed": False,
                     "evidence": "Recall-based not scenario-based",
                     "edit_refs": [0]}
        return True, json.dumps({
            "verdict": "REJECT",
            "severity": "targeted",
            "checks": checks,
            "edits": [{"type": "replace", "find": "What port",
                       "new": "In a scenario where", "reason": "Scenario framing"}],
            "feedback": "Quiz questions are recall-based, not scenario-based",
        })

    @patch("v1_pipeline.STATE_FILE")
    @patch("v1_pipeline.dispatch_auto")
    @patch("v1_pipeline.CONTENT_ROOT")
    @patch("subprocess.run")
    def test_pending_module_writes_then_reviews_to_done(
        self, mock_subprocess, mock_root, mock_dispatch, mock_state,
    ):
        """Fresh modules now go straight to write, then independent review."""
        import v1_pipeline as p

        mock_state.__class__ = type(self.state_file)
        mock_dispatch.side_effect = [
            self._mock_write_success(),
            self._mock_review_approve(),
        ]

        mock_root.resolve.return_value = Path(self.tmpdir).resolve()
        state = {"modules": {}}

        with patch.object(p, "STATE_FILE", self.state_file), \
             patch.object(p, "CONTENT_ROOT", Path(self.tmpdir)), \
             patch.object(p, "save_state"), \
             patch.object(p, "ensure_fact_ledger", return_value=sample_fact_ledger()), \
             patch.object(p, "step_content_aware_fact_ledger", return_value=None), \
             patch.object(p, "_compute_cite_check", return_value={"id": "CITE", "passed": True, "evidence": "ok"}), \
             patch.object(p, "step_check_integrity", return_value=(True, [])), \
             patch.object(p, "module_key_from_path", return_value="test/module-0.1-test"):
            p.run_module(self.module_path, state)

        ms = state["modules"].get("test/module-0.1-test", {})
        self.assertEqual(ms.get("phase"), "done")
        self.assertTrue(ms.get("passes"))
        self.assertEqual(ms.get("reviewer"), "gemini")
        self.assertFalse(ms.get("needs_independent_review", True))
        # Write + review dispatches should have fired
        self.assertEqual(mock_dispatch.call_count, 2)

    @patch("v1_pipeline.STATE_FILE")
    @patch("v1_pipeline.dispatch_auto")
    @patch("v1_pipeline.CONTENT_ROOT")
    @patch("subprocess.run")
    def test_done_module_without_pending_flag_returns_true(
        self, mock_subprocess, mock_root, mock_dispatch, mock_state,
    ):
        """phase=done without needs_independent_review returns True (skip, not fail)."""
        import v1_pipeline as p

        mock_state.__class__ = type(self.state_file)
        mock_root.resolve.return_value = Path(self.tmpdir).resolve()

        state = {
            "modules": {
                "test/module-0.1-test": {
                    "phase": "done",
                    "reviewer": "codex",
                    "scores": [5] * 8,
                    "sum": 40,
                    "passes": True,
                    "needs_independent_review": False,
                    "errors": [],
                },
            },
        }

        with patch.object(p, "STATE_FILE", self.state_file), \
             patch.object(p, "CONTENT_ROOT", Path(self.tmpdir)), \
             patch.object(p, "save_state"), \
             patch.object(p, "module_key_from_path", return_value="test/module-0.1-test"):
            result = p.run_module(self.module_path, state)

        self.assertTrue(result, "Already-done module should return True, not False")
        # No dispatch calls — nothing should have been re-run
        self.assertEqual(mock_dispatch.call_count, 0)

    @patch("v1_pipeline.STATE_FILE")
    @patch("v1_pipeline.dispatch_auto")
    @patch("v1_pipeline.CONTENT_ROOT")
    @patch("subprocess.run")
    def test_done_module_with_pending_flag_reruns_review_only(
        self, mock_subprocess, mock_root, mock_dispatch, mock_state,
    ):
        """phase=done with needs_independent_review flag re-runs review only."""
        import v1_pipeline as p

        mock_state.__class__ = type(self.state_file)
        mock_root.resolve.return_value = Path(self.tmpdir).resolve()
        mock_dispatch.side_effect = [
            self._mock_review_approve(),
        ]

        state = {
            "modules": {
                "test/module-0.1-test": {
                    "phase": "done",
                    "reviewer": "gemini",
                    "scores": [5] * 8,
                    "sum": 40,
                    "passes": True,
                    "needs_independent_review": True,
                    "errors": [],
                },
            },
        }

        with patch.object(p, "STATE_FILE", self.state_file), \
             patch.object(p, "CONTENT_ROOT", Path(self.tmpdir)), \
             patch.object(p, "save_state"), \
             patch.object(p, "ensure_fact_ledger", return_value=sample_fact_ledger()), \
             patch.object(p, "step_content_aware_fact_ledger", return_value=None), \
             patch.object(p, "_compute_cite_check", return_value={"id": "CITE", "passed": True, "evidence": "ok"}), \
             patch.object(p, "step_check_integrity", return_value=(True, [])), \
             patch.object(p, "module_key_from_path", return_value="test/module-0.1-test"):
            p.run_module(self.module_path, state)

        ms = state["modules"]["test/module-0.1-test"]
        self.assertEqual(ms.get("phase"), "done")
        self.assertEqual(ms.get("reviewer"), "gemini")
        self.assertFalse(ms.get("needs_independent_review", True))
        # Only re-review should fire
        self.assertEqual(mock_dispatch.call_count, 1)

    @patch("v1_pipeline.STATE_FILE")
    @patch("v1_pipeline.CONTENT_ROOT")
    @patch("subprocess.run")
    def test_review_falls_back_to_sonnet_without_pending_flag(
        self, mock_subprocess, mock_root, mock_state,
    ):
        """Codex rate limiting should fall back to Sonnet and still count as independent review."""
        import v1_pipeline as p

        mock_state.__class__ = type(self.state_file)
        mock_root.resolve.return_value = Path(self.tmpdir).resolve()

        state = {"modules": {}}
        all_pass_checks = [{"id": cid, "passed": True} for cid in p.CHECK_IDS]
        review_sequence = [
            {"rate_limited": True},
            {"verdict": "APPROVE", "severity": "clean",
             "checks": all_pass_checks, "edits": [], "feedback": ""},
        ]

        with patch.object(p, "STATE_FILE", self.state_file), \
             patch.object(p, "CONTENT_ROOT", Path(self.tmpdir)), \
             patch.object(p, "save_state"), \
             patch.object(p, "module_key_from_path", return_value="test/module-0.1-test"), \
             patch.object(p, "step_write", return_value=GOOD_MODULE), \
             patch.object(p, "step_review", side_effect=review_sequence) as mock_review, \
             patch.object(p, "ensure_fact_ledger", return_value=sample_fact_ledger()), \
             patch.object(p, "step_content_aware_fact_ledger", return_value=None), \
             patch.object(p, "step_check_integrity", return_value=(True, [])), \
             patch.object(p, "step_check", return_value=(True, [])):
            p.run_module(self.module_path, state)

        ms = state["modules"]["test/module-0.1-test"]
        self.assertEqual(ms.get("phase"), "done")
        self.assertEqual(ms.get("reviewer"), "claude")
        self.assertFalse(ms.get("needs_independent_review", True))
        self.assertEqual(mock_review.call_count, 2)

    @patch("v1_pipeline.STATE_FILE")
    @patch("v1_pipeline.CONTENT_ROOT")
    @patch("subprocess.run")
    def test_last_resort_same_family_review_sets_pending_flag(
        self, mock_subprocess, mock_root, mock_state,
    ):
        """Writer-family last-resort approvals must preserve the deferred re-review flag."""
        import v1_pipeline as p

        mock_state.__class__ = type(self.state_file)
        mock_root.resolve.return_value = Path(self.tmpdir).resolve()

        state = {"modules": {}}
        all_pass_checks = [{"id": cid, "passed": True} for cid in p.CHECK_IDS]
        review_sequence = [
            {"rate_limited": True},
            {"rate_limited": True},
            {"verdict": "APPROVE", "severity": "clean",
             "checks": all_pass_checks, "edits": [], "feedback": ""},
        ]

        with patch.object(p, "STATE_FILE", self.state_file), \
             patch.object(p, "CONTENT_ROOT", Path(self.tmpdir)), \
             patch.object(p, "save_state"), \
             patch.object(p, "module_key_from_path", return_value="test/module-0.1-test"), \
             patch.object(p, "step_write", return_value=GOOD_MODULE), \
             patch.object(p, "step_review", side_effect=review_sequence) as mock_review, \
             patch.object(p, "ensure_fact_ledger", return_value=sample_fact_ledger()), \
             patch.object(p, "step_content_aware_fact_ledger", return_value=None), \
             patch.object(p, "step_check_integrity", return_value=(True, [])), \
             patch.object(p, "step_check", return_value=(True, [])):
            p.run_module(self.module_path, state)

        ms = state["modules"]["test/module-0.1-test"]
        self.assertEqual(ms.get("phase"), "done")
        self.assertEqual(ms.get("reviewer"), "gemini")
        self.assertTrue(ms.get("needs_independent_review"))
        self.assertEqual(mock_review.call_count, 3)

    @patch("v1_pipeline.STATE_FILE")
    @patch("v1_pipeline.CONTENT_ROOT")
    @patch("subprocess.run")
    def test_review_skips_same_writer_family_fallback_to_last_resort(
        self, mock_subprocess, mock_root, mock_state,
    ):
        """Same-writer-family fallback should skip straight to last resort and preserve re-review flag."""
        import v1_pipeline as p

        mock_state.__class__ = type(self.state_file)
        mock_root.resolve.return_value = Path(self.tmpdir).resolve()

        state = {"modules": {}}
        models = {
            **p.MODELS,
            "write": "claude-sonnet-4-6",
            "review": "gemini-3.1-pro-preview",
            "review_fallback": "claude-sonnet-4-6",
        }
        all_pass_checks = [{"id": cid, "passed": True} for cid in p.CHECK_IDS]
        review_sequence = [
            {"rate_limited": True},
            {"verdict": "APPROVE", "severity": "clean",
             "checks": all_pass_checks, "edits": [], "feedback": ""},
        ]

        with patch.object(p, "STATE_FILE", self.state_file), \
             patch.object(p, "CONTENT_ROOT", Path(self.tmpdir)), \
             patch.object(p, "save_state"), \
             patch.object(p, "module_key_from_path", return_value="test/module-0.1-test"), \
             patch.object(p, "step_write", return_value=GOOD_MODULE), \
             patch.object(p, "step_review", side_effect=review_sequence) as mock_review, \
             patch.object(p, "ensure_fact_ledger", return_value=sample_fact_ledger()), \
             patch.object(p, "step_content_aware_fact_ledger", return_value=None), \
             patch.object(p, "step_check_integrity", return_value=(True, [])), \
             patch.object(p, "step_check", return_value=(True, [])):
            p.run_module(self.module_path, state, models=models)

        ms = state["modules"]["test/module-0.1-test"]
        self.assertEqual(ms.get("phase"), "done")
        self.assertEqual(ms.get("reviewer"), "claude")
        self.assertTrue(ms.get("needs_independent_review"))
        self.assertEqual(mock_review.call_count, 2)
        self.assertEqual(
            [call.kwargs["model"] for call in mock_review.call_args_list],
            [models["review"], models["write"]],
        )

    @patch("v1_pipeline.STATE_FILE")
    @patch("v1_pipeline.CONTENT_ROOT")
    @patch("subprocess.run")
    def test_review_uses_approved_cross_family_fallback_before_last_resort(
        self, mock_subprocess, mock_root, mock_state,
    ):
        """Approved cross-family fallback should be used instead of the last-resort writer reviewer."""
        import v1_pipeline as p

        mock_state.__class__ = type(self.state_file)
        mock_root.resolve.return_value = Path(self.tmpdir).resolve()

        state = {"modules": {}}
        models = {
            **p.MODELS,
            "write": "claude-sonnet-4-6",
            "review": "gemini-3.1-pro-preview",
            "review_fallback": "gpt-5.3-codex-spark",
        }
        all_pass_checks = [{"id": cid, "passed": True} for cid in p.CHECK_IDS]
        review_sequence = [
            {"rate_limited": True},
            {"verdict": "APPROVE", "severity": "clean",
             "checks": all_pass_checks, "edits": [], "feedback": ""},
        ]

        with patch.object(p, "STATE_FILE", self.state_file), \
             patch.object(p, "CONTENT_ROOT", Path(self.tmpdir)), \
             patch.object(p, "save_state"), \
             patch.object(p, "module_key_from_path", return_value="test/module-0.1-test"), \
             patch.object(p, "step_write", return_value=GOOD_MODULE), \
             patch.object(p, "step_review", side_effect=review_sequence) as mock_review, \
             patch.object(p, "ensure_fact_ledger", return_value=sample_fact_ledger()), \
             patch.object(p, "step_content_aware_fact_ledger", return_value=None), \
             patch.object(p, "step_check_integrity", return_value=(True, [])), \
             patch.object(p, "step_check", return_value=(True, [])):
            p.run_module(self.module_path, state, models=models)

        ms = state["modules"]["test/module-0.1-test"]
        self.assertEqual(ms.get("phase"), "done")
        self.assertEqual(ms.get("reviewer"), "codex")
        self.assertFalse(ms.get("needs_independent_review", True))
        self.assertEqual(mock_review.call_count, 2)
        self.assertEqual(
            [call.kwargs["model"] for call in mock_review.call_args_list],
            [models["review"], models["review_fallback"]],
        )

    @patch("v1_pipeline.STATE_FILE")
    @patch("v1_pipeline.dispatch_auto")
    @patch("v1_pipeline.CONTENT_ROOT")
    @patch("subprocess.run")
    def test_needs_targeted_fix_resumes_from_staging(
        self, mock_subprocess, mock_root, mock_dispatch, mock_state,
    ):
        """phase=needs_targeted_fix resumes at write step with staged content.

        Verifies the peak-hours pause/resume flow (Flavor B): when a module
        was paused mid-targeted-fix because Claude was unavailable, the next
        run should load the staged draft + saved plan, skip the initial
        write + initial review, and jump straight into the targeted-fix
        retry loop.
        """
        import v1_pipeline as p

        mock_state.__class__ = type(self.state_file)
        mock_root.resolve.return_value = Path(self.tmpdir).resolve()

        # Only the targeted-fix write + its re-review should fire on resume.
        # No initial write, no initial review.
        mock_dispatch.side_effect = [
            # Claude Sonnet write (targeted fix applied)
            (True, GOOD_MODULE),
            # Codex re-review (approve)
            self._mock_review_approve(),
        ]

        # Pre-stage a Gemini draft where the pause happened.
        staging = self.module_path.with_suffix(".staging.md")
        staging.write_text(GOOD_MODULE)

        state = {
            "modules": {
                "test/module-0.1-test": {
                    "phase": "needs_targeted_fix",
                    "plan": "TARGETED FIX. LAB check failed — fix per reviewer feedback.",
                    "targeted_fix": True,
                    "paused_reason": "Claude peak hours",
                    "severity": "targeted",
                    "checks_failed": [{"id": "LAB", "evidence": "example"}],
                    "reviewer_schema_version": 3,
                    "errors": [],
                },
            },
        }

        with patch.object(p, "STATE_FILE", self.state_file), \
             patch.object(p, "CONTENT_ROOT", Path(self.tmpdir)), \
             patch.object(p, "save_state"), \
             patch.object(p, "ensure_fact_ledger", return_value=sample_fact_ledger()), \
             patch.object(p, "step_content_aware_fact_ledger", return_value=None), \
             patch.object(p, "_compute_cite_check", return_value={"id": "CITE", "passed": True, "evidence": "ok"}), \
             patch.object(p, "step_check_integrity", return_value=(True, [])), \
             patch.object(p, "module_key_from_path", return_value="test/module-0.1-test"):
            p.run_module(self.module_path, state)

        ms = state["modules"]["test/module-0.1-test"]
        self.assertEqual(ms.get("phase"), "done", "Should converge after targeted fix + re-review")
        # Exactly 2 dispatch calls: targeted-fix write + re-review. No initial write.
        self.assertEqual(mock_dispatch.call_count, 2,
                         "Should skip the initial write + initial review; only write + review fire")

    @patch("v1_pipeline.STATE_FILE")
    @patch("v1_pipeline.CONTENT_ROOT")
    @patch("subprocess.run")
    def test_severity_severe_triggers_full_rewrite(
        self, mock_subprocess, mock_root, mock_state,
    ):
        """5+ failed binary checks should force severity=severe → Gemini rewrite."""
        import v1_pipeline as p

        mock_state.__class__ = type(self.state_file)
        mock_root.resolve.return_value = Path(self.tmpdir).resolve()

        state = {"modules": {}}
        write_calls = []
        # 6 failed checks with no edits → compute_severity forces severe.
        review_sequence = [
            {
                "verdict": "REJECT",
                "checks": [
                    {"id": "LAB", "passed": False, "evidence": "lab broken"},
                    {"id": "COV", "passed": False, "evidence": "outcome 3 missing"},
                    {"id": "QUIZ", "passed": False, "evidence": "recall-only"},
                    {"id": "EXAM", "passed": True},
                    {"id": "DEPTH", "passed": False, "evidence": "no gotchas"},
                    {"id": "WHY", "passed": False, "evidence": "no rationale"},
                    {"id": "PRES", "passed": False, "evidence": "missing unique value"},
                ],
                "edits": [],
                "feedback": "Severely broken module.",
            },
            {
                "verdict": "APPROVE",
                "checks": [{"id": cid, "passed": True} for cid in p.CHECK_IDS],
                "edits": [],
                "feedback": "",
            },
        ]

        def fake_step_write(module_path, plan, model=None, rewrite=False,
                            previous_output=None, knowledge_card=None, fact_ledger=None):
            write_calls.append({
                "plan": plan,
                "model": model,
                "rewrite": rewrite,
                "previous_output": previous_output,
                "knowledge_card": knowledge_card,
                "fact_ledger": fact_ledger,
            })
            return GOOD_MODULE

        with patch.object(p, "STATE_FILE", self.state_file), \
             patch.object(p, "CONTENT_ROOT", Path(self.tmpdir)), \
             patch.object(p, "save_state"), \
             patch.object(p, "module_key_from_path", return_value="test/module-0.1-test"), \
             patch.object(p, "step_write", side_effect=fake_step_write), \
             patch.object(p, "step_review", side_effect=review_sequence), \
             patch.object(p, "ensure_fact_ledger", return_value=sample_fact_ledger()), \
             patch.object(p, "step_content_aware_fact_ledger", return_value=None), \
             patch.object(p, "step_check_integrity", return_value=(True, [])), \
             patch.object(p, "step_check", return_value=(True, [])):
            p.run_module(self.module_path, state)

        self.assertEqual(len(write_calls), 2, "Expected initial write plus rewrite retry")
        self.assertFalse(write_calls[0]["rewrite"], "First pass should be normal write mode")
        self.assertTrue(write_calls[1]["rewrite"], "6 failed checks must trigger full rewrite mode")
        self.assertIn("SEVERE REWRITE REQUIRED", write_calls[1]["plan"])
        self.assertEqual(write_calls[1]["model"], p.MODELS["write"])

    @patch("v1_pipeline.STATE_FILE")
    @patch("v1_pipeline.CONTENT_ROOT")
    @patch("subprocess.run")
    def test_stale_targeted_fix_does_not_route_severe_resume_to_targeted_writer(
        self, mock_subprocess, mock_root, mock_state,
    ):
        """Severe rewrite resumes must clear stale targeted_fix before write routing."""
        import v1_pipeline as p

        mock_state.__class__ = type(self.state_file)
        mock_root.resolve.return_value = Path(self.tmpdir).resolve()

        staging = self.module_path.with_suffix(".staging.md")
        staging.write_text(GOOD_MODULE)

        state = {
            "modules": {
                "test/module-0.1-test": {
                    "phase": "write",
                    "plan": "STALE TARGETED FIX PLAN",
                    "targeted_fix": True,
                    "severity": "severe",
                    "check_failures": 1,
                    "checks_failed": [{"id": "LAB", "evidence": "stale targeted fix after CHECK failure"}],
                    "reviewer_schema_version": 3,
                    "errors": [],
                },
            },
        }
        write_calls = []

        def fake_step_write(module_path, plan, model=None, rewrite=False,
                            previous_output=None, knowledge_card=None, fact_ledger=None):
            write_calls.append({
                "plan": plan,
                "model": model,
                "rewrite": rewrite,
                "previous_output": previous_output,
            })
            return GOOD_MODULE

        with patch.object(p, "STATE_FILE", self.state_file), \
             patch.object(p, "CONTENT_ROOT", Path(self.tmpdir)), \
             patch.object(p, "save_state"), \
             patch.object(p, "module_key_from_path", return_value="test/module-0.1-test"), \
             patch.object(p, "step_write", side_effect=fake_step_write), \
             patch.object(p, "step_review", return_value={
                 "verdict": "APPROVE",
                 "severity": "clean",
                 "checks": [{"id": cid, "passed": True} for cid in p.CHECK_IDS],
                 "edits": [],
                 "feedback": "",
             }), \
             patch.object(p, "ensure_fact_ledger", return_value=sample_fact_ledger()), \
             patch.object(p, "step_content_aware_fact_ledger", return_value=None), \
             patch.object(p, "step_check_integrity", return_value=(True, [])), \
             patch.object(p, "step_check", return_value=(True, [])):
            p.run_module(self.module_path, state)

        self.assertEqual(len(write_calls), 1, "Expected a single resumed severe rewrite")
        self.assertTrue(write_calls[0]["rewrite"], "Severe resume must stay in rewrite mode")
        self.assertEqual(write_calls[0]["model"], p.MODELS["write"],
                         "Severe rewrite must use the full writer, not the targeted-fix writer")
        self.assertFalse(state["modules"]["test/module-0.1-test"]["targeted_fix"],
                         "Stale targeted_fix must be cleared before rewrite routing")

    @patch("v1_pipeline.STATE_FILE")
    @patch("v1_pipeline.CONTENT_ROOT")
    @patch("subprocess.run")
    def test_rewrite_retry_uses_committed_baseline_for_knowledge_packet(
        self, mock_subprocess, mock_root, mock_state,
    ):
        """Rewrite retries must preserve assets from the committed baseline."""
        import v1_pipeline as p

        mock_state.__class__ = type(self.state_file)
        mock_root.resolve.return_value = Path(self.tmpdir).resolve()

        state = {"modules": {}}
        write_calls = []
        baseline_packet = p.extract_knowledge_packet(GOOD_MODULE)
        damaged_packet = p.extract_knowledge_packet(DAMAGED_REWRITE_DRAFT)
        review_sequence = [
            {
                "verdict": "REJECT",
                "checks": [
                    {"id": "LAB", "passed": False, "evidence": "lab broken"},
                    {"id": "COV", "passed": False, "evidence": "outcome 3 missing"},
                    {"id": "QUIZ", "passed": False, "evidence": "recall-only"},
                    {"id": "EXAM", "passed": True},
                    {"id": "DEPTH", "passed": False, "evidence": "no gotchas"},
                    {"id": "WHY", "passed": False, "evidence": "no rationale"},
                    {"id": "PRES", "passed": False, "evidence": "missing unique value"},
                ],
                "edits": [],
                "feedback": "Severely broken module.",
            },
            {
                "verdict": "APPROVE",
                "checks": [{"id": cid, "passed": True} for cid in p.CHECK_IDS],
                "edits": [],
                "feedback": "",
            },
        ]

        def fake_step_write(module_path, plan, model=None, rewrite=False,
                            previous_output=None, knowledge_card=None, fact_ledger=None):
            write_calls.append({
                "rewrite": rewrite,
                "previous_output": previous_output,
                "knowledge_packet": (
                    p.extract_knowledge_packet(previous_output)
                    if previous_output is not None else None
                ),
            })
            if len(write_calls) == 1:
                return DAMAGED_REWRITE_DRAFT
            return GOOD_MODULE

        with patch.object(p, "STATE_FILE", self.state_file), \
             patch.object(p, "CONTENT_ROOT", Path(self.tmpdir)), \
             patch.object(p, "save_state"), \
             patch.object(p, "module_key_from_path", return_value="test/module-0.1-test"), \
             patch.object(p, "step_write", side_effect=fake_step_write), \
             patch.object(p, "step_review", side_effect=review_sequence), \
             patch.object(p, "ensure_fact_ledger", return_value=sample_fact_ledger()), \
             patch.object(p, "step_content_aware_fact_ledger", return_value=None), \
             patch.object(p, "step_check_integrity", return_value=(True, [])), \
             patch.object(p, "step_check", return_value=(True, [])):
            p.run_module(self.module_path, state)

        self.assertEqual(len(write_calls), 2, "Expected initial write plus rewrite retry")
        self.assertNotEqual(
            damaged_packet,
            baseline_packet,
            "Damaged draft must differ from the committed baseline packet",
        )
        self.assertTrue(write_calls[1]["rewrite"], "Second write should be full rewrite mode")
        self.assertEqual(
            write_calls[1]["previous_output"],
            GOOD_MODULE,
            "Rewrite retry should use the committed baseline, not the damaged draft",
        )
        self.assertEqual(
            write_calls[1]["knowledge_packet"],
            baseline_packet,
            "Rewrite retry must rebuild the knowledge packet from the baseline",
        )

    @patch("v1_pipeline.STATE_FILE")
    @patch("v1_pipeline.CONTENT_ROOT")
    @patch("subprocess.run")
    def test_severity_targeted_routes_to_sonnet(
        self, mock_subprocess, mock_root, mock_state,
    ):
        """1-4 failed checks WITH anchors that miss → Sonnet targeted fix.

        We provide edits with non-matching `find` strings so deterministic
        apply fails, forcing the pipeline to route the retry to the Sonnet
        targeted-fix writer (not a Gemini full rewrite).
        """
        import v1_pipeline as p

        mock_state.__class__ = type(self.state_file)
        mock_root.resolve.return_value = Path(self.tmpdir).resolve()

        state = {"modules": {}}
        write_calls = []
        # 2 failed checks, both claim an edit, but the edits have anchors
        # that DO NOT exist in GOOD_MODULE. Deterministic apply will fail
        # 2/2, escalating through the partial-apply path to severe on the
        # circuit breaker — but first retry still routes to Sonnet.
        review_sequence = [
            {
                "verdict": "REJECT",
                "checks": [
                    {"id": "LAB", "passed": False, "evidence": "wrong flag", "edit_refs": [0]},
                    {"id": "COV", "passed": True},
                    {"id": "QUIZ", "passed": False, "evidence": "recall", "edit_refs": [1]},
                    {"id": "EXAM", "passed": True},
                    {"id": "DEPTH", "passed": True},
                    {"id": "WHY", "passed": True},
                    {"id": "PRES", "passed": True},
                ],
                "edits": [
                    {"type": "replace", "find": "NONEXISTENT_ANCHOR_LAB", "new": "fixed", "reason": "LAB fix"},
                    {"type": "replace", "find": "NONEXISTENT_ANCHOR_QUIZ", "new": "better", "reason": "QUIZ fix"},
                ],
                "feedback": "Two targeted issues.",
            },
            {
                "verdict": "APPROVE",
                "checks": [{"id": cid, "passed": True} for cid in p.CHECK_IDS],
                "edits": [],
                "feedback": "",
            },
        ]

        def fake_step_write(module_path, plan, model=None, rewrite=False,
                            previous_output=None, knowledge_card=None, fact_ledger=None):
            write_calls.append({
                "plan": plan,
                "model": model,
                "rewrite": rewrite,
            })
            return GOOD_MODULE

        with patch.object(p, "STATE_FILE", self.state_file), \
             patch.object(p, "CONTENT_ROOT", Path(self.tmpdir)), \
             patch.object(p, "save_state"), \
             patch.object(p, "module_key_from_path", return_value="test/module-0.1-test"), \
             patch.object(p, "step_write", side_effect=fake_step_write), \
             patch.object(p, "step_review", side_effect=review_sequence), \
             patch.object(p, "ensure_fact_ledger", return_value=sample_fact_ledger()), \
             patch.object(p, "step_content_aware_fact_ledger", return_value=None), \
             patch.object(p, "step_check_integrity", return_value=(True, [])), \
             patch.object(p, "step_check", return_value=(True, [])):
            p.run_module(self.module_path, state)

        # The compute_severity path for 2 failed checks with edits that don't
        # land (0% anchor success) → code escalates to severe, which means
        # the retry uses Gemini rewrite, not Sonnet. This is the correct
        # degradation path and matches Gemini pair-review critique D.
        self.assertEqual(len(write_calls), 2, "Initial write + one retry")
        self.assertFalse(write_calls[0]["rewrite"])
        self.assertTrue(write_calls[1]["rewrite"],
                        "Zero anchor matches → circuit breaker → severe rewrite")
        self.assertIn("SEVERE REWRITE REQUIRED", write_calls[1]["plan"])

    def test_dry_run_does_not_modify_files(self):
        """Dry run should show the initial plan but not write any files."""
        import v1_pipeline as p

        original_content = self.module_path.read_text()
        state = {"modules": {}}

        with patch.object(p, "STATE_FILE", self.state_file), \
             patch.object(p, "CONTENT_ROOT", Path(self.tmpdir)), \
             patch.object(p, "save_state"), \
             patch.object(p, "module_key_from_path", return_value="test/module-0.1-test"), \
             patch.object(p, "dispatch_auto") as mock_dispatch:
            result = p.run_module(self.module_path, state, dry_run=True)

        # File should be unchanged
        self.assertEqual(self.module_path.read_text(), original_content)
        self.assertEqual(mock_dispatch.call_count, 0, "Dry run should not dispatch any model calls")
        # Should not pass (needs improvement)
        self.assertFalse(result)

    @patch("v1_pipeline.STATE_FILE")
    @patch("v1_pipeline.CONTENT_ROOT")
    @patch("subprocess.run")
    def test_write_only_preserves_draft_for_review_resume(
        self, mock_subprocess, mock_root, mock_state,
    ):
        """Write-only must leave a saved draft in phase=review for the next run."""
        import v1_pipeline as p

        mock_state.__class__ = type(self.state_file)
        mock_root.resolve.return_value = Path(self.tmpdir).resolve()

        module_key = "test/module-0.1-test"
        draft_content = GOOD_MODULE.replace(
            "Test Module — Good",
            "Test Module — Write-only Draft",
        )
        review_ok = {
            "verdict": "APPROVE",
            "checks": [{"id": cid, "passed": True} for cid in p.CHECK_IDS],
            "edits": [],
            "feedback": "",
        }
        git_ok = subprocess.CompletedProcess(["git"], 0, "", "")
        state = {"modules": {}}

        with patch.object(p, "STATE_FILE", self.state_file), \
             patch.object(p, "CONTENT_ROOT", Path(self.tmpdir)), \
             patch.object(p, "module_key_from_path", return_value=module_key), \
             patch.object(p, "step_write", return_value=draft_content) as mock_write, \
             patch.object(p, "step_review", return_value=review_ok) as mock_review, \
             patch.object(p, "append_review_audit"), \
             patch.object(p, "_git_stage_and_commit", return_value=(git_ok, git_ok)), \
             patch.object(p, "ensure_fact_ledger", return_value=sample_fact_ledger()), \
             patch.object(p, "step_content_aware_fact_ledger", return_value=None), \
             patch.object(p, "step_check_integrity", return_value=(True, [])), \
             patch.object(p, "step_check", return_value=(True, [])):
            first_ok = p.run_module(self.module_path, state, write_only=True)
            self.assertTrue(first_ok)
            self.assertEqual(state["modules"][module_key]["phase"], "review")
            self.assertEqual(mock_write.call_count, 1)
            self.assertEqual(mock_review.call_count, 0)
            self.assertIn("Write-only Draft", self.module_path.read_text())

            second_ok = p.run_module(self.module_path, state)

        self.assertTrue(second_ok)
        self.assertEqual(mock_write.call_count, 1, "Review resume must not trigger a second write")
        self.assertEqual(mock_review.call_count, 1, "Next run should resume at review")
        self.assertIn("Write-only Draft", mock_review.call_args.args[1])
        self.assertEqual(state["modules"][module_key]["phase"], "done")


    @patch("v1_pipeline.STATE_FILE")
    @patch("v1_pipeline.CONTENT_ROOT")
    @patch("subprocess.run")
    def test_check_failures_tracks_consecutive_failures_only(
        self, mock_subprocess, mock_root, mock_state,
    ):
        import v1_pipeline as p

        mock_state.__class__ = type(self.state_file)
        mock_root.resolve.return_value = Path(self.tmpdir).resolve()

        key = "test/module-0.1-test"
        state = {
            "modules": {
                key: {
                    "phase": "check",
                    "severity": "clean",
                    "reviewer": "codex",
                    "needs_independent_review": False,
                    "passes": False,
                    "errors": [],
                }
            }
        }
        failed_results = [CheckResult("QUIZ", False, "Missing scenario-based question")]
        git_ok = subprocess.CompletedProcess(["git"], 0, "", "")

        def prepare_check_phase():
            self.module_path.with_suffix(".staging.md").write_text(GOOD_MODULE)
            state["modules"][key]["phase"] = "check"

        with patch.object(p, "STATE_FILE", self.state_file), \
             patch.object(p, "CONTENT_ROOT", Path(self.tmpdir)), \
             patch.object(p, "REVIEW_AUDIT_DIR", Path(self.tmpdir) / ".pipeline" / "reviews"), \
             patch.object(p, "KNOWLEDGE_CARD_DIR", Path(self.tmpdir) / ".pipeline" / "knowledge-cards"), \
             patch.object(p, "save_state"), \
             patch.object(p, "ensure_fact_ledger", return_value=sample_fact_ledger()), \
             patch.object(p, "_git_stage_and_commit", return_value=(git_ok, git_ok)), \
             patch.object(p, "module_key_from_path", return_value=key), \
             patch.object(
                 p,
                 "step_check",
                 side_effect=[
                     (True, []),
                     (False, failed_results),
                     (False, failed_results),
                     (False, failed_results),
                     (False, failed_results),
                     (False, failed_results),
                     (True, []),
                     (False, failed_results),
                     (False, failed_results),
                     (False, failed_results),
                     (False, failed_results),
                     (False, failed_results),
                     (False, failed_results),
                 ],
             ):
            prepare_check_phase()
            self.assertTrue(p.run_module(self.module_path, state))
            self.assertEqual(state["modules"][key].get("check_failures"), 0)

            prepare_check_phase()
            self.assertFalse(p.run_module(self.module_path, state))
            self.assertEqual(state["modules"][key].get("check_failures"), 1)

            prepare_check_phase()
            self.assertTrue(p.run_module(self.module_path, state))
            self.assertEqual(state["modules"][key].get("check_failures"), 0)

            prepare_check_phase()
            self.assertFalse(p.run_module(self.module_path, state))
            self.assertEqual(state["modules"][key].get("check_failures"), 1)


# ---------------------------------------------------------------------------
# Test: Binary quality gate — compute_severity unit tests (issue #223)
# ---------------------------------------------------------------------------

class TestComputeSeverity(unittest.TestCase):
    """compute_severity is the code-side arbiter for review routing.

    Per Gemini pair-review critique A on PR for #223, the reviewer's
    self-reported severity cannot be trusted — the LLM may under-report
    (to avoid triggering a rewrite) or produce inconsistent states
    (targeted with zero edits). These tests pin the expected routing
    behavior in pure-Python, independent of any LLM mock.
    """

    def setUp(self):
        import v1_pipeline as p
        self.p = p
        self.all_pass = [{"id": cid, "passed": True} for cid in p.CHECK_IDS]

    def test_approve_returns_clean(self):
        """APPROVE → clean regardless of what reviewer said about severity."""
        sev = self.p.compute_severity("APPROVE", self.all_pass, [])
        self.assertEqual(sev, "clean")

    def test_routes_correctly_with_seven_checks(self):
        """Split-reviewer structural rubric has 7 checks after adding CITE."""
        self.assertEqual(len(self.p.CHECK_IDS), 7)
        checks = [
            {"id": "COV", "passed": False, "edit_refs": [0]},
            {"id": "QUIZ", "passed": True},
            {"id": "EXAM", "passed": True},
            {"id": "DEPTH", "passed": True},
            {"id": "WHY", "passed": True},
            {"id": "PRES", "passed": True},
            {"id": "CITE", "passed": True},
        ]
        edits = [{"type": "replace", "find": "x", "new": "y"}]
        self.assertEqual(self.p.compute_severity("REJECT", checks, edits), "targeted")

    def test_reject_no_failed_checks_is_severe(self):
        """REJECT with zero failed checks is a structural contradiction → severe."""
        sev = self.p.compute_severity("REJECT", self.all_pass, [])
        self.assertEqual(sev, "severe")

    def test_malformed_review_payload_is_severe(self):
        """Malformed review JSON must fail closed, never silently approve."""
        self.assertEqual(self.p.compute_review_payload_severity(None), "severe")

    def test_missing_checks_key_is_severe(self):
        """APPROVE without `checks` is invalid review output → severe."""
        self.assertEqual(
            self.p.compute_review_payload_severity({"verdict": "APPROVE", "edits": []}),
            "severe",
        )

    def test_reject_five_failures_is_severe(self):
        """5+ failed checks → severe, always."""
        checks = [{"id": cid, "passed": False, "edit_refs": [i]} for i, cid in enumerate(self.p.CHECK_IDS[:5])]
        checks += [{"id": cid, "passed": True} for cid in self.p.CHECK_IDS[5:]]
        edits = [{"type": "replace", "find": f"x{i}", "new": "y"} for i in range(5)]
        sev = self.p.compute_severity("REJECT", checks, edits)
        self.assertEqual(sev, "severe")

    def test_reject_with_zero_edits_is_severe(self):
        """REJECT with failed checks but no edits at all → severe (can't patch)."""
        checks = [{"id": "LAB", "passed": False, "evidence": "bad"}] + \
                 [{"id": cid, "passed": True} for cid in self.p.CHECK_IDS[1:]]
        sev = self.p.compute_severity("REJECT", checks, [])
        self.assertEqual(sev, "severe")

    def test_reject_uncovered_failure_is_severe(self):
        """A failed check with no edit_refs is uncovered → severe."""
        checks = [
            {"id": "LAB", "passed": False, "evidence": "bad", "edit_refs": [0]},
            {"id": "LAB", "passed": False, "evidence": "lab broken"},  # no edit_refs
        ] + [{"id": cid, "passed": True} for cid in self.p.CHECK_IDS[2:]]
        edits = [{"type": "replace", "find": "x", "new": "y"}]
        sev = self.p.compute_severity("REJECT", checks, edits)
        self.assertEqual(sev, "severe",
                         "LAB failure has no edit_refs — can't mechanically fix")

    def test_reject_targeted_one_to_four_covered_failures(self):
        """1-4 failures, all with edit_refs, all with edits → targeted."""
        checks = [
            {"id": "LAB", "passed": False, "evidence": "minor", "edit_refs": [0]},
            {"id": "LAB", "passed": False, "evidence": "fix", "edit_refs": [1]},
        ] + [{"id": cid, "passed": True} for cid in self.p.CHECK_IDS[2:]]
        edits = [
            {"type": "replace", "find": "a", "new": "b"},
            {"type": "replace", "find": "c", "new": "d"},
        ]
        sev = self.p.compute_severity("REJECT", checks, edits)
        self.assertEqual(sev, "targeted")

    def test_reject_four_covered_failures_still_targeted(self):
        """Boundary: exactly 4 failures, all covered → still targeted."""
        checks = [
            {"id": cid, "passed": False, "evidence": "x", "edit_refs": [i]}
            for i, cid in enumerate(self.p.CHECK_IDS[:4])
        ] + [{"id": cid, "passed": True} for cid in self.p.CHECK_IDS[4:]]
        edits = [{"type": "replace", "find": f"x{i}", "new": "y"} for i in range(4)]
        sev = self.p.compute_severity("REJECT", checks, edits)
        self.assertEqual(sev, "targeted")

    def test_edit_refs_bool_is_uncovered(self):
        """edit_refs=True looks truthy but is not a valid list → severe.

        Codex PR review: compute_severity previously treated any truthy
        edit_refs as coverage, so a reviewer producing a bool would
        misroute to targeted. Validate the shape strictly.
        """
        checks = [
            {"id": "LAB", "passed": False, "evidence": "x", "edit_refs": True},
        ] + [{"id": cid, "passed": True} for cid in self.p.CHECK_IDS[1:]]
        edits = [{"type": "replace", "find": "a", "new": "b"}]
        self.assertEqual(self.p.compute_severity("REJECT", checks, edits), "severe")

    def test_edit_refs_string_is_uncovered(self):
        """edit_refs="0" (string) is not a list of ints → severe."""
        checks = [
            {"id": "LAB", "passed": False, "evidence": "x", "edit_refs": "0"},
        ] + [{"id": cid, "passed": True} for cid in self.p.CHECK_IDS[1:]]
        edits = [{"type": "replace", "find": "a", "new": "b"}]
        self.assertEqual(self.p.compute_severity("REJECT", checks, edits), "severe")

    def test_edit_refs_out_of_bounds_is_uncovered(self):
        """edit_refs=[999] points at no real edit → severe."""
        checks = [
            {"id": "LAB", "passed": False, "evidence": "x", "edit_refs": [999]},
        ] + [{"id": cid, "passed": True} for cid in self.p.CHECK_IDS[1:]]
        edits = [{"type": "replace", "find": "a", "new": "b"}]
        self.assertEqual(self.p.compute_severity("REJECT", checks, edits), "severe")

    def test_edit_refs_mixed_valid_invalid_is_uncovered(self):
        """If any ref is invalid, the whole check is uncovered → severe."""
        checks = [
            {"id": "LAB", "passed": False, "evidence": "x", "edit_refs": [0, 999]},
        ] + [{"id": cid, "passed": True} for cid in self.p.CHECK_IDS[1:]]
        edits = [{"type": "replace", "find": "a", "new": "b"}]
        self.assertEqual(self.p.compute_severity("REJECT", checks, edits), "severe")

    def test_edits_not_a_list_is_severe(self):
        """edits=None or edits=dict → severe (can't patch)."""
        checks = [
            {"id": "LAB", "passed": False, "evidence": "x", "edit_refs": [0]},
        ] + [{"id": cid, "passed": True} for cid in self.p.CHECK_IDS[1:]]
        self.assertEqual(self.p.compute_severity("REJECT", checks, None), "severe")
        self.assertEqual(
            self.p.compute_severity("REJECT", checks, {"bad": "shape"}),
            "severe"
        )


class TestBinaryGateIntegration(_CalibrationIsolatedCase):
    """End-to-end: stub reviewer returns binary-gate output, pipeline routes
    correctly and converges with exactly the expected writer calls."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.module_path = Path(self.tmpdir) / "test" / "module-0.1-test.md"
        self.module_path.parent.mkdir(parents=True, exist_ok=True)
        self.module_path.write_text(GOOD_MODULE)
        self.state_file = Path(self.tmpdir) / "state.yaml"

    def tearDown(self):
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    @patch("v1_pipeline.STATE_FILE")
    @patch("v1_pipeline.CONTENT_ROOT")
    @patch("subprocess.run")
    def test_approve_on_first_review_sets_severity_clean(
        self, mock_subprocess, mock_root, mock_state,
    ):
        """Clean approval — module converges immediately, state records severity=clean."""
        import v1_pipeline as p

        mock_state.__class__ = type(self.state_file)
        mock_root.resolve.return_value = Path(self.tmpdir).resolve()

        state = {"modules": {}}
        review_sequence = [
            {
                "verdict": "APPROVE",
                "checks": [{"id": cid, "passed": True} for cid in p.CHECK_IDS],
                "edits": [],
                "feedback": "All good.",
            },
        ]

        with patch.object(p, "STATE_FILE", self.state_file), \
             patch.object(p, "CONTENT_ROOT", Path(self.tmpdir)), \
             patch.object(p, "save_state"), \
             patch.object(p, "module_key_from_path", return_value="test/module-0.1-test"), \
             patch.object(p, "step_write", return_value=GOOD_MODULE), \
             patch.object(p, "step_review", side_effect=review_sequence), \
             patch.object(p, "ensure_fact_ledger", return_value=sample_fact_ledger()), \
             patch.object(p, "step_content_aware_fact_ledger", return_value=None), \
             patch.object(p, "step_check_integrity", return_value=(True, [])), \
             patch.object(p, "step_check", return_value=(True, [])), \
             patch.object(p, "ensure_knowledge_card", return_value="card"):
            p.run_module(self.module_path, state)

        ms = state["modules"]["test/module-0.1-test"]
        self.assertEqual(ms.get("phase"), "done")
        self.assertEqual(ms.get("severity"), "clean")
        self.assertEqual(ms.get("checks_failed"), [])
        self.assertEqual(ms.get("reviewer_schema_version"), 3)
        self.assertTrue(ms.get("passes"))
        # Old schema fields must be absent on new-gate runs
        self.assertNotIn("scores", ms)
        self.assertNotIn("sum", ms)

    @patch("v1_pipeline.STATE_FILE")
    @patch("v1_pipeline.CONTENT_ROOT")
    @patch("subprocess.run")
    def test_targeted_reject_with_clean_apply_skips_writer(
        self, mock_subprocess, mock_root, mock_state,
    ):
        """REJECT with targeted severity + edits that all land → no second writer call."""
        import v1_pipeline as p

        self.assertEqual(p._second_reviewer_sample_rate(), 0.0)
        self.assertEqual(p.random.random(), 0.0)
        mock_state.__class__ = type(self.state_file)
        mock_root.resolve.return_value = Path(self.tmpdir).resolve()

        state = {"modules": {}}
        write_calls = []

        def fake_step_write(module_path, plan, model=None, rewrite=False,
                            previous_output=None, knowledge_card=None, fact_ledger=None):
            write_calls.append({"model": model, "rewrite": rewrite})
            return GOOD_MODULE

        review_sequence = [
            {
                "verdict": "REJECT",
                "checks": [
                    {"id": "LAB", "passed": False, "evidence": "one anchor",
                     "edit_refs": [0]},
                    {"id": "COV", "passed": True},
                    {"id": "QUIZ", "passed": True},
                    {"id": "EXAM", "passed": True},
                    {"id": "DEPTH", "passed": True},
                    {"id": "WHY", "passed": True},
                    {"id": "PRES", "passed": True},
                ],
                "edits": [
                    {"type": "replace", "find": "## Learning Outcomes",
                     "new": "## Learning Outcomes (v2)", "reason": "tag"},
                ],
                "feedback": "",
            },
            {
                "verdict": "APPROVE",
                "checks": [{"id": cid, "passed": True} for cid in p.CHECK_IDS],
                "edits": [],
                "feedback": "",
            },
        ]

        with patch.object(p, "STATE_FILE", self.state_file), \
             patch.object(p, "CONTENT_ROOT", Path(self.tmpdir)), \
             patch.object(p, "save_state"), \
             patch.object(p, "module_key_from_path", return_value="test/module-0.1-test"), \
             patch.object(p, "step_write", side_effect=fake_step_write), \
             patch.object(p, "step_review", side_effect=review_sequence), \
             patch.object(p, "ensure_fact_ledger", return_value=sample_fact_ledger()), \
             patch.object(p, "step_content_aware_fact_ledger", return_value=None), \
             patch.object(p, "step_check_integrity", return_value=(True, [])), \
             patch.object(p, "step_check", return_value=(True, [])), \
             patch.object(p, "ensure_knowledge_card", return_value="card"):
            p.run_module(self.module_path, state)

        # Initial write only — the deterministic apply patched the module
        # without invoking the writer a second time.
        self.assertEqual(len(write_calls), 1,
                         f"Expected 1 writer call, got {len(write_calls)}")
        self.assertIn("## Learning Outcomes (v2)", self.module_path.read_text())
        ms = state["modules"]["test/module-0.1-test"]
        self.assertEqual(ms.get("phase"), "done")
        self.assertEqual(ms.get("severity"), "clean")


class TestLegacyStateCompat(_CalibrationIsolatedCase):
    """Legacy state fixtures must continue to load and upgrade cleanly."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.state_file = Path(self.tmpdir) / "state.yaml"
        self.module_path = Path(self.tmpdir) / "module-0.1-test.md"
        self.module_path.write_text(GOOD_MODULE)

    def tearDown(self):
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_legacy_state_has_scores_and_no_severity(self):
        """v1 legacy fixture shape is still represented correctly."""
        legacy_ms = {
            "phase": "done",
            "scores": [4, 4, 4, 4, 4, 4, 4, 5],
            "sum": 33,
            "passes": True,
            "last_run": "2026-04-10T12:00:00+00:00",
            "errors": [],
            "reviewer": "codex",
            "needs_independent_review": False,
        }
        # Schema version is inferred: has scores + no reviewer_schema_version → v1
        self.assertIsNone(legacy_ms.get("reviewer_schema_version"))
        self.assertIsNotNone(legacy_ms.get("scores"))

    @patch("subprocess.run")
    def test_v2_state_fixture_upgrades_to_v3_shape(self, _mock_subprocess):
        """A v2 fixture (reviewer_schema_version=2) upgrades after one run."""
        import v1_pipeline as p

        state = {
            "modules": {
                "test/module-0.1-test": {
                    "phase": "review",
                    "reviewer_schema_version": 2,
                    "scores": [4, 4, 4, 4, 4, 4, 4, 5],
                    "sum": 33,
                    "passes": False,
                    "errors": [],
                }
            }
        }
        review_ok = {
            "verdict": "APPROVE",
            "checks": [{"id": cid, "passed": True} for cid in p.CHECK_IDS],
            "edits": [],
            "feedback": "",
        }

        with patch.object(p, "STATE_FILE", self.state_file), \
             patch.object(p, "CONTENT_ROOT", Path(self.tmpdir)), \
             patch.object(p, "save_state"), \
             patch.object(p, "module_key_from_path", return_value="test/module-0.1-test"), \
             patch.object(p, "ensure_fact_ledger", return_value=sample_fact_ledger()), \
             patch.object(p, "step_content_aware_fact_ledger", return_value=None), \
             patch.object(p, "step_check_integrity", return_value=(True, [])), \
             patch.object(p, "step_review", return_value=review_ok), \
             patch.object(p, "step_check", return_value=(True, [])):
            p.run_module(self.module_path, state, max_retries=0)

        ms = state["modules"]["test/module-0.1-test"]
        self.assertEqual(ms.get("reviewer_schema_version"), 3)
        self.assertIn("checks_failed", ms)
        self.assertNotIn("scores", ms)
        self.assertNotIn("sum", ms)

    @patch("subprocess.run")
    def test_v1_state_fixture_upgrades_to_v3_shape(self, _mock_subprocess):
        """A v1 fixture (no reviewer_schema_version) upgrades after one run."""
        import v1_pipeline as p

        state = {
            "modules": {
                "test/module-0.1-test": {
                    "phase": "review",
                    "scores": [4, 4, 4, 4, 4, 4, 4, 5],
                    "sum": 33,
                    "passes": False,
                    "errors": [],
                }
            }
        }
        review_ok = {
            "verdict": "APPROVE",
            "checks": [{"id": cid, "passed": True} for cid in p.CHECK_IDS],
            "edits": [],
            "feedback": "",
        }

        with patch.object(p, "STATE_FILE", self.state_file), \
             patch.object(p, "CONTENT_ROOT", Path(self.tmpdir)), \
             patch.object(p, "save_state"), \
             patch.object(p, "module_key_from_path", return_value="test/module-0.1-test"), \
             patch.object(p, "ensure_fact_ledger", return_value=sample_fact_ledger()), \
             patch.object(p, "step_content_aware_fact_ledger", return_value=None), \
             patch.object(p, "step_check_integrity", return_value=(True, [])), \
             patch.object(p, "step_review", return_value=review_ok), \
             patch.object(p, "step_check", return_value=(True, [])):
            p.run_module(self.module_path, state, max_retries=0)

        ms = state["modules"]["test/module-0.1-test"]
        self.assertEqual(ms.get("reviewer_schema_version"), 3)
        self.assertIn("checks_failed", ms)
        self.assertNotIn("scores", ms)
        self.assertNotIn("sum", ms)


class TestLegacyReviewerCompat(unittest.TestCase):
    """Legacy reviewer payloads with `scores` should normalize to v3 checks."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.module_path = Path(self.tmpdir) / "module-0.1-test.md"
        self.module_path.write_text(GOOD_MODULE)

    def tearDown(self):
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_legacy_scores_normalized_to_checks(self):
        import v1_pipeline as p

        payload = {
            "verdict": "APPROVE",
            "scores": {
                "lab": 5,
                "coverage": 4,
                "quiz": 2,
            },
            "feedback": "Legacy schema output",
        }
        with patch.object(p, "module_key_from_path", return_value="test/module-0.1-test"), \
             patch.object(p, "dispatch_auto", return_value=(True, json.dumps(payload))):
            review = p.step_review(self.module_path, GOOD_MODULE)

        self.assertIsNotNone(review)
        checks = review.get("checks", [])
        self.assertGreaterEqual(len(checks), 3)
        self.assertTrue(any(c.get("id") == "LAB" and c.get("passed") for c in checks))
        self.assertTrue(any(c.get("id") == "QUIZ" and not c.get("passed") for c in checks))
        self.assertTrue(all("evidence" in c for c in checks))


# ---------------------------------------------------------------------------
# Test: Track alias resolution (e2e command)
# ---------------------------------------------------------------------------

class TestTrackAliases(unittest.TestCase):
    """Test that track aliases resolve correctly."""

    def test_track_from_key_certs(self):
        import v1_pipeline as p
        self.assertEqual(p._track_from_key("k8s/cka/part1/module-1.1"), "certs")
        self.assertEqual(p._track_from_key("k8s/ckad/part2/module-2.1"), "certs")
        self.assertEqual(p._track_from_key("k8s/cks/part3/module-3.1"), "certs")
        self.assertEqual(p._track_from_key("k8s/kcna/part1/module-1.1"), "certs")
        self.assertEqual(p._track_from_key("k8s/kcsa/part1/module-1.1"), "certs")

    def test_track_from_key_prereqs(self):
        import v1_pipeline as p
        self.assertEqual(p._track_from_key("prerequisites/zero-to-terminal/module-0.1"), "prereqs")

    def test_track_from_key_cloud(self):
        import v1_pipeline as p
        self.assertEqual(p._track_from_key("cloud/aws-essentials/module-1.1"), "cloud")

    def test_track_from_key_platform(self):
        """Platform sub-sections resolve to their full sub-group for status display."""
        import v1_pipeline as p
        # Sub-sections are grouped distinctly (supports per-subsection progress)
        self.assertEqual(p._track_from_key("platform/foundations/module-1.1"), "platform/foundations")
        self.assertEqual(p._track_from_key("platform/disciplines/sre/module-1"), "platform/disciplines")
        self.assertEqual(p._track_from_key("platform/toolkits/gitops/module-1"), "platform/toolkits")
        # Top-level platform path with no recognized sub-section → "platform"
        self.assertEqual(p._track_from_key("platform/misc/module-1"), "platform")

    def test_track_from_key_linux(self):
        import v1_pipeline as p
        self.assertEqual(p._track_from_key("linux/foundations/networking/module-3.1"), "linux")

    def test_track_from_key_specialty(self):
        import v1_pipeline as p
        self.assertEqual(p._track_from_key("k8s/pca/module-1"), "specialty")


# ---------------------------------------------------------------------------
# Test: Four-stage status tracking table
# ---------------------------------------------------------------------------

class TestStatusFourStage(unittest.TestCase):
    """cmd_status should render four-stage completion ratios per track/section."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.content_root = Path(self.tmpdir) / "src" / "content" / "docs"
        self.content_root.mkdir(parents=True, exist_ok=True)
        self.ledger_dir = Path(self.tmpdir) / ".pipeline" / "fact-ledgers"
        self.ledger_dir.mkdir(parents=True, exist_ok=True)

    def tearDown(self):
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def _write(self, rel: str, chars: int) -> Path:
        path = self.content_root / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("x" * chars)
        return path

    def _write_ledger(self, key: str, days_old: int = 0) -> None:
        path = self.ledger_dir / f"{key.replace('/', '__')}.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(sample_fact_ledger()))
        if days_old:
            ts = (datetime.now(UTC) - timedelta(days=days_old)).timestamp()
            os.utime(path, (ts, ts))

    def test_cmd_status_prints_four_stage_completion_table(self):
        import io
        from contextlib import redirect_stdout

        import v1_pipeline as p

        self._write("prerequisites/intro/module-1.1-alpha.md", 2400)          # written + fresh ledger + pass + UK >= 500
        self._write("prerequisites/intro/module-1.2-beta.md", 2200)           # written + stale ledger + no pass + UK < 500
        self._write("k8s/cka/part1/module-1.1-gamma.md", 1200)                # not written + fresh ledger + pass + UK >= 500
        self._write("on-premises/storage/module-9.9-skip.staging.md", 2600)   # excluded

        self._write("uk/prerequisites/intro/module-1.1-alpha.md", 700)
        self._write("uk/prerequisites/intro/module-1.2-beta.md", 300)
        self._write("uk/k8s/cka/part1/module-1.1-gamma.md", 700)

        self._write_ledger("prerequisites/intro/module-1.1-alpha")
        self._write_ledger("prerequisites/intro/module-1.2-beta", days_old=8)
        self._write_ledger("k8s/cka/part1/module-1.1-gamma")

        state = {
            "modules": {
                "prerequisites/intro/module-1.1-alpha": {"passes": True, "phase": "done"},
                "prerequisites/intro/module-1.2-beta": {"passes": False, "phase": "write"},
                "k8s/cka/part1/module-1.1-gamma": {"passes": True, "phase": "done"},
            }
        }

        buf = io.StringIO()
        with patch.object(p, "CONTENT_ROOT", self.content_root), \
             patch.object(p, "FACT_LEDGER_DIR", self.ledger_dir), \
             patch.object(p, "load_state", return_value=state), \
             redirect_stdout(buf):
            p.cmd_status(Namespace(verbose=False))

        out = buf.getvalue()
        self.assertIn("=== Module Completion ===", out)
        self.assertRegex(out, r"(?m)^prerequisites\s+2/2\s+1/2\s+1/2\s+1/2\s+1/2$")
        self.assertRegex(out, r"(?m)^k8s/cka\s+0/1\s+1/1\s+1/1\s+1/1\s+0/1$")
        self.assertRegex(out, r"(?m)^TOTAL\s+2/3\s+2/3\s+2/3\s+2/3\s+1/3$")


class TestStatusHtmlDashboard(unittest.TestCase):
    """cmd_status --html should generate a grouped heatmap dashboard."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.content_root = Path(self.tmpdir) / "src" / "content" / "docs"
        self.content_root.mkdir(parents=True, exist_ok=True)
        self.ledger_dir = Path(self.tmpdir) / ".pipeline" / "fact-ledgers"
        self.ledger_dir.mkdir(parents=True, exist_ok=True)
        self.dashboard_path = Path(self.tmpdir) / ".pipeline" / "dashboard.html"

    def tearDown(self):
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def _write(self, rel: str, chars: int) -> Path:
        path = self.content_root / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("x" * chars)
        return path

    def _write_ledger(self, key: str, days_old: int = 0) -> None:
        path = self.ledger_dir / f"{key.replace('/', '__')}.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(sample_fact_ledger()))
        if days_old:
            ts = (datetime.now(UTC) - timedelta(days=days_old)).timestamp()
            os.utime(path, (ts, ts))

    def test_status_html_dashboard_generated(self):
        import v1_pipeline as p

        self._write("prerequisites/intro/module-1.1-alpha.md", 2400)   # written, fact, review, uk
        self._write("prerequisites/intro/module-1.2-beta.md", 2200)    # written only
        self._write("k8s/cka/part1/module-1.1-gamma.md", 1200)         # not written, fact+review+uk

        self._write("uk/prerequisites/intro/module-1.1-alpha.md", 700)
        self._write("uk/prerequisites/intro/module-1.2-beta.md", 300)
        self._write("uk/k8s/cka/part1/module-1.1-gamma.md", 700)

        self._write_ledger("prerequisites/intro/module-1.1-alpha")
        self._write_ledger("prerequisites/intro/module-1.2-beta", days_old=8)
        self._write_ledger("k8s/cka/part1/module-1.1-gamma")

        state = {
            "modules": {
                "prerequisites/intro/module-1.1-alpha": {"passes": True, "phase": "done"},
                "prerequisites/intro/module-1.2-beta": {"passes": False, "phase": "write"},
                "k8s/cka/part1/module-1.1-gamma": {"passes": True, "phase": "done"},
            }
        }

        with patch.object(p, "CONTENT_ROOT", self.content_root), \
             patch.object(p, "FACT_LEDGER_DIR", self.ledger_dir), \
             patch.object(p, "DASHBOARD_FILE", self.dashboard_path), \
             patch.object(p, "load_state", return_value=state), \
             patch("subprocess.run") as mock_run:
            p.cmd_status(Namespace(verbose=False, html=True))

        self.assertTrue(self.dashboard_path.exists())
        html = self.dashboard_path.read_text()

        self.assertIn('<table id="status-heatmap">', html)
        self.assertIn("<th>Written</th>", html)
        self.assertIn("<th>Fact-Checked</th>", html)
        self.assertIn("<th>Reviewed</th>", html)
        self.assertIn("<th>UK-Translated</th>", html)
        self.assertIn('class="cell-done"', html)
        self.assertIn('class="cell-not-done"', html)
        self.assertIn('class="cell-na"', html)
        self.assertIn("Track Summary: prerequisites", html)
        self.assertIn("Track Summary: k8s", html)
        self.assertIn('<tr class="total-summary">', html)
        self.assertIn(">TOTAL</td>", html)

        mock_run.assert_called_once_with(["open", str(self.dashboard_path)], check=False)


# ---------------------------------------------------------------------------
# Test: Knowledge cards
# ---------------------------------------------------------------------------

class TestKnowledgeCards(unittest.TestCase):
    """Test knowledge-card generation, caching, and prompt injection."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.repo_root = Path(self.tmpdir)
        self.content_root = self.repo_root / "src" / "content" / "docs"
        self.content_root.mkdir(parents=True, exist_ok=True)
        self.card_dir = self.repo_root / ".pipeline" / "knowledge-cards"
        self.module_key = "on-premises/planning/module-1.5-onprem-finops-chargeback"
        self.module_path = self.content_root / "on-premises" / "planning" / "module-1.5-onprem-finops-chargeback.md"
        self.module_path.parent.mkdir(parents=True, exist_ok=True)
        self.module_path.write_text(textwrap.dedent("""\
        ---
        title: "Module 1.5: On-Prem FinOps & Chargeback"
        slug: on-premises/planning/module-1.5-onprem-finops-chargeback
        sidebar:
          order: 105
        ---

        > **Topic**: On-prem FinOps and chargeback with OpenCost, Kubecost, and VPA

        ## Learning Outcomes

        By the end of this module, you will be able to:
        - Explain OpenCost pricing inputs on bare metal
        - Compare showback and chargeback trade-offs
        - Validate rightsizing and VPA recommendation sources
        """))

    def tearDown(self):
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def _card_path(self):
        import v1_pipeline as p
        return self.card_dir / f"{p.sanitize_module_key(self.module_key)}.md"

    def _build_card(self, *, generated_at: str | None = None,
                    expires: str | None = None) -> str:
        today = datetime.now(UTC).date()
        generated_at = generated_at or today.isoformat()
        expires = expires or (today + timedelta(days=30)).isoformat()
        return textwrap.dedent(f"""\
        ---
        topic: "On-prem FinOps and chargeback with OpenCost, Kubecost, and VPA"
        module_key: "{self.module_key}"
        generated_by: "codex"
        generated_at: "{generated_at}"
        expires: "{expires}"
        ---

        ## Current status (as of generated_at)
        - OpenCost is a CNCF Incubating project and not a sandbox project.
        - Current OpenCost custom pricing uses `costModel` keys like `CPU`, `RAM`, `GPU`, and `storage`.
        - VPA recommendations are surfaced on VerticalPodAutoscaler status.

        ## Authoritative sources
        - https://www.opencost.io/docs/configuration — current custom pricing schema and examples.
        - https://kyverno.io/docs/writing-policies/validate/ — current policy authoring guidance and deprecation path.
        - https://github.com/kubernetes/autoscaler/tree/master/vertical-pod-autoscaler — VPA components and recommendation flow.

        ## Do not
        - Call OpenCost a CNCF sandbox project.
        - Invent `cpuHourlyCost` or `ramHourlyCost` fields in OpenCost custom pricing examples.
        - Say VPA recommendations come from Prometheus instead of the VPA recommender path.
        """)

    def _write_seed_file(self, content: str) -> None:
        docs_dir = self.repo_root / "docs"
        docs_dir.mkdir(parents=True, exist_ok=True)
        (docs_dir / "citation-seeds-ai-foundations.md").write_text(content)

    def test_knowledge_card_written_with_correct_schema(self):
        """Generator writes a schema-valid knowledge card to the cache."""
        import generate_knowledge_card as g
        import v1_pipeline as p

        with patch.object(p, "CONTENT_ROOT", self.content_root), \
             patch.object(p, "KNOWLEDGE_CARD_DIR", self.card_dir), \
             patch.object(g, "KNOWLEDGE_CARD_DIR", self.card_dir), \
             patch.object(g, "dispatch_codex", return_value=(True, f"```markdown\n{self._build_card()}\n```")):
            card = g.generate(self.module_key, force=True)

        self.assertIsNotNone(card)
        card_path = self._card_path()
        self.assertTrue(card_path.exists(), "Knowledge card should be written to disk")
        frontmatter = yaml.safe_load(card_path.read_text().split("---", 2)[1])
        for key in ("topic", "module_key", "generated_by", "generated_at", "expires"):
            self.assertIn(key, frontmatter)
        self.assertEqual(frontmatter["module_key"], self.module_key)
        self.assertIn("## Do not", card_path.read_text())

    def test_knowledge_card_cached_when_fresh(self):
        """Fresh cached cards should be reused without calling Codex."""
        import generate_knowledge_card as g
        import v1_pipeline as p

        self.card_dir.mkdir(parents=True, exist_ok=True)
        existing = self._build_card()
        self._card_path().write_text(existing)
        ms = {}

        with patch.object(p, "CONTENT_ROOT", self.content_root), \
             patch.object(p, "KNOWLEDGE_CARD_DIR", self.card_dir), \
             patch.object(g, "KNOWLEDGE_CARD_DIR", self.card_dir), \
             patch.object(g, "dispatch_codex") as mock_codex:
            card = p.ensure_knowledge_card(self.module_path, ms)

        self.assertEqual(card, existing)
        self.assertEqual(mock_codex.call_count, 0, "Fresh cache should skip Codex")
        self.assertNotIn("stale_knowledge_card", ms)

    def test_knowledge_card_regenerated_when_expired(self):
        """Expired cached cards should trigger regeneration."""
        import generate_knowledge_card as g
        import v1_pipeline as p

        self.card_dir.mkdir(parents=True, exist_ok=True)
        expired = self._build_card(
            generated_at=(datetime.now(UTC).date() - timedelta(days=120)).isoformat(),
            expires=(datetime.now(UTC).date() - timedelta(days=1)).isoformat(),
        )
        fresh = self._build_card()
        self._card_path().write_text(expired)
        ms = {}

        with patch.object(p, "CONTENT_ROOT", self.content_root), \
             patch.object(p, "KNOWLEDGE_CARD_DIR", self.card_dir), \
             patch.object(g, "KNOWLEDGE_CARD_DIR", self.card_dir), \
             patch.object(g, "dispatch_codex", return_value=(True, fresh)) as mock_codex:
            card = p.ensure_knowledge_card(self.module_path, ms)

        self.assertEqual(card.strip(), fresh.strip())
        self.assertEqual(mock_codex.call_count, 1)
        self.assertEqual(self._card_path().read_text().strip(), fresh.strip())
        self.assertNotIn("stale_knowledge_card", ms)

    def test_knowledge_card_codex_rate_limited_uses_stale(self):
        """Expired stale card should be reused when Codex is rate-limited."""
        import generate_knowledge_card as g
        import v1_pipeline as p

        self.card_dir.mkdir(parents=True, exist_ok=True)
        stale = self._build_card(
            generated_at=(datetime.now(UTC).date() - timedelta(days=120)).isoformat(),
            expires=(datetime.now(UTC).date() - timedelta(days=1)).isoformat(),
        )
        self._card_path().write_text(stale)
        ms = {}

        with patch.object(p, "CONTENT_ROOT", self.content_root), \
             patch.object(p, "KNOWLEDGE_CARD_DIR", self.card_dir), \
             patch.object(g, "KNOWLEDGE_CARD_DIR", self.card_dir), \
             patch.object(g, "dispatch_codex", return_value=(False, "429 Too Many Requests")):
            card = p.ensure_knowledge_card(self.module_path, ms)

        self.assertEqual(card, stale)
        self.assertTrue(ms.get("stale_knowledge_card"))

    def test_knowledge_card_codex_rate_limited_no_stale_returns_none(self):
        """If Codex is rate-limited and no stale card exists, return None."""
        import generate_knowledge_card as g
        import v1_pipeline as p

        ms = {}
        with patch.object(p, "CONTENT_ROOT", self.content_root), \
             patch.object(p, "KNOWLEDGE_CARD_DIR", self.card_dir), \
             patch.object(g, "KNOWLEDGE_CARD_DIR", self.card_dir), \
             patch.object(g, "dispatch_codex", return_value=(False, "429 Too Many Requests")):
            card = p.ensure_knowledge_card(self.module_path, ms)

        self.assertIsNone(card)
        self.assertNotIn("stale_knowledge_card", ms)

    def test_knowledge_card_injected_into_write_prompt(self):
        """step_write should inject the card content into the writer prompt."""
        import v1_pipeline as p

        card = self._build_card()
        seen = {}

        def fake_dispatch(prompt, model=None, timeout=None):
            seen["prompt"] = prompt
            return True, GOOD_MODULE

        with patch.object(p, "dispatch_auto", side_effect=fake_dispatch), \
             patch.object(p, "module_key_from_path", return_value=self.module_key):
            result = p.step_write(self.module_path, "Improve factual accuracy", knowledge_card=card)

        self.assertIsNotNone(result)
        self.assertIn(card, seen["prompt"])
        self.assertIn("KNOWLEDGE CARD:", seen["prompt"])

    def test_write_prompt_includes_k8s_lifecycle_block(self):
        """Writer prompt should include the current Kubernetes version policy block."""
        import v1_pipeline as p

        seen = {}

        def fake_dispatch(prompt, model=None, timeout=None):
            seen["prompt"] = prompt
            return True, GOOD_MODULE

        with patch.object(p, "dispatch_auto", side_effect=fake_dispatch), \
             patch.object(p, "module_key_from_path", return_value=self.module_key):
            result = p.step_write(self.module_path, "Improve version guidance")

        self.assertIsNotNone(result)
        today = datetime.now(UTC).date().isoformat()
        self.assertIn("## Kubernetes Version Policy", seen["prompt"])
        self.assertIn(f"Current supported versions (as of {today}):", seen["prompt"])
        self.assertIn("- v1.35 (current stable release)", seen["prompt"])
        self.assertIn("- v1.32 and below: end-of-life", seen["prompt"])

    def test_write_prompt_includes_verified_claims_from_fact_ledger(self):
        """Supported/verified claims should be surfaced in a dedicated prompt block."""
        import v1_pipeline as p

        fact_ledger = {
            "as_of_date": "2026-04-12",
            "topic": "Versioning",
            "claims": [
                {
                    "id": "C1",
                    "claim": "Kubernetes current stable is v1.35",
                    "status": "SUPPORTED",
                    "sources": [{"url": "https://kubernetes.io/releases/"}],
                },
                {
                    "id": "C2",
                    "claim": "Helm current stable is v4.0.1",
                    "status": "VERIFIED",
                    "sources": [],
                },
                {
                    "id": "C3",
                    "claim": "This unverified claim should not be surfaced",
                    "status": "UNVERIFIED",
                    "sources": [],
                },
            ],
        }
        seen = {}

        def fake_dispatch(prompt, model=None, timeout=None):
            seen["prompt"] = prompt
            return True, GOOD_MODULE

        with patch.object(p, "dispatch_auto", side_effect=fake_dispatch), \
             patch.object(p, "module_key_from_path", return_value=self.module_key):
            result = p.step_write(self.module_path, "Improve factual accuracy", fact_ledger=fact_ledger)

        self.assertIsNotNone(result)
        self.assertIn("## Verified Facts (from fact-grounding pass)", seen["prompt"])
        self.assertIn(
            "- [C1] Kubernetes current stable is v1.35 (source: https://kubernetes.io/releases/)",
            seen["prompt"],
        )
        self.assertIn(
            "- [C2] Helm current stable is v4.0.1 (source: verified)",
            seen["prompt"],
        )
        verified_block = seen["prompt"].split("## Verified Facts (from fact-grounding pass)", 1)[1]
        verified_block = verified_block.split("IMPROVEMENT PLAN:", 1)[0]
        self.assertNotIn("This unverified claim should not be surfaced", verified_block)

    def test_seed_injection_extracts_matching_entry(self):
        """step_write should inject only the current module's citation seeds."""
        import v1_pipeline as p

        self._write_seed_file(textwrap.dedent("""\
        # AI Foundations — Citation Seeds

        ## `ai/foundations/module-1.1-what-is-ai`

        - [NIST AI RMF](https://nvlpubs.nist.gov/nistpubs/ai/nist.ai.100-1.pdf) — definitional framing
        1. [IBM Deep Blue](https://www.ibm.com/history/deep-blue) — rule-based milestone
        https://ai.google/responsibility/principles/ — current AI principles

        ## `ai/foundations/module-1.2-what-are-llms`

        - [Attention Is All You Need](https://arxiv.org/abs/1706.03762) — transformer source
        """))
        seen = {}

        def fake_dispatch(prompt, model=None, timeout=None):
            seen["prompt"] = prompt
            return True, GOOD_MODULE

        with patch.object(p, "REPO_ROOT", self.repo_root), \
             patch.object(p, "dispatch_auto", side_effect=fake_dispatch), \
             patch.object(p, "module_key_from_path", return_value="ai/foundations/module-1.1-what-is-ai"):
            result = p.step_write(self.module_path, "Improve factual accuracy")

        self.assertIsNotNone(result)
        self.assertIn("## Sources — cite these inline", seen["prompt"])
        self.assertIn("https://nvlpubs.nist.gov/nistpubs/ai/nist.ai.100-1.pdf", seen["prompt"])
        self.assertIn("https://www.ibm.com/history/deep-blue", seen["prompt"])
        self.assertIn("https://ai.google/responsibility/principles/", seen["prompt"])
        self.assertNotIn("https://arxiv.org/abs/1706.03762", seen["prompt"])

    def test_seed_injection_reaches_rewrite_prompt(self):
        """Rewrite prompts should include the authoritative sources block."""
        import v1_pipeline as p

        self._write_seed_file(textwrap.dedent("""\
        # AI Foundations — Citation Seeds

        ## `ai/foundations/module-1.1-what-is-ai`

        - [NIST AI RMF](https://nvlpubs.nist.gov/nistpubs/ai/nist.ai.100-1.pdf) — definitional framing
        """))
        seen = {}

        with patch.object(p, "REPO_ROOT", self.repo_root), \
             patch.object(p, "dispatch_auto", side_effect=lambda prompt, model=None, timeout=None: (seen.__setitem__("prompt", prompt), (True, GOOD_MODULE))[1]), \
             patch.object(p, "module_key_from_path", return_value="ai/foundations/module-1.1-what-is-ai"):
            p.step_write(self.module_path, "Improve factual accuracy", rewrite=True)

        self.assertIn("## Sources — cite these inline", seen["prompt"])
        self.assertIn("https://nvlpubs.nist.gov/nistpubs/ai/nist.ai.100-1.pdf", seen["prompt"])

    def test_seed_injection_no_seeds_file_is_noop(self):
        """Missing seed file should leave the WRITE prompt unchanged."""
        import v1_pipeline as p

        seen = {}

        def fake_dispatch(prompt, model=None, timeout=None):
            seen["prompt"] = prompt
            return True, GOOD_MODULE

        with patch.object(p, "REPO_ROOT", self.repo_root), \
             patch.object(p, "dispatch_auto", side_effect=fake_dispatch), \
             patch.object(p, "module_key_from_path", return_value="ai/foundations/module-1.1-what-is-ai"):
            result = p.step_write(self.module_path, "Improve factual accuracy")

        self.assertIsNotNone(result)
        self.assertNotIn("## Sources — cite these inline", seen["prompt"])

    def test_seed_injection_no_matching_module_is_noop(self):
        """Existing seed file without a matching section should be ignored."""
        import v1_pipeline as p

        self._write_seed_file(textwrap.dedent("""\
        # AI Foundations — Citation Seeds

        ## `ai/foundations/module-1.2-what-are-llms`

        - [Attention Is All You Need](https://arxiv.org/abs/1706.03762) — transformer source
        """))
        seen = {}

        def fake_dispatch(prompt, model=None, timeout=None):
            seen["prompt"] = prompt
            return True, GOOD_MODULE

        with patch.object(p, "REPO_ROOT", self.repo_root), \
             patch.object(p, "dispatch_auto", side_effect=fake_dispatch), \
             patch.object(p, "module_key_from_path", return_value="ai/foundations/module-1.1-what-is-ai"):
            result = p.step_write(self.module_path, "Improve factual accuracy")

        self.assertIsNotNone(result)
        self.assertNotIn("## Sources — cite these inline", seen["prompt"])

    def test_seed_injection_noop_for_root_level_module_key(self):
        """Root-level module keys should skip seed lookup entirely."""
        import v1_pipeline as p

        seen = {}

        with patch.object(p, "REPO_ROOT", self.repo_root), \
             patch.object(p, "dispatch_auto", side_effect=lambda prompt, model=None, timeout=None: (seen.__setitem__("prompt", prompt), (True, GOOD_MODULE))[1]), \
             patch.object(p, "module_key_from_path", return_value="module-0.1-test"), \
             patch.object(Path, "exists", side_effect=AssertionError("seed lookup should be skipped")):
            p.step_write(self.module_path, "Improve factual accuracy")

        self.assertNotIn("## Sources — cite these inline", seen["prompt"])


class TestCitationGate(_CalibrationIsolatedCase):
    """Test the seeded citation gate between WRITE and REVIEW."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.repo_root = Path(self.tmpdir)
        self.content_root = self.repo_root / "src" / "content" / "docs"
        self.content_root.mkdir(parents=True, exist_ok=True)
        self.module_key = "ai/foundations/module-1.1-what-is-ai"
        self.module_path = self.content_root / "ai" / "foundations" / "module-1.1-what-is-ai.md"
        self.module_path.parent.mkdir(parents=True, exist_ok=True)
        self.module_path.write_text(GOOD_MODULE)
        self.state_file = self.repo_root / ".pipeline" / "state.yaml"
        self.review_dir = self.repo_root / ".pipeline" / "reviews"
        self.seed_path = self.repo_root / "docs" / "citation-seeds-ai-foundations.md"
        self.seed_path.parent.mkdir(parents=True, exist_ok=True)
        self.seed_path.write_text(
            "## `ai/foundations/module-1.1-what-is-ai`\n"
            "- [NIST](https://nvlpubs.nist.gov/nistpubs/ai/nist.ai.100-1.pdf)\n"
            "- [IBM](https://www.ibm.com/history/deep-blue)\n"
        )

    def tearDown(self):
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def _patch_paths(self, p):
        return patch.multiple(
            p,
            REPO_ROOT=self.repo_root,
            CONTENT_ROOT=self.content_root,
            STATE_FILE=self.state_file,
            REVIEW_AUDIT_DIR=self.review_dir,
            FACT_LEDGER_DIR=self.repo_root / ".pipeline" / "fact-ledgers",
            KNOWLEDGE_CARD_DIR=self.repo_root / ".pipeline" / "knowledge-cards",
        )

    def _checker_result(self, *, passes=True, sources_count=3, issues=None, dead_urls=None):
        entry = {"path": str(self.module_path), "passes": passes, "issues": issues or [], "sources_count": sources_count}
        if dead_urls is not None:
            entry["dead_urls"] = dead_urls
        return subprocess.CompletedProcess(["python"], 0 if passes else 1, json.dumps({"passes": passes, "results": [entry]}), "")

    def _cite_ready_draft(
        self,
        inline_nist: bool = True,
        inline_ibm: bool = True,
        source_nist: bool = True,
        source_ibm: bool = True,
    ) -> str:
        body_links = []
        if inline_nist:
            body_links.append("[NIST](https://nvlpubs.nist.gov/nistpubs/ai/nist.ai.100-1.pdf)")
        if inline_ibm:
            body_links.append("[IBM](https://www.ibm.com/history/deep-blue)")
        sources_links = []
        if source_nist:
            sources_links.append("- [NIST](https://nvlpubs.nist.gov/nistpubs/ai/nist.ai.100-1.pdf)")
        if source_ibm:
            sources_links.append("- [IBM](https://www.ibm.com/history/deep-blue)")
        return (
            "---\ntitle: Test\n---\n\n"
            + " and ".join(body_links)
            + "\n\n## Sources\n"
            "- [NIST](https://nvlpubs.nist.gov/nistpubs/ai/nist.ai.100-1.pdf)\n"
            "- [IBM](https://www.ibm.com/history/deep-blue)\n"
            "\n## Sources\n"
            + "\n".join(sources_links)
            + "\n"
        )

    def test_cite_check_passes_when_all_seeds_cited_inline(self):
        import v1_pipeline as p

        with patch.object(p, "_resolve_url_statuses", return_value={
            "https://nvlpubs.nist.gov/nistpubs/ai/nist.ai.100-1.pdf": 200,
            "https://www.ibm.com/history/deep-blue": 200,
        }):
            result = p._compute_cite_check(self._cite_ready_draft())

        self.assertTrue(result["passed"])

    def test_cite_check_fails_when_seed_url_only_in_authoritative_sources_not_body(self):
        import v1_pipeline as p

        with patch.object(p, "_resolve_url_statuses", return_value={
            "https://nvlpubs.nist.gov/nistpubs/ai/nist.ai.100-1.pdf": 200,
            "https://www.ibm.com/history/deep-blue": 200,
        }):
            result = p._compute_cite_check(self._cite_ready_draft(inline_ibm=False, source_ibm=False))

        self.assertFalse(result["passed"])
        self.assertIn("https://www.ibm.com/history/deep-blue", result["evidence"])

    def test_cite_check_fails_on_dead_url(self):
        import v1_pipeline as p

        with patch.object(p, "_resolve_url_statuses", return_value={
            "https://nvlpubs.nist.gov/nistpubs/ai/nist.ai.100-1.pdf": 200,
            "https://www.ibm.com/history/deep-blue": 404,
        }):
            result = p._compute_cite_check(self._cite_ready_draft())

        self.assertFalse(result["passed"])
        self.assertIn("https://www.ibm.com/history/deep-blue", result["evidence"])

    def test_step_check_citations_passes_when_draft_meets_threshold(self):
        import v1_pipeline as p

        self.module_path.write_text(
            "---\ntitle: Test\n---\n\n"
            "See [NIST](https://nvlpubs.nist.gov/nistpubs/ai/nist.ai.100-1.pdf) and "
            "[IBM](https://www.ibm.com/history/deep-blue).\n\n## Sources\n"
            "- [NIST](https://nvlpubs.nist.gov/nistpubs/ai/nist.ai.100-1.pdf)\n"
            "- [IBM](https://www.ibm.com/history/deep-blue)\n"
            "- [Google](https://ai.google/responsibility/principles/)\n"
        )

        with self._patch_paths(p), \
             patch("v1_pipeline.subprocess.run", return_value=self._checker_result()):
            result = p.step_check_citations(self.module_path, self.seed_path)

        self.assertTrue(result["passes"])
        self.assertEqual(result["citation_count"], 3)
        self.assertEqual(result["missing_seed_urls"], [])

    def test_step_check_citations_rejects_below_threshold_and_loops_back(self):
        import v1_pipeline as p

        review_ok = {"verdict": "APPROVE", "checks": [{"id": cid, "passed": True} for cid in p.CHECK_IDS], "edits": [], "feedback": ""}
        git_ok = subprocess.CompletedProcess(["git"], 0, "", "")
        fail = {"passes": False, "citation_count": 1, "issues": ["needs_at_least_3_citations"], "missing_seed_urls": [], "dead_urls": []}
        ok = {"passes": True, "citation_count": 3, "issues": [], "missing_seed_urls": [], "dead_urls": []}
        state = {"modules": {}}

        with self._patch_paths(p), \
             patch.object(p, "step_write", return_value=GOOD_MODULE) as mock_write, \
             patch.object(p, "step_check_citations", side_effect=[fail, ok]) as mock_citations, \
             patch.object(p, "step_review", return_value=review_ok), \
             patch.object(p, "ensure_fact_ledger", return_value=sample_fact_ledger()), \
             patch.object(p, "step_content_aware_fact_ledger", return_value=None), \
             patch.object(p, "step_check_integrity", return_value=(True, [])), \
             patch.object(p, "step_check", return_value=(True, [])), \
             patch.object(p, "_git_stage_and_commit", return_value=(git_ok, git_ok)):
            result = p.run_module(self.module_path, state, max_retries=1)

        self.assertTrue(result)
        self.assertEqual(mock_write.call_count, 2)
        self.assertEqual(mock_citations.call_count, 2)

    def test_step_check_citations_aborts_after_three_failed_writes_preserves_state(self):
        import v1_pipeline as p

        original = {"phase": "pending", "errors": ["keep me"], "severity": "clean", "passes": False}
        state = {"modules": {self.module_key: copy.deepcopy(original)}}
        self.module_path.with_suffix(".staging.md").write_text("pre-run staging")
        fail = {"passes": False, "citation_count": 1, "issues": ["needs_at_least_3_citations"], "missing_seed_urls": [], "dead_urls": []}

        with self._patch_paths(p), \
             patch.object(p, "step_write", return_value=GOOD_MODULE) as mock_write, \
             patch.object(p, "step_check_citations", return_value=fail), \
             patch.object(p, "ensure_fact_ledger", return_value=sample_fact_ledger()):
            result = p.run_module(self.module_path, state, max_retries=2)

        self.assertFalse(result)
        self.assertEqual(mock_write.call_count, 3)
        self.assertEqual(state["modules"][self.module_key], original)
        self.assertEqual(self.module_path.with_suffix(".staging.md").read_text(), "pre-run staging")

    def test_step_check_citations_rejects_on_dead_url(self):
        import v1_pipeline as p

        self.module_path.write_text("## Sources\n- [dead](https://dead.example)")
        with self._patch_paths(p), \
             patch("v1_pipeline.subprocess.run", return_value=self._checker_result(
                 passes=False,
                 issues=["dead_url: https://dead.example"],
                 dead_urls=["https://dead.example"],
             )):
            result = p.step_check_citations(self.module_path, self.seed_path)

        self.assertFalse(result["passes"])
        self.assertIn("https://dead.example", result["dead_urls"])

    def test_review_verdict_cannot_be_APPROVE_when_cite_fails(self):
        import v1_pipeline as p

        self.module_path.write_text("---\ntitle: Test\n---\n")
        review_payload = json.dumps({
            "verdict": "APPROVE",
            "checks": [{"id": cid, "passed": True} for cid in ["COV", "QUIZ", "EXAM", "DEPTH", "WHY", "PRES"]],
            "edits": [],
            "feedback": "",
        })
        with self._patch_paths(p), \
             patch.object(p, "dispatch_auto", return_value=(True, review_payload)), \
             patch.object(p, "_resolve_url_statuses", return_value={
                 "https://nvlpubs.nist.gov/nistpubs/ai/nist.ai.100-1.pdf": 200,
                 "https://www.ibm.com/history/deep-blue": 200,
             }):
            review = p.step_review(self.module_path, self._cite_ready_draft(inline_ibm=False, source_ibm=False))

        self.assertEqual(review["verdict"], "REJECT")
        self.assertEqual(review["severity"], "severe")
        self.assertTrue(any(c["id"] == "CITE" and not c["passed"] for c in review["checks"]))


# ---------------------------------------------------------------------------
# Test: Fact ledger + integrity gate + split-reviewer run flow
# ---------------------------------------------------------------------------

class TestFactLedger(unittest.TestCase):
    """Test fact-ledger generation, validation, and cache behavior."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.repo_root = Path(self.tmpdir)
        self.content_root = self.repo_root / "src" / "content" / "docs"
        self.content_root.mkdir(parents=True, exist_ok=True)
        self.module_path = self.content_root / "test" / "module-0.1-test.md"
        self.module_path.parent.mkdir(parents=True, exist_ok=True)
        self.module_path.write_text("---\ntitle: Test Module\n---\n\nBody")
        self.ledger_dir = self.repo_root / ".pipeline" / "fact-ledgers"
        self.module_key = "test/module-0.1-test"

    def tearDown(self):
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def _ledger_payload(self, marker: str = "A") -> dict:
        return {
            "as_of_date": "2026-04-12",
            "topic": f"Test Module {marker}",
            "claims": [
                {
                    "id": "C1",
                    "claim": "Supported claim",
                    "status": "SUPPORTED",
                    "current_truth": f"Supported truth {marker}",
                    "sources": [{"url": "https://kubernetes.io/releases/", "source_date": "2026-04-12"}],
                    "conflict_summary": None,
                    "unverified_reason": None,
                },
                {
                    "id": "C2",
                    "claim": "Conflicting claim",
                    "status": "CONFLICTING",
                    "current_truth": None,
                    "sources": [
                        {"url": "https://example.com/a", "source_date": "2026-04-12"},
                        {"url": "https://example.com/b", "source_date": "2026-04-12"},
                    ],
                    "conflict_summary": "Sources disagree.",
                    "unverified_reason": None,
                },
                {
                    "id": "C3",
                    "claim": "Unverified claim",
                    "status": "UNVERIFIED",
                    "current_truth": None,
                    "sources": [],
                    "conflict_summary": None,
                    "unverified_reason": "No authoritative source found.",
                },
            ],
        }

    def test_fact_ledger_parses_valid_response(self):
        import v1_pipeline as p

        payload = self._ledger_payload()
        with patch.object(p, "FACT_LEDGER_DIR", self.ledger_dir), \
             patch.object(p, "module_key_from_path", return_value=self.module_key), \
             patch.object(p, "dispatch_auto", return_value=(True, json.dumps(payload))):
            result = p.step_fact_ledger(self.module_path, topic_hint="Topic", refresh=True)

        self.assertIsNotNone(result)
        statuses = {c["status"] for c in result["claims"]}
        self.assertEqual(statuses, {"SUPPORTED", "CONFLICTING", "UNVERIFIED"})

    def test_fact_ledger_validates_required_fields(self):
        import v1_pipeline as p

        bad_payload = {"as_of_date": "2026-04-12", "topic": "Missing claims"}
        with patch.object(p, "FACT_LEDGER_DIR", self.ledger_dir), \
             patch.object(p, "module_key_from_path", return_value=self.module_key), \
             patch.object(p, "dispatch_auto", return_value=(True, json.dumps(bad_payload))):
            result = p.step_fact_ledger(self.module_path, topic_hint="Topic", refresh=True)

        self.assertIsNone(result)

    def test_fact_ledger_caches_to_disk(self):
        import v1_pipeline as p

        payload = self._ledger_payload(marker="A")
        cache_path = self.ledger_dir / "test__module-0.1-test.json"
        with patch.object(p, "FACT_LEDGER_DIR", self.ledger_dir), \
             patch.object(p, "module_key_from_path", return_value=self.module_key), \
             patch.object(p, "dispatch_auto", return_value=(True, json.dumps(payload))):
            first = p.step_fact_ledger(self.module_path, topic_hint="Topic")

        self.assertIsNotNone(first)
        self.assertTrue(cache_path.exists())

        with patch.object(p, "FACT_LEDGER_DIR", self.ledger_dir), \
             patch.object(p, "module_key_from_path", return_value=self.module_key), \
             patch.object(p, "dispatch_auto", side_effect=AssertionError("dispatch should not run on cache hit")):
            second = p.step_fact_ledger(self.module_path, topic_hint="Topic")

        self.assertEqual(first["topic"], second["topic"])

    def test_fact_ledger_cache_expires_after_7_days(self):
        import v1_pipeline as p

        first_payload = self._ledger_payload(marker="A")
        second_payload = self._ledger_payload(marker="B")
        cache_path = self.ledger_dir / "test__module-0.1-test.json"

        with patch.object(p, "FACT_LEDGER_DIR", self.ledger_dir), \
             patch.object(p, "module_key_from_path", return_value=self.module_key), \
             patch.object(p, "dispatch_auto", return_value=(True, json.dumps(first_payload))):
            p.step_fact_ledger(self.module_path, topic_hint="Topic")

        old_ts = (datetime.now(UTC) - timedelta(days=8)).timestamp()
        os.utime(cache_path, (old_ts, old_ts))

        with patch.object(p, "FACT_LEDGER_DIR", self.ledger_dir), \
             patch.object(p, "module_key_from_path", return_value=self.module_key), \
             patch.object(p, "dispatch_auto", return_value=(True, json.dumps(second_payload))) as mock_dispatch:
            refreshed = p.step_fact_ledger(self.module_path, topic_hint="Topic")

        self.assertEqual(mock_dispatch.call_count, 1)
        self.assertEqual(refreshed["topic"], "Test Module B")

    def test_fact_ledger_refresh_busts_cache(self):
        import v1_pipeline as p

        first_payload = self._ledger_payload(marker="A")
        second_payload = self._ledger_payload(marker="B")

        with patch.object(p, "FACT_LEDGER_DIR", self.ledger_dir), \
             patch.object(p, "module_key_from_path", return_value=self.module_key), \
             patch.object(p, "dispatch_auto", return_value=(True, json.dumps(first_payload))):
            p.step_fact_ledger(self.module_path, topic_hint="Topic")

        with patch.object(p, "FACT_LEDGER_DIR", self.ledger_dir), \
             patch.object(p, "module_key_from_path", return_value=self.module_key), \
             patch.object(p, "dispatch_auto", return_value=(True, json.dumps(second_payload))) as mock_dispatch:
            refreshed = p.step_fact_ledger(self.module_path, topic_hint="Topic", refresh=True)

        self.assertEqual(mock_dispatch.call_count, 1)
        self.assertEqual(refreshed["topic"], "Test Module B")


class TestEnsureFactLedger(unittest.TestCase):
    """Test ensure_fact_ledger cache precedence and refresh behavior."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.repo_root = Path(self.tmpdir)
        self.content_root = self.repo_root / "src" / "content" / "docs"
        self.content_root.mkdir(parents=True, exist_ok=True)
        self.module_path = self.content_root / "test" / "module-0.1-test.md"
        self.module_path.parent.mkdir(parents=True, exist_ok=True)
        self.module_path.write_text("---\ntitle: Test Module\n---\n\nBody")
        self.ledger_dir = self.repo_root / ".pipeline" / "fact-ledgers"
        self.module_key = "test/module-0.1-test"

    def tearDown(self):
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def _payload(self, marker: str = "5") -> dict:
        return {
            "as_of_date": "2026-04-12",
            "topic": f"Test {marker}",
            "claims": [
                {
                    "id": "C1",
                    "claim": f"Kubernetes stable is v1.3{marker}",
                    "status": "SUPPORTED",
                    "current_truth": f"Kubernetes stable is v1.3{marker}",
                    "sources": [{"url": "https://kubernetes.io/releases/", "source_date": "2026-04-12"}],
                    "conflict_summary": None,
                    "unverified_reason": None,
                }
            ],
        }

    def _cache_path(self) -> Path:
        return self.ledger_dir / "test__module-0.1-test.json"

    def test_no_file_runs_generator(self):
        import v1_pipeline as p

        ms = {}
        payload = self._payload("5")
        with patch.object(p, "FACT_LEDGER_DIR", self.ledger_dir), \
             patch.object(p, "module_key_from_path", return_value=self.module_key), \
             patch.object(p, "step_fact_ledger", return_value=payload) as mock_step:
            result = p.ensure_fact_ledger(self.module_path, ms)

        self.assertEqual(mock_step.call_count, 1)
        self.assertEqual(result, payload)
        self.assertEqual(ms.get("fact_ledger"), payload)
        self.assertIn("fact_ledger_generated_at", ms)

    def test_fresh_file_returns_cached(self):
        import v1_pipeline as p

        payload = self._payload("5")
        self.ledger_dir.mkdir(parents=True, exist_ok=True)
        self._cache_path().write_text(json.dumps(payload))
        ms = {}
        with patch.object(p, "FACT_LEDGER_DIR", self.ledger_dir), \
             patch.object(p, "module_key_from_path", return_value=self.module_key), \
             patch.object(p, "step_fact_ledger", side_effect=AssertionError("should not regenerate")):
            result = p.ensure_fact_ledger(self.module_path, ms)

        self.assertEqual(result, payload)
        self.assertEqual(ms.get("fact_ledger"), payload)
        self.assertNotIn("fact_ledger_generated_at", ms)

    def test_stale_file_regenerates(self):
        import v1_pipeline as p

        stale_payload = self._payload("5")
        fresh_payload = self._payload("6")
        self.ledger_dir.mkdir(parents=True, exist_ok=True)
        self._cache_path().write_text(json.dumps(stale_payload))
        old_ts = (datetime.now(UTC) - timedelta(days=8)).timestamp()
        os.utime(self._cache_path(), (old_ts, old_ts))

        ms = {}
        with patch.object(p, "FACT_LEDGER_DIR", self.ledger_dir), \
             patch.object(p, "module_key_from_path", return_value=self.module_key), \
             patch.object(p, "step_fact_ledger", return_value=fresh_payload) as mock_step:
            result = p.ensure_fact_ledger(self.module_path, ms)

        self.assertEqual(mock_step.call_count, 1)
        self.assertEqual(result, fresh_payload)

    def test_corrupt_file_regenerates(self):
        import v1_pipeline as p

        self.ledger_dir.mkdir(parents=True, exist_ok=True)
        self._cache_path().write_text("{not-json")
        payload = self._payload("7")
        ms = {}
        with patch.object(p, "FACT_LEDGER_DIR", self.ledger_dir), \
             patch.object(p, "module_key_from_path", return_value=self.module_key), \
             patch.object(p, "step_fact_ledger", return_value=payload) as mock_step:
            result = p.ensure_fact_ledger(self.module_path, ms)

        self.assertEqual(mock_step.call_count, 1)
        self.assertEqual(result, payload)

    def test_file_cache_authoritative(self):
        import v1_pipeline as p

        ms = {
            "fact_ledger": self._payload("5"),
            "fact_ledger_generated_at": datetime.now(UTC).isoformat(),
        }
        regenerated = self._payload("8")
        with patch.object(p, "FACT_LEDGER_DIR", self.ledger_dir), \
             patch.object(p, "module_key_from_path", return_value=self.module_key), \
             patch.object(p, "step_fact_ledger", return_value=regenerated) as mock_step:
            result = p.ensure_fact_ledger(self.module_path, ms)

        self.assertEqual(mock_step.call_count, 1, "Missing file must force regeneration even with fresh state metadata")
        self.assertEqual(result, regenerated)
        self.assertEqual(ms.get("fact_ledger"), regenerated)

    def test_refresh_bypasses_cache(self):
        import v1_pipeline as p

        cached = self._payload("5")
        refreshed = self._payload("9")
        self.ledger_dir.mkdir(parents=True, exist_ok=True)
        self._cache_path().write_text(json.dumps(cached))
        ms = {}
        with patch.object(p, "FACT_LEDGER_DIR", self.ledger_dir), \
             patch.object(p, "module_key_from_path", return_value=self.module_key), \
             patch.object(p, "step_fact_ledger", return_value=refreshed) as mock_step:
            result = p.ensure_fact_ledger(self.module_path, ms, refresh=True)

        self.assertEqual(mock_step.call_count, 1)
        self.assertEqual(result, refreshed)


class TestContentAwareFactLedger(unittest.TestCase):
    """Test content-aware fact ledger and merge logic."""

    def test_merge_prefers_content_aware_claims(self):
        """Content-aware claims take precedence, topic claims fill gaps."""
        import v1_pipeline as p

        topic_ledger = {
            "as_of_date": "2026-04-12",
            "topic": "Test",
            "claims": [
                {"id": "C1", "claim": "topic claim A", "status": "SUPPORTED"},
                {"id": "C2", "claim": "topic claim B", "status": "SUPPORTED"},
            ],
        }
        content_ledger = {
            "as_of_date": "2026-04-12",
            "topic": "Test",
            "content_aware": True,
            "claims": [
                {"id": "C1", "claim": "topic claim A", "status": "SUPPORTED"},
                {"id": "C2", "claim": "new content claim", "status": "UNVERIFIED"},
            ],
        }

        merged = p._merge_fact_ledgers(topic_ledger, content_ledger)
        self.assertTrue(merged["content_aware"])
        # Content ledger's 2 claims + topic's "topic claim B" (non-overlapping)
        self.assertEqual(len(merged["claims"]), 3)
        # IDs renumbered
        self.assertEqual(merged["claims"][0]["id"], "C1")
        self.assertEqual(merged["claims"][2]["id"], "C3")
        # topic claim B was added from topic ledger
        claim_texts = {c["claim"] for c in merged["claims"]}
        self.assertIn("topic claim B", claim_texts)

    def test_merge_is_pure_and_idempotent(self):
        import v1_pipeline as p

        topic = {
            "as_of_date": "2026-04-12",
            "topic": "Test",
            "claims": [
                {"id": "C7", "claim": "topic claim A", "status": "SUPPORTED"},
                {"id": "C8", "claim": "topic claim B", "status": "SUPPORTED"},
            ],
        }
        content = {
            "as_of_date": "2026-04-12",
            "topic": "Test",
            "content_aware": True,
            "claims": [
                {"id": "C9", "claim": "topic claim A", "status": "SUPPORTED"},
                {"id": "C10", "claim": "new content claim", "status": "UNVERIFIED"},
            ],
        }
        topic_before = copy.deepcopy(topic)
        content_before = copy.deepcopy(content)

        merged_once = p._merge_fact_ledgers(topic, content)
        merged_twice = p._merge_fact_ledgers(topic, content)

        self.assertEqual(topic, topic_before)
        self.assertEqual(content, content_before)
        self.assertEqual(merged_once, merged_twice)
        self.assertIsNot(merged_once, topic)
        self.assertIsNot(merged_once, content)

    def test_merge_returns_topic_when_content_is_none(self):
        import v1_pipeline as p
        topic = {"claims": [{"id": "C1", "claim": "x"}]}
        merged = p._merge_fact_ledgers(topic, None)
        self.assertEqual(merged, topic)
        self.assertIsNot(merged, topic)
        self.assertIsNot(merged["claims"], topic["claims"])

    def test_merge_returns_content_when_topic_is_none(self):
        import v1_pipeline as p
        content = {"claims": [{"id": "C1", "claim": "x"}], "content_aware": True}
        merged = p._merge_fact_ledgers(None, content)
        self.assertEqual(merged, content)
        self.assertIsNot(merged, content)
        self.assertIsNot(merged["claims"], content["claims"])

    def test_content_aware_step_caches_with_suffix(self):
        """Content-aware ledger uses '-content' cache suffix."""
        import v1_pipeline as p

        tmpdir = tempfile.mkdtemp()
        try:
            ledger_dir = Path(tmpdir) / ".pipeline" / "fact-ledgers"
            content_root = Path(tmpdir) / "src" / "content" / "docs"
            module_path = content_root / "test" / "module-0.1-test.md"
            module_path.parent.mkdir(parents=True, exist_ok=True)
            module_path.write_text("---\ntitle: Test\n---\n\nBody")

            ledger_result = {
                "as_of_date": "2026-04-12",
                "topic": "Test",
                "content_aware": True,
                "claims": [{"id": "C1", "claim": "tested", "status": "SUPPORTED"}],
            }

            with patch.object(p, "FACT_LEDGER_DIR", ledger_dir), \
                 patch.object(p, "CONTENT_ROOT", content_root), \
                 patch.object(p, "module_key_from_path", return_value="test/module-0.1-test"), \
                 patch.object(p, "dispatch_auto", return_value=(True, json.dumps(ledger_result))):
                result = p.step_content_aware_fact_ledger(module_path, "content")

            self.assertIsNotNone(result)
            self.assertTrue(result["content_aware"])
            cache_path = ledger_dir / "test__module-0.1-test-content.json"
            self.assertTrue(cache_path.exists())
        finally:
            shutil.rmtree(tmpdir, ignore_errors=True)

    def test_content_aware_step_covers_late_sections_beyond_40k(self):
        import v1_pipeline as p

        tmpdir = tempfile.mkdtemp()
        try:
            ledger_dir = Path(tmpdir) / ".pipeline" / "fact-ledgers"
            content_root = Path(tmpdir) / "src" / "content" / "docs"
            module_path = content_root / "test" / "module-0.1-test.md"
            module_path.parent.mkdir(parents=True, exist_ok=True)
            module_path.write_text("---\ntitle: Test\n---\n\nBody")

            early_marker = "Kubernetes current stable is v1.35."
            late_marker = "Helm current stable is v3.19.0."
            filler_block = ("Padding text without factual claims.\n" * 1400)
            content = (
                "---\ntitle: Test\n---\n\n"
                "## Early Facts\n"
                f"{early_marker}\n\n"
                f"{filler_block}\n"
                "## Middle Narrative\n"
                f"{filler_block}\n"
                "## Late Facts\n"
                f"{late_marker}\n"
            )
            self.assertGreater(len(content), p.CONTENT_AWARE_FACT_LEDGER_MAX_CHARS)

            prompts: list[str] = []

            def fake_dispatch(prompt: str, model: str, timeout: int):
                prompts.append(prompt)
                claims = []
                if early_marker in prompt:
                    claims.append(
                        {
                            "id": "C1",
                            "claim": early_marker,
                            "status": "SUPPORTED",
                            "current_truth": early_marker,
                            "sources": [{"url": "https://kubernetes.io/releases/", "source_date": "2026-04-12"}],
                            "conflict_summary": None,
                            "unverified_reason": None,
                        }
                    )
                if late_marker in prompt:
                    claims.append(
                        {
                            "id": "C1",
                            "claim": late_marker,
                            "status": "SUPPORTED",
                            "current_truth": late_marker,
                            "sources": [{"url": "https://helm.sh/docs/faq/releases/", "source_date": "2026-04-12"}],
                            "conflict_summary": None,
                            "unverified_reason": None,
                        }
                    )
                payload = {
                    "as_of_date": "2026-04-12",
                    "topic": "Test",
                    "content_aware": True,
                    "claims": claims,
                }
                return True, json.dumps(payload)

            with patch.object(p, "FACT_LEDGER_DIR", ledger_dir), \
                 patch.object(p, "CONTENT_ROOT", content_root), \
                 patch.object(p, "module_key_from_path", return_value="test/module-0.1-test"), \
                 patch.object(p, "_extract_topic_from_module", return_value="Test"), \
                 patch.object(p, "dispatch_auto", side_effect=fake_dispatch):
                result = p.step_content_aware_fact_ledger(module_path, content)

            self.assertIsNotNone(result)
            self.assertTrue(result["content_aware"])
            self.assertGreaterEqual(len(prompts), 2)
            self.assertTrue(any(late_marker in prompt for prompt in prompts))
            claim_texts = {claim["claim"] for claim in result["claims"]}
            self.assertIn(early_marker, claim_texts)
            self.assertIn(late_marker, claim_texts)
        finally:
            shutil.rmtree(tmpdir, ignore_errors=True)


class TestCliRefreshFactLedgerFlag(unittest.TestCase):
    """CLI commands should propagate --refresh-fact-ledger into run_module."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.content_root = Path(self.tmpdir) / "src" / "content" / "docs"
        self.section = "prerequisites/zero-to-terminal"
        self.section_dir = self.content_root / self.section
        self.section_dir.mkdir(parents=True, exist_ok=True)
        self.module_path = self.section_dir / "module-0.1-test.md"
        self.module_path.write_text(GOOD_MODULE)

    def tearDown(self):
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    @patch("sys.exit", side_effect=SystemExit)
    def test_cmd_run_propagates_flag(self, _mock_exit):
        import v1_pipeline as p

        args = Namespace(
            module=str(self.module_path),
            write_model=None,
            review_model=None,
            dry_run=False,
            refresh_fact_ledger=True,
        )
        with patch.object(p, "load_state", return_value={"modules": {}}), \
             patch.object(p, "run_module", return_value=True) as mock_run, \
             self.assertRaises(SystemExit):
            p.cmd_run(args)

        self.assertTrue(mock_run.call_args.kwargs.get("refresh_fact_ledger"))

    @patch("sys.exit", side_effect=SystemExit)
    def test_cmd_run_section_propagates_flag(self, _mock_exit):
        import v1_pipeline as p

        args = Namespace(
            section=self.section,
            workers=1,
            track=None,
            skip_gaps=False,
            dry_run=False,
            write_model=None,
            review_model=None,
            refresh_fact_ledger=True,
        )
        with patch.object(p, "CONTENT_ROOT", self.content_root), \
             patch.object(p.gaps, "run_track_gap_analysis", return_value=[]), \
             patch.object(p, "load_state", return_value={"modules": {}}), \
             patch.object(p, "run_module", return_value=True) as mock_run, \
             self.assertRaises(SystemExit):
            p.cmd_run_section(args)

        self.assertTrue(mock_run.call_args.kwargs.get("refresh_fact_ledger"))

    def test_cmd_resume_propagates_flag(self):
        import v1_pipeline as p

        args = Namespace(
            write_model=None,
            review_model=None,
            refresh_fact_ledger=True,
        )
        state = {
            "modules": {
                "test/module-0.1-test": {"phase": "review"}
            }
        }
        with patch.object(p, "load_state", return_value=state), \
             patch.object(p, "find_module_path", return_value=self.module_path), \
             patch.object(p, "run_module", return_value=True) as mock_run:
            p.cmd_resume(args)

        self.assertTrue(mock_run.call_args.kwargs.get("refresh_fact_ledger"))

    def test_cmd_e2e_propagates_flag(self):
        import v1_pipeline as p

        args = Namespace(
            sections=[self.section],
            verbose=True,
            no_translate=True,
            write_model=None,
            review_model=None,
            refresh_fact_ledger=True,
        )
        with patch.object(p, "CONTENT_ROOT", self.content_root), \
             patch.object(p, "load_state", return_value={"modules": {}}), \
             patch.object(p, "run_module", return_value=True) as mock_run:
            p.cmd_e2e(args)

        self.assertTrue(mock_run.call_args.kwargs.get("refresh_fact_ledger"))


class TestStepCheckIntegrity(unittest.TestCase):
    """Test tier-1 deterministic integrity checks."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.link_cache = Path(self.tmpdir) / "link-cache.json"
        self.state_file = Path(self.tmpdir) / "state.yaml"
        self.module_path = Path(self.tmpdir) / "module-0.1-test.md"
        self.module_path.write_text(GOOD_MODULE)

    def tearDown(self):
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def _supported_ledger(self, claim_id: str, statement: str) -> dict:
        return {
            "claims": [
                {
                    "id": claim_id,
                    "claim": statement,
                    "status": "SUPPORTED",
                    "current_truth": statement,
                    "sources": [],
                    "conflict_summary": None,
                    "unverified_reason": None,
                }
            ]
        }

    def test_runs_before_review_on_fail(self):
        import v1_pipeline as p

        review_calls = {"count": 0}

        def fake_review(*_args, **_kwargs):
            review_calls["count"] += 1
            return {
                "verdict": "APPROVE",
                "checks": [{"id": cid, "passed": True} for cid in p.CHECK_IDS],
                "edits": [],
                "feedback": "",
            }

        state = {"modules": {}}
        with patch.object(p, "STATE_FILE", self.state_file), \
             patch.object(p, "CONTENT_ROOT", Path(self.tmpdir)), \
             patch.object(p, "save_state"), \
             patch.object(p, "module_key_from_path", return_value="test/module-0.1-test"), \
             patch.object(p, "ensure_fact_ledger", return_value=sample_fact_ledger()), \
             patch.object(p, "step_content_aware_fact_ledger", return_value=None), \
             patch.object(p, "step_write", return_value=GOOD_MODULE), \
             patch.object(p, "step_check_integrity", return_value=(False, ["LINK_DEAD: https://dead.example (404)"])), \
             patch.object(p, "step_review", side_effect=fake_review), \
             patch("subprocess.run"):
            ok = p.run_module(self.module_path, state, max_retries=0)

        self.assertFalse(ok)
        self.assertEqual(review_calls["count"], 0, "Integrity failure must short-circuit structural review")

    def test_link_health_all_resolve(self):
        import v1_pipeline as p

        content = (
            "Kubernetes current stable is v1.35. "
            "See https://example.com/a and https://example.com/b"
        )
        with patch.object(p, "LINK_CACHE_FILE", self.link_cache), \
             patch.object(p, "_probe_url", return_value=200):
            passed, messages = p.step_check_integrity(content, sample_fact_ledger())

        self.assertTrue(passed)
        self.assertFalse(any(m.startswith("LINK_DEAD") for m in messages))

    def test_link_health_dead_url_fails(self):
        import v1_pipeline as p

        content = (
            "Kubernetes current stable is v1.35. "
            "Good https://example.com/ok bad https://example.com/dead"
        )

        def fake_status(url):
            return 404 if "dead" in url else 200

        with patch.object(p, "LINK_CACHE_FILE", self.link_cache), \
             patch.object(p, "_probe_url", side_effect=fake_status):
            passed, messages = p.step_check_integrity(content, sample_fact_ledger())

        self.assertTrue(passed, "LINK_DEAD is now a warning, not a hard error")
        self.assertTrue(any("LINK_DEAD: https://example.com/dead (404)" in m for m in messages))

    def test_yaml_lint_valid_passes(self):
        import v1_pipeline as p

        content = (
            "Kubernetes current stable is v1.35.\n"
            "```yaml\napiVersion: v1\nkind: Pod\nmetadata:\n  name: demo\n```"
        )
        with patch.object(p, "LINK_CACHE_FILE", self.link_cache):
            passed, messages = p.step_check_integrity(content, sample_fact_ledger())

        self.assertTrue(passed)
        self.assertFalse(any(m.startswith("INVALID_YAML") for m in messages))

    def test_yaml_lint_invalid_fails(self):
        import v1_pipeline as p

        content = (
            "Kubernetes current stable is v1.35.\n"
            "```yaml\napiVersion: v1\nkind Pod\nmetadata:\n  name: demo\n```"
        )
        with patch.object(p, "LINK_CACHE_FILE", self.link_cache):
            passed, messages = p.step_check_integrity(content, sample_fact_ledger())

        self.assertFalse(passed)
        self.assertTrue(any(m.startswith("INVALID_YAML") for m in messages))

    def test_version_consistency_warns_only(self):
        import v1_pipeline as p

        ledger = {
            "claims": [
                {
                    "id": "C1",
                    "claim": "Controller behavior changed in v1.35.",
                    "status": "SUPPORTED",
                    "current_truth": "Controller behavior changed in v1.35.",
                    "sources": [],
                    "conflict_summary": None,
                    "unverified_reason": None,
                },
                {
                    "id": "C2",
                    "claim": "Scheduler behavior changed in v1.36.",
                    "status": "SUPPORTED",
                    "current_truth": "Scheduler behavior changed in v1.36.",
                    "sources": [],
                    "conflict_summary": None,
                    "unverified_reason": None,
                },
            ]
        }
        content = "Controller behavior changed in v1.35. Scheduler behavior changed in v1.36."
        with patch.object(p, "LINK_CACHE_FILE", self.link_cache):
            passed, messages = p.step_check_integrity(content, ledger)

        self.assertTrue(passed)
        self.assertTrue(any(m.startswith("VERSION_MISMATCH_WARNING") for m in messages))

    def test_version_floor_1_35(self):
        import v1_pipeline as p

        with patch.object(p, "LINK_CACHE_FILE", self.link_cache):
            passed_134, messages_134 = p.step_check_integrity(
                "Kubernetes current stable is v1.34.",
                self._supported_ledger("C34", "Kubernetes current stable is v1.34."),
            )
            passed_135, _ = p.step_check_integrity(
                "Kubernetes current stable is v1.35.",
                self._supported_ledger("C35", "Kubernetes current stable is v1.35."),
            )
            passed_136, _ = p.step_check_integrity(
                "Kubernetes current stable is v1.36.",
                self._supported_ledger("C36", "Kubernetes current stable is v1.36."),
            )

        self.assertTrue(passed_134, "STALE_K8S_VERSION is now a warning — v1.34 should not fail")
        self.assertTrue(any("STALE_K8S_VERSION: v1.34" in m for m in messages_134))
        self.assertTrue(passed_135)
        self.assertTrue(passed_136)

    def test_evidence_mapping_unhedged_conflict_fails(self):
        import v1_pipeline as p

        ledger = {
            "claims": [
                {
                    "id": "C8",
                    "claim": "Kubernetes current stable is v1.35",
                    "status": "SUPPORTED",
                    "current_truth": "Kubernetes current stable is v1.35",
                    "sources": [],
                    "conflict_summary": None,
                    "unverified_reason": None,
                },
                {
                    "id": "C9",
                    "claim": "Kubernetes current stable is v1.35",
                    "status": "CONFLICTING",
                    "current_truth": "Kubernetes current stable is v1.35",
                    "sources": [],
                    "conflict_summary": "Disagreement",
                    "unverified_reason": None,
                }
            ]
        }
        content = "Kubernetes current stable is v1.35."
        with patch.object(p, "LINK_CACHE_FILE", self.link_cache):
            passed, messages = p.step_check_integrity(content, ledger)

        self.assertFalse(passed)
        self.assertTrue(any("UNHEDGED_CONFLICT: claim C9" in m for m in messages))

    def test_evidence_mapping_hedged_conflict_passes(self):
        import v1_pipeline as p

        ledger = {
            "claims": [
                {
                    "id": "C11",
                    "claim": "Kubernetes current stable is v1.35",
                    "status": "SUPPORTED",
                    "current_truth": "Kubernetes current stable is v1.35",
                    "sources": [],
                    "conflict_summary": None,
                    "unverified_reason": None,
                },
                {
                    "id": "C10",
                    "claim": "Kubernetes current stable is v1.35",
                    "status": "CONFLICTING",
                    "current_truth": "Kubernetes current stable is v1.35",
                    "sources": [],
                    "conflict_summary": "Disagreement",
                    "unverified_reason": None,
                }
            ]
        }
        content = (
            "According to upstream docs as of 2026-04-12, "
            "Kubernetes current stable is v1.35."
        )
        with patch.object(p, "LINK_CACHE_FILE", self.link_cache):
            passed, messages = p.step_check_integrity(content, ledger)

        self.assertTrue(passed)
        self.assertFalse(any(m.startswith("UNHEDGED_CONFLICT") for m in messages))

    def test_reverse_evidence_mapping_catches_unmapped_claim(self):
        import v1_pipeline as p

        ledger = self._supported_ledger("C1", "Kubernetes current stable is v1.35.")
        content = (
            "Kubernetes current stable is v1.35. "
            "Helm v3.17.0 introduces imaginaryKey.priorityClass."
        )
        with patch.object(p, "LINK_CACHE_FILE", self.link_cache):
            passed, messages = p.step_check_integrity(content, ledger)

        self.assertTrue(passed, "UNMAPPED_CLAIM is now a warning, not a hard error")
        self.assertTrue(any(m.startswith("UNMAPPED_CLAIM: Helm v3.17.0") for m in messages))

    def test_reverse_evidence_mapping_ignores_fenced_yaml_examples(self):
        """Regression for round-2 gpt-5.4 finding: standard K8s YAML examples
        inside ```yaml fences contain API tokens like `apps/v1` that are
        syntax, not claims. They must not be forced to appear in the fact
        ledger, or every module with a code example fails tier-1.
        """
        import v1_pipeline as p

        ledger = self._supported_ledger("C1", "Kubernetes current stable is v1.35.")
        content = (
            "Kubernetes current stable is v1.35.\n"
            "\n"
            "```yaml\n"
            "apiVersion: apps/v1\n"
            "kind: Deployment\n"
            "metadata:\n"
            "  name: demo\n"
            "spec:\n"
            "  selector:\n"
            "    matchLabels:\n"
            "      app: demo\n"
            "  template:\n"
            "    metadata:\n"
            "      labels:\n"
            "        app: demo\n"
            "    spec:\n"
            "      containers:\n"
            "      - name: app\n"
            "        image: busybox:1.36\n"
            "```\n"
            "\n"
            "```bash\n"
            "kubectl apply -f deploy.yaml\n"
            "```\n"
        )
        with patch.object(p, "LINK_CACHE_FILE", self.link_cache):
            passed, messages = p.step_check_integrity(content, ledger)

        self.assertTrue(passed, f"integrity should pass; got messages: {messages}")
        self.assertFalse(
            any(m.startswith("UNMAPPED_CLAIM: apps/v1") for m in messages),
            "apps/v1 inside a ```yaml fence is syntax, not a claim",
        )


class TestRunModuleSplitReviewer(_CalibrationIsolatedCase):
    """Integration tests for split-reviewer routing in run_module."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.state_file = Path(self.tmpdir) / "state.yaml"
        self.module_path = Path(self.tmpdir) / "module-0.1-test.md"
        self.module_path.write_text(GOOD_MODULE)

    def tearDown(self):
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_pending_module_runs_fact_ledger_then_writes(self):
        import v1_pipeline as p

        events: list[str] = []
        review_ok = {
            "verdict": "APPROVE",
            "checks": [{"id": cid, "passed": True} for cid in p.CHECK_IDS],
            "edits": [],
            "feedback": "",
        }

        def fake_fact(*args, **kwargs):
            events.append("ledger")
            return sample_fact_ledger()

        def fake_write(*args, **kwargs):
            events.append("write")
            return GOOD_MODULE

        def fake_review(*args, **kwargs):
            events.append("review")
            return review_ok

        state = {"modules": {}}
        with patch.object(p, "STATE_FILE", self.state_file), \
             patch.object(p, "CONTENT_ROOT", Path(self.tmpdir)), \
             patch.object(p, "save_state"), \
             patch.object(p, "module_key_from_path", return_value="test/module-0.1-test"), \
             patch.object(p, "ensure_fact_ledger", side_effect=fake_fact), \
             patch.object(p, "step_content_aware_fact_ledger", return_value=None), \
             patch.object(p, "ensure_knowledge_card", return_value="card"), \
             patch.object(p, "step_write", side_effect=fake_write), \
             patch.object(p, "step_review", side_effect=fake_review), \
             patch.object(p, "step_check_integrity", return_value=(True, [])), \
             patch.object(p, "step_check", return_value=(True, [])), \
             patch("subprocess.run"):
            p.run_module(self.module_path, state)

        self.assertEqual(events[:3], ["ledger", "write", "review"])

    def test_topic_conflicts_not_in_final_draft_do_not_block(self):
        import v1_pipeline as p

        topic_conflict_ledger = {
            "as_of_date": "2026-04-12",
            "topic": "Conflict",
            "claims": [
                {
                    "id": f"C{i}",
                    "claim": f"Hypothetical claim {i}",
                    "status": "CONFLICTING",
                }
                for i in range(1, 6)
            ],
        }
        review_ok = {
            "verdict": "APPROVE",
            "checks": [{"id": cid, "passed": True} for cid in p.CHECK_IDS],
            "edits": [],
            "feedback": "",
        }
        content_ledger = sample_fact_ledger() | {"content_aware": True}
        state = {"modules": {}}
        with patch.object(p, "STATE_FILE", self.state_file), \
             patch.object(p, "CONTENT_ROOT", Path(self.tmpdir)), \
             patch.object(p, "save_state"), \
             patch.object(p, "module_key_from_path", return_value="test/module-0.1-test"), \
             patch.object(p, "ensure_fact_ledger", return_value=topic_conflict_ledger), \
             patch.object(p, "step_content_aware_fact_ledger", return_value=content_ledger), \
             patch.object(p, "ensure_knowledge_card", return_value="card"), \
             patch.object(p, "step_write", return_value=GOOD_MODULE), \
             patch.object(p, "step_review", return_value=review_ok), \
             patch.object(p, "step_check_integrity", return_value=(True, [])), \
             patch.object(p, "step_check", return_value=(True, [])), \
             patch("subprocess.run"):
            ok = p.run_module(self.module_path, state)

        self.assertTrue(ok)
        ms = state["modules"]["test/module-0.1-test"]
        self.assertEqual(ms.get("phase"), "done")
        self.assertFalse(any("DATA_CONFLICT" in e for e in ms.get("errors", [])))

    def test_data_conflict_triage_exit(self):
        import v1_pipeline as p

        conflict_ledger = {
            "as_of_date": "2026-04-12",
            "topic": "Conflict",
            "content_aware": True,
            "claims": [
                {
                    "id": f"C{i}",
                    "claim": f"Conflicting drafted claim {i}",
                    "status": "CONFLICTING",
                }
                for i in range(1, 6)
            ],
        }
        state = {"modules": {}}
        with patch.object(p, "STATE_FILE", self.state_file), \
             patch.object(p, "CONTENT_ROOT", Path(self.tmpdir)), \
             patch.object(p, "save_state"), \
             patch.object(p, "module_key_from_path", return_value="test/module-0.1-test"), \
             patch.object(p, "ensure_fact_ledger", return_value=sample_fact_ledger()), \
             patch.object(p, "step_content_aware_fact_ledger", return_value=conflict_ledger), \
             patch.object(p, "ensure_knowledge_card", return_value="card"), \
             patch.object(p, "step_write", return_value=GOOD_MODULE), \
             patch("subprocess.run"):
            ok = p.run_module(self.module_path, state)

        self.assertFalse(ok)
        ms = state["modules"]["test/module-0.1-test"]
        self.assertEqual(ms.get("phase"), "data_conflict")
        self.assertTrue(any("DATA_CONFLICT" in e for e in ms.get("errors", [])))

    def test_review_uses_gemini_not_codex(self):
        import v1_pipeline as p

        review_models = []
        state = {"modules": {}}
        review_ok = {
            "verdict": "APPROVE",
            "checks": [{"id": cid, "passed": True} for cid in p.CHECK_IDS],
            "edits": [],
            "feedback": "",
        }

        def fake_review(_module_path, _improved, model=None, fact_ledger=None):
            review_models.append(model)
            return review_ok

        with patch.object(p, "STATE_FILE", self.state_file), \
             patch.object(p, "CONTENT_ROOT", Path(self.tmpdir)), \
             patch.object(p, "save_state"), \
             patch.object(p, "module_key_from_path", return_value="test/module-0.1-test"), \
             patch.object(p, "ensure_fact_ledger", return_value=sample_fact_ledger()), \
             patch.object(p, "step_content_aware_fact_ledger", return_value=None), \
             patch.object(p, "ensure_knowledge_card", return_value="card"), \
             patch.object(p, "step_write", return_value=GOOD_MODULE), \
             patch.object(p, "step_review", side_effect=fake_review), \
             patch.object(p, "step_check_integrity", return_value=(True, [])), \
             patch.object(p, "step_check", return_value=(True, [])), \
             patch("subprocess.run"):
            p.run_module(self.module_path, state)

        self.assertTrue(review_models)
        self.assertEqual(review_models[0], p.MODELS["review"])
        self.assertTrue(review_models[0].startswith("gemini"))

    def test_second_reviewer_sampling_writes_jsonl_and_flags_drift(self):
        import v1_pipeline as p

        sample_file = Path(self.tmpdir) / ".cache" / "review_samples.jsonl"
        drift_file = Path(self.tmpdir) / ".cache" / "reviewer_drift_flagged.json"
        key = "test/module-0.1-test"
        state = {"modules": {}}
        primary_review = {
            "verdict": "APPROVE",
            "checks": [{"id": cid, "passed": True} for cid in p.CHECK_IDS],
            "edits": [],
            "feedback": "",
        }
        opus_review = {
            "verdict": "REJECT",
            "checks": [
                {"id": "COV", "passed": True},
                {"id": "QUIZ", "passed": False},
                {"id": "EXAM", "passed": True},
                {"id": "DEPTH", "passed": True},
                {"id": "WHY", "passed": False},
                {"id": "PRES", "passed": True},
                {"id": "CITE", "passed": True},
            ],
            "edits": [],
            "feedback": "Two structural disagreements.",
        }

        with patch.object(p, "STATE_FILE", self.state_file), \
             patch.object(p, "CONTENT_ROOT", Path(self.tmpdir)), \
             patch.object(p, "REVIEW_SAMPLES_FILE", sample_file), \
             patch.object(p, "REVIEWER_DRIFT_FLAGGED_FILE", drift_file), \
             patch.object(p, "save_state"), \
             patch.object(p, "module_key_from_path", return_value=key), \
             patch.object(p, "ensure_fact_ledger", return_value=sample_fact_ledger()), \
             patch.object(p, "step_content_aware_fact_ledger", return_value=None), \
             patch.object(p, "ensure_knowledge_card", return_value="card"), \
             patch.object(p, "step_write", return_value=GOOD_MODULE), \
             patch.object(p, "step_review", return_value=primary_review), \
             patch.object(p.random, "random", return_value=0.0), \
             patch.object(p, "dispatch_claude", return_value=(True, json.dumps(opus_review))) as mock_claude, \
             patch.object(p, "step_check_integrity", return_value=(True, [])), \
             patch.object(p, "step_check", return_value=(True, [])), \
             patch.dict(os.environ, {"SECOND_REVIEWER_SAMPLE_RATE": "1.0"}, clear=False), \
             patch("subprocess.run"):
            p.run_module(self.module_path, state)

        self.assertEqual(mock_claude.call_count, 1)
        lines = sample_file.read_text().splitlines()
        self.assertIn("delta_dims", lines[0])
        record = json.loads(lines[1])
        self.assertEqual(record["module_key"], key)
        self.assertEqual(record["delta_dims"], [0, 2, 0, 0, 2, 0, 0])
        self.assertEqual(record["delta_sum"], 4)
        self.assertEqual(json.loads(drift_file.read_text()), [key])

    def test_fact_ledger_cache_hit_skips_dispatch(self):
        import v1_pipeline as p

        key = "test/module-0.1-test"
        ledger_dir = Path(self.tmpdir) / ".pipeline" / "fact-ledgers"
        ledger_dir.mkdir(parents=True, exist_ok=True)
        cache_path = ledger_dir / "test__module-0.1-test.json"
        cache_path.write_text(json.dumps(sample_fact_ledger(), indent=2))

        state = {"modules": {}}
        review_ok = {
            "verdict": "APPROVE",
            "checks": [{"id": cid, "passed": True} for cid in p.CHECK_IDS],
            "edits": [],
            "feedback": "",
        }
        with patch.object(p, "STATE_FILE", self.state_file), \
             patch.object(p, "CONTENT_ROOT", Path(self.tmpdir)), \
             patch.object(p, "FACT_LEDGER_DIR", ledger_dir), \
             patch.object(p, "save_state"), \
             patch.object(p, "module_key_from_path", return_value=key), \
             patch.object(p, "dispatch_auto", side_effect=AssertionError("dispatch_auto should not run")), \
             patch.object(p, "step_content_aware_fact_ledger", return_value=None), \
             patch.object(p, "ensure_knowledge_card", return_value="card"), \
             patch.object(p, "step_write", return_value=GOOD_MODULE), \
             patch.object(p, "step_review", return_value=review_ok), \
             patch.object(p, "step_check_integrity", return_value=(True, [])), \
             patch.object(p, "step_check", return_value=(True, [])), \
             patch("subprocess.run"):
            ok = p.run_module(self.module_path, state)

        self.assertTrue(ok)

    def test_rejected_draft_content_ledger_stays_transient_until_approve(self):
        import v1_pipeline as p

        def content_ledger(claim_text: str) -> dict:
            return {
                "as_of_date": "2026-04-18",
                "topic": "Test Module",
                "claims": [
                    {
                        "id": "C1",
                        "claim": claim_text,
                        "status": "SUPPORTED",
                        "current_truth": claim_text,
                        "sources": [{"url": "https://example.com/facts", "source_date": "2026-04-18"}],
                        "conflict_summary": None,
                        "unverified_reason": None,
                    }
                ],
            }

        review_ledgers: list[dict | None] = []
        review_sequence = [
            {
                "verdict": "REJECT",
                "checks": [
                    {"id": "LAB", "passed": False, "evidence": "minor accuracy issue", "edit_refs": [0]},
                    {"id": "COV", "passed": True},
                    {"id": "QUIZ", "passed": True},
                    {"id": "EXAM", "passed": True},
                    {"id": "DEPTH", "passed": True},
                    {"id": "WHY", "passed": True},
                    {"id": "PRES", "passed": True},
                ],
                "edits": [
                    {
                        "type": "replace",
                        "find": "## Learning Outcomes",
                        "new": "## Learning Outcomes (Revised)",
                        "reason": "revision tag",
                    }
                ],
                "feedback": "Minor accuracy fix.",
            },
            {
                "verdict": "APPROVE",
                "checks": [{"id": cid, "passed": True} for cid in p.CHECK_IDS],
                "edits": [],
                "feedback": "",
            },
        ]

        def fake_review(_module_path, _improved, model=None, fact_ledger=None):
            review_ledgers.append(fact_ledger)
            return review_sequence[len(review_ledgers) - 1]

        state = {"modules": {}}
        with patch.object(p, "STATE_FILE", self.state_file), \
             patch.object(p, "CONTENT_ROOT", Path(self.tmpdir)), \
             patch.object(p, "save_state"), \
             patch.object(p, "module_key_from_path", return_value="test/module-0.1-test"), \
             patch.object(p, "ensure_fact_ledger", return_value=sample_fact_ledger()), \
             patch.object(
                 p,
                 "step_content_aware_fact_ledger",
                 side_effect=[
                     content_ledger("Rejected draft-only claim"),
                     content_ledger("Approved draft claim"),
                 ],
             ) as mock_content_ledger, \
             patch.object(p, "ensure_knowledge_card", return_value="card"), \
             patch.object(p, "step_write", return_value=GOOD_MODULE), \
             patch.object(p, "step_review", side_effect=fake_review), \
             patch.object(p, "step_check_integrity", return_value=(True, [])), \
             patch.object(p, "step_check", return_value=(True, [])), \
             patch("subprocess.run"):
            ok = p.run_module(self.module_path, state)

        self.assertTrue(ok)
        self.assertEqual(mock_content_ledger.call_count, 2)

        first_claims = {claim.get("claim") for claim in review_ledgers[0].get("claims", [])}
        second_claims = {claim.get("claim") for claim in review_ledgers[1].get("claims", [])}
        self.assertIn("Rejected draft-only claim", first_claims)
        self.assertNotIn("Rejected draft-only claim", second_claims)
        self.assertIn("Approved draft claim", second_claims)

        persisted_claims = {
            claim.get("claim")
            for claim in state["modules"]["test/module-0.1-test"]["fact_ledger"].get("claims", [])
        }
        self.assertNotIn("Rejected draft-only claim", persisted_claims)
        self.assertIn("Approved draft claim", persisted_claims)

    def test_existing_binary_gate_tests_still_pass(self):
        suite = unittest.defaultTestLoader.loadTestsFromTestCase(TestBinaryGateIntegration)
        result = unittest.TestResult()
        suite.run(result)
        self.assertEqual(result.errors, [])
        self.assertEqual(result.failures, [])


# ---------------------------------------------------------------------------
# Test: Score calculations
# ---------------------------------------------------------------------------

class TestBinaryGatePassingLogic(unittest.TestCase):
    """Binary-gate passing logic (#223).

    The old 8-dim 1-5 rubric with sum≥33 thresholds was removed (issue
    #223 — mathematically unreachable). Passing is now: verdict == APPROVE
    AND every check passed. This class pins the new behavior."""

    def setUp(self):
        import v1_pipeline as p
        self.p = p

    def test_all_checks_pass_is_approve(self):
        """Every check passed → compute_severity returns clean."""
        checks = [{"id": cid, "passed": True} for cid in self.p.CHECK_IDS]
        self.assertEqual(self.p.compute_severity("APPROVE", checks, []), "clean")

    def test_one_check_fails_routes_via_severity(self):
        """One failing check with a clean edit → targeted, not a numeric threshold."""
        checks = [{"id": cid, "passed": True} for cid in self.p.CHECK_IDS]
        checks[0] = {"id": "LAB", "passed": False, "evidence": "bad",
                     "edit_refs": [0]}
        edits = [{"type": "replace", "find": "a", "new": "b"}]
        self.assertEqual(self.p.compute_severity("REJECT", checks, edits), "targeted")

    def test_severity_is_routing_primitive_not_score(self):
        """There is no passing number — severity is the only ship/no-ship signal."""
        # A module with every check passing is clean regardless of how
        # many edits the reviewer returned (APPROVE ignores edits, per
        # Gemini critique B).
        checks = [{"id": cid, "passed": True} for cid in self.p.CHECK_IDS]
        extra_edits = [{"type": "replace", "find": "x", "new": "y"}] * 10
        self.assertEqual(
            self.p.compute_severity("APPROVE", checks, extra_edits),
            "clean"
        )


# ---------------------------------------------------------------------------
# Test: Content safety guards
# ---------------------------------------------------------------------------

class TestSafetyGuards(unittest.TestCase):
    """Test safety mechanisms in the pipeline."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.module_path = Path(self.tmpdir) / "module-test.md"
        self.module_path.write_text(GOOD_MODULE)

    def tearDown(self):
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def _patch_key(self, p):
        return patch.object(p, "module_key_from_path", return_value="test/module-test")

    def test_thinking_leak_detection(self):
        """step_write should reject output with chain-of-thought leaks."""
        import v1_pipeline as p

        leaked_output = "CRITICAL INSTRUCTION: I'll write the markdown...\n---\ntitle: Test\n---\nContent"

        with patch.object(p, "dispatch_auto", return_value=(True, leaked_output)), \
             self._patch_key(p):
            result = p.step_write(self.module_path, "improve D1")
        self.assertIsNone(result, "Should reject output with thinking leaks")

    def test_no_frontmatter_detection(self):
        """step_write should reject output without frontmatter."""
        import v1_pipeline as p

        no_fm = "# Just a heading\n\nNo frontmatter here."

        with patch.object(p, "dispatch_auto", return_value=(True, no_fm)), \
             self._patch_key(p):
            result = p.step_write(self.module_path, "improve D1")
        self.assertIsNone(result, "Should reject output without frontmatter")

    def test_markdown_wrapper_stripped(self):
        """step_write should strip ```markdown wrapper from Gemini output."""
        import v1_pipeline as p

        wrapped = f"```markdown\n{GOOD_MODULE}\n```"

        with patch.object(p, "dispatch_auto", return_value=(True, wrapped)), \
             self._patch_key(p):
            result = p.step_write(self.module_path, "improve D1")
        self.assertIsNotNone(result, "Should accept wrapped markdown")
        self.assertTrue(result.startswith("---"), "Should start with frontmatter after stripping")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

# ---------------------------------------------------------------------------
# Test: Knowledge packet extraction
# ---------------------------------------------------------------------------

class TestKnowledgePacket(unittest.TestCase):
    """Test extract_knowledge_packet on known content."""

    def test_extracts_code_blocks(self):
        import v1_pipeline as p
        packet = p.extract_knowledge_packet(GOOD_MODULE)
        self.assertIn("[CODE-", packet)
        self.assertIn("```bash", packet)

    def test_extracts_tables(self):
        import v1_pipeline as p
        packet = p.extract_knowledge_packet(GOOD_MODULE)
        self.assertIn("[TABLE-", packet)
        self.assertIn("veth pair", packet)

    def test_extracts_quiz_questions(self):
        import v1_pipeline as p
        packet = p.extract_knowledge_packet(GOOD_MODULE)
        self.assertIn("[QUIZ-", packet)
        self.assertIn("200 nodes", packet)

    def test_extracts_inline_prompts(self):
        import v1_pipeline as p
        packet = p.extract_knowledge_packet(GOOD_MODULE)
        self.assertIn("Pause and predict", packet)
        self.assertIn("Stop and think", packet)

    def test_extracts_links(self):
        import v1_pipeline as p
        packet = p.extract_knowledge_packet(GOOD_MODULE)
        self.assertIn("KEY LINKS", packet)

    def test_real_module_extraction(self):
        """Extract from a real 800-line module — should get substantial content."""
        import v1_pipeline as p
        path = REPO_ROOT / "src" / "content" / "docs" / "k8s" / "cka" / "part5-troubleshooting" / "module-5.4-worker-nodes.md"
        if not path.exists():
            self.skipTest("Module not found")
        content = path.read_text()
        packet = p.extract_knowledge_packet(content)
        self.assertGreater(len(packet), 5000, "800-line module should yield substantial packet")
        self.assertIn("CODE-", packet)
        self.assertIn("TABLE-", packet)
        self.assertIn("QUIZ-", packet)

    def test_stub_module_returns_fallback(self):
        import v1_pipeline as p
        stub = "---\ntitle: Stub\n---\n\nJust a paragraph."
        packet = p.extract_knowledge_packet(stub)
        self.assertIn("No technical assets", packet)


# ---------------------------------------------------------------------------
# Test: Deterministic review-edit application
# ---------------------------------------------------------------------------

class TestApplyReviewEdits(unittest.TestCase):
    """Test the deterministic edit applier — applies reviewer-structured edits
    to module content via Python string ops, without any LLM writer call."""

    def test_replace_exact_anchor(self):
        import v1_pipeline as p
        content = "Some text\nwrong config: cpuHourlyCost\nmore text"
        edits = [
            {"type": "replace", "find": "wrong config: cpuHourlyCost",
             "new": "correct config: CPU", "dim": "D2", "why": "key rename"},
        ]
        patched, applied, failed = p.apply_review_edits(content, edits)
        self.assertEqual(patched, "Some text\ncorrect config: CPU\nmore text")
        self.assertEqual(len(applied), 1)
        self.assertEqual(len(failed), 0)

    def test_insert_after_anchor(self):
        import v1_pipeline as p
        content = "## Learning Outcomes\n\nYou will learn X.\n\n## Section 2"
        edits = [
            {"type": "insert_after", "find": "## Learning Outcomes",
             "new": "\n\n## Module Map\n1. Step one\n2. Step two",
             "dim": "D1", "why": "add module map"},
        ]
        patched, applied, failed = p.apply_review_edits(content, edits)
        self.assertIn("## Module Map", patched)
        self.assertTrue(patched.startswith("## Learning Outcomes\n\n## Module Map"),
                        f"unexpected prefix: {patched[:80]!r}")
        self.assertEqual(len(applied), 1)
        self.assertEqual(len(failed), 0)

    def test_insert_before_anchor(self):
        import v1_pipeline as p
        content = "Intro\n\n## Section 2\n\nBody"
        edits = [
            {"type": "insert_before", "find": "## Section 2",
             "new": "## Section 1.5\n\nExtra content\n\n",
             "dim": "D6", "why": "fill gap"},
        ]
        patched, _applied, failed = p.apply_review_edits(content, edits)
        self.assertIn("## Section 1.5", patched)
        self.assertTrue("## Section 1.5\n\nExtra content\n\n## Section 2" in patched)
        self.assertEqual(len(failed), 0)

    def test_delete(self):
        import v1_pipeline as p
        content = "Keep this.\nDELETE ME\nKeep this too."
        edits = [{"type": "delete", "find": "DELETE ME\n", "dim": "D3", "why": "stale"}]
        patched, _applied, failed = p.apply_review_edits(content, edits)
        self.assertEqual(patched, "Keep this.\nKeep this too.")
        self.assertEqual(len(failed), 0)

    def test_ambiguous_anchor_fails_gracefully(self):
        import v1_pipeline as p
        content = "foo bar baz\nfoo bar qux"
        edits = [{"type": "replace", "find": "foo bar", "new": "BAZ",
                  "dim": "D2", "why": "rename"}]
        patched, applied, failed = p.apply_review_edits(content, edits)
        self.assertEqual(patched, content, "Ambiguous anchor must not mutate content")
        self.assertEqual(len(applied), 0)
        self.assertEqual(len(failed), 1)
        self.assertIn("ambiguous", failed[0]["reason"].lower())

    def test_anchor_not_found_fails_gracefully(self):
        import v1_pipeline as p
        content = "Some content here."
        edits = [{"type": "replace", "find": "nonexistent text",
                  "new": "X", "dim": "D2", "why": "x"}]
        patched, applied, failed = p.apply_review_edits(content, edits)
        self.assertEqual(patched, content)
        self.assertEqual(len(applied), 0)
        self.assertEqual(len(failed), 1)
        self.assertIn("not found", failed[0]["reason"].lower())

    def test_whitespace_normalized_match(self):
        """Anchor with slightly different whitespace (e.g. extra newline) should
        still match via the whitespace-normalized fallback."""
        import v1_pipeline as p
        content = "The  quick brown   fox jumps  over the lazy dog for sure this time."
        # Anchor uses single spaces; content has irregular whitespace
        edits = [
            {"type": "replace",
             "find": "The quick brown fox jumps over the lazy dog for sure this time.",
             "new": "REPLACED",
             "dim": "D2", "why": "ws normalize test"},
        ]
        patched, applied, failed = p.apply_review_edits(content, edits)
        self.assertIn("REPLACED", patched)
        self.assertEqual(len(applied), 1)
        self.assertEqual(len(failed), 0)

    def test_multiple_edits_reverse_order_application(self):
        """Multiple non-overlapping edits must land correctly — reverse-order
        application keeps earlier offsets valid."""
        import v1_pipeline as p
        content = "alpha beta gamma delta epsilon"
        edits = [
            {"type": "replace", "find": "alpha", "new": "AAA", "dim": "D1"},
            {"type": "replace", "find": "delta", "new": "DDD", "dim": "D2"},
            {"type": "insert_after", "find": "gamma", "new": " INSERTED", "dim": "D3"},
        ]
        patched, applied, failed = p.apply_review_edits(content, edits)
        self.assertEqual(patched, "AAA beta gamma INSERTED DDD epsilon")
        self.assertEqual(len(applied), 3)
        self.assertEqual(len(failed), 0)

    def test_overlapping_edits_detected(self):
        """Two edits that touch overlapping regions — the second is flagged
        as a conflict and falls back for LLM handling."""
        import v1_pipeline as p
        content = "the quick brown fox"
        edits = [
            {"type": "replace", "find": "quick brown", "new": "QB", "dim": "D1"},
            {"type": "replace", "find": "brown fox", "new": "BF", "dim": "D2"},
        ]
        _patched, applied, failed = p.apply_review_edits(content, edits)
        # Both edits resolve to overlapping ranges — second one conflicts
        self.assertEqual(len(applied), 1, "One edit should apply cleanly")
        self.assertEqual(len(failed), 1, "Overlapping edit should fail")
        self.assertIn("overlap", failed[0]["reason"].lower())

    def test_invalid_edit_type_fails(self):
        import v1_pipeline as p
        content = "x"
        edits = [{"type": "bogus", "find": "x", "new": "y"}]
        _, applied, failed = p.apply_review_edits(content, edits)
        self.assertEqual(len(applied), 0)
        self.assertEqual(len(failed), 1)
        self.assertIn("unknown edit type", failed[0]["reason"].lower())

    def test_empty_edit_list_is_noop(self):
        import v1_pipeline as p
        content = "unchanged"
        patched, applied, failed = p.apply_review_edits(content, [])
        self.assertEqual(patched, content)
        self.assertEqual(applied, [])
        self.assertEqual(failed, [])

    def test_missing_find_field_fails(self):
        import v1_pipeline as p
        edits = [{"type": "replace", "new": "y"}]
        _, applied, failed = p.apply_review_edits("content", edits)
        self.assertEqual(len(applied), 0)
        self.assertEqual(len(failed), 1)

    def test_adjacent_non_overlapping_edits_both_apply(self):
        """Edit ending at position X and another starting at position X are
        adjacent, not overlapping — both must apply cleanly."""
        import v1_pipeline as p
        content = "ABCDEFGH"
        edits = [
            {"type": "replace", "find": "AB", "new": "11"},  # [0, 2)
            {"type": "replace", "find": "CD", "new": "22"},  # [2, 4)
        ]
        patched, applied, failed = p.apply_review_edits(content, edits)
        self.assertEqual(patched, "1122EFGH")
        self.assertEqual(len(applied), 2, "Both adjacent edits must apply")
        self.assertEqual(len(failed), 0)


class TestDeterministicApplyIntegration(_CalibrationIsolatedCase):
    """End-to-end integration: reviewer returns structured edits, pipeline
    applies them deterministically, re-review approves. Verifies zero LLM
    writer calls happen in the common case."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.state_file = Path(self.tmpdir) / "state.yaml"
        self.module_path = Path(self.tmpdir) / "module-0.1-test.md"
        self.module_path.write_text(GOOD_MODULE)

    def tearDown(self):
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    @patch("v1_pipeline.STATE_FILE")
    @patch("v1_pipeline.CONTENT_ROOT")
    @patch("subprocess.run")
    def test_reject_with_edits_converges_without_llm_writer(
        self, mock_subprocess, mock_root, mock_state,
    ):
        """Reviewer returns structured edits that apply cleanly → pipeline
        re-reviews the patched content and approves, with exactly ONE
        step_write call (the initial draft). Exactly the intended hot path
        for PR #221's deterministic edit application."""
        import v1_pipeline as p

        mock_state.__class__ = type(self.state_file)
        mock_root.resolve.return_value = Path(self.tmpdir).resolve()

        step_write_calls = []

        def fake_step_write(module_path, plan, model=None, rewrite=False,
                            previous_output=None, knowledge_card=None, fact_ledger=None):
            step_write_calls.append({"model": model, "plan": plan[:100]})
            # Return GOOD_MODULE verbatim; the reviewer's edit will patch it.
            return GOOD_MODULE

        # First review: REJECT with one structured edit that matches a unique
        # substring of GOOD_MODULE. compute_severity returns "targeted"
        # because 1 failed check has an edit_ref. Second review: APPROVE.
        import v1_pipeline as pp
        review_sequence = [
            {
                "verdict": "REJECT",
                "checks": [
                    {"id": "LAB", "passed": False, "evidence": "minor accuracy",
                     "edit_refs": [0]},
                    {"id": "COV", "passed": True},
                    {"id": "QUIZ", "passed": True},
                    {"id": "EXAM", "passed": True},
                    {"id": "DEPTH", "passed": True},
                    {"id": "WHY", "passed": True},
                    {"id": "PRES", "passed": True},
                ],
                "edits": [
                    {
                        "type": "replace",
                        "find": "## Learning Outcomes",
                        "new": "## Learning Outcomes (Revised)",
                        "reason": "revision tag",
                    },
                ],
                "feedback": "Minor accuracy fix.",
            },
            {
                "verdict": "APPROVE",
                "checks": [{"id": cid, "passed": True} for cid in pp.CHECK_IDS],
                "edits": [],
                "feedback": "",
            },
        ]

        state = {"modules": {}}

        with patch.object(p, "STATE_FILE", self.state_file), \
             patch.object(p, "CONTENT_ROOT", Path(self.tmpdir)), \
             patch.object(p, "save_state"), \
             patch.object(p, "module_key_from_path", return_value="test/module-0.1-test"), \
             patch.object(p, "step_write", side_effect=fake_step_write), \
             patch.object(p, "step_review", side_effect=review_sequence), \
             patch.object(p, "ensure_fact_ledger", return_value=sample_fact_ledger()), \
             patch.object(p, "step_content_aware_fact_ledger", return_value=None), \
             patch.object(p, "step_check_integrity", return_value=(True, [])), \
             patch.object(p, "step_check", return_value=(True, [])), \
             patch.object(p, "ensure_knowledge_card", return_value="cached card"):
            p.run_module(self.module_path, state)

        # CRITICAL: exactly ONE step_write call (the initial draft). The
        # REJECT → deterministic apply → re-review path must NOT invoke
        # the writer again.
        self.assertEqual(
            len(step_write_calls), 1,
            f"Initial write only; deterministic apply must skip the writer "
            f"(got {len(step_write_calls)} writes)"
        )
        ms = state["modules"]["test/module-0.1-test"]
        self.assertEqual(ms.get("phase"), "done",
                         "Module must converge to done after deterministic apply + approve")
        self.assertTrue(ms.get("passes"))

    @patch("v1_pipeline.STATE_FILE")
    @patch("v1_pipeline.CONTENT_ROOT")
    @patch("subprocess.run")
    def test_crash_after_deterministic_apply_recovers_from_staging(
        self, mock_subprocess, mock_root, mock_state,
    ):
        """Proves crash recovery: simulates a process crash AFTER deterministic
        apply succeeds but BEFORE CHECK runs, then restarts run_module on the
        same state + staging file and asserts the patched content (not the
        un-patched on-disk content) is what gets re-reviewed.

        This test enforces Gemini's review finding: the staging write was
        landing, but without this test we couldn't prove the resume path
        actually reads it."""
        import v1_pipeline as p

        mock_state.__class__ = type(self.state_file)
        mock_root.resolve.return_value = Path(self.tmpdir).resolve()

        # Pre-seed the staging file with "patched" content different from
        # the on-disk module — simulating a crash after apply but before CHECK
        staging_path = self.module_path.with_suffix(".staging.md")
        patched_content = GOOD_MODULE.replace("## Learning Outcomes", "## Learning Outcomes (PATCHED)")
        staging_path.write_text(patched_content)

        # Pre-seed state as if the pipeline was mid-run and crashed at
        # phase=review (the state deterministic apply leaves behind)
        import v1_pipeline as pp
        state = {
            "modules": {
                "test/module-0.1-test": {
                    "phase": "review",
                    "severity": "targeted",
                    "checks_failed": [{"id": "LAB", "evidence": "example"}],
                    "reviewer_schema_version": 3,
                    "passes": False,
                    "errors": [],
                }
            }
        }

        reviews_seen = []

        def fake_step_review(module_path, improved, model=None, fact_ledger=None):
            reviews_seen.append(improved)
            return {
                "verdict": "APPROVE",
                "severity": "clean",
                "checks": [{"id": cid, "passed": True} for cid in pp.CHECK_IDS],
                "edits": [],
                "feedback": "",
            }

        step_write_calls = []

        def fake_step_write(module_path, plan, model=None, rewrite=False,
                            previous_output=None, knowledge_card=None, fact_ledger=None):
            step_write_calls.append(plan[:80])
            return GOOD_MODULE

        with patch.object(p, "STATE_FILE", self.state_file), \
             patch.object(p, "CONTENT_ROOT", Path(self.tmpdir)), \
             patch.object(p, "save_state"), \
             patch.object(p, "module_key_from_path", return_value="test/module-0.1-test"), \
             patch.object(p, "step_write", side_effect=fake_step_write), \
             patch.object(p, "step_review", side_effect=fake_step_review), \
             patch.object(p, "ensure_fact_ledger", return_value=sample_fact_ledger()), \
             patch.object(p, "step_content_aware_fact_ledger", return_value=None), \
             patch.object(p, "step_check_integrity", return_value=(True, [])), \
             patch.object(p, "step_check", return_value=(True, [])), \
             patch.object(p, "ensure_knowledge_card", return_value="cached card"):
            p.run_module(self.module_path, state)

        # Recovery must read from staging (patched), not from on-disk (original)
        self.assertEqual(len(reviews_seen), 1, "One review should fire on recovery")
        self.assertIn("(PATCHED)", reviews_seen[0],
                      "Resume at phase=review must load patched content from staging, "
                      "not the un-patched on-disk module")
        # No writer calls — the patched content was already staged
        self.assertEqual(len(step_write_calls), 0,
                         "Crash recovery at phase=review should NOT re-invoke the writer")
        ms = state["modules"]["test/module-0.1-test"]
        self.assertEqual(ms.get("phase"), "done")

    @patch("v1_pipeline.STATE_FILE")
    @patch("v1_pipeline.CONTENT_ROOT")
    @patch("subprocess.run")
    def test_crash_after_partial_apply_resumes_with_fallback_plan(
        self, mock_subprocess, mock_root, mock_state,
    ):
        """Proves Issue B crash recovery: partial-success deterministic apply
        persisted the fallback plan and targeted_fix flag to state, so a
        crash here and subsequent restart must:

          1. Load the staged partial-apply content as `improved`
          2. Reconstruct the FALLBACK FIX plan from ms["plan"]
          3. Route the writer to claude-sonnet-4-6 (targeted_fix=True)
          4. NOT re-run audit / initial write / initial review
        """
        import v1_pipeline as p

        mock_state.__class__ = type(self.state_file)
        mock_root.resolve.return_value = Path(self.tmpdir).resolve()

        # Pre-seed staging with the partially-patched content
        staging_path = self.module_path.with_suffix(".staging.md")
        partial_patched = GOOD_MODULE.replace("## Learning Outcomes", "## Learning Outcomes (PARTIALLY-PATCHED)")
        staging_path.write_text(partial_patched)

        # Pre-seed state as the partial-apply fallback branch would have saved it
        fallback_plan = (
            "FALLBACK FIX. The pipeline applied 3 of 5 structured edits deterministically; "
            "the remaining 2 could not be applied mechanically. Apply ONLY these remaining "
            'edits.\n\nFailed edit (reason: anchor not found): ```json\n{"type": "replace", '
            '"find": "nonexistent", "new": "replacement"}\n```'
        )
        import v1_pipeline as pp
        state = {
            "modules": {
                "test/module-0.1-test": {
                    "phase": "write",
                    "plan": fallback_plan,
                    "targeted_fix": True,
                    "severity": "targeted",
                    "checks_failed": [
                        {"id": "LAB", "evidence": "example1"},
                        {"id": "QUIZ", "evidence": "example2"},
                    ],
                    "reviewer_schema_version": 3,
                    "passes": False,
                    "errors": [],
                }
            }
        }

        write_calls_observed = []

        def fake_step_write(module_path, plan, model=None, rewrite=False,
                            previous_output=None, knowledge_card=None, fact_ledger=None):
            write_calls_observed.append({
                "model": model,
                "plan": plan,
                "previous_output": previous_output or "",
            })
            return GOOD_MODULE.replace("## Learning Outcomes", "## Learning Outcomes (FULLY-FIXED)")

        def fake_step_review(module_path, improved, model=None, fact_ledger=None):
            return {
                "verdict": "APPROVE",
                "severity": "clean",
                "checks": [{"id": cid, "passed": True} for cid in pp.CHECK_IDS],
                "edits": [],
                "feedback": "",
            }

        with patch.object(p, "STATE_FILE", self.state_file), \
             patch.object(p, "CONTENT_ROOT", Path(self.tmpdir)), \
             patch.object(p, "save_state"), \
             patch.object(p, "module_key_from_path", return_value="test/module-0.1-test"), \
             patch.object(p, "step_write", side_effect=fake_step_write), \
             patch.object(p, "step_review", side_effect=fake_step_review), \
             patch.object(p, "ensure_fact_ledger", return_value=sample_fact_ledger()), \
             patch.object(p, "step_content_aware_fact_ledger", return_value=None), \
             patch.object(p, "step_check_integrity", return_value=(True, [])), \
             patch.object(p, "step_check", return_value=(True, [])), \
             patch.object(p, "ensure_knowledge_card", return_value="cached card"):
            p.run_module(self.module_path, state)

        self.assertEqual(len(write_calls_observed), 1,
                         "Exactly one write should fire: the fallback Sonnet write")
        call = write_calls_observed[0]
        # Writer MUST be Sonnet (the targeted-fix model) because ms["targeted_fix"]
        # was restored from state on resume
        self.assertEqual(call["model"], p.MODELS["write_targeted"],
                         f"Fallback write must route to {p.MODELS['write_targeted']} "
                         f"(Sonnet), not Gemini — targeted_fix flag must survive resume")
        # Plan MUST be the restored FALLBACK FIX plan, not a generic one
        self.assertIn("FALLBACK FIX", call["plan"],
                      "Plan must be restored from ms['plan'], not regenerated as generic")
        # previous_output MUST be the staged partial-patched content — Sonnet
        # must operate on the progress we already made, not start over from
        # the un-patched on-disk module
        self.assertIn("(PARTIALLY-PATCHED)", call["previous_output"],
                      "Writer must operate on the staged partial-patched content, "
                      "not re-read the unpatched on-disk module")
        ms = state["modules"]["test/module-0.1-test"]
        self.assertEqual(ms.get("phase"), "done")

    @patch("v1_pipeline.STATE_FILE")
    @patch("v1_pipeline.CONTENT_ROOT")
    @patch("subprocess.run")
    def test_last_retry_full_apply_exits_in_rereview_state(
        self, mock_subprocess, mock_root, mock_state,
    ):
        """A clean deterministic apply on the last retry must not reject."""
        import v1_pipeline as p

        mock_state.__class__ = type(self.state_file)
        mock_root.resolve.return_value = Path(self.tmpdir).resolve()

        review_sequence = [
            {
                "verdict": "REJECT",
                "checks": [
                    {"id": "LAB", "passed": False, "evidence": "rewrite required"},
                    {"id": "COV", "passed": True},
                    {"id": "QUIZ", "passed": True},
                    {"id": "EXAM", "passed": True},
                    {"id": "DEPTH", "passed": True},
                    {"id": "WHY", "passed": True},
                    {"id": "PRES", "passed": True},
                ],
                "edits": [],
                "feedback": "Needs a rewrite first.",
            },
            {
                "verdict": "REJECT",
                "checks": [
                    {"id": "LAB", "passed": False, "evidence": "minor accuracy", "edit_refs": [0]},
                    {"id": "COV", "passed": True},
                    {"id": "QUIZ", "passed": True},
                    {"id": "EXAM", "passed": True},
                    {"id": "DEPTH", "passed": True},
                    {"id": "WHY", "passed": True},
                    {"id": "PRES", "passed": True},
                ],
                "edits": [
                    {
                        "type": "replace",
                        "find": "## Learning Outcomes",
                        "new": "## Learning Outcomes (Revised)",
                        "reason": "revision tag",
                    },
                ],
                "feedback": "Minor accuracy fix.",
            },
        ]

        state = {"modules": {}}

        with patch.object(p, "STATE_FILE", self.state_file), \
             patch.object(p, "CONTENT_ROOT", Path(self.tmpdir)), \
             patch.object(p, "save_state"), \
             patch.object(p, "module_key_from_path", return_value="test/module-0.1-test"), \
             patch.object(p, "step_write", return_value=GOOD_MODULE), \
             patch.object(p, "step_review", side_effect=review_sequence), \
             patch.object(p, "ensure_fact_ledger", return_value=sample_fact_ledger()), \
             patch.object(p, "step_content_aware_fact_ledger", return_value=None), \
             patch.object(p, "step_check_integrity", return_value=(True, [])), \
             patch.object(p, "step_check", return_value=(True, [])), \
             patch.object(p, "ensure_knowledge_card", return_value="cached card"):
            ok = p.run_module(self.module_path, state, max_retries=1)

        ms = state["modules"]["test/module-0.1-test"]
        staging = self.module_path.with_suffix(".staging.md")

        self.assertTrue(ok)
        self.assertEqual(ms.get("phase"), "review")
        self.assertEqual(ms.get("severity"), "targeted")
        self.assertNotIn("Review rejected 2 times", ms.get("errors", []))
        self.assertTrue(staging.exists(), "Patched content should be staged for resume re-review")
        self.assertIn("## Learning Outcomes (Revised)", staging.read_text())

    @patch("v1_pipeline.STATE_FILE")
    @patch("v1_pipeline.CONTENT_ROOT")
    @patch("subprocess.run")
    def test_last_retry_failed_apply_still_rejects(
        self, mock_subprocess, mock_root, mock_state,
    ):
        """A failed deterministic apply on the last retry must still reject."""
        import v1_pipeline as p

        mock_state.__class__ = type(self.state_file)
        mock_root.resolve.return_value = Path(self.tmpdir).resolve()

        review_sequence = [
            {
                "verdict": "REJECT",
                "checks": [
                    {"id": "LAB", "passed": False, "evidence": "rewrite required"},
                    {"id": "COV", "passed": True},
                    {"id": "QUIZ", "passed": True},
                    {"id": "EXAM", "passed": True},
                    {"id": "DEPTH", "passed": True},
                    {"id": "WHY", "passed": True},
                    {"id": "PRES", "passed": True},
                ],
                "edits": [],
                "feedback": "Needs a rewrite first.",
            },
            {
                "verdict": "REJECT",
                "checks": [
                    {"id": "LAB", "passed": False, "evidence": "minor accuracy", "edit_refs": [0]},
                    {"id": "COV", "passed": True},
                    {"id": "QUIZ", "passed": True},
                    {"id": "EXAM", "passed": True},
                    {"id": "DEPTH", "passed": True},
                    {"id": "WHY", "passed": True},
                    {"id": "PRES", "passed": True},
                ],
                "edits": [
                    {
                        "type": "replace",
                        "find": "## Missing Anchor",
                        "new": "## Missing Anchor (Revised)",
                        "reason": "missing anchor",
                    },
                ],
                "feedback": "Minor accuracy fix.",
            },
        ]

        state = {"modules": {}}

        with patch.object(p, "STATE_FILE", self.state_file), \
             patch.object(p, "CONTENT_ROOT", Path(self.tmpdir)), \
             patch.object(p, "save_state"), \
             patch.object(p, "module_key_from_path", return_value="test/module-0.1-test"), \
             patch.object(p, "step_write", return_value=GOOD_MODULE), \
             patch.object(p, "step_review", side_effect=review_sequence), \
             patch.object(p, "ensure_fact_ledger", return_value=sample_fact_ledger()), \
             patch.object(p, "step_content_aware_fact_ledger", return_value=None), \
             patch.object(p, "step_check_integrity", return_value=(True, [])), \
             patch.object(p, "step_check", return_value=(True, [])), \
             patch.object(p, "ensure_knowledge_card", return_value="cached card"):
            ok = p.run_module(self.module_path, state, max_retries=1)

        ms = state["modules"]["test/module-0.1-test"]
        self.assertFalse(ok)
        self.assertEqual(ms.get("phase"), "write")
        self.assertIn("Review rejected 2 times", ms.get("errors", []))


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    # Suppress pipeline logging during tests
    os.environ["KUBEDOJO_QUIET"] = "1"
    unittest.main(verbosity=2)
