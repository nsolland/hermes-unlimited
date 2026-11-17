import json
import unittest
from unittest.mock import patch
from scripts import harness_salad_worker as worker


class Response:
    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def read(self):
        return json.dumps({
            "model": worker.MODEL,
            "choices": [{"message": {"content": "650"}}],
            "usage": {"prompt_tokens": 50, "completion_tokens": 2}
        }).encode()


class SaladWorkerTests(unittest.TestCase):
    def test_baseline_and_checker_only_differ_in_verification(self):
        self.assertTrue(worker.CHECK.startswith(worker.BASE))
        self.assertIn("verify", worker.CHECK.lower())
        self.assertEqual(worker.MAX_ATTEMPTS, 40)
        self.assertEqual(str(worker.MODEL_BUDGET_USD), "0.40")

    def test_gateway_payload_has_no_oracle_answer(self):
        recorded = []

        def respond(req, timeout):
            recorded.append(json.loads(req.data))
            self.assertEqual(timeout, worker.TIMEOUT_SECONDS)
            return Response()

        with patch("urllib.request.urlopen", side_effect=respond):
            result = worker.send("Calculate sum of squares 1 to 12", worker.CHECK, "test-value")
        self.assertEqual(result["answer"], "650")
        self.assertEqual(result["model_returned"], worker.MODEL)
        self.assertIsNone(result["error"])
        self.assertEqual(len(recorded), 1)
        self.assertNotIn("650", json.dumps(recorded[0]))
        self.assertEqual(recorded[0]["model"], worker.MODEL)
        self.assertEqual(recorded[0]["temperature"], 0)

    def test_unreachable_gateway_fails_as_observation(self):
        from urllib.error import URLError
        with patch("urllib.request.urlopen", side_effect=URLError("offline")):
            result = worker.send("test", worker.BASE, "test-value")
        self.assertEqual(result["error"], "URLError")
        self.assertEqual(result["answer"], "")


if __name__ == "__main__":
    unittest.main()
