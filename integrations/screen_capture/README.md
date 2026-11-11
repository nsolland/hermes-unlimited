# Screen Capture — public adapter

Optional, provider-neutral visual capture for development, demonstrations, training and support.

## Working backend
FFmpeg X11 recording (Linux with an accessible X11 display), followed by ffprobe verification and a SHA-256 manifest. This is a real executable adapter, not a mock, but it has not yet been smoke-tested against a live Hermes Unlimited UI.

```sh
python -m integrations.screen_capture.cli --output-dir ./artifacts/capture --duration 30 --display :0
```

**Privacy:** Record only desktops and accounts where recording is authorized. Isolate test data. Do not record credentials, notifications, private customer information, or audio. The recorder has no automatic redaction; safe environment setup is required.

## External open-source engines
- [Screenplay](https://github.com/gmpetrov/agent-screenplay): agent-driven recording/editing. Integration candidate; not bundled.
- [voila](https://github.com/halleylabs/voila): headless narrated browser demo candidate; not bundled.
- [OpenScreen](https://github.com/getopenscreen/openscreen): postproduction candidate; not bundled.
- [FFmpeg](https://ffmpeg.org/): local capture/encoding, installed separately.
- [OBS Studio](https://obsproject.com/): optional live screen/scene capture; not bundled.

External projects are linked, not vendored, and retain their own licenses. No proprietary production engine or paywall code is included here.

## Next verification
Run local unit tests and an actual X11 capture smoke test. Add provider adapters only after validating upstream APIs and licenses. Keep changes on feature branch; do not merge automatically.
