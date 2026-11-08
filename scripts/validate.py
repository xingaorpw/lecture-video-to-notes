"""Validate transcript, chunks, study guide, DOCX and PPTX against quality gates."""
from __future__ import annotations

import argparse
import math
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from common import (
    content_chars,
    format_ts,
    load_course,
    now_iso,
    read_json,
    timestamp_count,
    write_json,
    write_text,
)

TS_RE = re.compile(r"\[\d{1,2}:\d{2}:\d{2}(?:\s*[–-]\s*\d{1,2}:\d{2}:\d{2})?\]")
COVER_RE = re.compile(
    r"^\s*>\s*覆盖[：:]\s*(\d{1,2}:\d{2}:\d{2})\s*[–\-—~至]\s*(\d{1,2}:\d{2}:\d{2})",
    re.MULTILINE,
)
PLACEHOLDER_RE = re.compile(r"TODO|待补充|此处省略|（略）|\(略\)|待完善|占位")
QUESTION_RE = re.compile(r"^\s*(?:\d+[.、)]|[（(]\d+[）)]|###?\s*第?\s*\d+)", re.MULTILINE)


@dataclass
class Check:
    name: str
    status: str  # PASS / WARN / FAIL
    detail: str
    data: dict[str, Any] = field(default_factory=dict)


def add(checks: list[Check], name: str, ok: bool, detail: str, *, warn: bool = False, data=None):
    status = "PASS" if ok else ("WARN" if warn else "FAIL")
    checks.append(Check(name, status, detail, data or {}))


def parse_ts(value: str) -> float:
    parts = [int(x) for x in value.split(":")]
    if len(parts) == 3:
        return parts[0] * 3600 + parts[1] * 60 + parts[2]
    return parts[0] * 60 + parts[1]


def merge_intervals(intervals: list[tuple[float, float]]) -> list[tuple[float, float]]:
    merged: list[list[float]] = []
    for start, end in sorted(intervals):
        if not merged or start > merged[-1][1] + 0.05:
            merged.append([start, end])
        else:
            merged[-1][1] = max(merged[-1][1], end)
    return [(a, b) for a, b in merged]


def interval_covered(start: float, end: float, intervals: list[tuple[float, float]]) -> bool:
    cursor = start
    for left, right in intervals:
        if right < cursor:
            continue
        if left > cursor + 1.0:
            return False
        cursor = max(cursor, right)
        if cursor >= end - 1.0:
            return True
    return cursor >= end - 1.0


def slide_text(slide) -> str:
    parts: list[str] = []
    for shape in slide.shapes:
        if getattr(shape, "has_text_frame", False):
            text = shape.text_frame.text.strip()
            if text:
                parts.append(text)
    return "\n".join(parts)


def validate(workdir: Path, *, min_chars: int | None = None, min_slides: int | None = None, min_chapters: int | None = None, min_questions: int = 20, require_pptx: bool = True) -> dict[str, Any]:
    checks: list[Check] = []
    course = load_course(workdir)
    duration = float(course.get("duration_sec") or 0)
    duration_min = duration / 60 if duration else 0

    # Transcript
    transcript_path = workdir / "transcript" / "transcript.json"
    segments: list[dict[str, Any]] = []
    if transcript_path.exists():
        payload = read_json(transcript_path)
        segments = payload.get("segments") or []
        empty = sum(1 for s in segments if not str(s.get("text", "")).strip())
        empty_ratio = empty / max(1, len(segments))
        add(checks, "转写段数", len(segments) > 0, f"{len(segments)} 段")
        add(checks, "空段占比", empty_ratio < 0.20, f"{empty_ratio:.1%}（阈值 <20%）")
        if duration and payload.get("duration"):
            diff = abs(float(payload["duration"]) - duration) / max(1.0, duration)
            add(checks, "时长一致性", diff < 0.05, f"误差 {diff:.1%}（阈值 <5%）")
        low_conf = sum(1 for s in segments if float(s.get("avg_logprob", 0)) < -1.0)
        add(checks, "低置信段", True, f"{low_conf} 段（需人工回看）", warn=low_conf > len(segments) * 0.15)
    else:
        add(checks, "转写文件", False, f"缺少 {transcript_path}")

    # Chunks
    manifest_path = workdir / "transcript" / "chunks" / "manifest.json"
    chapter_intervals: list[tuple[float, float]] = []
    if manifest_path.exists():
        manifest = read_json(manifest_path)
        coverage = manifest.get("coverage") or {}
        ratio = float(coverage.get("ratio", 0))
        add(checks, "分块覆盖", ratio >= 0.999, f"segment ratio={ratio:.3f}")
        add(checks, "分块时间覆盖", float(coverage.get("time_ratio", 0)) >= 0.999, f"time ratio={coverage.get('time_ratio')}")
        add(checks, "分块数", int(manifest.get("chunk_count", 0)) > 0, f"{manifest.get('chunk_count')} 块")
    else:
        add(checks, "分块清单", False, f"缺少 {manifest_path}")

    # Chapters
    chapters_dir = workdir / "notes" / "chapters"
    chapter_files = sorted(chapters_dir.glob("ch*.md")) if chapters_dir.exists() else []
    chapter_texts: list[str] = []
    missing_sections: list[str] = []
    for path in chapter_files:
        text = path.read_text(encoding="utf-8")
        chapter_texts.append(text)
        for match in COVER_RE.finditer(text):
            chapter_intervals.append((parse_ts(match.group(1)), parse_ts(match.group(2))))
        for required in ("本章目标", "核心概念", "详细讲解", "例题", "易错", "小结"):
            if required not in text:
                missing_sections.append(f"{path.name}:{required}")
    min_ch = min_chapters if min_chapters is not None else max(2, min(8, math.ceil(duration_min / 25))) if duration_min else 3
    add(checks, "章节数", len(chapter_files) >= min_ch, f"{len(chapter_files)} 章（要求 ≥{min_ch}）")
    add(checks, "章节覆盖声明", len(chapter_intervals) >= len(chapter_files), f"{len(chapter_intervals)} 条 / {len(chapter_files)} 章")
    add(checks, "章节七段式", not missing_sections, "齐全" if not missing_sections else "缺：" + ", ".join(missing_sections[:10]), warn=bool(missing_sections))

    # Notes
    notes_path = workdir / "notes" / "讲义.md"
    notes_text = notes_path.read_text(encoding="utf-8") if notes_path.exists() else ""
    chars = content_chars(notes_text)
    min_c = min_chars if min_chars is not None else max(1500, int(duration_min * 60)) if duration_min else 1500
    add(checks, "讲义存在", notes_path.exists(), str(notes_path))
    add(checks, "讲义字数", chars >= min_c, f"{chars:,} 字（要求 ≥{min_c:,}）")
    ts_count = timestamp_count(notes_text)
    min_ts = max(10, int(chars / 500))
    add(checks, "时间戳密度", ts_count >= min_ts, f"{ts_count} 个（要求 ≥{min_ts}）")
    add(checks, "无占位符", not PLACEHOLDER_RE.search(notes_text), "未发现 TODO/待补充/此处省略")

    # Chunk-to-chapter coverage
    if manifest_path.exists() and chapter_intervals:
        manifest = read_json(manifest_path)
        merged = merge_intervals(chapter_intervals)
        uncovered = []
        for chunk in manifest.get("chunks", []):
            if not interval_covered(float(chunk["start"]), float(chunk["end"]), merged):
                uncovered.append(chunk["id"])
        add(checks, "分块→章节归属", not uncovered, "全部归属" if not uncovered else "未归属：" + ", ".join(uncovered[:10]))

    # Appendices
    appendix_dir = workdir / "notes" / "appendices"
    required_appendix = ["00_知识点总表", "01_公式与术语", "02_题库", "03_复习路径"]
    missing_appendix = [name for name in required_appendix if not (appendix_dir / f"{name}.md").exists()]
    add(checks, "附录齐全", not missing_appendix, "齐全" if not missing_appendix else "缺：" + ", ".join(missing_appendix))
    question_count = 0
    q_path = appendix_dir / "02_题库.md"
    if q_path.exists():
        q_text = q_path.read_text(encoding="utf-8")
        # Count only the question section; the answer section repeats the numbering.
        question_part = q_text.split("## 答案与解析", 1)[0]
        question_count = len(QUESTION_RE.findall(question_part))
    add(checks, "题库题量", question_count >= min_questions, f"{question_count} 题（要求 ≥{min_questions}）")

    # DOCX
    docx_path = workdir / "output" / "讲义.docx"
    if docx_path.exists():
        try:
            from docx import Document

            doc = Document(str(docx_path))
            headings = sum(1 for p in doc.paragraphs if p.style.name.startswith("Heading"))
            add(checks, "DOCX 可打开", True, f"{len(doc.paragraphs)} 段 / {headings} 标题 / {len(doc.tables)} 表")
            add(checks, "DOCX 标题数", headings >= len(chapter_files), f"{headings}（要求 ≥{len(chapter_files)}）")
            add(checks, "DOCX 表格数", len(doc.tables) >= 2, f"{len(doc.tables)} 张（要求 ≥2）")
        except Exception as exc:
            add(checks, "DOCX 可打开", False, f"{type(exc).__name__}: {exc}")
    else:
        add(checks, "DOCX 存在", False, f"缺少 {docx_path}")

    # PPTX
    pptx_path = workdir / "output" / "课件.pptx"
    if not require_pptx:
        add(checks, "PPTX", True, "跳过（--no-ppt，只交付讲义）")
    elif pptx_path.exists():
        try:
            from pptx import Presentation

            prs = Presentation(str(pptx_path))
            slides = list(prs.slides)
            min_s = min_slides if min_slides is not None else max(8, min(45, round(duration_min / 4))) if duration_min else 15
            add(checks, "PPTX 页数", len(slides) >= min_s, f"{len(slides)} 页（要求 ≥{min_s}）")
            texts = [slide_text(s) for s in slides]
            empty = sum(1 for t in texts if len(t.strip()) < 5)
            add(checks, "PPTX 空页", empty == 0, f"{empty} 页空")
            notes_count = sum(
                1 for s in slides if s.has_notes_slide and s.notes_slide.notes_text_frame.text.strip()
            )
            add(checks, "PPTX 讲稿", notes_count >= max(3, int(len(slides) * 0.6)), f"{notes_count}/{len(slides)} 页有备注")
            all_text = "\n".join(texts)
            add(checks, "PPTX 无占位符", not PLACEHOLDER_RE.search(all_text), "未发现 TODO/待补充")
            add(checks, "PPTX 标题", all(len(t.strip()) > 0 for t in texts), "每页有文字")
        except Exception as exc:
            add(checks, "PPTX 可打开", False, f"{type(exc).__name__}: {exc}")
    else:
        add(checks, "PPTX 存在", False, f"缺少 {pptx_path}")

    fails = [c for c in checks if c.status == "FAIL"]
    warns = [c for c in checks if c.status == "WARN"]
    result = {
        "ok": not fails,
        "generated_at": now_iso(),
        "duration": duration,
        "checks": [c.__dict__ for c in checks],
        "fails": len(fails),
        "warnings": len(warns),
        "stats": {
            "transcript_segments": len(segments),
            "chapters": len(chapter_files),
            "notes_chars": chars,
            "timestamps": ts_count,
            "questions": question_count,
            "docx": str(docx_path) if docx_path.exists() else None,
            "pptx": str(pptx_path) if pptx_path.exists() else None,
        },
    }
    report = render_report(result, course)
    output_dir = workdir / "output"
    write_text(output_dir / "校验报告.md", report)
    write_json(output_dir / "validate.json", result)
    print(report.split("\n\n")[0])
    print(f"[validate] {'PASS' if result['ok'] else 'FAIL'} fails={len(fails)} warnings={len(warns)}")
    return result


def render_report(result: dict[str, Any], course: dict[str, Any]) -> str:
    lines = [
        "# 校验报告",
        "",
        f"- 课程：{course.get('course', '')} · {course.get('lecture', '')}",
        f"- 生成：{result['generated_at']}",
        f"- 结论：**{'PASS' if result['ok'] else 'FAIL'}**",
        f"- 失败：{result['fails']} 项；警告：{result['warnings']} 项",
        "",
        "## 汇总",
        "",
        "| 检查项 | 结果 | 说明 |",
        "| --- | --- | --- |",
    ]
    for check in result["checks"]:
        lines.append(f"| {check['name']} | {check['status']} | {check['detail'].replace('|', '/')} |")
    lines += [
        "",
        "## 统计",
        "",
        "| 指标 | 值 |",
        "| --- | --- |",
        f"| 视频时长 | {format_ts(result['duration'])} |",
        f"| 转写段数 | {result['stats']['transcript_segments']} |",
        f"| 章节数 | {result['stats']['chapters']} |",
        f"| 讲义字数 | {result['stats']['notes_chars']:,} |",
        f"| 时间戳 | {result['stats']['timestamps']} |",
        f"| 题库 | {result['stats']['questions']} 题 |",
    ]
    fails = [c for c in result["checks"] if c["status"] == "FAIL"]
    warns = [c for c in result["checks"] if c["status"] == "WARN"]
    if fails:
        lines += ["", "## 失败项", ""]
        for check in fails:
            lines.append(f"- **{check['name']}**：{check['detail']}")
    if warns:
        lines += ["", "## 警告项", ""]
        for check in warns:
            lines.append(f"- {check['name']}：{check['detail']}")
    lines += [
        "",
        "## 说明",
        "",
        "- 本报告只检查结构和硬性质量门，不替代人工试听/试讲。",
        "- 低置信段、公式降级、画面未截取等，应在交付说明中单独列出。",
        "",
    ]
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate lecture outputs")
    parser.add_argument("--workdir", required=True)
    parser.add_argument("--min-chars", type=int, default=None)
    parser.add_argument("--min-slides", type=int, default=None)
    parser.add_argument("--min-chapters", type=int, default=None)
    parser.add_argument("--min-questions", type=int, default=20)
    args = parser.parse_args()
    result = validate(
        Path(args.workdir).resolve(),
        min_chars=args.min_chars,
        min_slides=args.min_slides,
        min_chapters=args.min_chapters,
        min_questions=args.min_questions,
    )
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
