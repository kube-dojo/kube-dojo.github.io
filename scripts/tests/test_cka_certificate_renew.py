"""cka_certificate_renew: real state_read admission + CRI/fingerprint contracts."""
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
source "$1"; source "$2"; t=$3; m=$4; S=$t/state.json; I='{"transaction_id":"a"}'
cka_cert_state_environment(){ return 0; }; cka_cert_state_locked(){ return 0; }
cka_cert_state_expected(){ printf %s "$I"; }; cka_cert_state_artifacts(){ return 0; }
cka_cert_state_directory(){ return 0; }
cka_cert_state_file(){ [[ $1 == /var/lib/cka-certificate-transaction/state.json || (-f $1 && ! -L $1) ]]; }
cka_cert_state_backup_verify(){ return 0; }
jq(){ if [[ ${!#} == /var/lib/cka-certificate-transaction/state.json ]]; then command jq "${@:1:$#-1}" "$S"; else command jq "$@"; fi; }
mv(){ if [[ $1 == -T && $2 == -- ]]; then d=$4; [[ $d == /var/lib/cka-certificate-transaction/state.json ]]&&d=$S; command mv -- "$3" "$d"; else command mv "$@"; fi; }
sync(){ return 0; }; mktemp(){ command mktemp "$t/state.XXXXXXXX"; }
cka_cert_obs_running_ids(){ [[ $# == 2 && -n $1 && $2 == unix:///* ]]||return 1; printf '[]\n'; }
cka_cert_obs_fingerprint(){ if [[ -f $t/fp ]]; then printf 'SHA256 Fingerprint=%s\n' "$(printf 9%.0s {1..64})"; else :>"$t/fp"; printf 'SHA256 Fingerprint=%s\n' "$(printf 1%.0s {1..64})"; fi; }
cka_cert_obs_pair(){ printf 'SHA256(stdin)= %s\n' "$(printf 2%.0s {1..64})"; }
case $m in
phase) cka_cert_renew_phase id backup_verified consumer_stop_requested||exit 1
  cka_cert_renew_phase id consumer_stop_requested consumer_stopped||exit 2
  jq -e '.recovery.stage=="consumer_stopped" and .revision==4' <"$S" >/dev/null||exit 3 ;;
contracts) cka_cert_renew_wait_stopped 1 /bin/crictl unix:///run/x.sock||exit 1
  if cka_cert_renew_wait_stopped 1; then exit 2; fi; kubeadm(){ return 0; }
  cka_cert_renew_cert_fingerprint(){ local f; f=$(cka_cert_obs_fingerprint x)||return 1; f=${f#*=}; f=${f//:/}; f=${f,,}
    cka_cert_obs_pair x y >/dev/null||return 1; [[ $f =~ ^[a-f0-9]{64}$ ]]||return 1; printf '%s\n' "$f"; }
  cka_cert_renew_apiserver id /bin/crictl unix:///run/x.sock||exit 3
  jq -e '.recovery.stage=="renew_verified"' <"$S" >/dev/null||exit 4 ;;
*) exit 9 ;;
esac
'''


class TestCertificateRenew(unittest.TestCase):
    def setUp(self):
        r = Path(__file__).resolve().parents[2]
        self.state, self.renew = r / "scripts/cka_certificate_state.sh", r / "scripts/cka_certificate_renew.sh"

    def run_mode(self, mode, revision, stage):
        seed = {"schema": 1, "identity": {"transaction_id": "a"}, "revision": revision,
                "recovery": {"direction": "forward", "stage": stage}, "baseline": B}
        with tempfile.TemporaryDirectory() as temporary:
            Path(temporary, "state.json").write_text(json.dumps(seed) + "\n")
            return subprocess.run(
                ["bash", "-c", H, "--", str(self.state), str(self.renew), temporary, mode],
                capture_output=True, text=True, check=False, timeout=5)

    def test_phase_chain_uses_real_state_read(self):
        self.assertEqual(self.run_mode("phase", 2, "backup_verified").returncode, 0)

    def test_cri_and_fingerprint_contracts(self):
        r = self.run_mode("contracts", 4, "consumer_stopped")
        self.assertEqual(r.returncode, 0, r.stderr)
