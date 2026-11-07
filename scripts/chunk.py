"""Split a long transcript into semantic, overlapping study chunks."""
from __future__ import annotations

import argparse
import math
from pathlib import Path
from typing import Any

from common import (
    content_chars,
    ensure_dir,
    format_ts,
    load_course,
    read_json,
    write_json,
    write_text,
)


def make_chunks(
    segments: list[dict[str, Any]],
    *,
    target_chars: int = 6000,
    max_chars: int | None = None,
    overlap: int = 2,
) -> list[dict[str, Any]]:
    if not segments:
        return []
    target_chars = max(800, int(target_chars))
    max_chars = max(target_chars + 500, int(max_chars or target_chars * 1.6))
    overlap = max(0, int(overlap))

    chunks: list[dict[str, Any]] = []
    index = 0
    total = len(segments)
    while index < total:
        start_index = index
        chars = 0
        cursor = index
        while cursor < total:
            chars += content_chars(segments[cursor]["text"])
            cursor += 1
            if chars >= max_chars:
                break
            if chars >= target_chars:
                gap = 0.0
                if cursor < total:
                    gap = float(segments[cursor]["start"]) - float(segments[cursor - 1]["end"])
                if gap >= 0.9 or cursor >= total:
                    break
        selected = segments[start_index:cursor]
        chunks.append(
            {
                "id": f"chunk_{len(chunks) + 1:03d}",
                "segment_start": int(selected[0]["id"]),
                "segment_end": int(selected[-1]["id"]),
                "start": float(selected[0]["start"]),
                "end": float(selected[-1]["end"]),
                "chars": sum(content_chars(s["text"]) for s in selected),
                "segments": selected,
            }
        )
        if cursor >= total:
            break
        next_index = max(start_index + 1, cursor - overlap)
        index = next_index
    return chunks


def chunk_markdown(chunk: dict[str, Any], *, total_chunks: int) -> str:
    selected = chunk["segments"]
    lines = [
        f"# Chunk {chunk['id'].split('_')[-1]} / {total_chunks:03d}",
        "",
        f"- 时间范围：{format_ts(chunk['start'])}–{format_ts(chunk['end'])}",
        f"- 段号：S{chunk['segment_start']:04d}–S{chunk['segment_end']:04d}（{len(selected)} 段）",
        f"- 字符数：{chunk['chars']:,}",
        f"- 相邻块重叠：{chunk.get('overlap', 0)} 段",
        "",
        "## 逐字稿",
        "",
    ]
    for seg in selected:
        lines.append(f"[{format_ts(seg['start'])}] {seg['text']}")
        lines.append("")
    return "\n".join(lines)


def coverage_stats(chunks: list[dict[str, Any]], segments: list[dict[str, Any]]) -> dict[str, Any]:
    total_segments = len(segments)
    assigned: set[int] = set()
    for chunk in chunks:
        for seg in chunk["segments"]:
            assigned.add(int(seg["id"]))
    missing = [int(s["id"]) for s in segments if int(s["id"]) not in assigned]

    intervals = sorted(
        (float(chunk["start"]), float(chunk["end"])) for chunk in chunks
    )
    merged: list[list[float]] = []
    for start, end in intervals:
        if not merged or start > merged[-1][1] + 0.05:
            merged.append([start, end])
        else:
            merged[-1][1] = max(merged[-1][1], end)
    covered_time = sum(end - start for start, end in merged)
    timeline_start = float(segments[0]["start"])
    timeline_end = float(segments[-1]["end"])
    timeline = max(0.001, timeline_end - timeline_start)
    gaps = []
    for left, right in zip(merged, merged[1:]):
        if right[0] - left[1] > 0.75:
            gaps.append(
                {
                    "start": round(left[1], 3),
                    "end": round(right[0], 3),
                    "duration": round(right[0] - left[1], 3),
                }
            )
    return {
        "total_segments": total_segments,
        "assigned_segments": len(assigned),
        "ratio": round(min(1.0, len(assigned) / max(1, total_segments)), 6),
        "time_ratio": round(min(1.0, covered_time / timeline), 6),
        "start": round(timeline_start, 3),
        "end": round(timeline_end, 3),
        "missing_segment_ids": missing[:50],
        "gaps": gaps,
    }


def chunk_transcript(
    workdir: Path,
    *,
    target_chars: int = 6000,
    max_chars: int | None = None,
    overlap: int = 2,
) -> dict[str, Any]:
    transcript_path = workdir / "transcript" / "transcript.json"
    if not transcript_path.exists():
        raise FileNotFoundError(f"Transcript not found: {transcript_path}")
    payload = read_json(transcript_path)
    segments = payload.get("segments") or []
    if not segments:
        raise RuntimeError("Transcript has no segments")

    chunks = make_chunks(
        segments, target_chars=target_chars, max_chars=max_chars, overlap=overlap
    )
    if not chunks:
        raise RuntimeError("Chunking produced no chunks")

    chunks_dir = ensure_dir(workdir / "transcript" / "chunks")
    for old in chunks_dir.glob("chunk_*.md"):
        old.unlink()
    for chunk in chunks:
        chunk["overlap"] = overlap
        path = chunks_dir / f"{chunk['id']}.md"
        write_text(path, chunk_markdown(chunk, total_chunks=len(chunks)))
        chunk["file"] = str(path.relative_to(workdir)).replace("\\", "/")

    manifest = {
        "source": payload.get("source_video", ""),
        "language": payload.get("language", ""),
        "duration": payload.get("duration", 0),
        "target_chars": target_chars,
        "max_chars": max_chars or int(target_chars * 1.6),
        "overlap": overlap,
        "total_segments": len(segments),
        "total_chars": sum(content_chars(s["text"]) for s in segments),
        "chunk_count": len(chunks),
        "chunks": [
            {
                "id": c["id"],
                "file": c["file"],
                "segment_start": c["segment_start"],
                "segment_end": c["segment_end"],
                "start": round(c["start"], 3),
                "end": round(c["end"], 3),
                "chars": c["chars"],
                "segments": len(c["segments"]),
            }
            for c in chunks
        ],
        "coverage": coverage_stats(chunks, segments),
    }
    write_json(chunks_dir / "manifest.json", manifest)
    print(
        f"[chunk] {len(chunks)} chunks, {manifest['total_chars']:,} chars, "
        f"coverage={manifest['coverage']['ratio']:.3f}, "
        f"time={manifest['coverage']['time_ratio']:.3f}"
    )
    return manifest


def main() -> int:
    parser = argparse.ArgumentParser(description="Chunk a lecture transcript")
    parser.add_argument("--workdir", required=True)
    parser.add_argument("--target-chars", type=int, default=6000)
    parser.add_argument("--max-chars", type=int, default=None)
    parser.add_argument("--overlap", type=int, default=2)
    args = parser.parse_args()
    manifest = chunk_transcript(
        Path(args.workdir).resolve(),
        target_chars=args.target_chars,
        max_chars=args.max_chars,
        overlap=args.overlap,
    )
    print(f"OK chunks={manifest['chunk_count']} coverage={manifest['coverage']['ratio']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
