"""Owned disposable etcd fixture helpers; lifecycle reuses certificate Fixture."""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import re
import shlex
import signal
import subprocess
import time
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
_spec = importlib.util.spec_from_file_location(
    "cka_certificate_fixture", ROOT / "scripts/cka_certificate_fixture.py"
)
_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_mod)
Fixture = _mod.Fixture

ETCD_ENDPOINT = "https://127.0.0.1:2379"
ETCD_PKI = "/etc/kubernetes/pki/etcd"
ETCD_DATA = "/var/lib/etcd"
ETCD_MANIFEST = "/etc/kubernetes/manifests/etcd.yaml"
RESTORE_TXN = "/var/lib/etcd-fixture-transaction"
MARKER_NAME = "snapshot-marker"
SNAPSHOT_FILE = "etcd-snapshot.db"
NODE_ETCDCTL = "/usr/local/bin/etcdctl"
NODE_ETCDUTL = "/usr/local/bin/etcdutl"


class EtcdFixture:
    """Compose the owned kind fixture; add etcd topology capture only."""

    def __init__(self, directory, create=False):
        self.inner = Fixture(directory, create=create)

    def __getattr__(self, name):
        return getattr(self.inner, name)

    def _node_id(self):
        return self.inner.state["node"]["id"]

    def _ensure_etcd(self):
        if not self.inner.state.get("etcd"):
            self.etcd_inspect()
        return self.inner.state["etcd"]

    def _discover_etcd_image(self):
        raw = self.inner.run(
            "docker",
            "exec",
            self._node_id(),
            "crictl",
            "ps",
            "--name",
            "etcd",
            "-o",
            "json",
        )
        containers = json.loads(raw).get("containers") or []
        if not containers:
            raise RuntimeError("No running etcd container on owned node")
        image = containers[0].get("image", {}).get("userSpecifiedImage") or ""
        if not image.startswith("registry.k8s.io/etcd:"):
            raise RuntimeError(f"Unexpected etcd image ref: {image!r}")
        return image

    def _ensure_etcd_tools(self):
        node_id = self._node_id()
        present = self.inner.run(
            "docker",
            "exec",
            node_id,
            "sh",
            "-c",
            f"if [ -x {NODE_ETCDCTL} ] && [ -x {NODE_ETCDUTL} ]; then echo present; fi",
        )
        if "present" in present:
            return {"source": "preinstalled"}
        image = self._discover_etcd_image()
        staging = self.inner.directory / "etcd-tools"
        staging.mkdir(mode=0o700, exist_ok=True)
        cid = self.inner.run("docker", "create", "--entrypoint", "/bin/true", image)
        try:
            self.inner.run("docker", "cp", f"{cid}:{NODE_ETCDCTL}", str(staging / "etcdctl"))
            self.inner.run("docker", "cp", f"{cid}:{NODE_ETCDUTL}", str(staging / "etcdutl"))
        finally:
            self.inner.run("docker", "rm", "-f", cid)
        self.inner.run("docker", "cp", str(staging / "etcdctl"), f"{node_id}:{NODE_ETCDCTL}")
        self.inner.run("docker", "cp", str(staging / "etcdutl"), f"{node_id}:{NODE_ETCDUTL}")
        self.inner.run(
            "docker",
            "exec",
            node_id,
            "sh",
            "-c",
            f"chmod 0755 {NODE_ETCDCTL} {NODE_ETCDUTL}",
        )
        return {"source": "etcd_image", "image": image}

    def _etcdctl(self, *args):
        pki = ETCD_PKI
        cmd = [
            "etcdctl",
            f"--endpoints={ETCD_ENDPOINT}",
            f"--cacert={pki}/ca.crt",
            f"--cert={pki}/server.crt",
            f"--key={pki}/server.key",
            *args,
        ]
        return self.inner.run(
            "docker", "exec", self._node_id(), "sh", "-c", " ".join(shlex.quote(a) for a in cmd)
        )

    def _refuse_unauthenticated(self):
        probe = f"etcdctl --endpoints={ETCD_ENDPOINT} endpoint status -w json"
        try:
            self.inner.run("docker", "exec", self._node_id(), "sh", "-c", probe)
        except RuntimeError:
            return
        raise RuntimeError("Unauthenticated etcdctl succeeded; refusing")

    def _marker_cm(self, namespace, name):
        return json.loads(self.inner.api("-n", namespace, "get", "configmap", name, "-o", "json"))

    def etcd_inspect(self):
        self.inner.verify()
        self.inner.inspect()
        tools = self._ensure_etcd_tools()
        node_id = self._node_id()
        inventory = self.inner.run(
            "docker",
            "exec",
            node_id,
            "sh",
            "-c",
            "command -v etcdctl; command -v etcdutl; "
            f"test -d {ETCD_DATA} && test -d {ETCD_PKI} && echo paths_ok",
        )
        if "etcdctl" not in inventory or "etcdutl" not in inventory:
            raise RuntimeError("etcdctl/etcdutl missing on owned node")
        if "paths_ok" not in inventory:
            raise RuntimeError("etcd data/pki paths missing on owned node")
        version = self.inner.run(
            "docker",
            "exec",
            node_id,
            "sh",
            "-c",
            "etcdctl version 2>/dev/null | head -1",
        ).strip()
        if not version or not re.search(r"etcdctl\s+version:\s*3\.", version):
            raise RuntimeError(
                "etcdctl version line missing or not etcd 3.x: "
                f"{version!r}"
            )
        self.inner.state["etcd"] = {
            "endpoint": ETCD_ENDPOINT,
            "data_dir": ETCD_DATA,
            "pki_dir": ETCD_PKI,
            "tool_inventory": inventory,
            "etcdctl_version_line": version,
            "tools_provision": tools,
            "restore_executed": False,
        }
        self.inner.save()
        return self.inner.state["etcd"]

    def ensure_marker(self):
        self.inner.verify()
        marker = self.inner.state.get("etcd_marker")
        if marker:
            observed = self._marker_cm(marker["namespace"], marker["name"])
            if observed["metadata"]["uid"] != marker["uid"]:
                raise RuntimeError("Marker object identity changed")
            if observed["data"]["value"] != marker["value"]:
                raise RuntimeError("Marker value drifted before snapshot")
            return marker
        namespace = "etcd-marker-" + uuid.uuid4().hex
        value = uuid.uuid4().hex
        self.inner.api("create", "namespace", namespace)
        self.inner.api("-n", namespace, "create", "configmap", MARKER_NAME, "--from-literal=value=" + value)
        observed = self._marker_cm(namespace, MARKER_NAME)
        marker = {"namespace": namespace, "name": MARKER_NAME, "uid": observed["metadata"]["uid"], "value": value}
        self.inner.state["etcd_marker"] = marker
        self.inner.save()
        return marker

    def etcd_baseline(self):
        self._ensure_etcd()
        self._refuse_unauthenticated()
        marker = self.ensure_marker()
        status = json.loads(self._etcdctl("endpoint", "status", "-w", "json"))[0]["Status"]
        revision = status["header"]["revision"]
        etcd_key = f"/registry/configmaps/{marker['namespace']}/{marker['name']}"
        if not self._etcdctl("get", etcd_key):
            raise RuntimeError("Marker key missing in etcd")
        baseline = {"revision": revision, "marker_etcd_key": etcd_key, "authenticated": True}
        self.inner.state["etcd_baseline"] = baseline
        self.inner.state["etcd"]["restore_executed"] = False
        self.inner.save()
        return baseline

    def snapshot_save(self):
        etcd = self._ensure_etcd()
        baseline = self.inner.state.get("etcd_baseline")
        if not baseline:
            raise RuntimeError("etcd baseline required before snapshot")
        snap_path = self.inner.directory / SNAPSHOT_FILE
        if self.inner.state.get("snapshot") or snap_path.exists():
            raise RuntimeError("Refusing to overwrite existing snapshot")
        node_snap = "/tmp/etcd-snapshot-" + uuid.uuid4().hex + ".db"
        self._etcdctl("snapshot", "save", node_snap)
        status = json.loads(
            self.inner.run(
                "docker", "exec", self._node_id(), "etcdutl", "snapshot", "status", node_snap, "-w", "json"
            )
        )
        snap_revision = status.get("revision", status.get("Revision"))
        if snap_revision is None or snap_revision < baseline["revision"]:
            raise RuntimeError("Snapshot revision does not cover baseline")
        self.inner.run("docker", "cp", f"{self._node_id()}:{node_snap}", str(snap_path))
        digest = hashlib.sha256(snap_path.read_bytes()).hexdigest()
        self.inner.state["snapshot"] = {
            "path": str(snap_path),
            "sha256": digest,
            "status": status,
            "node_temp_path": node_snap,
        }
        etcd["restore_executed"] = False
        self.inner.save()
        return self.inner.state["snapshot"]

    def post_snapshot_mutate(self):
        marker = self.inner.state.get("etcd_marker")
        snapshot = self.inner.state.get("snapshot")
        if not marker or not snapshot:
            raise RuntimeError("Snapshot and marker required before post-snapshot mutation")
        patch = json.dumps({"data": {"value": uuid.uuid4().hex}})
        self.inner.api("-n", marker["namespace"], "patch", "configmap", marker["name"], "--type", "merge", "-p", patch)
        observed = self._marker_cm(marker["namespace"], marker["name"])
        self.inner.state["post_snapshot_mutation"] = {
            "value": observed["data"]["value"],
            "uid": observed["metadata"]["uid"],
        }
        digest = hashlib.sha256(Path(snapshot["path"]).read_bytes()).hexdigest()
        if digest != snapshot["sha256"]:
            raise RuntimeError("Snapshot file hash changed after mutation")
        self.inner.state["etcd"]["restore_executed"] = False
        self.inner.save()
        return self.inner.state["post_snapshot_mutation"]

    def snapshot_observe(self):
        self.etcd_baseline()
        self.snapshot_save()
        self.post_snapshot_mutate()
        return self.inner.state

    def _node_sh(self, script):
        return self.inner.run("docker", "exec", self._node_id(), "sh", "-c", script)

    def _restore_rec(self):
        etcd = self._ensure_etcd()
        return etcd.setdefault("restore", {"direction": "restore", "stage": None})

    def _require_restore_inputs(self):
        marker = self.inner.state.get("etcd_marker")
        baseline = self.inner.state.get("etcd_baseline")
        snapshot = self.inner.state.get("snapshot")
        etcd = self._ensure_etcd()
        if not marker or not baseline or not snapshot:
            raise RuntimeError("snapshot, etcd_marker, and etcd_baseline required before restore")
        if etcd.get("restore_executed"):
            raise RuntimeError("Restore already executed")
        if not Path(snapshot["path"]).is_file():
            raise RuntimeError("Snapshot file missing")
        return marker, snapshot

    def _advance_restore(self, expected, nxt):
        rec = self._restore_rec()
        stage = rec.get("stage")
        if stage is None and expected == "restore_requested":
            rec["stage"] = expected
            self.inner.save()
            stage = expected
        if stage != expected:
            raise RuntimeError(f"Restore stage {stage!r} != expected {expected!r}")
        rec["stage"] = nxt
        self.inner.state["etcd"]["restore_executed"] = False
        self.inner.save()

    def _parse_etcd_restore_params(self, manifest_text):
        keys = (
            "name",
            "initial-cluster",
            "initial-advertise-peer-urls",
            "initial-cluster-token",
        )
        params = {}
        for line in manifest_text.splitlines():
            match = re.search(
                r"--(name|initial-cluster|initial-advertise-peer-urls|initial-cluster-token)=(\S+)",
                line,
            )
            if not match:
                continue
            key, value = match.group(1), match.group(2).strip("\"'")
            if key in keys:
                params[key] = value
        return params

    def _etcd_restore_params(self):
        rec = self._restore_rec()
        if rec.get("restore_params"):
            return rec["restore_params"]
        staged = f"{RESTORE_TXN}/etcd.yaml.staged"
        text = self._node_sh(
            f'M={shlex.quote(ETCD_MANIFEST)}; [ -f "$M" ] || M={shlex.quote(staged)}; cat "$M"'
        )
        params = self._parse_etcd_restore_params(text)
        if not params.get("name"):
            raise RuntimeError("Could not parse etcd restore params from manifest")
        rec["restore_params"] = params
        self.inner.save()
        return params

    def restore_begin(self):
        marker, _snapshot = self._require_restore_inputs()
        rec = self._restore_rec()
        if rec.get("stage") is None:
            rec["stage"] = "restore_requested"
            rec["expected_marker_value"] = marker["value"]
            self.inner.state["etcd"]["restore_executed"] = False
            self.inner.save()
        return self.inner.state

    def _stop_etcd_pod(self):
        rec = self._restore_rec()
        staged = f"{RESTORE_TXN}/etcd.yaml.staged"
        stage = rec.get("stage")
        if stage == "restore_requested":
            self._advance_restore("restore_requested", "etcd_stop_requested")
        elif stage != "etcd_stop_requested":
            return
        self._etcd_restore_params()
        self._node_sh(f"mkdir -p {RESTORE_TXN}")
        if "stopped" not in self._node_sh(
            f"if [ ! -f {ETCD_MANIFEST} ] && [ -f {staged} ]; then echo stopped; fi"
        ):
            self._node_sh(
                f"if [ -f {ETCD_MANIFEST} ] && [ ! -f {staged} ]; then "
                f"cp -a {ETCD_MANIFEST} {staged} && rm -f {ETCD_MANIFEST}; fi"
            )
            for _ in range(30):
                try:
                    self._etcdctl("endpoint", "health")
                except RuntimeError:
                    break
                time.sleep(1)
            else:
                raise RuntimeError("etcd did not stop")
        self._advance_restore("etcd_stop_requested", "etcd_stopped")

    def _offline_restore(self, snapshot):
        rec = self._restore_rec()
        stage = rec.get("stage")
        if stage == "etcd_stopped":
            self._advance_restore("etcd_stopped", "offline_restore_requested")
        elif stage != "offline_restore_requested":
            return
        moved = rec.setdefault("live_data_moved", f"/var/lib/etcd-pre-{uuid.uuid4().hex[:8]}")
        restore_dir = rec.setdefault("restore_data_dir", f"/var/lib/etcd-restored-{uuid.uuid4().hex[:8]}")
        self.inner.save()
        if "ready" in self._node_sh(
            f"if [ -d {ETCD_DATA} ] && [ -d {moved} ]; then echo ready; fi"
        ):
            self._advance_restore("offline_restore_requested", "offline_restored")
            return
        if "aside" not in self._node_sh(f"if [ -d {moved} ]; then echo aside; fi"):
            self._node_sh(
                f"if [ -d {restore_dir} ]; then rm -rf {restore_dir}; fi; "
                f"if [ -d {ETCD_DATA} ]; then mv {ETCD_DATA} {moved}; fi"
            )
            rec["offline_substage"] = "live_data_aside"
            self.inner.save()
        if "restored" not in self._node_sh(
            f"if [ -d {restore_dir}/member ]; then echo restored; fi"
        ):
            self._node_sh(f"rm -rf {restore_dir}; mkdir -p {restore_dir}")
            node_snap = f"/tmp/etcd-restore-{uuid.uuid4().hex}.db"
            self.inner.run("docker", "cp", snapshot["path"], f"{self._node_id()}:{node_snap}")
            params = self._etcd_restore_params()
            flags = " ".join(f"--{k}={shlex.quote(params[k])}" for k in sorted(params))
            self._node_sh(
                f"etcdutl snapshot restore {shlex.quote(node_snap)} "
                f"--data-dir={shlex.quote(restore_dir)} {flags}"
            )
            rec["offline_substage"] = "restored_dir_ready"
            self.inner.save()
        self._node_sh(f"rm -rf {ETCD_DATA} && mv {restore_dir} {ETCD_DATA}")
        rec["offline_substage"] = "activated"
        self.inner.save()
        self._advance_restore("offline_restore_requested", "offline_restored")

    def _return_etcd_pod(self):
        rec = self._restore_rec()
        staged = f"{RESTORE_TXN}/etcd.yaml.staged"
        stage = rec.get("stage")
        if stage == "offline_restored":
            self._advance_restore("offline_restored", "etcd_return_requested")
        elif stage != "etcd_return_requested":
            return
        if "ok" not in self._node_sh(
            f"if [ -f {ETCD_MANIFEST} ] && [ -f {staged} ] && cmp -s {ETCD_MANIFEST} {staged}; "
            f"then echo ok; fi"
        ):
            self._node_sh(f"test -f {staged} && cp -a {staged} {ETCD_MANIFEST}")
        for _ in range(60):
            try:
                if self.inner.api("get", "--raw=/readyz") == "ok":
                    break
            except RuntimeError:
                pass
            time.sleep(2)
        else:
            raise RuntimeError("API not ready after restore")
        self._advance_restore("etcd_return_requested", "etcd_returned")

    def _verify_restored_marker(self):
        marker, _snapshot = self._require_restore_inputs()
        rec = self._restore_rec()
        stage = rec.get("stage")
        if stage not in ("etcd_returned", "restore_verified"):
            raise RuntimeError(f"Restore stage {stage!r} != expected etcd_returned")
        observed = self._marker_cm(marker["namespace"], marker["name"])
        if observed["data"]["value"] != marker["value"]:
            raise RuntimeError("Restored marker value does not match snapshot-era marker")
        rec["observed_marker_uid"] = observed["metadata"]["uid"]
        rec["marker_uid_may_differ"] = observed["metadata"]["uid"] != marker["uid"]
        rec["stage"] = "restore_verified"
        self.inner.state["etcd"]["restore_executed"] = True
        self.inner.save()

    def restore_continue(self):
        self.inner.verify()
        rec = self._restore_rec()
        stage = rec.get("stage")
        if stage is None:
            self.restore_begin()
            stage = rec.get("stage")
        if stage in ("restore_requested", "etcd_stop_requested"):
            self._stop_etcd_pod()
        elif stage in ("etcd_stopped", "offline_restore_requested"):
            self._offline_restore(self.inner.state["snapshot"])
        elif stage in ("offline_restored", "etcd_return_requested"):
            self._return_etcd_pod()
        elif stage == "etcd_returned":
            self._verify_restored_marker()
        elif stage == "restore_verified":
            if not self.inner.state["etcd"].get("restore_executed"):
                self._verify_restored_marker()
        else:
            raise RuntimeError(f"Unknown restore stage {stage!r}")
        return self.inner.state

    def restore_execute(self):
        while self._restore_rec().get("stage") != "restore_verified":
            self.restore_continue()
        return self.inner.state


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "action",
        choices=(
            "create",
            "inspect",
            "etcd-inspect",
            "snapshot-observe",
            "restore",
            "restore-continue",
            "delete",
        ),
    )
    parser.add_argument("run_dir")
    args = parser.parse_args()
    fixture = None

    def interrupted(signum, _frame):
        raise InterruptedError(
            f"Signal {signum}; client cancellation does not prove node work stopped"
        )

    signal.signal(signal.SIGINT, interrupted)
    signal.signal(signal.SIGTERM, interrupted)
    try:
        fixture = EtcdFixture(args.run_dir, create=args.action == "create")
        if args.action == "etcd-inspect":
            print(json.dumps(fixture.etcd_inspect(), indent=2))
        elif args.action == "snapshot-observe":
            print(json.dumps(fixture.snapshot_observe(), indent=2, default=str))
        elif args.action == "restore":
            print(json.dumps(fixture.restore_execute(), indent=2, default=str))
        elif args.action == "restore-continue":
            print(json.dumps(fixture.restore_continue(), indent=2, default=str))
        elif args.action == "create":
            fixture.create()
        elif args.action == "inspect":
            fixture.inspect()
        else:
            fixture.delete()
    except (OSError, ValueError, RuntimeError, KeyError, TypeError, subprocess.SubprocessError) as error:
        if fixture is not None:
            fixture.inner.state["error"] = str(error)
            fixture.inner.save()
        raise SystemExit(str(error)) from None
    finally:
        if fixture is not None:
            fixture.inner.lock.close()


if __name__ == "__main__":
    main()
