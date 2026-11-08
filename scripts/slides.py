"""Extract slide/PPT frames from a classroom recording.

This is the fallback when a recording has no usable audio.  It deliberately does
not OCR or invent content: the agent reads the images and records provenance.
"""
from __future__ import annotations

import argparse
from pathlib import Path

from common import ensure_dir, load_course, now_iso, preflight_media, write_json


def extract(
    video: Path,
    out_dir: Path,
    *,
    interval: float = 60.0,
    start: float = 0.0,
    end: float | None = None,
) -> dict:
    import av

    ensure_dir(out_dir)
    times: list[float] = []
    with av.open(str(video)) as container:
        stream = next((s for s in container.streams if s.type == "video"), None)
        if stream is None:
            raise RuntimeError(f"没有视频流：{video}")
        duration = float(stream.duration * stream.time_base) if stream.duration else 0.0
        stop = min(duration, end) if end else duration
        t = max(0.0, start)
        while t < stop:
            times.append(t)
            t += max(1.0, interval)

        for t in times:
            container.seek(int(t * 1_000_000), stream=stream, backward=True)
            frame = None
            for f in container.decode(stream):
                if f.pts is not None and float(f.pts * stream.time_base) >= t:
                    frame = f
                    break
            if frame is not None:
                frame.to_image().save(out_dir / f"t{int(t):05d}.jpg", quality=88)

    meta = {
        "video": str(video),
        "duration": round(duration, 3),
        "interval": interval,
        "frames": len(times),
        "dir": str(out_dir),
        "created": now_iso(),
    }
    write_json(out_dir / "slides.json", meta)
    return meta


def main() -> int:
    parser = argparse.ArgumentParser(description="Extract slide frames from a lecture recording")
    parser.add_argument("--workdir", help="lecture workdir containing course.json")
    parser.add_argument("--video", help="video path (overrides workdir/source_video)")
    parser.add_argument("--interval", type=float, default=60.0)
    parser.add_argument("--start", type=float, default=0.0)
    parser.add_argument("--end", type=float, default=None)
    parser.add_argument("--out", default=None)
    parser.add_argument("--delete-video", action="store_true", help="delete source video after extraction")
    args = parser.parse_args()

    if args.video:
        video = Path(args.video).expanduser().resolve()
        workdir = Path(args.workdir).expanduser().resolve() if args.workdir else video.parent
    else:
        if not args.workdir:
            raise SystemExit("need --video or --workdir")
        workdir = Path(args.workdir).expanduser().resolve()
        video = Path(load_course(workdir)["source_video"])
    if not video.exists():
        raise SystemExit(f"video not found: {video}")

    check = preflight_media(video)
    for warning in check.get("warnings", []):
        print(f"[slides] WARN {warning}")
    out = Path(args.out).expanduser().resolve() if args.out else workdir / "slides"
    meta = extract(video, out, interval=args.interval, start=args.start, end=args.end)
    print(f"[slides] {meta['frames']} frames -> {out}")
    if args.delete_video:
        video.unlink()
        print(f"[slides] deleted {video}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
