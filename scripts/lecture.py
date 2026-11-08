"""CLI entry point for lecture-video-to-notes."""
from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

from common import (
    ensure_dir,
    load_course,
    now_iso,
    probe_duration,
    read_json,
    write_json,
)
from doctor import build_report, print_human
from transcribe import transcribe
from chunk import chunk_transcript
from assemble import assemble
from docx_build import build_docx
from pptx_build import build_pptx
from validate import validate


def cmd_init(args) -> int:
    video = Path(args.video).expanduser().resolve()
    if not video.exists():
        raise FileNotFoundError(f"Video not found: {video}")
    workdir = ensure_dir(Path(args.workdir).expanduser().resolve())
    for sub in ("audio", "transcript", "transcript/chunks", "notes/chapters", "notes/appendices", "notes/assets", "output", "logs"):
        ensure_dir(workdir / sub)

    course_path = workdir / "course.json"
    existing = read_json(course_path) if course_path.exists() else {}
    glossary = [x.strip() for x in (args.glossary or "").split(",") if x.strip()]
    probed_duration = probe_duration(video)
    data = {
        **existing,
        "course": args.course or existing.get("course", ""),
        "lecture": args.lecture or existing.get("lecture", ""),
        "instructor": args.instructor or existing.get("instructor", ""),
        "source_video": str(video),
        "language": args.language or existing.get("language", "zh"),
        "glossary": glossary or existing.get("glossary", []),
        # A new source must not inherit the previous file's duration.
        "duration_sec": probed_duration or existing.get("duration_sec") or 0,
        "created": existing.get("created") or now_iso(),
        "updated": now_iso(),
    }
    write_json(course_path, data)
    print(f"[init] workdir={workdir}")
    print(f"[init] course={data['course']} lecture={data['lecture']} duration={data['duration_sec']:.1f}s")
    return 0


def cmd_doctor(args) -> int:
    report = build_report()
    if args.json:
        from common import print_json

        print_json(report)
    else:
        print_human(report)
    return 0 if report["ok"] else 1


def cmd_transcribe(args) -> int:
    workdir = Path(args.workdir).expanduser().resolve()
    result = transcribe(
        workdir,
        language=args.language,
        model=args.model,
        device=args.device,
        compute_type=args.compute_type,
        beam_size=args.beam_size,
        initial_prompt=args.initial_prompt,
        start=args.start,
        end=args.end,
        simplify=getattr(args, "simplify", True),
        no_vad=getattr(args, "no_vad", False),
    )
    print(f"OK segments={result['segments']} duration={result['duration']:.1f}s")
    return 0


def _run_tool(script: str, argv: list[str]) -> int:
    path = Path(__file__).resolve().parent / script
    return subprocess.run([sys.executable, str(path), *argv]).returncode


def cmd_slides(args) -> int:
    argv = ["--workdir", args.workdir, "--interval", str(args.interval)]
    if args.start:
        argv += ["--start", str(args.start)]
    if args.end:
        argv += ["--end", str(args.end)]
    if args.delete_video:
        argv.append("--delete-video")
    return _run_tool("slides.py", argv)


def cmd_validate_notes(args) -> int:
    return _run_tool(
        "validate_notes.py",
        [
            "--workdir",
            args.workdir,
            "--min-chapters",
            str(args.min_chapters),
            "--min-chars",
            str(args.min_chars),
            "--min-questions",
            str(args.min_questions),
        ],
    )


def cmd_chunk(args) -> int:
    workdir = Path(args.workdir).expanduser().resolve()
    manifest = chunk_transcript(
        workdir,
        target_chars=args.target_chars,
        max_chars=args.max_chars,
        overlap=args.overlap,
    )
    print(f"OK chunks={manifest['chunk_count']} coverage={manifest['coverage']['ratio']}")
    return 0


def cmd_assemble(args) -> int:
    workdir = Path(args.workdir).expanduser().resolve()
    meta = assemble(workdir)
    print(f"OK chapters={len(meta['chapters'])} chars={meta['total_chars']}")
    return 0


def cmd_docx(args) -> int:
    workdir = Path(args.workdir).expanduser().resolve()
    result = build_docx(workdir, engine=args.engine, pdf=args.pdf)
    print(f"OK engine={result['engine']} path={result['path']}")
    return 0


def cmd_pptx(args) -> int:
    workdir = Path(args.workdir).expanduser().resolve()
    input_path = Path(args.input).expanduser().resolve() if args.input else None
    result = build_pptx(workdir, input_json=input_path)
    print(f"OK slides={result['slides']} path={result['path']}")
    return 0


def cmd_validate(args) -> int:
    workdir = Path(args.workdir).expanduser().resolve()
    result = validate(
        workdir,
        min_chars=args.min_chars,
        min_slides=args.min_slides,
        min_chapters=args.min_chapters,
        min_questions=args.min_questions,
        require_pptx=getattr(args, "require_pptx", True),
    )
    return 0 if result["ok"] else 1


def cmd_all(args) -> int:
    # init
    ns = argparse.Namespace(**vars(args))
    cmd_init(ns)
    # transcribe
    workdir = Path(args.workdir).expanduser().resolve()
    result = transcribe(
        workdir,
        language=args.language,
        model=args.model,
        device=args.device,
        compute_type=args.compute_type,
        beam_size=args.beam_size,
        initial_prompt=args.initial_prompt,
        start=None,
        end=None,
        simplify=getattr(args, "simplify", True),
    )
    print(f"[all] transcribed {result['segments']} segments")
    manifest = chunk_transcript(
        workdir,
        target_chars=args.target_chars,
        max_chars=args.max_chars,
        overlap=args.overlap,
    )
    print(f"[all] chunked {manifest['chunk_count']} chunks")
    print("[all] next: write notes/chapters/*.md, appendices, output/slides.json")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="lecture.py",
        description="课堂录播 → 逐字稿 → 完整讲义 DOCX → 授课 PPTX",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("doctor", help="check environment")
    p.add_argument("--json", action="store_true")
    p.set_defaults(func=cmd_doctor)

    p = sub.add_parser("init", help="create workspace")
    p.add_argument("--video", required=True)
    p.add_argument("--workdir", required=True)
    p.add_argument("--course", default="")
    p.add_argument("--lecture", default="")
    p.add_argument("--instructor", default="")
    p.add_argument("--language", default="zh")
    p.add_argument("--glossary", default="")
    p.set_defaults(func=cmd_init)

    p = sub.add_parser("transcribe", help="extract audio and transcribe")
    p.add_argument("--workdir", required=True)
    p.add_argument("--language", default="zh")
    p.add_argument("--model", default="small")
    p.add_argument("--device", default="auto", choices=["auto", "cpu", "cuda"])
    p.add_argument("--compute-type", default=None)
    p.add_argument("--beam-size", type=int, default=5)
    p.add_argument("--initial-prompt", default=None)
    p.add_argument("--start", type=float, default=None)
    p.add_argument("--end", type=float, default=None)
    p.add_argument("--no-simplify", action="store_false", dest="simplify", help="keep traditional Chinese as-is")
    p.add_argument("--no-vad", action="store_true", help="disable VAD; use when VAD drops all speech")
    p.set_defaults(func=cmd_transcribe)

    p = sub.add_parser("chunk", help="split transcript into study chunks")
    p.add_argument("--workdir", required=True)
    p.add_argument("--target-chars", type=int, default=6000)
    p.add_argument("--max-chars", type=int, default=None)
    p.add_argument("--overlap", type=int, default=2)
    p.set_defaults(func=cmd_chunk)

    p = sub.add_parser("assemble", help="merge chapters + appendices")
    p.add_argument("--workdir", required=True)
    p.set_defaults(func=cmd_assemble)

    p = sub.add_parser("docx", help="build DOCX")
    p.add_argument("--workdir", required=True)
    p.add_argument("--engine", default="auto", choices=["auto", "pandoc", "python"])
    p.add_argument("--pdf", action="store_true")
    p.set_defaults(func=cmd_docx)

    p = sub.add_parser("pptx", help="build PPTX")
    p.add_argument("--workdir", required=True)
    p.add_argument("--input", default=None)
    p.set_defaults(func=cmd_pptx)

    p = sub.add_parser("validate", help="validate all outputs")
    p.add_argument("--workdir", required=True)
    p.add_argument("--min-chars", type=int, default=None)
    p.add_argument("--min-slides", type=int, default=None)
    p.add_argument("--min-chapters", type=int, default=None)
    p.add_argument("--min-questions", type=int, default=20)
    p.add_argument("--no-ppt", action="store_false", dest="require_pptx", help="only deliver notes/DOCX, skip PPTX checks")
    p.set_defaults(func=cmd_validate)

    p = sub.add_parser("slides", help="extract PPT/board frames when audio is unusable")
    p.add_argument("--workdir", required=True)
    p.add_argument("--interval", type=float, default=60.0)
    p.add_argument("--start", type=float, default=0.0)
    p.add_argument("--end", type=float, default=None)
    p.add_argument("--delete-video", action="store_true")
    p.set_defaults(func=cmd_slides)

    p = sub.add_parser("validate-notes", help="validate notes-only / visual deliverables")
    p.add_argument("--workdir", required=True)
    p.add_argument("--min-chapters", type=int, default=5)
    p.add_argument("--min-chars", type=int, default=8000)
    p.add_argument("--min-questions", type=int, default=20)
    p.set_defaults(func=cmd_validate_notes)

    p = sub.add_parser("all", help="init + transcribe + chunk")
    p.add_argument("--video", required=True)
    p.add_argument("--workdir", required=True)
    p.add_argument("--course", default="")
    p.add_argument("--lecture", default="")
    p.add_argument("--instructor", default="")
    p.add_argument("--language", default="zh")
    p.add_argument("--glossary", default="")
    p.add_argument("--model", default="small")
    p.add_argument("--device", default="auto", choices=["auto", "cpu", "cuda"])
    p.add_argument("--compute-type", default=None)
    p.add_argument("--beam-size", type=int, default=5)
    p.add_argument("--initial-prompt", default=None)
    p.add_argument("--target-chars", type=int, default=6000)
    p.add_argument("--max-chars", type=int, default=None)
    p.add_argument("--overlap", type=int, default=2)
    p.add_argument("--no-simplify", action="store_false", dest="simplify", help="keep traditional Chinese as-is")
    p.set_defaults(func=cmd_all)
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    try:
        return int(args.func(args))
    except KeyboardInterrupt:
        print("Interrupted", file=sys.stderr)
        return 130
    except Exception as exc:
        print(f"ERROR: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
