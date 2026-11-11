import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from integrations.screen_capture.adapter import CaptureAdapter, CaptureConfig, CaptureError

class ScreenCaptureTests(unittest.TestCase):
    def test_duration_bounds(self):
        with self.assertRaises(ValueError):
            CaptureAdapter().record(CaptureConfig(Path("/tmp"), duration_seconds=0))

    def test_reject_unsupported_source(self):
        with self.assertRaises(CaptureError):
            CaptureAdapter().record(CaptureConfig(Path("/tmp"), source="avfoundation"))

    def test_missing_binary(self):
        with patch("integrations.screen_capture.adapter.shutil.which", return_value=None):
            with self.assertRaises(CaptureError):
                CaptureAdapter().record(CaptureConfig(Path("/tmp")))

if __name__ == "__main__":
    unittest.main()
