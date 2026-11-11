"""Run with python -m integrations.screen_capture.cli."""
import argparse
from pathlib import Path
from .adapter import CaptureAdapter, CaptureConfig

def main():
    parser = argparse.ArgumentParser(description="Record a consented X11 test desktop to MP4")
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--duration", type=int, default=30)
    parser.add_argument("--display", default=":0")
    args = parser.parse_args()
    result = CaptureAdapter().record(CaptureConfig(
        output_dir=args.output_dir, duration_seconds=args.duration, display=args.display))
    print(result.video)
    print(result.manifest)

if __name__ == "__main__":
    main()
