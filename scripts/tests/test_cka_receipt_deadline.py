"""Portable orchestration probes with injected identity; not Linux custody proof."""
import subprocess
import tempfile
import time
import unittest
from pathlib import Path


class TestReceiptDeadline(unittest.TestCase):
    def probe(self, failure="none", status=124):
        source = Path(__file__).resolve().parents[1] / "cka_certificate_process.sh"
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            library = root / "writer.sh"
            library.write_text(source.read_text().replace("/var/lib/cka-certificate-transaction", str(root)))
            started = time.monotonic()
            result = subprocess.run(["bash", "-c", r'''
source "$1"; root=$2; failure=$3; failure_status=$4; sync_count=0
CKA_CERT_STATE_OWNS_FD=1; writer=$BASHPID
check() { [[ $1 == 10000 ]] || return 97; printf '%s\n' "$2" >> "$root/log"; }
cka_cert_deadline_budget() { check "$1" budget; }
cka_cert_process_stat() {
  CKA_CERT_PROC_START=42; CKA_CERT_PROC_PGID=21; CKA_CERT_PROC_SID=21; CKA_CERT_PROC_PPID=21
  [[ $1 == 21 || $1 == "$writer" ]] || return 96
}
cka_cert_run_read_helper() {
  check "$1" "$2" || return $?; shift
  [[ $failure != "$1" ]] || return "$failure_status"
  case $1 in
    cka_cert_supervisor_receipt_payload)
      case $failure in
        descendant) sleep 4 & return 124 ;;
        oversized) printf '%65537s\n' x ;;
        nul) printf 'before\0after\n' ;;
        multiline) printf 'first\nsecond\n' ;;
        *) printf '%s\n' "$6" ;;
      esac ;;
    cka_cert_supervisor_receipt_read) cat "$root/command.json" ;;
  esac
}
cka_cert_run_utility() {
  check "$1" "$3" || return $?; [[ $2 == -- ]] || return 95; shift 2
  case $1 in
    flock) [[ $failure != flock ]] || return "$failure_status" ;;
    jq) command "$@" || return $? ;;
    mktemp) command "$@" || return $? ;;
    sync) sync_count=$((sync_count + 1))
      [[ $failure != "sync$sync_count" ]] || return "$failure_status" ;;
    ln) command ln "$4" "$5" || return $? ;;
    unlink) command unlink "$3" || return $? ;;
    *) return 94 ;;
  esac
  [[ $failure != "$1" ]] || return "$failure_status"
}
runner=$(printf '{"pid":%s,"start_time":"42"}' "$writer")
[[ $failure != identity ]] || runner='{"pid":1,"start_time":"42"}'
if cka_cert_supervisor_receipt_write 10000 '{}' operation \
  '{"pid":21,"start_time":"42"}' "$runner" payload; then result=0; else result=$?; fi
printf '%s' "$result"
''', "--", str(library), str(root), failure, str(status)], capture_output=True, text=True, check=False, timeout=6)
            elapsed = time.monotonic() - started
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(result.stderr, "")
            paths = list(root.glob("command.*"))
            residue = {path.name: (path.read_text(), path.stat().st_nlink) for path in paths}
            if failure in ("descendant", "oversized", "nul", "multiline"):
                self.assertEqual(len(list(root.glob("capture.*"))), 1)
            if failure == "descendant":
                self.assertLess(elapsed, 2, "writer waited for surviving descendant output EOF")
            return int(result.stdout), (root / "log").read_text().splitlines(), residue

    def test_direct_writer_and_shared_deadline(self):
        status, calls, residue = self.probe()
        self.assertEqual(status, 0)
        self.assertEqual(calls.count("jq"), 4)
        self.assertLess(calls.index("flock"), calls.index("mktemp"))
        self.assertEqual(calls[-1], "cka_cert_supervisor_receipt_read")
        self.assertEqual(residue, {"command.json": ("payload\n", 1)})

    def test_refusal_before_publication(self):
        for failure in ("cka_cert_capture_directory", "cka_cert_supervisor_receipt_payload", "cka_cert_process_check",
                        "cka_cert_state_descriptor", "flock", "identity"):
            with self.subTest(failure=failure):
                status, calls, residue = self.probe(failure)
                self.assertEqual(status, 1 if failure == "identity" else 124)
                self.assertNotIn("mktemp", calls)
                self.assertEqual(residue, {})

    def test_capture_rejects_unbounded_or_nontext_output(self):
        for failure in ("descendant", "oversized", "nul", "multiline"):
            with self.subTest(failure=failure):
                status, calls, residue = self.probe(failure)
                self.assertEqual(status, 124 if failure == "descendant" else 1)
                self.assertNotIn("cka_cert_process_check", calls)
                self.assertEqual(residue, {})

    def test_late_publication_preserves_status_and_residue(self):
        for failure, count, links in (("sync1", 1, 1), ("ln", 2, 2), ("unlink", 1, 1),
                                      ("sync2", 1, 1), ("cka_cert_supervisor_receipt_read", 1, 1)):
            for expected_status in (124, 37):
                with self.subTest(failure=failure, status=expected_status):
                    status, calls, residue = self.probe(failure, expected_status)
                    self.assertEqual(status, expected_status)
                    self.assertEqual(len(residue), count)
                    self.assertTrue(all(value == ("payload\n", links) for value in residue.values()))
                    self.assertEqual("command.json" in residue, failure != "sync1")
                    self.assertEqual(calls[-1], "sync" if failure.startswith("sync") else failure)


if __name__ == "__main__":
    unittest.main()
