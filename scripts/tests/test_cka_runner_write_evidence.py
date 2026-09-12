"""Runner write/evidence helpers with injected custody; not kind renewal proof."""
import json
import subprocess
import tempfile
import unittest
from pathlib import Path


class TestRunnerWriteEvidence(unittest.TestCase):
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
        self.root = Path(__file__).resolve().parents[2]

    def bash(self, script, *args, library=None):
        return subprocess.run(
            ["bash", "-c", script, "--",
             str(self.root / "scripts/cka_certificate_state.sh"),
             str(library or self.root / "scripts/cka_certificate_process.sh"), *args],
            capture_output=True, text=True, check=False, timeout=8,
        )

    def test_record_and_evidence(self):
        result = self.bash(
            r'''
source "$1"; source "$2"
CKA_CERT_STATE_OWNS_FD=1
cka_cert_capture() { shift 2; "$@"; CKA_CERT_CAPTURED=$(cat); }
cka_cert_runner_record 10000 "$3" "$4" "$5" ready null
printf '%s' "$CKA_CERT_CAPTURED"
''',
            json.dumps(self.identity), self.operation, json.dumps(self.binding),
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        payload = json.loads(result.stdout)
        self.assertEqual((payload["schema"], payload["kind"], payload["child"]), (1, "ready", None))

        child = {"pid": 23, "start_time": "125"}
        birth = {**self.binding, "schema": 1, "identity": self.identity,
                 "operation_id": self.operation, "kind": "birth", "child": child}
        entry = dict(birth, kind="entry")
        ok = self.bash(
            r'''
source "$1"; source "$2"
birth_json=$3; entry_json=$4
cka_cert_runner_read() {
  case $4 in birth) printf '%s' "$birth_json" ;; entry) printf '%s' "$entry_json" ;; *) return 1 ;; esac
}
cka_cert_runner_evidence id op '{}'
''',
            json.dumps(birth), json.dumps(entry),
        )
        self.assertEqual(ok.returncode, 0, ok.stderr)
        self.assertEqual(json.loads(ok.stdout), child)

    def test_write_publishes_exclusive_ready_record(self):
        process = (self.root / "scripts/cka_certificate_process.sh").read_text()
        with tempfile.TemporaryDirectory() as temporary:
            base = Path(temporary)
            library = base / "process.sh"
            library.write_text(process.replace("/var/lib/cka-certificate-transaction", str(base)))
            payload = {**self.binding, "schema": 1, "identity": self.identity,
                       "operation_id": self.operation, "kind": "ready", "child": None}
            result = self.bash(
                r'''
source "$1"; source "$2"
root=$3; payload=$4; CKA_CERT_STATE_OWNS_FD=1
cka_cert_deadline_budget() { [[ $1 == 10000 ]]; }
cka_cert_capture() {
  local deadline=$1 mode=$2; shift 2
  case $mode:$1 in
    read:cka_cert_runner_payload) shift; CKA_CERT_CAPTURED=$5 ;;
    utility:jq|utility:mktemp) CKA_CERT_CAPTURED=$(command "$@") || return $? ;;
    *) return 1 ;;
  esac
}
cka_cert_run_read_helper() {
  shift
  case $1 in
    cka_cert_runner_live|cka_cert_process_check|cka_cert_state_descriptor) ;;
    cka_cert_state_file) [[ -f $2 ]] ;;
    cka_cert_runner_read) cat -- "$root/runner-ready.json" ;;
    *) return 1 ;;
  esac
}
cka_cert_run_utility() {
  shift; [[ $1 == -- ]] || return 1; shift
  case $1 in
    flock|sync) ;;
    unlink) command unlink -- "$3" ;;
    ln) shift; while [[ ${1:-} == -T || ${1:-} == -- ]]; do shift; done; command ln "$1" "$2" ;;
    *) return 1 ;;
  esac
}
pid=$BASHPID
payload=$(jq -c --argjson pid "$pid" '.runner.pid=$pid' <<< "$payload")
cka_cert_runner_write 10000 "$5" "$6" "$7" ready "$payload"
jq -e --argjson want "$payload" '.==$want' < "$root/runner-ready.json" >/dev/null
''',
                str(base), json.dumps(payload), json.dumps(self.identity),
                self.operation, json.dumps(self.binding), library=library,
            )
            self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
