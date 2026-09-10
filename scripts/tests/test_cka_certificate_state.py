"""The internal node library must be inert when loaded by a caller."""
import json
import subprocess
import tempfile
import unittest
from pathlib import Path


class TestCertificateStateSource(unittest.TestCase):
    def test_process_payload_rejects_malformed_and_foreign_records(self):
        library = Path(__file__).resolve().parents[1] / "cka_certificate_process.sh"
        operation = "a" * 32
        coordinator = {"pid": 20, "start_time": "123"}
        supervisor = {"pid": 21, "pgid": 21, "sid": 21, "start_time": "124"}
        launch = {"schema": 1, "identity": {}, "operation_id": operation,
                  "coordinator": coordinator, "supervisor": None, "child_exit": None,
                  "stage": "launch_requested", "timeout_seconds": 60}
        running = dict(launch, supervisor=supervisor, stage="running")
        done = dict(running, stage="supervision_complete", child_exit=0)
        cancel = {"schema": 1, "identity": {}, "operation_id": operation, "request": "cancel"}
        cases = [(v, "process", True) for v in [launch, running, done]]
        cases += [(cancel, "cancel", True), (dict(cancel, extra=True), "cancel", False)]
        invalid = [dict(launch, supervisor=supervisor), dict(running, supervisor=None),
                   dict(running, child_exit=0), dict(done, child_exit=None),
                   dict(done, child_exit=256), dict(done, child_exit=0.5),
                   dict(running, supervisor=dict(supervisor, pgid=22)),
                   dict(running, coordinator=dict(coordinator, start_time=123)),
                   dict(running, operation_id="b" * 32), dict(running, identity={"foreign": 1}),
                   dict(running, timeout_seconds=0), dict(running, timeout_seconds=3601),
                   dict(running, stage="invented"), dict(running, extra=True), [], None]
        cases += [(v, "process", False) for v in invalid]
        for value, kind, accepted in cases:
            with self.subTest(value=value, kind=kind):
                result = subprocess.run(["bash", "-c", r'''
source "$1"
cka_cert_state_expected() { printf '{}'; }
if cka_cert_process_payload '{}' "$2" "$3" "$4" >/dev/null; then
  printf accepted
else printf refused; fi
''', "--", str(library), operation, kind, json.dumps(value)],
                    capture_output=True, text=True, check=False)
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertEqual(result.stdout, "accepted" if accepted else "refused")

    def test_backup_state_schema_with_injected_filesystem(self):
        library = Path(__file__).resolve().parents[1] / "cka_certificate_state.sh"
        names = ("apiserver.crt", "apiserver.key", "kube-apiserver.yaml")
        baseline = {"fingerprint": "a" * 64, "public_key": "b" * 64,
                    "hashes": dict.fromkeys(names, "c" * 64),
                    "metadata": {name: {"uid": 0, "gid": 0, "mode": "600"} for name in names}}
        valid = [{"schema": 1, "identity": {}, "revision": revision,
                  "recovery": {"direction": "forward", "stage": stage}, "baseline": baseline}
                 for revision, stage in ((1, "backup_requested"), (2, "backup_verified"))]
        invalid = [dict(valid[0], revision=2), dict(valid[1], revision=1),
                   dict(valid[0], schema=2), dict(valid[0], extra=True), dict(valid[0], baseline={})]
        for field, bad in (("fingerprint", "invalid"), ("public_key", None), ("hashes", {})):
            invalid.append(dict(valid[0], baseline=dict(baseline, **{field: bad})))
        for field, bad in (("uid", 1), ("gid", -1), ("gid", 0.5), ("mode", "644")):
            broken = json.loads(json.dumps(valid[0]))
            broken["baseline"]["metadata"]["apiserver.key"][field] = bad
            invalid.append(broken)
        with tempfile.TemporaryDirectory() as directory:
            fixture = Path(directory) / "state.json"
            cases = [(v, "accepted", "") for v in valid] + [(v, "refused", "") for v in invalid]
            cases.append((valid[1], "refused", "fail-revision"))
            for value, expected, fault in cases:
                with self.subTest(value=value):
                    fixture.write_text(json.dumps(value))
                    result = subprocess.run(["bash", "-c", r'''
source "$1"; fixture=$2; fault=$3
cka_cert_state_directory() { return 0; }
cka_cert_state_file() { return 0; }
cka_cert_state_backup_verify() { return 0; }
jq() {
  [[ $1 != -r || $2 != .revision || $fault != fail-revision ]] || return 1
  if [[ ${!#} == /var/lib/cka-certificate-transaction/state.json ]]; then
    command jq "${@:1:$#-1}" "$fixture"
  else command jq "$@"; fi
}
if cka_cert_state_read '{}' >/dev/null; then printf accepted; else printf refused; fi
''', "--", str(library), str(fixture), fault], capture_output=True, text=True, check=False)
                    self.assertEqual(result.returncode, 0, result.stderr)
                    self.assertEqual(result.stdout, expected)

    def test_explicit_identity_schema_under_conditional_caller(self):
        library = Path(__file__).resolve().parents[1] / "cka_certificate_state.sh"
        identity = {"transaction_id": "a" * 32, "fixture_cluster": "cert-fixture-" + "b" * 32,
                    "docker_container_id": "c" * 64, "image_id": "sha256:" + "d" * 64,
                    "system_namespace_uid": "12345678-1234-1234-1234-123456789abc",
                    "artifact_hashes": {"state.sh": "e" * 64, "observe.sh": "f" * 64, "process.sh": "a" * 64}}
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
source "$2" || exit 1
[[ "$before" == "$(set +o)" && "$mask" == "$(umask)" && "$location" == "$PWD" ]] || exit 2
printf preserved >&9 || exit 3
[[ $(cat sentinel) == preserved ]] || exit 4
[[ $(find . -type f | wc -l) -eq 1 ]] || exit 5
''', "--", str(library), str(library.with_name("cka_certificate_process.sh"))],
                cwd=directory, capture_output=True, text=True, check=False)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(result.stdout, "")


if __name__ == "__main__":
    unittest.main()
