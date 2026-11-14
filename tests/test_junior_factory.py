import unittest
from unlimited.junior_factory import (catalog, propose_junior, junior_manifest,
                                    dispatch_read, evaluate_models, propose_tool_junior)
from unlimited.specialist_factory import Trial


class JuniorFactoryTests(unittest.TestCase):
    def setUp(self):
        self.junior = propose_junior('gmail', 'tenant-a', ['list_messages', 'get_message'])
        self.calls = []
        self.kwargs = dict(tenant='tenant-a', identity='@user',
                           verify_identity=lambda tenant, user: (tenant, user) == ('tenant-a', '@user'),
                           authorize=lambda *scope: scope == ('tenant-a', '@user', 'gmail', 'list_messages'),
                           adapter=lambda operation, arguments: self.calls.append((operation, arguments)) or ['m1'])

    def test_catalog_is_descriptive_not_authority(self):
        self.assertIn('gmail', catalog())
        self.assertFalse(catalog()['gmail']['connected'])
        self.assertEqual(self.junior.tool, 'gmail')
        self.assertEqual(self.junior.status, 'DRAFT_UNVERIFIED')
        self.assertFalse(junior_manifest(self.junior)['execution_authorized'])
        self.assertFalse(junior_manifest(self.junior)['model_qualified'])
        self.assertEqual(self.junior, propose_junior('gmail', 'tenant-a', ['get_message', 'list_messages']))

    def test_unknown_and_cross_tool_proposals_denied(self):
        for ops in ([], ['gmail'], ['list_messages', 'list_messages'], ['slack.search']):
            with self.assertRaises(ValueError): propose_junior('gmail', 'tenant-a', ops)
        with self.assertRaises(ValueError): propose_junior('outlook', 'tenant-a', ['list_messages'])
        with self.assertRaises(ValueError): propose_junior('gmail', '', ['list_messages'])

    def test_read_dispatch_is_host_authorized_and_scoped(self):
        result = dispatch_read(self.junior, 'list_messages', {'query':'in:inbox'}, **self.kwargs)
        self.assertEqual(result['result'], ['m1'])
        self.assertEqual(self.calls, [('list_messages', {'query':'in:inbox'})])
        self.assertFalse(result['external_write'])
        with self.assertRaises(PermissionError):
            dispatch_read(self.junior, 'list_messages', {'query':'x'}, **{**self.kwargs,'tenant':'tenant-b'})
        with self.assertRaises(PermissionError):
            dispatch_read(self.junior, 'list_messages', {'query':'x'}, **{**self.kwargs,'identity':'@other'})
        with self.assertRaises(PermissionError):
            dispatch_read(self.junior, 'get_message', {'message_id':'m1'}, **self.kwargs)
        self.assertEqual(len(self.calls), 1)

    def test_effectful_operations_fail_even_if_host_authorizes(self):
        write_junior=propose_junior('gmail', 'tenant-a', ['create_draft','send_message','trash_message'])
        kw={**self.kwargs,'authorize':lambda *args:True}
        for op, fields in [('create_draft', {'to':'a@b.c','subject':'x','body':'y'}),
                           ('send_message', {'message_id':'m1'}),
                           ('trash_message', {'message_id':'m1'})]:
            with self.assertRaises(PermissionError): dispatch_read(write_junior, op, fields, **kw)
        self.assertEqual(self.calls, [])

    def test_unknown_operation_invalid_args_and_missing_adapter(self):
        with self.assertRaises(PermissionError):dispatch_read(self.junior,'send_message',{'message_id':'m1'},**self.kwargs)
        for val in ({'query':'x','evil':'y'},{'query':''},{'query':123},{'query':'x'*2050}):
            with self.assertRaises(ValueError):dispatch_read(self.junior,'list_messages',val,**self.kwargs)
        with self.assertRaises(PermissionError):dispatch_read(self.junior,'list_messages',{'query':'x'},**{**self.kwargs,'adapter':None})
        self.assertEqual(self.calls,[])

    def test_generic_tool_first_junior_and_unreviewed_effect_rejection(self):
        from unlimited.specialist_factory import discover_capabilities, review_capability_effects
        caps=discover_capabilities([{"name":"dns_read", "parameters":{"type":"object",
                                    "properties":{"zone":{"type":"string"}},
                                    "required":["zone"]}}])
        with self.assertRaises(PermissionError):propose_tool_junior(caps[0],"tenant-a",objective="Read DNS")
        reviewed=review_capability_effects(caps,{"dns_read":"read"})
        junior=propose_tool_junior(reviewed[0],"tenant-a",objective="Read DNS")
        self.assertEqual(junior.tool,"dns_read")
        self.assertEqual(len(junior.operations),1)
        self.assertFalse(junior_manifest(junior)["execution_authorized"])
        self.assertIsNone(propose_junior("gmail","tenant-a",["get_message"],
                    model_evaluation={"status":"QUALIFIED","recommended_model":"untrusted"}).model_id)

    def test_model_evaluation_needs_verified_complete_cases(self):
        cases=['inbox-triage','spam-triage']
        trials=[Trial(model,case,True,cost,1.0,True,f'{model}-{case}-{rep}')
                for model,cost in [('tiny',1),('frontier',10)] for case in cases for rep in range(3)]
        verdict=evaluate_models(trials,cases)
        self.assertEqual(verdict['recommended_model'],'tiny')
        unverified=[Trial('cheap','inbox-triage',True,0,1,False,'r1')]
        self.assertIsNone(evaluate_models(unverified,cases)['recommended_model'])

if __name__ == '__main__': unittest.main()
