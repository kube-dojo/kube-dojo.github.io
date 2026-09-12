"""Runner launch gate refusals with injected custody; not kind renewal proof."""
import subprocess
import unittest
from pathlib import Path


class TestRunnerLaunch(unittest.TestCase):
    def setUp(self):
        self.root = Path(__file__).resolve().parents[2]

    def bash(self, script):
        return subprocess.run(
            [
                "bash",
                "-c",
                script,
                "--",
                str(self.root / "scripts/cka_certificate_state.sh"),
                str(self.root / "scripts/cka_certificate_process.sh"),
            ],
            capture_output=True,
            text=True,
            check=False,
            timeout=5,
        )

    def test_launch_helpers_defined(self):
        result = self.bash(
            r"""
source "$1"; source "$2"
declare -F cka_cert_runner_launch_actual >/dev/null
declare -F cka_cert_runner_launch >/dev/null
"""
        )
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_launch_actual_refuses_without_custody(self):
        result = self.bash(
            r"""
source "$1"; source "$2"
unset CKA_CERT_STATE_OWNS_FD
CKA_CERT_SUPERVISOR_TERM=0
# argc>=6 but no FD ownership
if cka_cert_runner_launch_actual 10000 id op '{}' '{}' /bin/true; then exit 1; fi
"""
        )
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_launch_wrapper_closes_control_on_refusal(self):
        result = self.bash(
            r"""
source "$1"; source "$2"
CKA_CERT_STATE_OWNS_FD=1
CKA_CERT_SUPERVISOR_TERM=0
CKA_CERT_CONTROL_OWNER=$BASHPID
closed=0
cka_cert_control_close() { closed=1; return 0; }
cka_cert_runner_launch_actual() { return 7; }
cka_cert_runner_launch 10000 id op '{}' '{}' /bin/true
[[ $? == 7 && $closed == 1 ]]
"""
        )
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_launch_actual_closes_on_term_after_open(self):
        """Post-open SUPERVISOR_TERM refusal must release FD8 custody."""
        result = self.bash(
            r"""
source "$1"; source "$2"
CKA_CERT_STATE_OWNS_FD=1
CKA_CERT_SUPERVISOR_TERM=0
close_count=0
cka_cert_control_locked() { return 0; }
cka_cert_run_read_helper() {
  # before + ready wait + live + supervisor_ready permission
  return 0
}
cka_cert_capture() {
  case $3 in
    jq)
      shift 3
      if [[ $* == *--args* ]]; then CKA_CERT_CAPTURED='["/bin/true"]'
      elif [[ $* == *.pid* ]]; then CKA_CERT_CAPTURED=$BASHPID
      elif [[ $* == *.start_time* ]]; then CKA_CERT_CAPTURED=1
      elif [[ $* == *supervisor* && $* == *runner* ]]; then
        CKA_CERT_CAPTURED="{\"supervisor\":{\"pid\":$BASHPID},\"runner\":{\"pid\":1,\"start_time\":\"1\"},\"argv\":[\"/bin/true\"]}"
      elif [[ $* == *presence* ]]; then CKA_CERT_CAPTURED='{"presence":"present"}'
      elif [[ $* == *command_launch_committed* ]]; then CKA_CERT_CAPTURED='{"stage":"command_launch_committed"}'
      else CKA_CERT_CAPTURED=1; fi
      return 0
      ;;
    *) return 1 ;;
  esac
}
cka_cert_process_self() { return 0; }
cka_cert_process_stat() {
  CKA_CERT_PROC_PPID=$BASHPID; CKA_CERT_PROC_SID=$BASHPID
  CKA_CERT_PROC_PGID=$BASHPID; CKA_CERT_PROC_STATE=S; CKA_CERT_PROC_START=1
}
cka_cert_control_close() { close_count=$((close_count + 1)); unset CKA_CERT_CONTROL_OWNER; return 0; }
cka_cert_control_open() { CKA_CERT_CONTROL_OWNER=$BASHPID; CKA_CERT_SUPERVISOR_TERM=1; return 0; }
cka_cert_runner_body() { sleep 0.05; }
# Avoid waiting on ready forever: make ready read succeed immediately via run_read_helper.
if cka_cert_runner_launch_actual 10000 id op "{\"pid\":$BASHPID,\"start_time\":\"1\"}" '{}' /bin/true; then
  echo unexpected-success; exit 1
fi
[[ $close_count -ge 1 && -z ${CKA_CERT_CONTROL_OWNER:-} ]]
"""
        )
        self.assertEqual(result.returncode, 0, result.stderr)

