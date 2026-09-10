"""Dispatch tests with a fake timeout; no GNU-timeout or Linux custody proof."""
import os
import subprocess
import tempfile
import unittest
from pathlib import Path


class TestDeadlineHelper(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.directory = Path(temporary.name)
        self.log = self.directory / "calls"
        fake = self.directory / "timeout"
        fake.write_text('''#!/bin/bash
printf 'CALL\\0' >> "$TIMEOUT_LOG"
printf '%s\\0' "$@" >> "$TIMEOUT_LOG"
if [[ $FD_PROBE == 1 ]]; then
  if (printf leaked >&8) 2>/dev/null; then printf FD8_LEAK; fi
  printf child9 >&9 || exit 98
fi
exit "$FAKE_STATUS"
''')
        fake.chmod(0o700)

    def invoke(self, command, clocks="0 1", status=0, probe=False):
        library = Path(__file__).resolve().parents[1] / "cka_certificate_process.sh"
        self.log.write_bytes(b"")
        environment = dict(os.environ, PATH=str(self.directory) + os.pathsep + os.environ["PATH"],
                           TIMEOUT_LOG=str(self.log), FAKE_STATUS=str(status), FD_PROBE=str(int(probe)),
                           CLOCK_VALUES=clocks, FD8_FILE=str(self.directory / "fd8"),
                           FD9_FILE=str(self.directory / "fd9"))
        result = subprocess.run(["bash", "-c", r'''
source "$1"; shift
read -ra clock_values <<< "$CLOCK_VALUES"; clock_i=0
cka_cert_process_now() {
  local value=${clock_values[$clock_i]:-fail}; clock_i=$((clock_i + 1))
  [[ $value != fail ]] || return 1
  CKA_CERT_PROCESS_NOW=$value
}
chain() { cka_cert_run_utility "$@" || return $?; cka_cert_run_utility "$@"; }
if [[ $FD_PROBE == 1 ]]; then exec 8>"$FD8_FILE" 9>"$FD9_FILE"; fi
if "$@"; then result=0; else result=$?; fi
if [[ $FD_PROBE == 1 ]]; then printf parent8 >&8; printf parent9 >&9; fi
printf '%s|%s' "$result" "${CKA_CERT_DEADLINE_SOFT:-unset}"
''', "--", str(library), *command], env=environment, capture_output=True, text=True, check=False)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stderr, "")
        calls = [] if not self.log.exists() else [
            [argument.decode() for argument in call.split(b"\0")[:-1]]
            for call in self.log.read_bytes().split(b"CALL\0")[1:]]
        return result.stdout, calls

    def test_budget_validation_and_grace_boundaries(self):
        cases = [("100", "69", "0|0.01s"), ("100", "70", "124|unset"),
                 ("100", "100", "124|unset"), ("100", "101", "124|unset"),
                 ("00100", "0", "0|0.70s"), ("250", "100", "0|1.20s"),
                 ("999999999999999", "0", "0|9999999999999.69s"), ("100", "fail", "1|unset")]
        cases += [(value, "0", "1|unset") for value in ("", "-1", "1.0", "bad", "1" * 16)]
        for deadline, clock, expected in cases:
            with self.subTest(deadline=deadline, clock=clock):
                self.assertEqual(self.invoke(["cka_cert_deadline_budget", deadline], clock), (expected, []))

    def test_expired_and_forbidden_dispatch_never_launches(self):
        cases = [(["cka_cert_run_utility", "30", "--", "cat"], "124|unset"),
                 (["cka_cert_run_utility", "100", "--", "bash"], "1|unset"),
                 (["cka_cert_run_utility", "100", "missing-separator", "cat"], "1|unset")]
        cases += [(["cka_cert_run_read_helper", "100", function], "1|unset") for function in
                  ("cka_cert_process_write", "cka_cert_supervisor_receipt_write", "cka_cert_state_backup")]
        for command, expected in cases:
            with self.subTest(command=command):
                self.assertEqual(self.invoke(command), (expected, []))

    def test_late_zero_original_status_and_dispatch_arguments(self):
        for status, after, expected in ((0, 99, 0), (0, 100, 124), (37, 99, 37), (124, 99, 124), (0, "fail", 1)):
            with self.subTest(status=status, after=after):
                output, calls = self.invoke(["cka_cert_run_utility", "100", "--", "cat", "two words"], f"0 {after}", status)
                self.assertEqual(output, f"{expected}|0.70s")
                self.assertEqual(calls, [["--foreground", "--kill-after=0.25s", "0.70s", "cat", "two words"]])
        output, calls = self.invoke(["cka_cert_run_read_helper", "100", "cka_cert_process_read", "identity", "operation"])
        self.assertEqual(output, "0|0.70s")
        self.assertEqual(len(calls), 1)
        self.assertEqual(calls[-1][:4], ["--foreground", "--kill-after=0.25s", "0.70s", "env"])
        self.assertEqual(calls[-1][-3:], ["cka_cert_process_read", "identity", "operation"])

    def test_shared_deadline_and_descriptor_inheritance(self):
        output, calls = self.invoke(["chain", "100", "--", "cat"], "0 50 50 75", probe=True)
        self.assertEqual(output, "0|0.20s")
        self.assertEqual([call[2] for call in calls], ["0.70s", "0.20s"])
        self.assertEqual((self.directory / "fd8").read_text(), "parent8")
        self.assertEqual((self.directory / "fd9").read_text(), "child9child9parent9")


if __name__ == "__main__":
    unittest.main()
