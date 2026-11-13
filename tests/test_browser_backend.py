"""Tests for the real-browser backend adapters (issue #16).

All tests are offline and deterministic. No display, real browser or network is
opened: the Playwright backend gracefully falls back to the bounded NullBackend
when a real browser is unavailable.
"""

import json
import shutil
import tempfile
import unittest
from pathlib import Path

from unlimited.browser_backend import (
    CaptureResult,
    NullBackend,
    PlaywrightBackend,
)
from unlimited.demo_pipeline import from_spec


class NullBackendTests(unittest.TestCase):
    def setUp(self):
        self.backend = NullBackend()
        self.scenario = from_spec(
            {
                "name": "demo-null",
                "selectors": ("button.start", "span.status"),
                "duration_seconds": 2,
                "width": 640,
                "height": 360,
                "narration": "Welcome.",
            }
        )
        self.tmp = Path(tempfile.mkdtemp(prefix="nbb-"))

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_capture_returns_reproducible_evidence(self):
        result = self.backend.capture(
            self.scenario, "feedf00d", raw_logs="token=AKEY12345", output_dir=self.tmp
        )
        self.assertIsInstance(result, CaptureResult)
        self.assertTrue(result.mp4.is_file())
        self.assertTrue(result.screenshot.is_file())
        self.assertTrue(result.manifest.is_file())
        self.assertTrue(result.sanitized_logs.is_file())
        self.assertIn("nb_frames", result.ffprobe)

    def test_capture_secrets_redacted(self):
        result = self.backend.capture(
            self.scenario, "deadbeef", raw_logs="url=/x token=AKEY12345", output_dir=self.tmp
        )
        text = result.sanitized_logs.read_text(encoding="utf-8")
        self.assertNotIn("AKEY12345", text)
        self.assertIn("***REDACTED***", text)

    def test_capture_immutable_assets(self):
        first = self.backend.capture(
            self.scenario, "aabbcc", raw_logs="", output_dir=self.tmp / "run1"
        )
        second = self.backend.capture(
            self.scenario, "aabbcc", raw_logs="", output_dir=self.tmp / "run2"
        )
        self.assertEqual(first.mp4.read_bytes(), second.mp4.read_bytes())
        self.assertEqual(first.screenshot.read_bytes(), second.screenshot.read_bytes())
        # The manifest has a generated_at timestamp that changes between runs.
        f = json.loads(first.manifest.read_text(encoding="utf-8"))
        s = json.loads(second.manifest.read_text(encoding="utf-8"))
        f.pop("generated_at")
        s.pop("generated_at")
        self.assertEqual(f, s)


class PlaywrightBackendTests(unittest.TestCase):
    """PlaywrightBackend must fall back to NullBackend when no real browser."""

    def setUp(self):
        self.backend = PlaywrightBackend(use_real=False)
        self.scenario = from_spec(
            {
                "name": "demo-fallback",
                "selectors": ("button.start",),
                "duration_seconds": 1,
                "width": 640,
                "height": 360,
                "narration": "Test.",
            }
        )
        self.tmp = Path(tempfile.mkdtemp(prefix="pbb-"))

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_capture_falls_back_to_null(self):
        result = self.backend.capture(
            self.scenario, "deadbeef", raw_logs="", output_dir=self.tmp
        )
        self.assertTrue(result.mp4.is_file())
        self.assertTrue(result.manifest.is_file())
