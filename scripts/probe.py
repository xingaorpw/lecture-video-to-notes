"""Preflight a lecture recording: stream durations, audio level, fatal warnings."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from common import preflight_media


def main() -> int:
    parser = argparse.ArgumentParser(description="Check whether a recording is usable for ASR")
    parser.add_argument("video")
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--min-audio-seconds", type=float, default=10.0)
    args = parser.parse_args()
    result = preflight_media(Path(args.video), min_audio_seconds=args.min_audio_seconds)
    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print(f"audio={result.get('has_audio')} audio_duration={result.get('audio_duration'):.2f}s "
              f"video_duration={result.get('video_duration'):.2f}s")
        for warning in result.get("warnings", []):
            print("WARN", warning)
        print("OK" if result.get("ok") else "FATAL")
    return 0 if result.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
