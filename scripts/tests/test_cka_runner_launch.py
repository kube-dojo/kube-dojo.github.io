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
