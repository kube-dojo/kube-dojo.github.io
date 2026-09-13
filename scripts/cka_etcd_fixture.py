"""Owned disposable etcd fixture helpers; lifecycle reuses certificate Fixture. No restore."""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import re
import shlex
import signal
import subprocess
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
MARKER_NAME = "snapshot-marker"
SNAPSHOT_FILE = "etcd-snapshot.db"


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


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "action",
        choices=("create", "inspect", "etcd-inspect", "snapshot-observe", "delete"),
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
