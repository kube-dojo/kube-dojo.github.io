"""cka_etcd_fixture: composition + snapshot observe without live kind."""
import importlib.util
import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock


class TestEtcdFixture(unittest.TestCase):
    def setUp(self):
        root = Path(__file__).resolve().parents[2]
        spec = importlib.util.spec_from_file_location(
            "cka_etcd_fixture", root / "scripts/cka_etcd_fixture.py"
        )
        self.mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(self.mod)

    def test_constants_match_pins(self):
        self.assertEqual(self.mod.ETCD_ENDPOINT, "https://127.0.0.1:2379")
        self.assertTrue(self.mod.ETCD_DATA.startswith("/var/lib/"))
        self.assertIn("etcd", self.mod.ETCD_PKI)

    def _wrapper(self, runs, directory=None, state=None):
        fake = mock.Mock()
        fake.state = state or {"node": {"id": "abc"}, "etcd": {}}
        fake.verify = mock.Mock()
        fake.inspect = mock.Mock()
        fake.run = mock.Mock(side_effect=runs)
        fake.save = mock.Mock()
        fake.directory = directory or Path("/tmp/etcd-fixture-run")
        wrapper = self.mod.EtcdFixture.__new__(self.mod.EtcdFixture)
        wrapper.inner = fake
        return wrapper, fake

    def test_etcd_inspect_records_no_restore(self):
        wrapper, fake = self._wrapper(
            [
                "/usr/local/bin/etcdctl\n/usr/local/bin/etcdutl\npaths_ok",
                "etcdctl version: 3.5.16",
            ]
        )
        result = wrapper.etcd_inspect()
        self.assertFalse(result["restore_executed"])
        self.assertEqual(result["endpoint"], self.mod.ETCD_ENDPOINT)
        self.assertIn("3.5", result["etcdctl_version_line"])
        fake.save.assert_called()

    def test_etcd_inspect_rejects_missing_tools(self):
        wrapper, fake = self._wrapper(["paths_ok"])
        with self.assertRaisesRegex(RuntimeError, "etcdctl/etcdutl missing"):
            wrapper.etcd_inspect()
        fake.save.assert_not_called()

    def test_etcd_inspect_rejects_empty_version(self):
        wrapper, fake = self._wrapper(
            [
                "/usr/local/bin/etcdctl\n/usr/local/bin/etcdutl\npaths_ok",
                "",
            ]
        )
        with self.assertRaisesRegex(RuntimeError, "version line missing"):
            wrapper.etcd_inspect()
        fake.save.assert_not_called()

    def test_snapshot_observe_success(self):
        tmp_path = Path(tempfile.mkdtemp())
        status_json = json.dumps({"revision": 42, "totalSize": 4})
        cm = lambda value, uid: json.dumps({"metadata": {"uid": uid}, "data": {"value": value}})

        def run(tool, *args):
            shell = args[-1] if args and isinstance(args[-1], str) else ""
            if tool == "docker" and args[0] == "exec" and len(args) > 2 and args[2] == "etcdutl":
                return status_json
            if tool == "docker" and args[0] == "exec" and "endpoint status" in shell:
                if "--cacert=" not in shell:
                    raise RuntimeError("unauth")
                return json.dumps([{"Status": {"header": {"revision": 40}}}])
            if tool == "docker" and args[0] == "exec" and "etcdctl version" in shell:
                return "etcdctl version: 3.5.16"
            if tool == "docker" and args[0] == "exec" and "command -v" in shell:
                return "/usr/local/bin/etcdctl\n/usr/local/bin/etcdutl\npaths_ok"
            if tool == "docker" and args[0] == "exec" and shell.startswith("etcdctl"):
                return "" if "snapshot save" in shell else "present"
            if tool == "docker" and args[0] == "cp":
                Path(args[2]).write_bytes(b"snap")
                return ""
            raise AssertionError(args)

        wrapper, fake = self._wrapper([], directory=tmp_path)
        fake.state = {"node": {"id": "node-abc"}}
        fake.run = mock.Mock(side_effect=run)
        fake.api = mock.Mock(side_effect=[None, None, cm("one", "u1"), None, cm("two", "u2")])
        state = wrapper.snapshot_observe()
        self.assertFalse(state["etcd"]["restore_executed"])
        self.assertGreaterEqual(state["snapshot"]["status"]["revision"], state["etcd_baseline"]["revision"])
        self.assertEqual(state["post_snapshot_mutation"]["value"], "two")
        self.assertTrue((tmp_path / self.mod.SNAPSHOT_FILE).exists())

    def test_snapshot_refuse_overwrite(self):
        tmp_path = Path(tempfile.mkdtemp())
        snap_path = tmp_path / self.mod.SNAPSHOT_FILE
        snap_path.write_bytes(b"existing")
        wrapper, fake = self._wrapper([], directory=tmp_path)
        fake.state = {
            "node": {"id": "node-abc"},
            "etcd": {"restore_executed": False},
            "etcd_baseline": {"revision": 1, "marker_etcd_key": "/registry/x", "authenticated": True},
            "snapshot": {"path": str(snap_path), "sha256": "deadbeef"},
        }
        with self.assertRaisesRegex(RuntimeError, "overwrite"):
            wrapper.snapshot_save()

    def test_snapshot_observe_refuses_missing_tools(self):
        wrapper, fake = self._wrapper(["paths_ok"])
        fake.state = {"node": {"id": "abc"}}
        with self.assertRaisesRegex(RuntimeError, "etcdctl/etcdutl missing"):
            wrapper.snapshot_observe()

    def _restore_state(self, tmp_path, stage=None, restore_executed=False):
        snap_path = tmp_path / self.mod.SNAPSHOT_FILE
        snap_path.write_bytes(b"snap")
        state = {
            "node": {"id": "node-abc"},
            "etcd": {
                "restore_executed": restore_executed,
                "restore": {"direction": "restore", "stage": stage},
            },
            "etcd_marker": {
                "namespace": "ns-marker",
                "name": self.mod.MARKER_NAME,
                "uid": "uid-original",
                "value": "marker-original",
            },
            "etcd_baseline": {"revision": 1, "marker_etcd_key": "/registry/x", "authenticated": True},
            "snapshot": {"path": str(snap_path), "sha256": "deadbeef"},
            "post_snapshot_mutation": {"value": "mutated", "uid": "uid-original"},
        }
        return state

    def test_restore_happy_path_sets_restore_executed(self):
        tmp_path = Path(tempfile.mkdtemp())
        state = self._restore_state(tmp_path, stage="etcd_returned")
        cm = json.dumps({"metadata": {"uid": "uid-new"}, "data": {"value": "marker-original"}})

        def run(tool, *args):
            if tool == "docker" and args[0] == "exec" and args[2] == "sh":
                return "ok"
            raise AssertionError(args)

        wrapper, fake = self._wrapper([], directory=tmp_path)
        fake.state = state
        fake.run = mock.Mock(side_effect=run)
        wrapper._marker_cm = mock.Mock(return_value=json.loads(cm))
        wrapper.restore_continue()
        self.assertTrue(fake.state["etcd"]["restore_executed"])
        self.assertEqual(fake.state["etcd"]["restore"]["stage"], "restore_verified")
        self.assertTrue(fake.state["etcd"]["restore"]["marker_uid_may_differ"])

    def test_restore_refuses_without_snapshot(self):
        wrapper, fake = self._wrapper([])
        fake.state = {
            "node": {"id": "abc"},
            "etcd": {"restore_executed": False},
            "etcd_marker": {"namespace": "n", "name": "m", "uid": "u", "value": "v"},
            "etcd_baseline": {"revision": 1},
        }
        with self.assertRaisesRegex(RuntimeError, "snapshot, etcd_marker, and etcd_baseline"):
            wrapper.restore_begin()

    def test_restore_interrupt_leaves_restore_executed_false(self):
        tmp_path = Path(tempfile.mkdtemp())
        state = self._restore_state(tmp_path, stage="restore_requested")
        manifest = (
            "    - --name=etcd\n"
            "    - --initial-cluster=etcd=https://127.0.0.1:2380\n"
            "    - --initial-advertise-peer-urls=https://127.0.0.1:2380\n"
            "    - --initial-cluster-token=tok\n"
        )

        def run(tool, *args):
            if tool == "docker" and args[0] == "exec" and args[2] == "sh":
                shell = args[-1]
                if "cat " in shell:
                    return manifest
                raise InterruptedError("Signal 2")
            raise AssertionError(args)

        wrapper, fake = self._wrapper([], directory=tmp_path)
        fake.state = state
        fake.run = mock.Mock(side_effect=run)
        with self.assertRaises(InterruptedError):
            wrapper.restore_continue()
        self.assertFalse(fake.state["etcd"]["restore_executed"])

    def test_parse_etcd_restore_params_from_manifest(self):
        wrapper, _fake = self._wrapper([])
        params = wrapper._parse_etcd_restore_params(
            "    - --name=etcd\n"
            "    - --initial-cluster=etcd=https://127.0.0.1:2380\n"
            "    - --initial-advertise-peer-urls=https://127.0.0.1:2380\n"
            "    - --initial-cluster-token=tok\n"
        )
        self.assertEqual(params["name"], "etcd")
        self.assertIn("2380", params["initial-cluster"])

    def test_offline_restore_resumes_when_restore_dir_exists(self):
        tmp_path = Path(tempfile.mkdtemp())
        state = self._restore_state(tmp_path, stage="offline_restore_requested")
        state["etcd"]["restore"].update(
            {
                "live_data_moved": "/var/lib/etcd-pre-abc",
                "restore_data_dir": "/var/lib/etcd-restored-abc",
                "restore_params": {
                    "name": "etcd",
                    "initial-cluster": "etcd=https://127.0.0.1:2380",
                    "initial-advertise-peer-urls": "https://127.0.0.1:2380",
                    "initial-cluster-token": "tok",
                },
                "offline_substage": "live_data_aside",
            }
        )
        seen = {"cp": 0, "restore": 0, "activate": 0}

        def run(tool, *args):
            if tool == "docker" and args[0] == "cp":
                seen["cp"] += 1
                return ""
            if tool == "docker" and args[0] == "exec" and args[2] == "sh":
                shell = args[-1]
                if "echo ready" in shell:
                    return ""
                if "echo aside" in shell:
                    return "aside"
                if "echo restored" in shell:
                    return ""
                if "etcdutl snapshot restore" in shell:
                    seen["restore"] += 1
                    return ""
                if "mv /var/lib/etcd-restored-abc /var/lib/etcd" in shell:
                    seen["activate"] += 1
                    return ""
                if "rm -rf /var/lib/etcd-restored-abc" in shell or "mkdir -p" in shell:
                    return ""
                raise AssertionError(shell)
            raise AssertionError(args)

        wrapper, fake = self._wrapper([], directory=tmp_path)
        fake.state = state
        fake.run = mock.Mock(side_effect=run)
        wrapper.restore_continue()
        self.assertEqual(fake.state["etcd"]["restore"]["stage"], "offline_restored")
        self.assertEqual(seen["cp"], 1)
        self.assertEqual(seen["restore"], 1)
        self.assertEqual(seen["activate"], 1)
        self.assertFalse(fake.state["etcd"]["restore_executed"])

    def test_restore_verified_repairs_missing_executed_flag(self):
        tmp_path = Path(tempfile.mkdtemp())
        state = self._restore_state(tmp_path, stage="restore_verified", restore_executed=False)
        cm = {"metadata": {"uid": "uid-new"}, "data": {"value": "marker-original"}}
        wrapper, fake = self._wrapper([], directory=tmp_path)
        fake.state = state
        wrapper._marker_cm = mock.Mock(return_value=cm)
        wrapper.restore_continue()
        self.assertTrue(fake.state["etcd"]["restore_executed"])
        self.assertEqual(fake.state["etcd"]["restore"]["stage"], "restore_verified")

    def test_stop_probe_does_not_raise_when_manifest_still_present(self):
        tmp_path = Path(tempfile.mkdtemp())
        state = self._restore_state(tmp_path, stage="restore_requested")
        manifest = "    - --name=etcd\n"
        calls = []

        def run(tool, *args):
            if tool != "docker" or args[0] != "exec" or args[2] != "sh":
                raise AssertionError(args)
            shell = args[-1]
            calls.append(shell)
            if "cat " in shell:
                return manifest
            if "echo stopped" in shell:
                return ""
            if "cp -a" in shell and "rm -f" in shell:
                raise InterruptedError("Signal 2")
            if "mkdir -p" in shell:
                return ""
            raise AssertionError(shell)

        wrapper, fake = self._wrapper([], directory=tmp_path)
        fake.state = state
        fake.run = mock.Mock(side_effect=run)
        with self.assertRaises(InterruptedError):
            wrapper.restore_continue()
        self.assertFalse(fake.state["etcd"]["restore_executed"])
        self.assertTrue(any("echo stopped" in c for c in calls))
        self.assertTrue(any("if [ ! -f" in c for c in calls))
