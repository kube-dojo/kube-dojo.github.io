"""Runner before-permission gate with injected process records; not kind renewal."""
import json
import subprocess
import unittest
from pathlib import Path


class TestRunnerBefore(unittest.TestCase):
    def test_before_accepts_matching_supervisor_ready(self):
        root = Path(__file__).resolve().parents[2]
        before = {
            "stage": "supervisor_ready",
            "supervisor": {"pid": 21, "pgid": 21, "sid": 21, "start_time": "123"},
            "cancel_ack": False,
            "cause": "none",
        }
        supervisor = before["supervisor"]
        result = subprocess.run(
            [
                "bash",
                "-c",
                r"""
source "$1"; source "$2"
# Avoid shadowing before()'s local `observed`.
record_json=$3; supervisor_json=$4
cka_cert_process_check() { [[ $# == 2 ]]; }
cka_cert_process_read() { printf '%s' "$record_json"; }
cka_cert_process_cancel_read() { CKA_CERT_PROCESS_CANCEL=0; }
cka_cert_runner_before id op "$supervisor_json" "$record_json"
""",
                "--",
                str(root / "scripts/cka_certificate_state.sh"),
                str(root / "scripts/cka_certificate_process.sh"),
                json.dumps(before),
                json.dumps(supervisor),
            ],
            capture_output=True,
            text=True,
            check=False,
            timeout=5,
        )
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_before_rejects_wrong_stage(self):
        root = Path(__file__).resolve().parents[2]
        before = {
            "stage": "command_launch_committed",
            "supervisor": {"pid": 21, "pgid": 21, "sid": 21, "start_time": "123"},
            "cancel_ack": False,
            "cause": "none",
        }
        result = subprocess.run(
            [
                "bash",
                "-c",
                r"""
source "$1"; source "$2"
record_json=$3; supervisor_json=$4
cka_cert_process_check() { [[ $# == 2 ]]; }
cka_cert_process_read() { printf '%s' "$record_json"; }
cka_cert_process_cancel_read() { CKA_CERT_PROCESS_CANCEL=0; }
cka_cert_runner_before id op "$supervisor_json" "$record_json"
""",
                "--",
                str(root / "scripts/cka_certificate_state.sh"),
                str(root / "scripts/cka_certificate_process.sh"),
                json.dumps(before),
                json.dumps(before["supervisor"]),
            ],
            capture_output=True,
            text=True,
            check=False,
            timeout=5,
        )
        self.assertNotEqual(result.returncode, 0)

    def test_body_and_before_are_defined(self):
        root = Path(__file__).resolve().parents[2]
        result = subprocess.run(
            [
                "bash",
                "-c",
                r'''
source "$1"; source "$2"
declare -F cka_cert_runner_body >/dev/null
declare -F cka_cert_runner_before >/dev/null
''',
                "--",
                str(root / "scripts/cka_certificate_state.sh"),
                str(root / "scripts/cka_certificate_process.sh"),
            ],
            capture_output=True,
            text=True,
            check=False,
            timeout=5,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
