import io
import json
import unittest
from urllib.error import URLError

from unlimited.comfyui import ComfyUI, ComfyUIError


class Response(io.BytesIO):
    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()


class ComfyUITests(unittest.TestCase):
    def setUp(self):
        self.calls = []
        self.responses = []

        def opener(request, timeout):
            self.calls.append((request, timeout))
            response = self.responses.pop(0)
            if isinstance(response, Exception):
                raise response
            return Response(response if isinstance(response, bytes) else json.dumps(response).encode())

        self.client = ComfyUI(opener=opener)

    def test_submit_and_status(self):
        self.responses = [{"prompt_id": "abc-123", "number": 1},
                          {"abc-123": {"status": {"completed": True, "status_str": "success"},
                                       "outputs": {"9": {"images": [{"filename": "out.png"}]}}}}]
        self.assertEqual(self.client.submit({"1": {"class_type": "SaveImage", "inputs": {}}})["prompt_id"], "abc-123")
        payload = json.loads(self.calls[0][0].data)
        self.assertIn("prompt", payload)
        self.assertEqual(self.client.result("abc-123")["state"], "completed")
        self.assertEqual(self.client.result.__name__, "result")

    def test_unknown_failure_and_pending(self):
        self.responses = [{}, {"job": {"status": {"status_str": "error", "completed": False}}},
                          {"job": {"status": {"status_str": "running", "completed": False}}}]
        self.assertEqual(self.client.result("job")["state"], "unknown")
        self.assertEqual(self.client.result("job")["state"], "failed")
        self.assertEqual(self.client.result("job")["state"], "pending")

    def test_artifact_and_input_validation(self):
        self.responses = [b"PNG"]
        self.assertEqual(self.client.download(filename="image 1.png"), b"PNG")
        self.assertIn("image+1.png", self.calls[-1][0].full_url)
        for name in ("../secret", "a\\b", "", "."):
            with self.assertRaises(ValueError):
                self.client.download(filename=name)
        with self.assertRaises(ValueError):
            self.client.download(filename="x", subfolder="../secrets")
        with self.assertRaises(ValueError):
            self.client.submit({})
        with self.assertRaises(ValueError):
            self.client.history("../secret")
        with self.assertRaises(ValueError):
            ComfyUI("http://username:password@localhost:8188")

    def test_fail_closed_transport_and_protocol(self):
        self.responses = [URLError("offline"), {"error": "bad workflow"}, b"garbage"]
        with self.assertRaises(ComfyUIError):
            self.client.submit({"1": {}})
        with self.assertRaises(ComfyUIError):
            self.client.submit({"1": {}})
        with self.assertRaises(ComfyUIError):
            self.client.history("job")


if __name__ == "__main__":
    unittest.main()
