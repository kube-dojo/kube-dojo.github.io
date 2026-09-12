"""cka_certificate_rollback: begin, resume stop/pair/return, and continue dispatch."""
import json
import subprocess
import tempfile
import unittest
from pathlib import Path

B = {
    "fingerprint": "a" * 64, "public_key": "b" * 64,
    "hashes": dict.fromkeys(("apiserver.crt", "apiserver.key", "kube-apiserver.yaml"), "c" * 64),
    "metadata": {n: {"uid": 0, "gid": 0, "mode": "600" if n.endswith(".key") else "644"}
                 for n in ("apiserver.crt", "apiserver.key", "kube-apiserver.yaml")},
}
H = r'''
source "$1"; source "$2"; source "$3"
t=$4; m=$5; S=$t/state.json; I='{"transaction_id":"a"}'
cka_cert_state_environment(){ return 0; }; cka_cert_state_locked(){ return 0; }
cka_cert_state_expected(){ printf %s "$I"; }; cka_cert_state_artifacts(){ return 0; }
cka_cert_state_directory(){ return 0; }
cka_cert_state_file(){ [[ $1 == /var/lib/cka-certificate-transaction/state.json || (-f $1 && ! -L $1) ]]; }
cka_cert_state_backup_verify(){ return 0; }
jq(){ if [[ ${!#} == /var/lib/cka-certificate-transaction/state.json ]]; then command jq "${@:1:$#-1}" "$S"; else command jq "$@"; fi; }
mv(){ if [[ $1 == -T && $2 == -- ]]; then d=$4; [[ $d == /var/lib/cka-certificate-transaction/state.json ]]&&d=$S; command mv -- "$3" "$d"; else command mv "$@"; fi; }
sync(){ return 0; }; mktemp(){ command mktemp "$t/state.XXXXXXXX"; }
cka_cert_obs_running_ids(){ [[ $# == 2 ]]||return 1; printf '[]\n'; }
cka_cert_renew_cert_fingerprint(){ printf '%s\n' "$(printf a%.0s {1..64})"; }
case $m in
begin) cka_cert_rollback_begin id||exit 1
  jq -e '.recovery.stage=="rollback_requested"' <"$S" >/dev/null||exit 2 ;;
resume-pair)
  cka_cert_state_file(){ return 0; }; cmp(){ return 0; }
  cka_cert_rollback_restore_pair id /bin/crictl unix:///run/x.sock||exit 1
  jq -e '.recovery.stage=="pair_restored"' <"$S" >/dev/null||exit 2 ;;
resume-stop)
  mkdir -p "$t/txn"; printf yaml >"$t/txn/kube-apiserver.yaml.rollback"
  cka_cert_state_file(){
    case $1 in
      /var/lib/cka-certificate-transaction/state.json) return 0 ;;
      /var/lib/cka-certificate-transaction/kube-apiserver.yaml.rollback)
        [[ -f $t/txn/kube-apiserver.yaml.rollback ]] ;;
      *) [[ -f $1 && ! -L $1 ]] ;;
    esac
  }
  # Live manifest absent → resume finishes from staged copy.
  cka_cert_rollback_stop_consumer id||exit 1
  jq -e '.recovery.stage=="consumer_stopped"' <"$S" >/dev/null||exit 2 ;;
resume-return)
  mkdir -p "$t/txn" "$t/manifests"
  printf yaml >"$t/txn/kube-apiserver.yaml"; printf yaml >"$t/manifests/kube-apiserver.yaml"
  cka_cert_state_file(){
    case $1 in
      /var/lib/cka-certificate-transaction/state.json) return 0 ;;
      /var/lib/cka-certificate-transaction/kube-apiserver.yaml) [[ -f $t/txn/kube-apiserver.yaml ]] ;;
      *) [[ -f $1 && ! -L $1 ]] ;;
    esac
  }
  # Live already matches backup; remap existence/cmp onto fixture paths.
  cka_cert_rollback_return_manifest() {
    local expected state stage backup
    [[ $# == 1 ]] || return 1
    cka_cert_state_environment && cka_cert_state_locked || return 1
    expected=$(cka_cert_state_expected "$1") || return 1
    state=$(cka_cert_state_read "$expected") || return 1
    stage=$(jq -er '.recovery.stage' <<< "$state") || return 1
    backup=/var/lib/cka-certificate-transaction/kube-apiserver.yaml
    cka_cert_state_file "$backup" || return 1
    if [[ $stage == pair_restored ]]; then
      cka_cert_rollback_phase "$1" pair_restored manifest_return_requested || return 1
    elif [[ $stage != manifest_return_requested ]]; then
      return 1
    fi
    cmp -s -- "$t/txn/kube-apiserver.yaml" "$t/manifests/kube-apiserver.yaml" || return 1
    cka_cert_rollback_phase "$1" manifest_return_requested manifest_returned || return 1
  }
  cka_cert_rollback_return_manifest id||exit 1
  jq -e '.recovery.stage=="manifest_returned"' <"$S" >/dev/null||exit 2 ;;
continue-verify)
  cka_cert_rollback_continue id /bin/crictl unix:///run/x.sock||exit 1
  jq -e '.recovery.stage=="rollback_verified"' <"$S" >/dev/null||exit 2 ;;
continue-done)
  cka_cert_rollback_continue id /bin/crictl unix:///run/x.sock||exit 1 ;;
*) exit 9 ;;
esac
'''


class TestCertificateRollback(unittest.TestCase):
    def setUp(self):
        r = Path(__file__).resolve().parents[2]
        self.state = r / "scripts/cka_certificate_state.sh"
        self.renew = r / "scripts/cka_certificate_renew.sh"
        self.rollback = r / "scripts/cka_certificate_rollback.sh"

    def run_mode(self, mode, revision, direction, stage):
        seed = {"schema": 1, "identity": {"transaction_id": "a"}, "revision": revision,
                "recovery": {"direction": direction, "stage": stage}, "baseline": B}
        with tempfile.TemporaryDirectory() as temporary:
            Path(temporary, "state.json").write_text(json.dumps(seed) + "\n")
            return subprocess.run(
                ["bash", "-c", H, "--", str(self.state), str(self.renew), str(self.rollback),
                 temporary, mode],
                capture_output=True, text=True, check=False, timeout=5)

    def test_begin_from_manifest_returned(self):
        self.assertEqual(self.run_mode("begin", 8, "forward", "manifest_returned").returncode, 0)

    def test_restore_pair_resumes(self):
        self.assertEqual(self.run_mode("resume-pair", 12, "rollback", "pair_restore_requested").returncode, 0)

    def test_stop_consumer_resumes_when_manifest_already_removed(self):
        result = self.run_mode("resume-stop", 10, "rollback", "consumer_stop_requested")
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_return_manifest_resumes_when_live_already_matches(self):
        result = self.run_mode("resume-return", 13, "rollback", "manifest_return_requested")
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_continue_verifies_from_manifest_returned(self):
        self.assertEqual(self.run_mode("continue-verify", 14, "rollback", "manifest_returned").returncode, 0)

    def test_continue_noop_when_verified(self):
        self.assertEqual(self.run_mode("continue-done", 15, "rollback", "rollback_verified").returncode, 0)
