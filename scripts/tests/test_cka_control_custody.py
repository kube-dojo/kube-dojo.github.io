"""Portable Bash descriptor tests; injected statuses do not prove Linux inode/flock custody."""
import subprocess
import tempfile
import unittest
from pathlib import Path


class TestControlCustody(unittest.TestCase):
    def run_case(self, body, control="", inherited=""):
        library = Path(__file__).resolve().parents[1] / "cka_certificate_process.sh"
        # Darwin FD entries are not symlinks: adapt Linux's FD-existence -L to -e.
        # Real FD duplication/closure is exercised; inode validation remains stubbed.
        code = library.read_text().replace("/proc/$BASHPID/fd", "/dev/fd").replace(
            "/var/lib/cka-certificate-transaction/control.lock", '"$CONTROL_FILE"').replace("-L /dev/fd/", "-e /dev/fd/")
        stubs = r'''
helper_calls=0; descriptor_calls=0
cka_cert_run_read_helper() { helper_calls=$((helper_calls + 1)); return "${HELPER_RESULT:-0}"; }
cka_cert_deadline_budget() { return "${BUDGET_RESULT:-0}"; }
cka_cert_control_acquire() { return "${ACQUIRE_RESULT:-0}"; }
cka_cert_control_descriptor() {
  descriptor_calls=$((descriptor_calls + 1))
  if (( descriptor_calls == 1 )); then return "${DESCRIPTOR_FIRST:-0}"; fi
  return "${DESCRIPTOR_AFTER:-0}"
}
fd8_open() { ( : >&8 ) 2>/dev/null; }
'''
        with tempfile.TemporaryDirectory() as directory:
            control_file = Path(directory) / "control"
            inherited_file = Path(directory) / "inherited"
            control_file.write_text("")
            result = subprocess.run(["bash", "-c", 'CONTROL_FILE=$1; INHERITED_FILE=$2\n' +
                                     code + stubs + body, "--", str(control_file), str(inherited_file)],
                                    capture_output=True, text=True, check=False)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(result.stdout, "")
            self.assertEqual(result.stderr, "")
            self.assertEqual(control_file.read_text(), control)
            self.assertEqual(inherited_file.read_text() if inherited_file.exists() else "", inherited)

    def test_owner_close_is_local_and_needs_no_remaining_budget(self):
        self.run_case(r'''
exec 8<>"$CONTROL_FILE"; CKA_CERT_CONTROL_OWNER=$BASHPID; CKA_CERT_CONTROL_LOCKED=1
if cka_cert_control_close unexpected; then exit 10; fi
fd8_open || exit 11
BUDGET_RESULT=124; HELPER_RESULT=124
cka_cert_control_close || exit 12
if fd8_open; then exit 13; fi
[[ -z ${CKA_CERT_CONTROL_OWNER+x} && -z ${CKA_CERT_CONTROL_LOCKED+x} && $helper_calls == 0 ]] || exit 14
''')

    def test_child_drop_retains_fd9_and_parent_state(self):
        self.run_case(r'''
exec 8<>"$CONTROL_FILE" 9>"$INHERITED_FILE"; CKA_CERT_CONTROL_OWNER=$BASHPID; CKA_CERT_CONTROL_LOCKED=1
if cka_cert_control_child_drop; then exit 20; fi
(
  if cka_cert_control_close || cka_cert_control_open 100; then exit 21; fi
  fd8_open || exit 22
  cka_cert_control_child_drop || exit 23
  if fd8_open; then exit 24; fi
  [[ -z ${CKA_CERT_CONTROL_OWNER+x} && -z ${CKA_CERT_CONTROL_LOCKED+x} ]] || exit 25
  printf child9 >&9
) || exit 26
[[ $CKA_CERT_CONTROL_OWNER == "$BASHPID" && $CKA_CERT_CONTROL_LOCKED == 1 ]] || exit 27
printf parent8 >&8; printf parent9 >&9
''', control="parent8", inherited="child9parent9")

    def test_unowned_drop_and_occupied_or_stale_open_refuse(self):
        self.run_case(r'''
exec 8<>"$CONTROL_FILE"
if cka_cert_control_child_drop; then exit 30; fi
if cka_cert_control_close; then exit 34; fi
if cka_cert_control_open 100; then exit 35; fi
fd8_open || exit 31
exec 8>&-; CKA_CERT_CONTROL_OWNER=999999
if cka_cert_control_open 100; then exit 32; fi
[[ $CKA_CERT_CONTROL_OWNER == 999999 && $helper_calls == 0 ]] || exit 33
''')

    def test_open_success_and_failure_cleanup_preserve_status(self):
        for setting, expected in (("HELPER_RESULT=7", 7), ("BUDGET_RESULT=124", 124),
                                  ("DESCRIPTOR_FIRST=55", 55), ("ACQUIRE_RESULT=37", 37),
                                  ("DESCRIPTOR_AFTER=124", 124), ("ACQUIRE_RESULT=0", 0)):
            with self.subTest(setting=setting):
                self.run_case(setting + r'''
if cka_cert_control_open 100; then status=0; else status=$?; fi
''' + f'[[ $status == {expected} ]] || exit 40\n' + (r'''
[[ $CKA_CERT_CONTROL_OWNER == "$BASHPID" && $CKA_CERT_CONTROL_LOCKED == 1 ]] || exit 41
fd8_open || exit 42
cka_cert_control_close || exit 43
''' if expected == 0 else r'''
if fd8_open; then exit 44; fi
[[ -z ${CKA_CERT_CONTROL_OWNER+x} && -z ${CKA_CERT_CONTROL_LOCKED+x} ]] || exit 45
'''))

    def test_init_arity_and_missing_ownership_refuse_before_helpers(self):
        self.run_case(r'''
if cka_cert_control_init 100 identity operation; then exit 50; fi
CKA_CERT_STATE_OWNS_FD=1
if cka_cert_control_init 100 identity; then exit 51; fi
[[ $helper_calls == 0 ]] || exit 52
''')


if __name__ == "__main__":
    unittest.main()
