"""The internal node library must be inert when loaded by a caller."""
import json
import subprocess
import tempfile
import unittest
from pathlib import Path


class TestCertificateStateSource(unittest.TestCase):
    def test_explicit_identity_schema_under_conditional_caller(self):
        library = Path(__file__).resolve().parents[1] / "cka_certificate_state.sh"
        identity = {"transaction_id": "a" * 32, "fixture_cluster": "cert-fixture-" + "b" * 32,
                    "docker_container_id": "c" * 64, "image_id": "sha256:" + "d" * 64,
                    "system_namespace_uid": "12345678-1234-1234-1234-123456789abc",
                    "artifact_hashes": {"state.sh": "e" * 64, "observe.sh": "f" * 64}}
        invalid = [{}, [], None, dict(identity, extra=True)]
        invalid += [{k: v for k, v in identity.items() if k != key} for key in identity]
        invalid += [dict(identity, **{key: None}) for key in identity]
        invalid += [dict(identity, artifact_hashes={"elsewhere": "e" * 64})]
        for value, expected in [(identity, "accepted")] + [(v, "refused") for v in invalid]:
            with self.subTest(value=value):
                result = subprocess.run(
                    ["bash", "-c", ('source "$1"; if cka_cert_state_expected "$2" >/dev/null; '
                     'then printf accepted; else printf refused; fi'),
                     "--", str(library), json.dumps(value)], capture_output=True, text=True, check=False)
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertEqual(result.stdout, expected)

    def test_source_preserves_caller_and_existing_descriptor(self):
        library = Path(__file__).resolve().parents[1] / "cka_certificate_state.sh"
        with tempfile.TemporaryDirectory() as directory:
            result = subprocess.run(
                ["bash", "-c", r'''
set -u
umask 027
exec 9> sentinel
before=$(set +o); mask=$(umask); location=$PWD
source "$1" || exit 1
[[ "$before" == "$(set +o)" && "$mask" == "$(umask)" && "$location" == "$PWD" ]] || exit 2
printf preserved >&9 || exit 3
[[ $(cat sentinel) == preserved ]] || exit 4
[[ $(find . -type f | wc -l) -eq 1 ]] || exit 5
''', "--", str(library)], cwd=directory, capture_output=True, text=True, check=False)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(result.stdout, "")


if __name__ == "__main__":
    unittest.main()
