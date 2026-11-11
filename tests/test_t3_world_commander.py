import unittest
from unlimited.t3_world_commander import T3WorldCommanderClient, T3ClientError


class T3ClientTests(unittest.TestCase):
    def test_scoped_start_and_read(self):
        calls = []
        def dispatcher(operation, **kwargs):
            calls.append((operation, kwargs))
            return {"thread_id": "thread_1", "completed": False,
                    "verified": False, "evidence_ref": "effect_1"}
        client = T3WorldCommanderClient(dispatcher, tenant="tenant-a", project_id="project_1")
        self.assertEqual(client.start("Fix a test")["thread_id"], "thread_1")
        client.read("thread_1")
        self.assertEqual(calls[0], ("t3.start", {"tenant": "tenant-a", "project_id": "project_1", "instruction": "Fix a test"}))
        self.assertEqual(calls[1][1]["tenant"], "tenant-a")

    def test_fail_closed(self):
        client = T3WorldCommanderClient(lambda *_a, **_k: {}, tenant="tenant-a", project_id="project_1")
        with self.assertRaises(T3ClientError):
            client.start("Fix a test")
        with self.assertRaises(ValueError):
            client.read("../escape")
        client = T3WorldCommanderClient(lambda *_a, **_k: {"thread_id": "thread_1", "completed": True,
                                                           "evidence_ref": "r"}, tenant="tenant-a", project_id="project_1")
        with self.assertRaises(T3ClientError):
            client.start("Fix a test")
        client = T3WorldCommanderClient(lambda *_a, **_k: {"thread_id": "thread_1", "completed": False,
                                                           "verified": True, "evidence_ref": "r"}, tenant="tenant-a", project_id="project_1")
        with self.assertRaises(T3ClientError):
            client.start("Fix a test")


if __name__ == "__main__":
    unittest.main()
