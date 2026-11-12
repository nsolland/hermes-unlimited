import hashlib
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from unlimited.adapter_gate import AdapterDenied, authorize_adapter, load_approved_adapter


class AdapterGateTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        root = Path(self.temp.name)
        (root/'adapters').mkdir()
        (root/'unlimited').mkdir()
        self.source = root/'unlimited'/'sample.py'
        self.source.write_text('VALUE=1\n')
        self.catalog = root/'adapters'/'catalog.json'
        self.approvals = root/'adapters'/'approvals.json'
        self.entry = {'id':'sample','module':'unlimited.sample','status':'approved','approved_version':'1.0.0'}
        self.approval = {'id':'sample','module':'unlimited.sample','status':'approved',
            'version':'1.0.0','sha256':hashlib.sha256(self.source.read_bytes()).hexdigest(),
            'source_path':'unlimited/sample.py','host_scope':'tenant-a','capabilities':['read'],
            'reviewer':'maintainer','evidence':'test:sha256',
            'checks':{'unit':'passed','contract':'passed','security':'passed','integration':'passed'},
            'tested_version':'1.0.0','tested_sha256':hashlib.sha256(self.source.read_bytes()).hexdigest()}
        self.save()

    def save(self):
        self.catalog.write_text(json.dumps({'schema_version':1,'adapters':[self.entry]}))
        self.approvals.write_text(json.dumps({'schema_version':1,'approvals':[self.approval]}))

    def authorize(self):
        return authorize_adapter('sample',catalog_path=self.catalog,approvals_path=self.approvals,
            host_scope='tenant-a',capability='read',status_provider=self.live)

    def live(self, adapter_id, version, digest):
        return {'version':version,'sha256':digest,'revoked':False,'checks':dict(self.approval['checks'])}

    def test_exact_pinned_approval(self):
        self.assertEqual(self.authorize()['version'],'1.0.0')

    def test_missing_live_provider_denies_stale_approval(self):
        with self.assertRaises(AdapterDenied):
            authorize_adapter('sample',catalog_path=self.catalog,approvals_path=self.approvals,
                host_scope='tenant-a',capability='read')

    def test_live_failure_revokes_approved_adapter(self):
        def failed(_id, version, digest):
            return {'version':version,'sha256':digest,'revoked':False,
                'checks':{'unit':'passed','contract':'passed','security':'failed','integration':'passed'}}
        with self.assertRaises(AdapterDenied):
            authorize_adapter('sample',catalog_path=self.catalog,approvals_path=self.approvals,
                host_scope='tenant-a',capability='read',status_provider=failed)

    def test_live_revocation_denies(self):
        def revoked(_id, version, digest):
            return {'version':version,'sha256':digest,'revoked':True,'checks':dict(self.approval['checks'])}
        with self.assertRaises(AdapterDenied):
            authorize_adapter('sample',catalog_path=self.catalog,approvals_path=self.approvals,
                host_scope='tenant-a',capability='read',status_provider=revoked)

    def test_live_provider_outage_denies(self):
        def unavailable(*args): raise ConnectionError('offline')
        with self.assertRaises(AdapterDenied):
            authorize_adapter('sample',catalog_path=self.catalog,approvals_path=self.approvals,
                host_scope='tenant-a',capability='read',status_provider=unavailable)

    def test_evaluation_is_denied(self):
        self.entry['status']='evaluation';self.save()
        with self.assertRaises(AdapterDenied): self.authorize()

    def test_revocation_is_denied(self):
        self.approval['status']='revoked';self.save()
        with self.assertRaises(AdapterDenied): self.authorize()

    def test_source_tampering_is_denied(self):
        self.source.write_text('VALUE=2\n')
        with self.assertRaises(AdapterDenied): self.authorize()

    def test_failed_mandatory_test_revokes_access(self):
        self.approval['checks']['security']='failed';self.save()
        with self.assertRaises(AdapterDenied): self.authorize()

    def test_pending_test_revokes_access(self):
        self.approval['checks']['integration']='pending';self.save()
        with self.assertRaises(AdapterDenied): self.authorize()

    def test_missing_test_evidence_revokes_access(self):
        del self.approval['checks'];self.save()
        with self.assertRaises(AdapterDenied): self.authorize()

    def test_stale_test_digest_revokes_access(self):
        self.approval['tested_sha256']='0'*64;self.save()
        with self.assertRaises(AdapterDenied): self.authorize()

    def test_stale_test_version_revokes_access(self):
        self.approval['tested_version']='0.9.0';self.save()
        with self.assertRaises(AdapterDenied): self.authorize()

    def test_wrong_scope_is_denied(self):
        self.approval['host_scope']='tenant-b';self.save()
        with self.assertRaises(AdapterDenied): self.authorize()

    def test_wrong_capability_is_denied(self):
        self.approval['capabilities']=['write'];self.save()
        with self.assertRaises(AdapterDenied): self.authorize()

    def test_missing_review_is_denied(self):
        self.approval['reviewer']='';self.save()
        with self.assertRaises(AdapterDenied): self.authorize()

    def test_duplicate_approval_is_denied(self):
        self.approvals.write_text(json.dumps({'schema_version':1,'approvals':[self.approval,self.approval]}))
        with self.assertRaises(AdapterDenied): self.authorize()

    def test_path_escape_is_denied(self):
        self.approval['source_path']='../../etc/passwd';self.save()
        with self.assertRaises(AdapterDenied): self.authorize()

    def test_never_import_before_admission(self):
        self.entry['status']='evaluation';self.save()
        with patch('unlimited.adapter_gate.importlib.import_module',side_effect=AssertionError('imported')):
            with self.assertRaises(AdapterDenied):
                load_approved_adapter('sample',catalog_path=self.catalog,approvals_path=self.approvals,
                    host_scope='tenant-a',capability='read')

    def test_default_catalog_is_not_approved(self):
        root=Path(__file__).resolve().parents[1]
        with self.assertRaises(AdapterDenied):
            authorize_adapter('a2ui',catalog_path=root/'adapters/catalog.json',
                approvals_path=root/'adapters/approvals.json',host_scope='tenant-a',capability='read')
