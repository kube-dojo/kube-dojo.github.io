"""Runner wait_candidate + entry gates with injected custody; not kind renewal."""
import json
import subprocess
import unittest
from pathlib import Path


class TestRunnerEntryWait(unittest.TestCase):
    def setUp(self):
        self.root = Path(__file__).resolve().parents[2]
        self.binding = {
            "supervisor": {"pid": 21, "pgid": 21, "sid": 21, "start_time": "123"},
            "runner": {"pid": 22, "start_time": "124"},
            "argv": ["/bin/true"],
        }

    def bash(self, script, *args):
        return subprocess.run(
            [
                "bash",
                "-c",
                script,
                "--",
                str(self.root / "scripts/cka_certificate_state.sh"),
                str(self.root / "scripts/cka_certificate_process.sh"),
                *args,
            ],
            capture_output=True,
            text=True,
            check=False,
            timeout=8,
        )

    def test_wait_candidate_records_child_exit(self):
        result = self.bash(
            r"""
source "$1"; source "$2"
set +o posix; set +m
CKA_CERT_WAIT_GENERATION=0
(exit 42) &
child=$!
cka_cert_runner_wait_candidate "$child" || exit 1
[[ $CKA_CERT_WAIT_EXIT == 42 ]]
"""
        )
        self.assertEqual(result.returncode, 0, result.stderr)


    def test_entry_enforces_bash_52_and_argv(self):
        birth = {
            **self.binding,
            "schema": 1,
            "kind": "birth",
            "child": {"pid": 23, "start_time": "125"},
            "identity": {"transaction_id": "a" * 32},
            "operation_id": "f" * 32,
        }
        result = self.bash(
            r"""
source "$1"; source "$2"
binding=$3
birth_json=$4
CKA_CERT_STATE_OWNS_FD=1
cka_cert_deadline_budget() { [[ $1 == 10000 ]]; }
cka_cert_capture() {
  local deadline=$1 mode=$2; shift 2
  case $mode:$1 in
    utility:jq) CKA_CERT_CAPTURED=$(command "$@") || return $? ;;
    read:cka_cert_runner_read) CKA_CERT_CAPTURED=$birth_json ;;
    *) return 1 ;;
  esac
}
cka_cert_runner_record() {
  CKA_CERT_CAPTURED=$(jq -cn --argjson binding "$4" --arg kind "$5" --argjson child "$6" \
    '$binding+{schema:1,kind:$kind,child:$child}')
}
cka_cert_runner_write() { [[ $5 == entry && -n $6 ]]; }
if cka_cert_runner_entry 10000 id op "$binding" /bin/echo ok; then
  printf 'ran:%s.%s\n' "${BASH_VERSINFO[0]}" "${BASH_VERSINFO[1]}"
else
  printf 'refuse:%s.%s\n' "${BASH_VERSINFO[0]}" "${BASH_VERSINFO[1]}"
fi
""",
            json.dumps(self.binding),
            json.dumps(birth),
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        major, minor = result.stdout.strip().split(":")[1].split(".")
        if (major, minor) == ("5", "2"):
            self.assertTrue(result.stdout.startswith("ran:"), result.stdout)
        else:
            self.assertTrue(result.stdout.startswith("refuse:"), result.stdout)
