"""Owned disposable etcd fixture helpers; lifecycle reuses certificate Fixture. No restore."""
from __future__ import annotations

import argparse
import importlib.util
import json
import re
import signal
import subprocess
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


class EtcdFixture:
    """Compose the owned kind fixture; add etcd topology capture only."""

    def __init__(self, directory, create=False):
        self.inner = Fixture(directory, create=create)

    def __getattr__(self, name):
        return getattr(self.inner, name)

    def etcd_inspect(self):
        self.inner.verify()
        self.inner.inspect()
        node_id = self.inner.state["node"]["id"]
        inventory = self.inner.run(
            "docker",
            "exec",
            node_id,
            "sh",
            "-c",
            "command -v etcdctl; command -v etcdutl; "
            f"test -d {ETCD_DATA} && test -d {ETCD_PKI} && echo paths_ok",
        )
        version = self.inner.run(
            "docker",
            "exec",
            node_id,
            "sh",
            "-c",
            "etcdctl version 2>/dev/null | head -1 || true",
        )
        if version and not re.search(r"etcdctl\s+version:\s*3\.", version):
            # Fall back to recording raw output; refuse empty inventry.
            pass
        if "paths_ok" not in inventory:
            raise RuntimeError("etcd data/pki paths missing on owned node")
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


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("create", "inspect", "etcd-inspect", "delete"))
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
