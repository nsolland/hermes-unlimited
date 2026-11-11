"""Bounded demo build pipeline for Hermes Unlimited product demos.

Issue #9 fragment 2 of N (continuation of ``demo_recorder`` fragment 1).

Fragment 1 supplied the recorder, manifest writer, screenshot capture and
log sanitisation primitives.  Fragment 2 supplies the fail-closed read-only
preflight check and the single-command offline pipeline that turns a plain
scenario spec into a branded demo package: screenshots, an MP4 and a source
manifest that carries sanitised execution logs.

All behaviour is deterministic and offline: no display, browser or network is
opened.  Recording is delegated to a trusted ``ffmpeg`` binary, exactly as in
``demo_recorder``.
"""
from __future__ import annotations

import tempfile
from dataclasses import dataclass
from pathlib import Path

from unlimited.demo_recorder import (
    DemoRecorder,
    DemoRecorderError,
    DemoScenario,
    FfmpegMissingArgError,
    capture_screenshot,
    preflight_selectors,
    sanitize_logs,
    write_manifest,
)


@dataclass(frozen=True)
class DemoPackage:
    """The reproducible, offline-assessable artefact produced by the pipeline."""

    mp4: Path
    screenshot: Path
    manifest: Path
    sanitized_logs: Path
    ffprobe: dict


class DemoScenarioSpecError(DemoRecorderError):
    """A scenario spec (plain dict) failed validation."""


def from_spec(spec: dict) -> DemoScenario:
    """Build a validated :class:`DemoScenario` from a plain-dict spec.

    Fail closed: every required key must be present and well-shaped before a
    scenario can be used for preflight or recording.
    """
    if not isinstance(spec, dict):
        raise DemoScenarioSpecError(f"spec must be a dict, got {type(spec).__name__}")
    required = ("name", "selectors", "duration_seconds", "width", "height", "narration")
    missing = [key for key in required if key not in spec]
    if missing:
        raise DemoScenarioSpecError(f"missing spec keys: {sorted(missing)}")

    name = spec["name"]
    selectors = tuple(spec["selectors"])
    duration_seconds = spec["duration_seconds"]
    width = spec["width"]
    height = spec["height"]
    narration = spec["narration"]
    brand = spec.get("brand", "Hermes Unlimited")

    if not isinstance(name, str) or not name.strip():
        raise DemoScenarioSpecError("name must be a non-empty string")
    if not isinstance(duration_seconds, int) or duration_seconds <= 0:
        raise DemoScenarioSpecError("duration_seconds must be a positive int")
    for key, value in (("width", width), ("height", height)):
        if not isinstance(value, int) or value <= 0:
            raise DemoScenarioSpecError(f"{key} must be a positive int")
    if not isinstance(narration, str):
        raise DemoScenarioSpecError("narration must be a string")

    return DemoScenario(
        name=name.strip(),
        selectors=selectors,
        duration_seconds=duration_seconds,
        width=width,
        height=height,
        narration=narration,
        brand=brand,
    )


def check_scenario(scenario: DemoScenario) -> None:
    """Fail-closed preflight WITHOUT recording.

    Issue #9 scope item 4 requires a "check scenario without recording"
    step.  This is exactly that step: every selector is inspected and the
    frame size is validated, but no audio/video data is produced and no
    ffmpeg encoding is started.
    """
    if not isinstance(scenario, DemoScenario):
        raise DemoScenarioSpecError("scenario must be a DemoScenario")
    preflight_selectors(scenario.selectors)
    if scenario.duration_seconds <= 0:
        raise FfmpegMissingArgError("duration must be positive")


def build_demo_package(
    scenario: DemoScenario,
    source_revision: str,
    output_dir: Path | None = None,
    *,
    ffmpeg_path: str | None = None,
    raw_logs: str = "",
) -> DemoPackage:
    """Run the single-command offline pipeline for one demo scenario.

    Ordered guarantees:
      1. fail-closed preflight with no recording;
      2. branded screenshot capture;
      3. MP4 record via :class:`DemoRecorder`;
      4. ffprobe validation of the produced MP4;
      5. source manifest with the immutable *source_revision*;
      6. sanitised execution logs written as plain text.

    Returns the pinned :class:`DemoPackage` with exact output paths and the
    ffprobe report.  Everything is written under *output_dir* (created if
    missing) so the caller retains exact, verifiable paths.
    """
    if not isinstance(scenario, DemoScenario):
        raise DemoScenarioSpecError("scenario must be a DemoScenario")
    if not isinstance(source_revision, str) or not source_revision.strip():
        raise DemoScenarioSpecError("source_revision must be a non-empty string")

    output_dir = Path(output_dir) if output_dir else Path(
        tempfile.mkdtemp(prefix="demo-package-")
    )
    output_dir.mkdir(parents=True, exist_ok=True)

    # 1. Read-only preflight: no recording happens here.
    check_scenario(scenario)

    # 2. Branded screenshot (solid-colour placeholder, offline).
    screenshot_path = output_dir / f"{scenario.name}.png"
    capture_screenshot(screenshot_path, width=scenario.width, height=scenario.height)

    # 3. MP4 record.
    recorder = DemoRecorder(
        ffmpeg_path=ffmpeg_path,
        output_dir=output_dir,
        default_width=scenario.width,
        default_height=scenario.height,
        default_duration=scenario.duration_seconds,
    )
    mp4_path = recorder.record(scenario)

    # 4. ffprobe validation of the produced MP4.
    ffprobe = recorder.validate_output(mp4_path)

    # 5. Source manifest carrying the immutable source revision.
    manifest_path = output_dir / f"{scenario.name}.manifest.json"
    write_manifest(scenario, source_revision, manifest_path)

    # 6. Sanitised execution logs.
    sanitized = sanitize_logs(raw_logs)
    sanitized_logs_path = output_dir / f"{scenario.name}.sanitized.log"
    sanitized_logs_path.write_text(sanitized, encoding="utf-8")
    if not sanitized_logs_path.is_file():
        raise DemoRecorderError(f"sanitised logs not written: {sanitized_logs_path}")

    return DemoPackage(
        mp4=mp4_path,
        screenshot=screenshot_path,
        manifest=manifest_path,
        sanitized_logs=sanitized_logs_path,
        ffprobe=ffprobe,
    )
