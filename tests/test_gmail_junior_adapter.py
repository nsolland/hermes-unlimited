import unittest
from unlimited.gmail_junior_adapter import GmailJuniorReadAdapter

class MockRequest:
    def __init__(self, result):self.result=result
    def execute(self):return self.result

class GmailService:
    def __init__(self):self.calls=[]
    def users(self):return self
    def messages(self):return self
    def list(self, **kw):
        self.calls.append(("list",kw))
        return MockRequest({"messages":[{"id":"123abc","threadId":"thr1"}],"resultSizeEstimate":1})
    def get(self, **kw):
        self.calls.append(("get",kw))
        return MockRequest({"id":"123abc","threadId":"thr1","snippet":"subject summary",
                            "labelIds":["INBOX"],"payload":{"headers":[
                              {"name":"Subject","value":"Help"},{"name":"From","value":"sender@example.com"},
                              {"name":"Authentication-Results","value":"unwanted"}]}})

class GmailJuniorAdapterTests(unittest.TestCase):
    def setUp(self):
        self.service=GmailService();self.adapter=GmailJuniorReadAdapter(self.service)
    def test_listing_is_read_only_bounded_and_account_locked(self):
        result=self.adapter("list_messages",{"query":"in:inbox"})
        self.assertEqual(result["messages"][0]["id"],"123abc")
        self.assertEqual(self.service.calls,[('list',{"userId":"me","q":"in:inbox","maxResults":20})])
    def test_get_exposes_bounded_metadata_only(self):
        result=self.adapter("get_message",{"message_id":"123abc"})
        self.assertEqual(result["headers"],{"subject":"Help","from":"sender@example.com"})
        self.assertEqual(self.service.calls[0][1]["format"],"metadata")
        self.assertNotIn("body",result)
    def test_mutations_and_bad_ids_fail_without_call(self):
        for op in ("send_message","create_draft","trash_message","delete","unknown"):
            with self.assertRaises(PermissionError):self.adapter(op,{"message_id":"123abc"})
        for mid in ("../accounts", "", "a"*130):
            with self.assertRaises(ValueError):self.adapter("get_message",{"message_id":mid})
        for query in ("", "a"*257):
            with self.assertRaises(ValueError):self.adapter("list_messages",{"query":query})
        self.assertEqual(self.service.calls,[])
    def test_missing_host_service_denied(self):
        with self.assertRaises(PermissionError):GmailJuniorReadAdapter(None)

if __name__=='__main__':unittest.main()
