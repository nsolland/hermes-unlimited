import base64
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from unlimited.public_doctor import diagnose
from unlimited.completion_lite import Task, Observation, assess, ready
from unlimited.ghost_adapter import GhostAdmin, GhostError, admin_jwt


class SharedPublicTests(unittest.TestCase):
    def test_doctor_never_claims_live_runtime(self):
        with tempfile.TemporaryDirectory() as root:
            output = diagnose(root=root, binaries=())
            self.assertFalse(output["ready_for_local_plugin_inspection"])
            self.assertFalse(output["live_host_verified"])
            self.assertFalse(output["customer_execution_verified"])

    def test_completion_preserves_main_goal(self):
        tasks = [Task("a"), Task("b", ("a",))]
        self.assertEqual(ready(tasks, {}), ("a",))
        incomplete = assess(tasks, {"a": Observation("COMPLETED")})
        self.assertEqual(incomplete["status"], "INCOMPLETE")
        self.assertFalse(incomplete["goal_verified"])
        self.assertEqual(ready(tasks, {"a": Observation("COMPLETED", "digest", True)}), ("b",))
        verified = assess(tasks, {"a": Observation("COMPLETED", "digest", True),
                                  "b": Observation("COMPLETED", "digest2", True)})
        self.assertEqual(verified["status"], "TASKS_VERIFIED")
        self.assertFalse(verified["goal_verified"])

    def test_cycles_and_unknown_results_fail(self):
        with self.assertRaises(ValueError):
            assess([Task("a", ("b",)), Task("b", ("a",))], {})
        with self.assertRaises(ValueError):
            assess([Task("a")], {"b": Observation("COMPLETED", "d", True)})

    def test_ghost_short_lived_jwt(self):
        token = admin_jwt("id:" + "ab" * 32, now=1000)
        head, body, signature = token.split(".")
        decoded = json.loads(base64.urlsafe_b64decode(body + "==="))
        self.assertEqual(decoded["exp"], 1300)
        self.assertEqual(decoded["aud"], "/admin/")
        self.assertTrue(signature)

    def test_ghost_create_draft_and_readback(self):
        requests = []
        class Response:
            def __init__(self, payload): self.payload = payload
            def __enter__(self): return self
            def __exit__(self, *args): return False
            def read(self, _limit): return json.dumps(self.payload).encode()
        identifier = "a" * 24
        def opener(request, timeout):
            requests.append(request)
            if request.get_method() == "POST":
                return Response({"posts": [{"id": identifier, "status": "draft"}]})
            return Response({"posts": [{"id": identifier, "status": "draft", "title": "My post"}]})
        client = GhostAdmin("https://example.com", "id:" + "ab" * 32, opener=opener)
        result = client.create_draft("My post", "<h1>Hello</h1>")
        self.assertFalse(result["readback_verified"])
        readback = client.read_post(identifier)
        self.assertTrue(readback["readback_verified"])
        self.assertEqual(requests[0].get_method(), "POST")
        self.assertEqual(requests[1].get_method(), "GET")

    def test_ghost_never_exposes_key_in_errors(self):
        with self.assertRaises(ValueError):
            GhostAdmin("https://user:pass@example.com", "id:" + "ab" * 32)
        with self.assertRaises(ValueError):
            admin_jwt("secret")
        with self.assertRaises(ValueError):
            GhostAdmin("http://external.example", "id:" + "ab" * 32)
        def failing_opener(*args, **kwargs):
            raise TimeoutError("secret remote message")
        client = GhostAdmin("https://example.com", "id:" + "ab" * 32, opener=failing_opener)
        with self.assertRaisesRegex(GhostError, "^Ghost request failed$"):
            client.create_draft("Post", "text")

    def test_ghost_fails_closed_on_wrong_post(self):
        class Response:
            def __enter__(self): return self
            def __exit__(self, *args): return False
            def read(self, _limit): return b'{"posts":[{"id":"bbbbbbbbbbbbbbbbbbbbbbbb"}]}'
        client = GhostAdmin("https://example.com", "id:" + "ab" * 32,
                            opener=lambda req, timeout: Response())
        with self.assertRaises(GhostError):
            client.read_post("a" * 24)


if __name__ == "__main__":
    unittest.main()
