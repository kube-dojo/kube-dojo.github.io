"""cka_certificate_renew phase/mutate helpers with injected custody; not live kind proof."""

import subprocess
import tempfile
import unittest
from pathlib import Path

HARNESS = r"""
source "$1"
tmpdir=$2
mode=$3
export TMPDIR=$tmpdir
STATE=$tmpdir/state.json
printf '%s\n' '{"revision":2,"recovery":{"direction":"forward","stage":"backup_verified"}}' > "$STATE"
cka_cert_state_environment() { return 0; }
cka_cert_state_locked() { return 0; }
cka_cert_state_expected() { printf '{"transaction_id":"a"}'; }
cka_cert_state_artifacts() { return 0; }
cka_cert_state_file() { [[ -f $1 && ! -L $1 ]]; }
cka_cert_state_read() { cat -- "$STATE"; }
# Remap in-node paths onto the disposable fixture directory.
mv() {
  if [[ $1 == -T && $2 == -- ]]; then
    dest=$4
    [[ $dest == /var/lib/cka-certificate-transaction/state.json ]] && dest=$STATE
    command mv -- "$3" "$dest"
  else
    command mv "$@"
  fi
}
sync() { return 0; }
mktemp() { command mktemp "$tmpdir/state.XXXXXXXX"; }
case $mode in
  phase)
    cka_cert_renew_phase id backup_verified consumer_stop_requested || exit 1
    jq -e '.recovery.stage=="consumer_stop_requested" and .revision==3' < "$STATE" >/dev/null
    ;;
  phase-refuse)
    if cka_cert_renew_phase id wrong_stage consumer_stop_requested; then exit 1; fi
    ;;
  *) exit 2 ;;
esac
"""


class TestCertificateRenew(unittest.TestCase):
    def setUp(self):
        self.root = Path(__file__).resolve().parents[2]
        self.renew = self.root / "scripts/cka_certificate_renew.sh"

    def run_harness(self, mode):
        with tempfile.TemporaryDirectory() as temporary:
            return subprocess.run(
                ["bash", "-c", HARNESS, "--", str(self.renew), temporary, mode],
                capture_output=True,
                text=True,
                check=False,
                timeout=5,
            )

    def test_phase_advances_from_backup_verified(self):
        result = self.run_harness("phase")
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_phase_refuses_wrong_from_stage(self):
        result = self.run_harness("phase-refuse")
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_helpers_defined(self):
        result = subprocess.run(
            [
                "bash",
                "-c",
                r"""
source "$1"
declare -F cka_cert_renew_stop_consumer >/dev/null
declare -F cka_cert_renew_wait_stopped >/dev/null
declare -F cka_cert_renew_apiserver >/dev/null
declare -F cka_cert_renew_return_manifest >/dev/null
""",
                "--",
                str(self.renew),
            ],
            capture_output=True,
            text=True,
            check=False,
            timeout=5,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
