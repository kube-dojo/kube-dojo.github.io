"""Pure runner-record validation with real jq and identity schema; no live custody proof."""
import json
import subprocess
import unittest
from pathlib import Path


class TestRunnerPayload(unittest.TestCase):
    def setUp(self):
        self.identity = {"transaction_id": "a" * 32, "fixture_cluster": "cert-fixture-" + "b" * 32,
                         "docker_container_id": "c" * 64, "image_id": "sha256:" + "d" * 64,
                         "system_namespace_uid": "12345678-1234-1234-1234-123456789abc",
                         "artifact_hashes": {name + ".sh": "e" * 64 for name in ("state", "observe", "process")}}
        self.operation = "f" * 32
        self.binding = {"supervisor": {"pid": 21, "pgid": 21, "sid": 21, "start_time": "123"},
                        "runner": {"pid": 22, "start_time": "124"}, "argv": ["/bin/true", ""]}

    def record(self, kind, binding=None):
        return dict(self.binding if binding is None else binding, schema=1, identity=self.identity,
                    operation_id=self.operation, kind=kind,
                    child={"pid": 23, "start_time": "125"} if kind in ("birth", "entry") else None)

    def check(self, kind, value, accepted=False, binding=None, identity=None, operation=None, count=5):
        root = Path(__file__).resolve().parents[2]
        args = [json.dumps(self.identity if identity is None else identity),
                self.operation if operation is None else operation,
                json.dumps(self.binding if binding is None else binding), kind,
                value if isinstance(value, str) else json.dumps(value)]
        result = subprocess.run(["bash", "-c", ('source "$1"; source "$2"; shift 2; '
                                 'cka_cert_runner_payload "$@"'), "--",
                                 str(root / "scripts/cka_certificate_state.sh"),
                                 str(root / "scripts/cka_certificate_process.sh"), *args[:count]],
                                capture_output=True, text=True, check=False, timeout=5)
        self.assertEqual(result.returncode == 0, accepted, result.stderr)
        if accepted:
            self.assertEqual(json.loads(result.stdout), value)
        else:
            self.assertEqual(result.stdout, "")

    def test_valid_kinds_and_argument_boundaries(self):
        for kind in ("ready", "admission", "birth", "entry"):
            with self.subTest(kind=kind):
                self.check(kind, self.record(kind), True)
                self.check(kind, self.record(kind), count=4)
        for argv in (["x"], ["x"] + [""] * 31, ["x", "two words", "line\nbreak"]):
            binding = dict(self.binding, argv=argv)
            self.check("ready", self.record("ready", binding), True, binding=binding)
        for argv in ([], [""], ["", "x"], ["x"] * 33, ["x", 1], [None], "x",
                     ["x\0y"], ["x", "\0"], ["x", "before\0after"]):
            binding = dict(self.binding, argv=argv)
            self.check("ready", self.record("ready", binding), binding=binding)

    def test_exact_shape_and_kind(self):
        for kind in ("ready", "admission", "birth", "entry"):
            record = self.record(kind)
            invalid = [None, [], {}, dict(record, extra=True), dict(record, schema=2),
                       dict(record, kind="other"), "{", json.dumps(record) + "\n" + json.dumps(record)]
            invalid += [{key: value for key, value in record.items() if key != missing} for missing in record]
            for value in invalid:
                with self.subTest(kind=kind, value=value):
                    self.check(kind, value)
        self.check("other", self.record("other"))

    def test_binding_mismatches_and_invalid_expected_identity(self):
        record = self.record("ready")
        for field, value in (("identity", {}), ("operation_id", "0" * 32), ("argv", ["other"]),
                             ("runner", {"pid": 24, "start_time": "124"}),
                             ("supervisor", dict(self.binding["supervisor"], start_time="999"))):
            self.check("ready", dict(record, **{field: value}))
        for identity in ({}, dict(self.identity, transaction_id="0" * 32)):
            self.check("ready", record, identity=identity)
        for operation in ("bad", "0" * 32):
            self.check("ready", record, operation=operation)
        for binding in ({}, dict(self.binding, extra=True), dict(self.binding, runner=None),
                        dict(self.binding, runner={"pid": 21, "start_time": "124"}),
                        dict(self.binding, supervisor=dict(self.binding["supervisor"], sid=99))):
            self.check("ready", self.record("ready", binding), binding=binding)

    def test_person_shapes_and_child_distinctness(self):
        for field in ("runner", "supervisor"):
            original = self.binding[field]
            malformed = [None, {}, dict(original, extra=True), dict(original, pid=True),
                         dict(original, pid=0), dict(original, start_time=123), dict(original, start_time="-1")]
            for value in malformed:
                binding = dict(self.binding, **{field: value})
                self.check("ready", self.record("ready", binding), binding=binding)
        invalid = [None, {}, {"pid": 23}, {"pid": 23, "start_time": "125", "extra": True}]
        invalid += [{"pid": pid, "start_time": "125"} for pid in (0, -1, True, 1.5, "23", 21, 22)]
        invalid += [{"pid": 23, "start_time": value} for value in (125, "-1", "", None)]
        for kind in ("birth", "entry"):
            for child in invalid:
                self.check(kind, dict(self.record(kind), child=child))
        for kind in ("ready", "admission"):
            self.check(kind, dict(self.record(kind), child={"pid": 23, "start_time": "125"}))


if __name__ == "__main__":
    unittest.main()
