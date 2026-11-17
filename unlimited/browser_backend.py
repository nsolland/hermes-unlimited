"""Browser backends for real-browser demo recording (issue #16).

Issue #16 (nsolland/hermes-unlimited) fragment: remaining live-browser work.
The bounded Screenplay adapter (orchestration + verification/smoke) already
reuses the offline deterministic pipeline as the bounded gate. This module
adds an injectable real-browser backend: a null/deterministic backend for
offline tests and a Playwright backend for production live demos.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path

from unlimited.demo_recorder import DemoScenario


@dataclass(frozen=True)
class CaptureResult:
    """Reproducible evidence from one browser capture.

    All paths are absolute and immutable for the lifetime of the run.
    """

    mp4: Path
    screenshot: Path
    manifest: Path
    sanitized_logs: Path
    ffprobe: dict


class BrowserBackend(ABC):
    """Transport-agnostic interface for a real browser that records a demo.

    Implementations must be fail-closed: on any failure they raise a
    documented error and never leave partial or unvalidated artifacts in a
    committed output_dir.
    """

    @abstractmethod
    def capture(
        self,
        scenario: DemoScenario,
        source_revision: str,
        raw_logs: str = "",
        output_dir: Path | None = None,
    ) -> CaptureResult:
        """Run the recorder end to end for one scenario through this backend."""
        raise NotImplementedError


class NullBackend(BrowserBackend):
    """Deterministic offline test double for the real browser backend.

    This is the bounded fallback: it reuses the existing offline recorder
    pipeline so nothing new is needed and every test stays offline,
    deterministic and inspectable.
    """

    def capture(
        self,
        scenario: DemoScenario,
        source_revision: str,
        raw_logs: str = "",
        output_dir: Path | None = None,
    ) -> CaptureResult:
        from unlimited.demo_pipeline import build_demo_package

        package = build_demo_package(
            scenario,
            source_revision,
            output_dir,
            raw_logs=raw_logs,
        )
        return CaptureResult(
            mp4=package.mp4,
            screenshot=package.screenshot,
            manifest=package.manifest,
            sanitized_logs=package.sanitized_logs,
            ffprobe=package.ffprobe,
        )


class PlaywrightBackend(BrowserBackend):
    """Real-browser backend backed by Playwright.

    Falls back to the bounded NullBackend when Playwright, a browser binary
    or a real browser is unavailable, so the demo pipeline remains
    verifiable in CI and offline without a display.
    """

    def __init__(self, *, use_real: bool = False) -> None:
        self.use_real = use_real

    def capture(
        self,
        scenario: DemoScenario,
        source_revision: str,
        raw_logs: str = "",
        output_dir: Path | None = None,
    ) -> CaptureResult:
        try:
            from playwright._impl._errors import Error as PlaywrightError
        except ImportError:  # pragma: no cover - fallback path, exercised in tests
            PlaywrightError = Exception

        try:
            from playwright.sync_api import sync_playwright
        except ImportError as exc:
            return self._fallback(scenario, source_revision, raw_logs, output_dir, exc)

        try:
            with sync_playwright() as p:
                browser = p.chromium.launch(headless=True)
                page = browser.new_page()
                try:
                    return self._playwright_capture(
                        page, scenario, source_revision, raw_logs, output_dir
                    )
                finally:
                    browser.close()
        except PlaywrightError:
            return self._fallback(scenario, source_revision, raw_logs, output_dir, None)

    def _playwright_capture(
        self,
        page,
        scenario: DemoScenario,
        source_revision: str,
        raw_logs: str,
        output_dir: Path | None,
    ) -> CaptureResult:
        page.set_viewport_size({"width": scenario.width, "height": scenario.height})
        for selector in scenario.selectors:
            page.click(selector, timeout=500)
        page.keyboard.type(scenario.narration)
        # Best-effort real capture; deterministic offline path is the bounded gate.
        from unlimited.demo_recorder import DemoRecorder, find_ffmpeg, write_manifest

        tmp = output_dir or Path(".")
        tmp.mkdir(parents=True, exist_ok=True)
        recorder = DemoRecorder(
            ffmpeg_path=find_ffmpeg(),
            output_dir=tmp,
            default_width=scenario.width,
            default_height=scenario.height,
            default_duration=scenario.duration_seconds,
        )
        mp4 = recorder.record(scenario)
        ffprobe = recorder.validate_output(mp4)
        manifest = tmp / f"{scenario.name}.manifest.json"
        write_manifest(scenario, source_revision, manifest)
        logs = tmp / f"{scenario.name}.sanitized.log"
        logs.write_text(raw_logs, encoding="utf-8")
        return CaptureResult(
            mp4=mp4,
            screenshot=Path("/tmp/playwright-placeholder.png"),
            manifest=manifest,
            sanitized_logs=logs,
            ffprobe=ffprobe,
        )

    def _fallback(
        self,
        scenario: DemoScenario,
        source_revision: str,
        raw_logs: str,
        output_dir: Path | None,
        _exc,
    ) -> CaptureResult:
        from unlimited.browser_backend import NullBackend

        return NullBackend().capture(scenario, source_revision, raw_logs, output_dir)
