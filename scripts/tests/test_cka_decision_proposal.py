"""Pure supplied-record checks; no deadline, filesystem observation or custody proof."""
import json
import subprocess
import tempfile
import unittest
from pathlib import Path


class TestDecisionProposal(unittest.TestCase):
    def setUp(self):
        self.identity = {"transaction_id": "a" * 32, "fixture_cluster": "cert-fixture-" + "b" * 32,
                         "docker_container_id": "c" * 64, "image_id": "sha256:" + "d" * 64,
                         "system_namespace_uid": "12345678-1234-1234-1234-123456789abc",
                         "artifact_hashes": {name + ".sh": "e" * 64 for name in ("state", "observe", "process")}}
        self.operation = "f" * 32
        self.before = {"schema": 2, "identity": self.identity, "operation_id": self.operation,
                       "stage": "launch_requested", "coordinator": {"pid": 21, "start_time": "123"},
                       "supervisor": None, "timeout_seconds": 30, "cancel_ack": False, "cause": "none",
                       "launch_disposition": "not_committed",
                       "command": {"started": None, "child_pid": None, "exit_code": None}}
        self.after = dict(self.before, stage="launch_committed", launch_disposition="supervisor_committed")
        self.absent = {"presence": "absent"}
        self.present = {"presence": "present", "record": self.before}

    def invoke(self, method, *values, accepted=True, identity=None, operation=None):
        root = Path(__file__).resolve().parents[2]
        args = [json.dumps(self.identity if identity is None else identity),
                self.operation if operation is None else operation]
        args += [value if isinstance(value, str) else json.dumps(value) for value in values]
        with tempfile.TemporaryDirectory() as directory:
            result = subprocess.run(["bash", "-c", 'source "$1"; source "$2"; shift 2; "$@"',
                                     "--", str(root / "scripts/cka_certificate_state.sh"),
                                     str(root / "scripts/cka_certificate_process.sh"),
                                     "cka_cert_decision_" + method, *args], cwd=directory,
                                    capture_output=True, text=True, check=False)
            self.assertEqual(list(Path(directory).iterdir()), [])
        self.assertEqual(result.returncode == 0, accepted, result.stderr)
        if not accepted:
            self.assertEqual(result.stdout, "")
        return result.stdout.strip()

    def test_exact_tags_and_malformed_observations(self):
        for value in (self.absent, self.present):
            self.assertEqual(json.loads(self.invoke("observation", value)), value)
        invalid = [None, [], {}, {"presence": "absent", "record": None},
                   {"presence": "present", "record": None}, {"presence": "present"},
                   {"presence": "unknown"}, dict(self.present, extra=True), "{",
                   json.dumps(self.absent) + "\n" + json.dumps(self.absent)]
        for value in invalid:
            with self.subTest(value=value):
                self.invoke("observation", value, accepted=False)
                self.invoke("proposal", value, self.after, accepted=False)

    def test_proposal_shape_and_binding(self):
        for expected in (self.absent, self.present):
            self.assertEqual(json.loads(self.invoke("proposal", expected, self.after)),
                             {"schema": 1, "identity": self.identity, "operation_id": self.operation,
                              "expected": expected, "next": self.after})
        for overrides in ({"identity": {}}, {"identity": dict(self.identity, transaction_id="0" * 32)},
                          {"operation": "bad"}, {"operation": "0" * 32}):
            self.invoke("observation", self.present, accepted=False, **overrides)
            self.invoke("proposal", self.absent, self.after, accepted=False, **overrides)
        invalid = [None, {}, dict(self.after, schema=1), dict(self.after, extra=True),
                   dict(self.after, identity={}), dict(self.after, operation_id="0" * 32),
                   dict(self.after, stage="unknown"), json.dumps(self.after) + "\n" + json.dumps(self.after)]
        for value in invalid:
            self.invoke("proposal", self.absent, value, accepted=False)
            self.invoke("observation", {"presence": "present", "record": value}, accepted=False)
            self.invoke("classify", self.present, self.after,
                        {"presence": "present", "record": value}, accepted=False)

    def test_stable_metadata_and_noop(self):
        for successor in (self.before, dict(self.after, timeout_seconds=31),
                          dict(self.after, coordinator={"pid": 22, "start_time": "123"})):
            self.invoke("proposal", self.present, successor, accepted=False)
        self.invoke("proposal", self.present, dict(reversed(list(self.before.items()))), accepted=False)

    def test_four_classifications_and_semantic_order(self):
        conflict = dict(self.before, timeout_seconds=31)
        cases = [(self.present, {"presence": "present", "record": self.after}, "successor"),
                 (self.present, self.present, "predecessor"), (self.present, self.absent, "missing"),
                 (self.absent, self.absent, "predecessor"),
                 (self.present, {"presence": "present", "record": conflict}, "conflict")]
        for expected, observed, classification in cases:
            self.assertEqual(self.invoke("classify", expected, self.after, observed), classification)
        reordered = dict(reversed(list(self.after.items())))
        reordered["identity"] = dict(reversed(list(self.identity.items())))
        self.assertEqual(self.invoke("classify", self.present, self.after,
                                     {"record": reordered, "presence": "present"}), "successor")
        self.invoke("classify", self.present, None, self.present, accepted=False)
        self.invoke("classify", None, self.after, self.present, accepted=False)


if __name__ == "__main__":
    unittest.main()
