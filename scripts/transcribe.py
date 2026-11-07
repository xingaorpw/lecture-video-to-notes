"""Extract audio and transcribe it with faster-whisper."""
from __future__ import annotations

import argparse
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any

from common import (
    TOOLS_DIR,
    ensure_dir,
    find_ffmpeg,
    format_ts,
    load_course,
    normalize_text,
    now_iso,
    probe_duration,
    read_json,
    run,
    srt_ts,
    write_json,
    write_text,
)


def detect_device(requested: str) -> str:
    if requested != "auto":
        return requested
    nvidia = shutil.which("nvidia-smi")
    if nvidia:
        try:
            proc = run([nvidia, "--query-gpu=name", "--format=csv,noheader"], check=False, timeout=10)
            if proc.returncode == 0 and (proc.stdout or "").strip():
                return "cuda"
        except Exception:
            pass
    return "cpu"


def default_compute_type(device: str) -> str:
    return "float16" if device == "cuda" else "int8"


def extract_audio_pyav(
    video: Path,
    output: Path,
    *,
    start: float | None = None,
    end: float | None = None,
) -> float:
    """Decode the first audio stream to 16 kHz mono WAV without an ffmpeg binary."""
    import av
    import wave

    ensure_dir(output.parent)
    with av.open(str(video)) as container:
        streams = [s for s in container.streams if s.type == "audio"]
        if not streams:
            raise RuntimeError(f"No audio stream found in {video}")
        stream = streams[0]
        if start and start > 0:
            base = stream.time_base or av.time_base
            container.seek(int(start / float(base)), stream=stream, backward=True)
        resampler = av.AudioResampler(format="s16", layout="mono", rate=16000)
        wrote = 0
        with wave.open(str(output), "wb") as wav:
            wav.setnchannels(1)
            wav.setsampwidth(2)
            wav.setframerate(16000)
            for frame in container.decode(stream):
                ts = float(frame.pts * stream.time_base) if frame.pts is not None else 0.0
                if end is not None and end > 0 and ts > end:
                    break
                if start is not None and start > 0 and ts < start - 0.10:
                    continue
                for out_frame in resampler.resample(frame):
                    data = out_frame.to_ndarray().tobytes()
                    wav.writeframes(data)
                    wrote += len(data)
            for out_frame in resampler.resample(None):
                data = out_frame.to_ndarray().tobytes()
                wav.writeframes(data)
                wrote += len(data)
    if wrote < 2000:
        raise RuntimeError(f"Audio decode produced no usable samples: {output}")
    return probe_duration(output)


def extract_audio(
    video: Path,
    output: Path,
    *,
    start: float | None = None,
    end: float | None = None,
) -> float:
    ffmpeg = find_ffmpeg()
    ensure_dir(output.parent)
    if ffmpeg:
        cmd = [ffmpeg, "-y", "-hide_banner", "-loglevel", "error"]
        if start is not None and start > 0:
            cmd += ["-ss", f"{start:.3f}"]
        cmd += ["-i", str(video)]
        if end is not None and end > 0:
            if start is not None and start > 0:
                cmd += ["-t", f"{max(0.1, end - start):.3f}"]
            else:
                cmd += ["-to", f"{end:.3f}"]
        cmd += ["-vn", "-map", "0:a:0?", "-ac", "1", "-ar", "16000", "-c:a", "pcm_s16le", str(output)]
        try:
            run(cmd)
            if output.exists() and output.stat().st_size > 1000:
                return probe_duration(output)
        except Exception as exc:
            print(f"[transcribe] ffmpeg extraction failed, trying PyAV: {exc}", file=sys.stderr)
    return extract_audio_pyav(video, output, start=start, end=end)


def build_prompt(glossary: list[str], extra: str | None) -> str | None:
    parts: list[str] = []
    if glossary:
        parts.append("课堂术语：" + "、".join(glossary) + "。")
    if extra:
        parts.append(extra.strip())
    return "".join(parts) if parts else None


def transcribe_audio(
    audio: Path,
    *,
    model_size: str,
    language: str | None,
    device: str,
    compute_type: str,
    beam_size: int,
    initial_prompt: str | None,
    offset: float = 0.0,
    simplify: bool = True,
) -> dict[str, Any]:
    try:
        from faster_whisper import WhisperModel
    except ImportError as exc:
        raise RuntimeError(
            "faster-whisper is not installed. Run: $PY -m pip install faster-whisper"
        ) from exc

    model_root = ensure_dir(TOOLS_DIR / "models")
    print(
        f"[transcribe] model={model_size} device={device} compute={compute_type} "
        f"beam={beam_size} language={language or 'auto'}",
        file=sys.stderr,
        flush=True,
    )
    model = WhisperModel(
        model_size,
        device=device,
        compute_type=compute_type,
        download_root=str(model_root),
        cpu_threads=max(1, (os.cpu_count() or 4) - 1),
    )
    segments_iter, info = model.transcribe(
        str(audio),
        language=None if language in (None, "", "auto") else language,
        beam_size=beam_size,
        vad_filter=True,
        vad_parameters={"min_silence_duration_ms": 500},
        condition_on_previous_text=False,
        initial_prompt=initial_prompt,
        word_timestamps=False,
    )
    total = float(getattr(info, "duration", 0.0) or 0.0)
    converter = None
    detected_language = getattr(info, "language", None) or language or ""
    if simplify and str(detected_language).lower().startswith("zh"):
        try:
            from zhconv import convert as zh_convert

            converter = zh_convert
        except ImportError:
            converter = None
    segments: list[dict[str, Any]] = []
    for index, seg in enumerate(segments_iter, start=1):
        text = normalize_text(seg.text or "")
        if converter is not None:
            text = converter(text, "zh-cn")
        if not text:
            continue
        segments.append(
            {
                "id": len(segments) + 1,
                "start": round(float(seg.start) + offset, 3),
                "end": round(float(seg.end) + offset, 3),
                "text": text,
                "avg_logprob": round(float(getattr(seg, "avg_logprob", 0.0)), 4),
                "no_speech_prob": round(float(getattr(seg, "no_speech_prob", 0.0)), 4),
            }
        )
        if index % 20 == 0:
            print(
                f"[transcribe] {format_ts(seg.end)} / {format_ts(total or seg.end)} "
                f"({len(segments)} segments)",
                file=sys.stderr,
                flush=True,
            )
    return {
        "segments": segments,
        "info": {
            "language": getattr(info, "language", language),
            "language_probability": round(float(getattr(info, "language_probability", 0.0) or 0.0), 4),
            "duration": round(total, 3),
        },
    }


def transcript_markdown(meta: dict[str, Any], segments: list[dict[str, Any]]) -> str:
    lines = [
        f"# 逐字稿：{meta.get('lecture') or meta.get('course') or '课堂录播'}",
        "",
        f"- 来源：`{meta.get('source_video', '')}`",
        f"- 语言：{meta.get('language', '')}",
        f"- 模型：{meta.get('model', '')} / {meta.get('device', '')} / {meta.get('compute_type', '')}",
        f"- 时长：{format_ts(meta.get('duration', 0))}",
        f"- 生成：{meta.get('created', '')}",
        "",
        "> 低置信段落标有 `[低置信]`；不要直接据此改写，先回看视频。",
        "",
        "---",
        "",
    ]
    for seg in segments:
        flag = " `[低置信]`" if seg.get("avg_logprob", 0) < -1.0 else ""
        lines.append(f"[{format_ts(seg['start'])}] {seg['text']}{flag}")
        lines.append("")
    return "\n".join(lines)


def transcript_srt(segments: list[dict[str, Any]]) -> str:
    blocks: list[str] = []
    for index, seg in enumerate(segments, start=1):
        blocks.append(
            f"{index}\n{srt_ts(seg['start'])} --> {srt_ts(seg['end'])}\n{seg['text']}\n"
        )
    return "\n".join(blocks)


def transcribe(
    workdir: Path,
    *,
    language: str = "zh",
    model: str = "small",
    device: str = "auto",
    compute_type: str | None = None,
    beam_size: int = 5,
    initial_prompt: str | None = None,
    start: float | None = None,
    end: float | None = None,
    simplify: bool = True,
) -> dict[str, Any]:
    course = load_course(workdir)
    source = Path(course["source_video"])
    if not source.exists():
        raise FileNotFoundError(f"Source video not found: {source}")

    device = detect_device(device)
    compute_type = compute_type or default_compute_type(device)
    audio_name = "lecture.wav"
    if start is not None or end is not None:
        audio_name = f"clip_{int(start or 0):06d}_{int(end or 0):06d}.wav"
    audio_path = workdir / "audio" / audio_name
    duration = extract_audio(source, audio_path, start=start, end=end)

    glossary = course.get("glossary") or []
    prompt = build_prompt(glossary, initial_prompt)
    result = transcribe_audio(
        audio_path,
        model_size=model,
        language=language,
        device=device,
        compute_type=compute_type,
        beam_size=beam_size,
        initial_prompt=prompt,
        offset=float(start or 0),
        simplify=simplify,
    )
    segments = result["segments"]
    if not segments:
        raise RuntimeError("No speech segments were recognized; check the audio track/language")

    if start is None and end is None:
        full_duration = float(duration or result["info"]["duration"] or course.get("duration_sec") or 0)
    else:
        full_duration = float(course.get("duration_sec") or duration or result["info"]["duration"] or 0)
    meta = {
        "source_video": str(source),
        "course": course.get("course", ""),
        "lecture": course.get("lecture", ""),
        "language": result["info"].get("language") or language,
        "language_probability": result["info"].get("language_probability", 0.0),
        "model": model,
        "device": device,
        "compute_type": compute_type,
        "beam_size": beam_size,
        "duration": round(full_duration, 3),
        "audio_duration": round(duration, 3),
        "clip_start": start,
        "clip_end": end,
        "created": now_iso(),
        "segment_count": len(segments),
    }
    payload = {**meta, "segments": segments}
    transcript_dir = ensure_dir(workdir / "transcript")
    write_json(transcript_dir / "transcript.json", payload)
    write_text(transcript_dir / "transcript.md", transcript_markdown(meta, segments))
    write_text(transcript_dir / "transcript.srt", transcript_srt(segments))

    course["duration_sec"] = full_duration
    course["language"] = meta["language"]
    course["transcribed_at"] = meta["created"]
    course["transcript_model"] = model
    write_json(workdir / "course.json", course)

    print(
        f"[transcribe] done: {len(segments)} segments, {format_ts(full_duration)}, "
        f"language={meta['language']} ({meta['language_probability']})",
        file=sys.stderr,
    )
    return {"ok": True, "segments": len(segments), "duration": full_duration, "meta": meta}


def main() -> int:
    parser = argparse.ArgumentParser(description="Extract audio and transcribe a lecture")
    parser.add_argument("--workdir", required=True)
    parser.add_argument("--language", default="zh")
    parser.add_argument("--model", default="small")
    parser.add_argument("--device", default="auto", choices=["auto", "cpu", "cuda"])
    parser.add_argument("--compute-type", default=None)
    parser.add_argument("--beam-size", type=int, default=5)
    parser.add_argument("--initial-prompt", default=None)
    parser.add_argument("--start", type=float, default=None, help="start second")
    parser.add_argument("--end", type=float, default=None, help="end second")
    parser.add_argument("--no-simplify", action="store_false", dest="simplify", help="keep traditional Chinese as-is")
    args = parser.parse_args()
    result = transcribe(
        Path(args.workdir).resolve(),
        language=args.language,
        model=args.model,
        device=args.device,
        compute_type=args.compute_type,
        beam_size=args.beam_size,
        initial_prompt=args.initial_prompt,
        start=args.start,
        end=args.end,
        simplify=args.simplify,
    )
    print(f"OK segments={result['segments']} duration={format_ts(result['duration'])}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
