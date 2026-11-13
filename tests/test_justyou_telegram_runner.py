import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock

from unlimited.justyou_telegram import TelegramInboundAdapter
from unlimited.justyou_telegram_runner import TelegramPollRunner


class RunnerTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = str(Path(self.temp.name) / "offset.sqlite")
        self.adapter = Mock(spec=TelegramInboundAdapter)
        self.token = "123456789:fake-telegram-token-for-test"

    def runner(self, fetch):
        return TelegramPollRunner(token=self.token, adapter=self.adapter,
                                  state_path=self.path, fetch=fetch)

    def test_offset_committed_after_effect_and_restart(self):
        updates = [{"update_id": 42, "message": {"text": "hi"}}]
        runner = self.runner(lambda offset: updates if offset <= 42 else [])
        self.assertEqual(runner.poll_once(), 1)
        self.assertEqual(runner.next_offset(), 43)
        runner.close()
        restarted = self.runner(lambda offset: updates)
        self.assertEqual(restarted.poll_once(), 0)
        self.assertEqual(self.adapter.receive_update.call_count, 1)
        restarted.close()

    def test_delivery_failure_does_not_advance(self):
        update = {"update_id": 9, "message": {"text": "hi"}}
        self.adapter.receive_update.side_effect = RuntimeError("effect failure")
        runner = self.runner(lambda offset: [update])
        with self.assertRaisesRegex(RuntimeError, "effect failure"):
            runner.poll_once()
        self.assertEqual(runner.next_offset(), 0)
        self.adapter.receive_update.side_effect = None
        self.assertEqual(runner.poll_once(), 1)
        self.assertEqual(runner.next_offset(), 10)
        runner.close()

    def test_second_consumer_rejected(self):
        first = self.runner(lambda offset: [])
        with self.assertRaisesRegex(RuntimeError, "ALREADY_RUNNING"):
            self.runner(lambda offset: [])
        first.close()

    def test_untrusted_update_blocks_checkpoint(self):
        runner = self.runner(lambda offset: [{"update_id": 3}])
        self.adapter.receive_update.side_effect = PermissionError("unknown")
        with self.assertRaises(PermissionError):
            runner.poll_once()
        self.assertEqual(runner.next_offset(), 0)
        runner.close()
