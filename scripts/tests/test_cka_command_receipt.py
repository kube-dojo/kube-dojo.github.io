"""Receipt schema and prevalidation; live custody is verified separately."""
import json
import subprocess
import unittest
from pathlib import Path


class TestCommandReceipt(unittest.TestCase):
    def setUp(self):
        self.identity = {"fixture": "expected"}
        self.operation = "a" * 32
        self.supervisor = {"pid": 21, "pgid": 21, "sid": 21, "start_time": "123"}
        self.runner = {"pid": 22, "start_time": "124"}
        self.receipt = {"schema": 1, "identity": self.identity, "operation_id": self.operation,
                        "supervisor": self.supervisor, "runner": self.runner,
                        "child_pid": 23, "exit_code": 0}

    def check_receipt(self, value, accepted, method="payload", raw=False, custody=False, count=5, **expected):
        library = Path(__file__).resolve().parents[1] / "cka_certificate_process.sh"
        arguments = [json.dumps(expected.get("identity", self.identity)),
                     expected.get("operation", self.operation),
                     json.dumps(expected.get("supervisor", self.supervisor)),
                     json.dumps(expected.get("runner", self.runner)),
                     value if raw else json.dumps(value)]
        arguments = (["10000"] if method == "write" else []) + arguments[:count]
        result = subprocess.run(["bash", "-c", r'''
source "$1"; method=$2; shift 2
CKA_CERT_STATE_OWNS_FD=1
cka_cert_run_read_helper() { [[ $1 == 10000 ]] || return 97; shift; "$@"; }
cka_cert_capture() { [[ $1 == 10000 && $2 == read ]] || return 97; shift 2; CKA_CERT_CAPTURED=$("$@"); }
cka_cert_state_expected() { printf '%s\n' "$1"; }
cka_cert_process_check() { printf REACHED_CUSTODY >&2; return 1; }
mktemp() { printf REACHED_MKTEMP >&2; return 1; }
if "cka_cert_supervisor_receipt_$method" "$@" >/dev/null; then
  printf accepted
else printf refused; fi
''', "--", str(library), method, *arguments], capture_output=True, text=True, check=False)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout, "accepted" if accepted else "refused")
        self.assertNotIn("REACHED_MKTEMP", result.stderr)
        if custody:
            self.assertIn("REACHED_CUSTODY", result.stderr)
        else:
            self.assertNotIn("REACHED_CUSTODY", result.stderr)

    def test_valid_exit_boundaries_and_writer_validation_control(self):
        for status in (0, 42, 255):
            with self.subTest(status=status):
                self.check_receipt(dict(self.receipt, exit_code=status), True)
        # A valid payload reaches our refusing custody stub; no filesystem call occurs.
        self.check_receipt(self.receipt, False, method="write", custody=True)
        self.check_receipt(self.receipt, False, method="read")  # Read rejects five arguments.
        self.check_receipt(self.receipt, False, method="read", count=4, custody=True)
        for method in ("payload", "write"):
            self.check_receipt(self.receipt, False, method=method, count=4)

    def test_invalid_payloads_refuse_before_writer_custody_or_mktemp(self):
        invalid = [None, [], {}, dict(self.receipt, extra=True), dict(self.receipt, schema=2),
                   dict(self.receipt, identity={"foreign": 1}), dict(self.receipt, operation_id="b" * 32),
                   dict(self.receipt, supervisor=None), dict(self.receipt, runner=None)]
        invalid += [{k: v for k, v in self.receipt.items() if k != key} for key in self.receipt]
        invalid += [dict(self.receipt, exit_code=v) for v in (-1, 256, 0.5, "0", None, True)]
        invalid += [dict(self.receipt, child_pid=v) for v in (0, -1, 1.5, "23", None, True)]
        for value in invalid:
            for method in ("payload", "write"):
                with self.subTest(value=value, method=method):
                    self.check_receipt(value, False, method=method)
        for value in ("{", json.dumps(self.receipt) + "\n" + json.dumps(self.receipt)):
            for method in ("payload", "write"):
                with self.subTest(raw=value, method=method):
                    self.check_receipt(value, False, method=method, raw=True)

    def test_independently_supplied_expected_identities(self):
        mismatches = [{"identity": {"foreign": 1}}, {"operation": "bad"}, {"operation": "b" * 32},
                      {"supervisor": dict(self.supervisor, start_time="999")},
                      {"runner": dict(self.runner, pid=99)}, {"runner": dict(self.runner, start_time="999")}]
        for expected in mismatches:
            for method in ("payload", "write"):
                with self.subTest(expected=expected, method=method):
                    self.check_receipt(self.receipt, False, method=method, **expected)
        for field, original in (("supervisor", self.supervisor), ("runner", self.runner)):
            malformed = [None, [], dict(original, extra=True), dict(original, pid=True),
                         dict(original, start_time=123), dict(original, start_time="-1")]
            malformed += [{k: v for k, v in original.items() if k != key} for key in original]
            if field == "supervisor":
                malformed += [dict(original, pgid=99), dict(original, sid=99)]
            for value in malformed:
                for method in ("payload", "write"):
                    with self.subTest(field=field, value=value, method=method):
                        self.check_receipt(dict(self.receipt, **{field: value}), False,
                                           method=method, **{field: value})


if __name__ == "__main__":
    unittest.main()
