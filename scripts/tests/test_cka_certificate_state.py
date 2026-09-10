"""The internal node library must be inert when loaded by a caller."""
import json
import subprocess
import tempfile
import unittest
from pathlib import Path


class TestCertificateStateSource(unittest.TestCase):
    def test_process_clock_with_injected_read(self):
        library = Path(__file__).resolve().parents[1] / "cka_certificate_process.sh"
        # Redirect only the proc clock input so the injected read works on macOS too.
        code = library.read_text().replace("< /proc/uptime", "< /dev/null")
        cases = [("00.08 0.00", "8"), ("08.09 100.01", "809"),
                 ("999999999999.99 0.00", "99999999999999")]
        cases += [(sample, "refused") for sample in (
            "", "read-failure", "1 0.00", "-1.00 0.00", "1.1 0.00", "1.001 0.00",
            "1.00 0.0", "1.00 -0.01", "1.00 0.00 extra", "1000000000000.00 0.00")]
        for sample, expected in cases:
            with self.subTest(sample=sample):
                result = subprocess.run(["bash", "-c", code + r'''
sample=$1
read() { [[ $sample != read-failure ]] && builtin read "$@" <<< "$sample"; }
if cka_cert_process_now; then printf '%s' "$CKA_CERT_PROCESS_NOW"; else printf refused; fi
''', "--", sample], capture_output=True, text=True, check=False)
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertEqual(result.stdout, expected)

    def test_process_snapshot_refuses_expired_or_failed_clock_before_stat(self):
        library = Path(__file__).resolve().parents[1] / "cka_certificate_process.sh"
        for fault, expected in (("expired", "124"), ("failed", "1")):
            with self.subTest(fault=fault):
                result = subprocess.run(["bash", "-c", r'''
source "$1"; fault=$2
cka_cert_process_now() { [[ $fault != failed ]] || return 1; CKA_CERT_PROCESS_NOW=200; }
cka_cert_process_stat() { printf unexpected-stat; return 1; }
if cka_cert_process_snapshot 999 0 200; then printf 0; else printf '%s' "$?"; fi
''', "--", str(library), fault], capture_output=True, text=True, check=False)
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertEqual(result.stdout, expected)

    def test_process_payload_rejects_malformed_and_foreign_records(self):
        library = Path(__file__).resolve().parents[1] / "cka_certificate_process.sh"
        operation = "a" * 32
        coordinator = {"pid": 20, "start_time": "123"}
        supervisor = {"pid": 21, "pgid": 21, "sid": 21, "start_time": "124"}
        unknown = {"started": None, "child_pid": None, "exit_code": None}
        exited = {"started": True, "child_pid": 22, "exit_code": 0}
        launch = {"schema": 2, "identity": {}, "operation_id": operation,
                  "coordinator": coordinator, "supervisor": None, "command": unknown,
                  "stage": "launch_requested", "timeout_seconds": 60,
                  "launch_disposition": "not_committed", "cancel_ack": False, "cause": "none"}
        committed = dict(launch, stage="launch_committed", launch_disposition="supervisor_committed")
        ready = dict(committed, supervisor=supervisor, stage="supervisor_ready")
        running = dict(ready, stage="command_launch_committed", launch_disposition="command_committed")
        stopped = dict(launch, stage="cancelled_before_launch", launch_disposition="not_started",
                       cancel_ack=True, cause="cancel", command=dict(unknown, started=False))
        term = dict(running, stage="term_requested", cause="timeout")
        done = dict(running, stage="supervision_complete", command=exited)
        cancel = {"schema": 1, "identity": {}, "operation_id": operation, "request": "cancel"}
        valid = [launch, committed, ready, running, stopped, dict(stopped, supervisor=supervisor),
                 term, dict(term, stage="kill_requested"), done,
                 dict(done, cancel_ack=True, cause="cancel", command=dict(exited, exit_code=42)),
                 dict(running, stage="supervision_unresolved", cause="unknown")]
        valid += [dict(launch, timeout_seconds=n) for n in (1, 3600)]
        valid += [dict(done, command=dict(exited, exit_code=255)), dict(term, cause="signal")]
        cases = [(v, "process", True) for v in valid]
        cases += [(cancel, "cancel", True), (dict(cancel, extra=True), "cancel", False)]
        invalid = [dict(launch, schema=1), dict(launch, supervisor=supervisor),
                   dict(committed, supervisor=supervisor), dict(ready, supervisor=None),
                   dict(running, command=exited), dict(done, command=unknown),
                   dict(stopped, command=exited), dict(stopped, cancel_ack=False),
                   dict(term, cause="none"), dict(launch, cause="cancel"), dict(launch, cancel_ack=True),
                   dict(running, launch_disposition="supervisor_committed"),
                   dict(running, supervisor=dict(supervisor, pgid=22)),
                   dict(running, coordinator=dict(coordinator, start_time=123)),
                   dict(running, operation_id="b" * 32), dict(running, identity={"foreign": 1}),
                   dict(running, stage="invented"), dict(running, cause="invented"),
                   dict(running, cancel_ack=1), dict(running, extra=True), [], None]
        invalid += [dict(launch, timeout_seconds=n) for n in (0, 3601, 1.5, "60", True)]
        invalid += [dict(done, command=dict(exited, exit_code=n)) for n in (-1, 256, 0.5, None, True)]
        invalid += [dict(done, command=dict(exited, child_pid=n)) for n in (0, -1, "22", True)]
        invalid += [dict(launch, **{key: None}) for key in ("command", "coordinator", "launch_disposition")]
        invalid += [dict(v, cause="unknown") for v in (ready, running, term, dict(term, stage="kill_requested"), done)]
        invalid += [dict(v, command=dict(unknown, started=False)) for v in
                    (term, done, dict(running, stage="supervision_unresolved", cause="unknown"))]
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
