"""Owned disposable fixture lifecycle only; no certificate transaction or renewal."""
import argparse
import fcntl
import json
import os
import re
import shutil
import signal
import stat
import subprocess
import uuid
from pathlib import Path

IMAGE = "kindest/node@sha256:4613778f3cfcd10e615029370f5786704559103cf27bef934597ba562b269661"


class Fixture:
    def __init__(self, directory, create=False):
        self.directory = Path(directory).absolute()
        if create:
            self.directory.mkdir(mode=0o700)
        info = self.directory.lstat()
        if not stat.S_ISDIR(info.st_mode) or info.st_uid != os.geteuid() or stat.S_IMODE(info.st_mode) != 0o700:
            raise ValueError("Run directory must be owned by this user with mode 0700")
        self.lock = os.fdopen(os.open(self.directory / "lock", os.O_RDWR | os.O_CREAT | os.O_NOFOLLOW, 0o600), "r+")
        fcntl.flock(self.lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        if create:
            self.state = {"cluster": "cert-fixture-" + uuid.uuid4().hex,
                          "phase": "allocated", "commands": [], "image": IMAGE}
        else:
            self.state = json.loads((self.directory / "state.json").read_text())
        self.config = self.directory / "kubeconfig"
        self.cluster = self.state["cluster"]
        if not re.fullmatch(r"cert-fixture-[0-9a-f]{32}", self.cluster):
            raise ValueError("Invalid recorded cluster identity")
        self.context = "kind-" + self.cluster
        self.tools = {name: shutil.which(name) for name in ("kind", "docker", "kubectl")}
        self.state["tools"] = self.tools
        self.save()
        if not all(self.tools.values()):
            raise ValueError("kind, docker and kubectl must be available on PATH")

    def save(self):
        temporary = self.directory / ("state-" + uuid.uuid4().hex + ".tmp")
        with os.fdopen(os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600), "w") as stream:
            json.dump(self.state, stream, indent=2)
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
        temporary.replace(self.directory / "state.json")

    def run(self, tool, *args, timeout=45):
        entry = {"tool": tool, "args": list(args)}
        self.state["commands"].append(entry)
        self.save()
        try:
            result = subprocess.run([self.tools[tool], *args], capture_output=True, text=True, check=False,
                                    timeout=timeout, env={**os.environ, "KIND_EXPERIMENTAL_PROVIDER": "docker"})
        except (subprocess.TimeoutExpired, InterruptedError):
            entry["error"] = "Client timeout/interruption; underlying work may continue"
            self.save()
            raise
        entry.update(returncode=result.returncode, stdout=result.stdout, stderr=result.stderr)
        self.save()
        if result.returncode:
            raise RuntimeError(f"{tool} failed; inspect private state.json")
        return result.stdout.strip()

    def clusters(self):
        return self.run("kind", "get", "clusters").splitlines()

    def node(self):
        nodes = self.run("kind", "get", "nodes", "--name", self.cluster).splitlines()
        if len(nodes) != 1:
            raise RuntimeError("Expected exactly one owned node; refusing ambiguous identity")
        value = json.loads(self.run("docker", "inspect", nodes[0], "--format",
                                   '{"id":{{json .Id}},"labels":{{json .Config.Labels}},"image":{{json .Image}}}'))
        labels = value["labels"]
        if (not re.fullmatch(r"[0-9a-f]{64}", value["id"])
                or labels.get("io.x-k8s.kind.cluster") != self.cluster
                or labels.get("io.x-k8s.kind.role") != "control-plane"):
            raise RuntimeError("Node identity/ownership labels did not match")
        return value

    def verify(self):
        if not self.state.get("node") or self.cluster not in self.clusters():
            raise RuntimeError("No captured live ownership identity; manual reconciliation required")
        if self.node() != self.state["node"]:
            raise RuntimeError("Recorded container ID, labels or image changed; refusing")

    def api(self, *args):
        return self.run("kubectl", "--kubeconfig", str(self.config), "--context", self.context,
                        "--request-timeout=15s", *args)

    def create(self):
        if self.cluster in self.clusters():
            raise RuntimeError("Cluster collision; no adoption or deletion permitted")
        self.state["local_image"] = self.run("docker", "image", "inspect", IMAGE, "--format", "{{.Id}}")
        self.state.update(phase="creation_requested", kubeconfig=str(self.config), context=self.context)
        self.save()
        self.run("kind", "create", "cluster", "--name", self.cluster, "--image", IMAGE,
                 "--kubeconfig", str(self.config), "--wait", "120s", timeout=300)
        self.state["node"] = self.node()
        self.state["phase"] = "identity_captured"
        self.save()
        if self.state["node"]["image"] != self.state["local_image"]:
            raise RuntimeError("Created node image differs from the required local image")
        self.inspect()
        namespace = "certificate-marker-" + uuid.uuid4().hex
        marker = uuid.uuid4().hex
        self.state.update(marker_namespace=namespace, marker_value=marker)
        self.save()
        self.api("create", "namespace", namespace)
        self.api("-n", namespace, "create", "configmap", "lifecycle-marker", "--from-literal=value=" + marker)
        self.check_marker()
        self.state["phase"] = "ready"
        self.save()

    def check_marker(self):
        observed = json.loads(self.api("-n", self.state["marker_namespace"], "get", "configmap",
                                       "lifecycle-marker", "-o", "json"))
        if observed["data"]["value"] != self.state["marker_value"]:
            raise RuntimeError("Marker read did not match the created value")
        if self.state.get("marker_uid", observed["metadata"]["uid"]) != observed["metadata"]["uid"]:
            raise RuntimeError("Marker object identity changed")
        self.state["marker_uid"] = observed["metadata"]["uid"]

    def inspect(self):
        self.verify()
        versions = json.loads(self.api("version", "-o", "json"))
        if versions["serverVersion"]["gitVersion"] != "v1.35.0":
            raise RuntimeError("Server version is not v1.35.0")
        if self.api("get", "--raw=/readyz") != "ok":
            raise RuntimeError("API readiness was not confirmed")
        system_uid = self.api("get", "namespace", "kube-system", "-o", "jsonpath={.metadata.uid}")
        if not system_uid or self.state.get("system_namespace_uid", system_uid) != system_uid:
            raise RuntimeError("System namespace identity missing or changed")
        inventory = self.run("docker", "exec", self.state["node"]["id"], "sh", "-c",
                             "id -u; for t in openssl kubeadm crictl jq; do command -v \"$t\" || true; done")
        self.state.update(versions=versions, system_namespace_uid=system_uid, tool_inventory=inventory,
                          known_paths={"manifest": "/etc/kubernetes/manifests/kube-apiserver.yaml",
                                       "certificate": "/etc/kubernetes/pki/apiserver.crt"})
        if self.state.get("marker_namespace"):
            self.check_marker()
        self.save()

    def absent(self):
        ids = self.run("docker", "ps", "-a", "--no-trunc", "--format", "{{.ID}}").splitlines()
        return self.cluster not in self.clusters() and self.state["node"]["id"] not in ids

    def delete(self):
        if not self.state.get("node"):
            raise RuntimeError("Creation identity uncaptured; preserve partial creation for reconciliation")
        if self.state["phase"] == "deleted":
            if not self.absent():
                raise RuntimeError("Previously deleted fixture is not absent; refusing")
            return
        if self.state["phase"] != "deletion_requested" or not self.absent():
            self.verify()
            self.state["phase"] = "deletion_requested"
            self.save()
            self.run("kind", "delete", "cluster", "--name", self.cluster,
                     "--kubeconfig", str(self.directory / "delete-kubeconfig"), timeout=180)
        if not self.absent():
            raise RuntimeError("Cluster/container absence unconfirmed; retain private kubeconfig")
        self.config.unlink(missing_ok=True)
        self.state["phase"] = "deleted"
        self.save()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("create", "inspect", "delete"))
    parser.add_argument("run_dir")
    args = parser.parse_args()
    fixture = None

    def interrupted(signum, _frame):
        raise InterruptedError(f"Signal {signum}; client cancellation does not prove node work stopped")

    signal.signal(signal.SIGINT, interrupted)
    signal.signal(signal.SIGTERM, interrupted)
    try:
        fixture = Fixture(args.run_dir, create=args.action == "create")
        getattr(fixture, args.action)()
    except (OSError, ValueError, RuntimeError, KeyError, TypeError, subprocess.SubprocessError) as error:
        if fixture is not None:
            fixture.state["error"] = str(error)
            fixture.save()
        raise SystemExit(str(error)) from None
    finally:
        if fixture is not None:
            fixture.lock.close()


if __name__ == "__main__":
    main()
