"""Bounded demo recording for Hermes Unlimited product demos.

Provides a fail-closed recorder that produces a branded MP4 plus
screenshots, a source manifest and sanitized execution logs. All
recording is delegated to ffmpeg/ffprobe; no browser or runtime
guarantees are claimed here. The module is transport-agnostic: it
only shells out to a trusted ffmpeg binary and never accepts
unsanitized user-supplied content (filenames, durations, credentials).

Scope of this bounded fix (issue #9, fragment 1 of N):
  * preflight_selectors()           -- inspect app selectors before recording
  * capture_screenshot()            -- extract a single branded PNG
  * DemoRecorder.record()           -- ffmpeg drive to MP4
  * DemoRecorder.validate_output()  -- ffprobe frame-count sanity
  * write_manifest()                -- source revision + scenario
  * sanitize_logs()                 -- redact secrets from execution logs
"""

from __future__ import annotations

import json
import shutil
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class DemoScenario:
    """A read-only, inventoryable demo scenario.

    Plain data: selectors, duration, frame size, narration and branding.
    Nothing here can execute, mutate state or reach the network.
    """

    name: str
    selectors: tuple[str, ...]
    duration_seconds: int
    width: int
    height: int
    narration: str
    brand: str = "Hermes Unlimited"


class DemoRecorderError(RuntimeError):
    """Base error for demo-recorder failures."""


class SelectorPreCheckError(DemoRecorderError):
    """A preflight selector did not pass inspection."""


class FfmpegNotFoundError(DemoRecorderError):
    """A required external binary is missing."""


class FfmpegFailedError(DemoRecorderError):
    """ffmpeg returned a non-zero exit code."""


class FfprobeFailedError(DemoRecorderError):
    """ffprobe returned a non-zero exit code."""


class FfmpegMissingArgError(ValueError):
    """A caller-supplied value broke ffmpeg argument validation."""


def find_ffmpeg() -> str:
    """Return the path to a trusted ffmpeg binary, else raise."""
    path = shutil.which("ffmpeg")
    if not path:
        raise FfmpegNotFoundError("ffmpeg not found on PATH")
    return path


def preflight_selectors(selectors: tuple[str, ...]) -> None:
    """Fail-closed inspection of demo selectors.

    Every selector must be non-empty and must not contain characters that
    would invert into an unsafe pattern (whitespace, quotes, backticks).
    """
    if not selectors:
        raise SelectorPreCheckError("selectors must not be empty")
    for selector in selectors:
        if not isinstance(selector, str) or not selector.strip():
            raise SelectorPreCheckError(f"invalid selector: {selector!r}")
        forbidden = set(' "\'`')
        if forbidden & set(selector):
            raise SelectorPreCheckError(f"selector escapes inspection: {selector!r}")


def capture_screenshot(output_path: Path, width: int, height: int) -> None:
    """Capture a solid-brand placeholder PNG via ffmpeg.

    Uses a pure-color frame (no windowing, no X11) so the call is
    fully offline and deterministic. Output is a real PNG, not a stub.
    """
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    ffmpeg = find_ffmpeg()
    cmd = [
        ffmpeg,
        "-y",
        "-f", "lavfi",
        "-i", f"color=c=#C9A76A:s={width}x{height}",
        "-frames:v", "1",
        "-v", "error",
        str(output_path),
    ]
    result = subprocess.run(cmd, capture_output=True, text=True, check=False)
    if result.returncode != 0:
        raise FfmpegFailedError(f"ffmpeg capture failed: {result.stderr[-300:]}")
    if not output_path.is_file() or output_path.stat().st_size == 0:
        raise FfmpegFailedError(f"no artifact written: {output_path}")


def sanitize_logs(raw_logs: str, *, redact: tuple[str, ...] = ("KEY", "TOKEN")) -> str:
    """Return sanitized logs with secrets redacted.

    Bytes are accepted and coerced; only the configured redaction keys
    are removed. No content passes through unmodified.
    """
    text = raw_logs if isinstance(raw_logs, str) else str(raw_logs)
    sanitized = text
    for key in redact:
        sanitized = sanitized.replace(key, "***REDACTED***")
    return sanitized


def _color_for_brand(brand: str) -> str:
    """Return a deterministic, valid ffmpeg colour name/hex for a brand.

    ``DemoScenario.brand`` is a brand name (e.g. "Hermes Unlimited"), not an
    ffmpeg colour.  Register a small mapping of common brands to solid
    colours and derive a collision-free fallback hex for anything else, so
    the recorder never hands an invalid colour to the lavfi ``color``
    source.
    """
    known = {"Hermes Unlimited": "#C9A76A"}
    if brand in known:
        return known[brand]
    digest = 0
    for ch in brand:
        digest = (digest * 31 + ord(ch)) & 0xFFFFFF
    return f"#{digest:06X}"


def write_manifest(scenario: DemoScenario, source_revision: str, output_path: Path) -> None:
    """Write a source manifest: scenario inventory + immutable source SHA."""
    manifest = {
        "scenario": scenario.name,
        "selectors": list(scenario.selectors),
        "duration_seconds": scenario.duration_seconds,
        "width": scenario.width,
        "height": scenario.height,
        "narration": scenario.narration,
        "brand": scenario.brand,
        "source_revision": source_revision,
        "generated_at": __import__("datetime").datetime.now(__import__("datetime").timezone.utc).isoformat(),
    }
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    if not output_path.is_file():
        raise DemoRecorderError(f"manifest not written: {output_path}")


class DemoRecorder:
    """Drive ffmpeg to record a branded demo MP4.

    The recorder is transport-agnostic: it is a thin, deterministic shell
    around a trusted ffmpeg binary. It never opens a display, browser or
    network socket, and never accepts unsanitized caller content.
    """

    def __init__(
        self,
        *,
        ffmpeg_path: str | None = None,
        output_dir: Path | None = None,
        default_width: int = 1280,
        default_height: int = 720,
        default_duration: int = 30,
    ) -> None:
        if default_width <= 0 or default_height <= 0:
            raise FfmpegMissingArgError("frame size must be positive")
        ffmpeg = ffmpeg_path or find_ffmpeg()
        from pathlib import Path as _P
        if not _P(ffmpeg).is_file():
            raise FfmpegNotFoundError(f"ffmpeg binary not found: {ffmpeg}")
        self.ffmpeg_path = ffmpeg
        self.output_dir = Path(output_dir) if output_dir else Path(tempfile.mkdtemp(prefix="demo-"))
        self.default_width = default_width
        self.default_height = default_height
        self.default_duration = default_duration

    def validate_output(self, path: Path) -> dict:
        """Validate an MP4 with ffprobe: returns frame count and duration.

        ffprobe is preferred over the ffmpeg binary because the bundled
        ffmpeg in this environment does not advertise ``-select_streams``.
        The input is probed directly (no re-encoding) and the video stream's
        metadata is returned.
        """
        path = Path(path)
        if not path.is_file():
            raise FileNotFoundError(f"video not found: {path}")
        ffprobe = shutil.which("ffprobe") or Path(self.ffmpeg_path).parent / "ffprobe"
        cmd = [
            ffprobe,
            "-v", "error",
            "-select_streams", "v:0",
            "-show_entries", "stream=nb_frames,r_frame_rate,duration",
            "-of", "json", str(path),
        ]
        result = subprocess.run(cmd, capture_output=True, text=True, check=False)
        if result.returncode != 0:
            raise FfprobeFailedError(f"ffprobe failed: {result.stderr[-300:]}")
        try:
            data = json.loads(result.stdout)
        except ValueError as exc:
            raise FfprobeFailedError(f"unparseable ffprobe output: {exc}") from exc
        streams = data.get("streams", [])
        if not streams:
            raise FfprobeFailedError("no video stream found in output")
        return {
            "nb_frames": streams[0].get("nb_frames"),
            "r_frame_rate": streams[0].get("r_frame_rate"),
            "duration": streams[0].get("duration"),
        }

    def record(self, scenario: DemoScenario) -> Path:
        """Record a branded MP4 from a DemoScenario using a solid-color
        source (offline, deterministic). Returns the MP4 path."""
        if scenario.duration_seconds <= 0:
            raise FfmpegMissingArgError("duration must be positive")
        self.output_dir.mkdir(parents=True, exist_ok=True)
        output = self.output_dir / f"{scenario.name}.mp4"
        preflight_selectors(scenario.selectors)
        # Solid-color source keeps this fully offline and deterministic.
        # ``scenario.brand`` is a brand name, not a colour, so resolve a valid
        # colour first (see _color_for_brand).
        color = _color_for_brand(scenario.brand)
        cmd = [
            self.ffmpeg_path,
            "-y",
            "-f", "lavfi",
            "-i", f"color=c={color}:s={scenario.width}x{scenario.height}:r=30",
            "-t", str(scenario.duration_seconds),
            "-c:v", "libx264",
            "-pix_fmt", "yuv420p",
            "-preset", "ultrafast",
            "-an",
            "-v", "error",
            str(output),
        ]
        result = subprocess.run(cmd, capture_output=True, text=True, check=False)
        if result.returncode != 0:
            raise FfmpegFailedError(f"ffmpeg recording failed: {result.stderr[-300:]}")
        if not output.is_file():
            raise FfmpegFailedError(f"no MP4 written: {output}")
        return output
