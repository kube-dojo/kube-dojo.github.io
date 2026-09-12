"""Runner live/read helpers with injected process identity; not Linux custody proof."""
import json
import subprocess
import tempfile
import unittest
from pathlib import Path


class TestRunnerLiveRead(unittest.TestCase):
    def setUp(self):
        self.identity = {
            "transaction_id": "a" * 32,
            "fixture_cluster": "cert-fixture-" + "b" * 32,
            "docker_container_id": "c" * 64,
            "image_id": "sha256:" + "d" * 64,
            "system_namespace_uid": "12345678-1234-1234-1234-123456789abc",
            "artifact_hashes": {
                name + ".sh": "e" * 64 for name in ("state", "observe", "process")
            },
        }
        self.operation = "f" * 32
        self.binding = {
            "supervisor": {"pid": 21, "pgid": 21, "sid": 21, "start_time": "123"},
            "runner": {"pid": 22, "start_time": "124"},
            "argv": ["/bin/true"],
        }

    def live(self, binding=None, child="null", mutate=""):
        root = Path(__file__).resolve().parents[2]
        result = subprocess.run(
            [
                "bash",
                "-c",
                r"""
source "$1"; source "$2"
binding=$3; child=$4
cka_cert_process_stat() {
  case $1 in
    21) CKA_CERT_PROC_STATE=S; CKA_CERT_PROC_PPID=1; CKA_CERT_PROC_PGID=21
        CKA_CERT_PROC_SID=21; CKA_CERT_PROC_START=123 ;;
    22) CKA_CERT_PROC_STATE=S; CKA_CERT_PROC_PPID=21; CKA_CERT_PROC_PGID=21
        CKA_CERT_PROC_SID=21; CKA_CERT_PROC_START=124 ;;
    23) CKA_CERT_PROC_STATE=S; CKA_CERT_PROC_PPID=22; CKA_CERT_PROC_PGID=21
        CKA_CERT_PROC_SID=21; CKA_CERT_PROC_START=125 ;;
    *) return 1 ;;
  esac
}
eval "$5"
cka_cert_runner_live "$binding" "$child"
""",
                "--",
                str(root / "scripts/cka_certificate_state.sh"),
                str(root / "scripts/cka_certificate_process.sh"),
                json.dumps(binding or self.binding),
                child,
                mutate,
            ],
            capture_output=True,
            text=True,
            check=False,
            timeout=5,
        )
        return result.returncode

    def test_live_accepts_matching_tree(self):
        self.assertEqual(self.live(), 0)
        self.assertEqual(self.live(child='{"pid":23,"start_time":"125"}'), 0)

    def test_live_rejects_mismatched_identity(self):
        bad = dict(self.binding, runner={"pid": 22, "start_time": "999"})
        self.assertNotEqual(self.live(binding=bad), 0)
        self.assertNotEqual(self.live(child='{"pid":23,"start_time":"999"}'), 0)
        self.assertNotEqual(
            self.live(mutate='cka_cert_process_stat() { CKA_CERT_PROC_STATE=Z; return 0; }'),
            0,
        )

    def test_read_validates_on_disk_record(self):
        root = Path(__file__).resolve().parents[2]
        process = (root / "scripts/cka_certificate_process.sh").read_text()
        with tempfile.TemporaryDirectory() as temporary:
            base = Path(temporary)
            library = base / "process.sh"
            library.write_text(
                process.replace("/var/lib/cka-certificate-transaction", str(base))
            )
            record = {
                **self.binding,
                "schema": 1,
                "identity": self.identity,
                "operation_id": self.operation,
                "kind": "ready",
                "child": None,
            }
            path = base / "runner-ready.json"
            path.write_text(json.dumps(record))
            path.chmod(0o600)
            result = subprocess.run(
                [
                    "bash",
                    "-c",
                    r"""
source "$1"; source "$2"
cka_cert_process_check() { [[ $# == 2 ]]; }
cka_cert_state_file() { [[ -f $1 && ! -L $1 ]]; }
cka_cert_runner_read "$3" "$4" "$5" ready
""",
                    "--",
                    str(root / "scripts/cka_certificate_state.sh"),
                    str(library),
                    json.dumps(self.identity),
                    self.operation,
                    json.dumps(self.binding),
                ],
                capture_output=True,
                text=True,
                check=False,
                timeout=5,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(json.loads(result.stdout), record)
            # Missing file refuses.
            path.unlink()
            missing = subprocess.run(
                [
                    "bash",
                    "-c",
                    r"""
source "$1"; source "$2"
cka_cert_process_check() { [[ $# == 2 ]]; }
cka_cert_state_file() { [[ -f $1 && ! -L $1 ]]; }
cka_cert_runner_read "$3" "$4" "$5" ready
""",
                    "--",
                    str(root / "scripts/cka_certificate_state.sh"),
                    str(library),
                    json.dumps(self.identity),
                    self.operation,
                    json.dumps(self.binding),
                ],
                capture_output=True,
                text=True,
                check=False,
                timeout=5,
            )
            self.assertNotEqual(missing.returncode, 0)
