"""cka_etcd_fixture: composition + refuse restore claims without live kind."""
import importlib.util
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

    def test_etcd_inspect_records_no_restore(self):
        with tempfile.TemporaryDirectory() as temporary:
            # Avoid real Fixture ctor (needs 0700 owned dir + tools).
            fake = mock.Mock()
            fake.state = {"node": {"id": "abc"}, "etcd": {}}
            fake.verify = mock.Mock()
            fake.inspect = mock.Mock()
            fake.run = mock.Mock(
                side_effect=[
                    "/usr/local/bin/etcdctl\n/usr/local/bin/etcdutl\npaths_ok",
                    "etcdctl version: 3.5.16",
                ]
            )
            fake.save = mock.Mock()
            wrapper = self.mod.EtcdFixture.__new__(self.mod.EtcdFixture)
            wrapper.inner = fake
            result = wrapper.etcd_inspect()
            self.assertFalse(result["restore_executed"])
            self.assertEqual(result["endpoint"], self.mod.ETCD_ENDPOINT)
            self.assertIn("3.5", result["etcdctl_version_line"])
