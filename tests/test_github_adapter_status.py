import io
import json
import unittest
from unittest.mock import patch
from unlimited.github_adapter_status import GitHubAdapterStatus

SHA='a'*40

class Response(io.BytesIO):
    def __enter__(self): return self
    def __exit__(self,*args): self.close()

class GitHubStatusTests(unittest.TestCase):
    def setUp(self):
        self.provider=GitHubAdapterStatus(repo='rrglab/hermes-unlimited',commit_sha=SHA,token='host-token')

    def runs(self, override=None):
        items=[]
        for i, workflow in enumerate(('tests.yml','release-gate.yml','codeql.yml')):
            item={'path':'.github/workflows/'+workflow,'head_sha':SHA,'event':'pull_request',
                  'created_at':'2026-11-12T11:00:00Z','id':i+1,'status':'completed','conclusion':'success'}
            items.append(item)
        if override: override(items)
        with patch('unlimited.github_adapter_status.urlopen',return_value=Response(json.dumps({'workflow_runs':items}).encode())):
            return self.provider('adapter','1.0.0','b'*64)

    def test_all_green(self):
        self.assertTrue(all(v=='passed' for v in self.runs()['checks'].values()))

    def test_failed_security(self):
        self.assertEqual(self.runs(lambda r:r[2].update(conclusion='failure'))['checks']['security'],'failed')

    def test_pending_is_not_green(self):
        self.assertEqual(self.runs(lambda r:r[0].update(status='in_progress'))['checks']['unit'],'failed')

    def test_wrong_commit_is_not_green(self):
        self.assertEqual(self.runs(lambda r:r[0].update(head_sha='b'*40))['checks']['unit'],'failed')

    def test_newer_failure_overrides_older_success(self):
        def add(r):
            x=dict(r[0]);x.update(id=99,created_at='2026-11-12T12:00:00Z',conclusion='failure');r.append(x)
        self.assertEqual(self.runs(add)['checks']['unit'],'failed')

    def test_missing_workflow_is_not_green(self):
        self.assertEqual(self.runs(lambda r:r.pop())['checks']['security'],'failed')

    def test_bad_repo_rejected(self):
        with self.assertRaises(ValueError): GitHubAdapterStatus(repo='evil/path/extra',commit_sha=SHA,token='x')
