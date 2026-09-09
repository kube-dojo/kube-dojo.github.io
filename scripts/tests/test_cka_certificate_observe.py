"""Injected CRI boundaries; no cluster commands or certificate mutations."""
import json
import subprocess
import unittest
from pathlib import Path

LIBRARY = Path(__file__).resolve().parents[1] / 'cka_certificate_observe.sh'
SCRIPT = r'''
before=$(set +o)
source "$1" || exit 90
[[ $(set +o) == "$before" ]] || exit 91
timeout() {
  [[ $4 != --version ]] || { printf '%s\n' "$VERSION"; return 0; }
  [[ $FAIL != yes ]] || return 1
  printf '%s\n' "$PAYLOAD"
}
PAYLOAD=$2 VERSION=$3 FAIL=$4
if cka_cert_obs_running_ids mock-cri unix:///run/containerd/containerd.sock; then
  exit 0
else
  exit 37
fi
'''


class TestCertificateObservations(unittest.TestCase):
    def test_cri_boundaries_under_conditional_caller(self):
        item = {'id': 'a' * 64, 'metadata': {'name': 'kube-apiserver'},
                'labels': {'io.kubernetes.pod.namespace': 'kube-system'}, 'state': 'CONTAINER_RUNNING'}
        cases = [('running', {'containers': [item]}, True), ('empty', {'containers': []}, True),
                 ('null', None, False), ('wrong-root', [], False), ('missing-array', {}, False),
                 ('null-array', {'containers': None}, False), ('duplicate', {'containers': [item, item]}, False)]
        for field, value in [('id', 'short'), ('id', 'A' * 64), ('state', 'UNKNOWN'),
                             ('metadata', {'name': 'etcd'}), ('labels', {}), ('metadata', None)]:
            cases.append((field + str(value), {'containers': [{**item, field: value}]}, False))
        for state in ['CONTAINER_CREATED', 'CONTAINER_EXITED', 'CONTAINER_UNKNOWN']:
            cases.append((state, {'containers': [{**item, 'state': state}]}, True))
        for name, payload, accepted in cases:
            with self.subTest(name=name):
                result = self.invoke(json.dumps(payload))
                self.assertEqual(result.returncode, 0 if accepted else 37, result.stderr)
                if accepted:
                    self.assertEqual(json.loads(result.stdout), [item['id']] if name == 'running' else [])
        for payload, version, failure in [('', 'v1.35.0', 'no'), ('{', 'v1.35.0', 'no'),
                                          ('{} {}', 'v1.35.0', 'no'), (json.dumps({'containers': []}), 'v1.33.0', 'no'),
                                          (json.dumps({'containers': []}), 'v1.35.0', 'yes')]:
            with self.subTest(payload=payload, version=version, failure=failure):
                self.assertEqual(self.invoke(payload, version, failure).returncode, 37)

    @staticmethod
    def invoke(payload, version='v1.35.0', failure='no'):
        return subprocess.run(['bash', '-c', SCRIPT, '--', str(LIBRARY), payload,
                               'crictl version ' + version, failure], text=True,
                              capture_output=True, timeout=10, check=False)


if __name__ == '__main__':
    unittest.main()
