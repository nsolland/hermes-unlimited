import asyncio
import json
import unittest
from unlimited.council_cli import ollama_chat, parse_members
from unlimited.socratic_council import QUESTIONS, SocraticCouncil


class LocalCouncilClientTests(unittest.IsolatedAsyncioTestCase):
    async def test_chat_request_to_local_endpoint(self):
        requests = []
        class Reply:
            def __enter__(self): return self
            def __exit__(self, *args): return False
            def read(self, limit): return b'{"message":{"content":"evidence and uncertainty"}}'
        def opener(request, timeout):
            requests.append((request.full_url, json.loads(request.data)))
            return Reply()
        client = ollama_chat("local-model", opener=opener)
        self.assertEqual(await client("system", "question"), "evidence and uncertainty")
        self.assertEqual(requests[0][0], "http://127.0.0.1:11434/api/chat")
        self.assertFalse(requests[0][1]["stream"])

    async def test_end_to_end_local_model_protocol(self):
        def opener(request, timeout):
            req = json.loads(request.data)
            system = req["messages"][0]["content"]
            output = (json.dumps({"status": "DISSENT", "synthesis": "More evidence needed",
                                  "dissent": ["The assumptions are contested"],
                                  "uncertainty": ["Unknown costs"]})
                      if system.startswith("Socratic chair") else "Evidence-driven perspective")
            class Reply:
                def __enter__(self): return self
                def __exit__(self, *args): return False
                def read(self, limit): return json.dumps({"message": {"content": output}}).encode()
            return Reply()
        model = ollama_chat("local-model", opener=opener)
        council = SocraticCouncil({"explorer": model, "skeptic": model}, model)
        result = await council.run("Should we implement?", {key: "known" for key, _ in QUESTIONS})
        self.assertEqual(result.status, "DISSENT")
        self.assertFalse(result.execution_authority)

    def test_no_remote_model_origin_or_duplicate_members(self):
        with self.assertRaises(ValueError):
            ollama_chat("model", origin="https://external.example")
        with self.assertRaises(ValueError):
            parse_members(["skeptic=m1", "skeptic=m2"])
        self.assertEqual(parse_members(["skeptic=m1", "explorer=m2"]),
                         {"skeptic": "m1", "explorer": "m2"})


if __name__ == "__main__":
    unittest.main()
