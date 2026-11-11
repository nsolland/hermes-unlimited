"""Provider-neutral screen recording with safe subprocess invocation."""
from dataclasses import dataclass
from pathlib import Path
import json
import os
import shutil
import subprocess
import time

class CaptureError(RuntimeError):
    pass

@dataclass(frozen=True)
class CaptureConfig:
    output_dir: Path
    duration_seconds: int = 30
    fps: int = 30
    display: str = ":0"
    source: str = "x11grab"
    width: int = 1280
    height: int = 720

@dataclass(frozen=True)
class CaptureResult:
    video: Path
    manifest: Path

class CaptureAdapter:
    """Local FFmpeg engine; other providers can implement the same record contract."""
    provider = "ffmpeg"

    def __init__(self, runner=subprocess.run):
        self.runner = runner

    def record(self, config: CaptureConfig) -> CaptureResult:
        if not 1 <= config.duration_seconds <= 600:
            raise ValueError("duration_seconds must be 1..600")
        if not 1 <= config.fps <= 120 or config.width <= 0 or config.height <= 0:
            raise ValueError("invalid video dimensions or fps")
        if config.source != "x11grab":
            raise CaptureError("Only explicit X11 capture supported by this adapter")
        if not shutil.which("ffmpeg") or not shutil.which("ffprobe"):
            raise CaptureError("ffmpeg and ffprobe are required")
        directory = config.output_dir.resolve()
        directory.mkdir(parents=True, exist_ok=True)
        video = directory / "capture.mp4"
        manifest = directory / "capture.json"
        command = ["ffmpeg", "-nostdin", "-y", "-f", "x11grab", "-video_size",
                   f"{config.width}x{config.height}", "-framerate", str(config.fps),
                   "-i", config.display, "-t", str(config.duration_seconds),
                   "-an", "-c:v", "libx264", "-pix_fmt", "yuv420p", str(video)]
        started = time.time()
        try:
            self.runner(command, check=True, capture_output=True, timeout=config.duration_seconds + 45)
            probe = self.runner(["ffprobe", "-v", "error", "-show_entries",
                                 "format=duration", "-of", "json", str(video)],
                                check=True, capture_output=True, text=True, timeout=15)
            duration = float(json.loads(probe.stdout)["format"]["duration"])
            if duration <= 0 or not video.is_file() or video.stat().st_size == 0:
                raise CaptureError("empty recording")
        except (subprocess.SubprocessError, OSError, ValueError, KeyError, json.JSONDecodeError) as exc:
            raise CaptureError("recording or verification failed") from exc
        import hashlib
        digest = hashlib.sha256(video.read_bytes()).hexdigest()
        manifest.write_text(json.dumps({"provider": self.provider, "duration_seconds": duration,
            "sha256": digest, "started_at": started, "file": video.name}, indent=2) + "\n")
        return CaptureResult(video, manifest)
