"""Assemble chapter files and appendices into a single study guide."""
from __future__ import annotations

import argparse
import re
from pathlib import Path
from typing import Any

from common import (
    appendix_sort_key,
    chapter_sort_key,
    content_chars,
    ensure_dir,
    format_ts,
    load_course,
    now_iso,
    read_json,
    timestamp_count,
    write_json,
    write_text,
)

COVER_RE = re.compile(
    r"^\s*>\s*覆盖[：:]\s*(\d{1,2}:\d{2}:\d{2})\s*[–\-—~至]\s*(\d{1,2}:\d{2}:\d{2})",
    re.MULTILINE,
)
H1_RE = re.compile(r"^#\s+(.+?)\s*$", re.MULTILINE)

REQUIRED_SECTIONS = [
    ("本章目标", ("本章目标", "学习目标")),
    ("核心概念", ("核心概念", "关键概念")),
    ("详细讲解", ("详细讲解", "讲解", "正文")),
    ("公式/推导", ("公式与推导", "公式", "推导")),
    ("例题/证明", ("例题与证明", "例题", "证明")),
    ("易错点", ("易错点", "常见错误", "考试提示")),
    ("小结/自测", ("本章小结", "小结", "自测")),
]


def parse_coverage(text: str) -> tuple[str, str] | None:
    match = COVER_RE.search(text)
    if not match:
        return None
    return match.group(1), match.group(2)


def first_h1(text: str) -> str | None:
    match = H1_RE.search(text)
    return match.group(1).strip() if match else None


def validate_chapter(path: Path, text: str) -> dict[str, Any]:
    title = first_h1(text)
    coverage = parse_coverage(text)
    missing_sections = [
        label for label, alternatives in REQUIRED_SECTIONS if not any(a in text for a in alternatives)
    ]
    return {
        "file": path.name,
        "title": title,
        "coverage": coverage,
        "chars": content_chars(text),
        "timestamps": timestamp_count(text),
        "missing_sections": missing_sections,
    }


def build_toc(chapters: list[dict[str, Any]], appendices: list[Path]) -> str:
    lines = ["## 目录", ""]
    for item in chapters:
        lines.append(f"{len(lines) - 1}. {item['title']}")
    if appendices:
        lines.append("")
        lines.append("**附录**")
        lines.append("")
        for path in appendices:
            lines.append(f"- {path.stem.replace('_', ' ')}")
    lines.append("")
    return "\n".join(lines)


def assemble(workdir: Path) -> dict[str, Any]:
    course = load_course(workdir)
    chapters_dir = workdir / "notes" / "chapters"
    if not chapters_dir.exists():
        raise FileNotFoundError(f"Chapter directory not found: {chapters_dir}")
    chapter_paths = sorted(chapters_dir.glob("ch*.md"), key=chapter_sort_key)
    if not chapter_paths:
        raise FileNotFoundError(
            f"No chapter files found in {chapters_dir}; expected ch01.md, ch02.md, ..."
        )

    chapters: list[dict[str, Any]] = []
    body_parts: list[str] = []
    errors: list[str] = []
    warnings: list[str] = []
    for path in chapter_paths:
        text = path.read_text(encoding="utf-8")
        info = validate_chapter(path, text)
        if not info["title"]:
            errors.append(f"{path.name}: 缺少 H1 标题")
        if not info["coverage"]:
            errors.append(f"{path.name}: 缺少覆盖声明（> 覆盖：HH:MM:SS–HH:MM:SS）")
        if info["missing_sections"]:
            warnings.append(f"{path.name}: 缺少段落 {', '.join(info['missing_sections'])}")
        chapters.append(info)
        body_parts.append(text.strip())

    if errors:
        raise ValueError("Chapter validation failed:\n- " + "\n- ".join(errors))

    appendices_dir = workdir / "notes" / "appendices"
    appendix_paths = (
        sorted(appendices_dir.glob("*.md"), key=appendix_sort_key) if appendices_dir.exists() else []
    )
    required_appendix_names = ["00_知识点总表", "01_公式与术语", "02_题库", "03_复习路径"]
    existing_stems = {p.stem for p in appendix_paths}
    for name in required_appendix_names:
        if name not in existing_stems:
            warnings.append(f"缺少附录：{name}.md")

    appendix_parts: list[str] = []
    for path in appendix_paths:
        text = path.read_text(encoding="utf-8").strip()
        if not text:
            warnings.append(f"{path.name}: 附录为空")
            continue
        if not first_h1(text):
            text = f"# 附录：{path.stem.replace('_', ' ')}\n\n{text}"
        appendix_parts.append(text)

    duration = float(course.get("duration_sec") or 0)
    total_chars = sum(item["chars"] for item in chapters)
    total_timestamps = sum(item["timestamps"] for item in chapters)
    coverage_rows = []
    for item in chapters:
        start, end = item["coverage"] if item["coverage"] else ("?", "?")
        coverage_rows.append(f"| {item['title']} | {start}–{end} | {item['chars']:,} | {item['timestamps']} |")

    frontmatter = [
        "---",
        f'title: "{course.get("course", "")} · {course.get("lecture", "")}"',
        f'subtitle: "课堂录播完整学习讲义"',
        f'author: "{course.get("instructor", "")}"',
        f'date: "{now_iso()[:10]}"',
        "lang: zh-CN",
        "---",
        "",
    ]
    info_lines = [
        "## 课程信息",
        "",
        "| 项目 | 内容 |",
        "| --- | --- |",
        f"| 课程 | {course.get('course', '')} |",
        f"| 讲次 | {course.get('lecture', '')} |",
        f"| 教师 | {course.get('instructor', '') or '未填写'} |",
        f"| 时长 | {format_ts(duration)} |",
        f"| 来源 | `{course.get('source_video', '')}` |",
        f"| 转写 | {course.get('transcript_model', '')} / {course.get('language', '')} |",
        f"| 生成 | {now_iso()} |",
        "",
    ]
    usage_lines = [
        "## 使用说明",
        "",
        "- `[HH:MM:SS]` 是视频时间锚点；复习时可直接跳回原视频核对。",
        "- `[补充]` 表示讲义补充，不是课堂原文；`[ASR存疑]` / `[口误修正]` 表示转写不确定或已修正。",
        "- 每章末尾有自测题；文末有知识点总表、公式/术语、题库和三条复习路径。",
        "- 先读“本章目标”和“小结”，再回到“详细讲解”；例题要遮住答案自己做一遍。",
        "",
    ]
    coverage_lines = [
        "## 覆盖核对",
        "",
        "| 章节 | 时间范围 | 字数 | 时间戳 |",
        "| --- | --- | ---: | ---: |",
        *coverage_rows,
        "",
        f"> 合计：{total_chars:,} 字，{total_timestamps} 个时间戳，{len(chapters)} 章。",
        "",
    ]
    transcript_lines = [
        "# 附：逐字稿索引",
        "",
        "- 人读版：`transcript/transcript.md`",
        "- 字幕：`transcript/transcript.srt`",
        "- 结构化数据：`transcript/transcript.json`",
        "- 分块材料：`transcript/chunks/`",
        "",
    ]

    document = "\n".join(frontmatter) + "\n" + "\n\n".join(
        [
            "\n".join(info_lines),
            "\n".join(usage_lines),
            build_toc(chapters, appendix_paths),
            "\n\n---\n\n".join(body_parts),
            "\n\n---\n\n".join(appendix_parts) if appendix_parts else "## 附录\n\n（未生成附录）",
            "\n".join(transcript_lines),
        ]
    )
    out_path = workdir / "notes" / "讲义.md"
    write_text(out_path, document)

    meta = {
        "generated_at": now_iso(),
        "chapters": chapters,
        "appendix_files": [str(p.relative_to(workdir)).replace("\\", "/") for p in appendix_paths],
        "total_chars": total_chars,
        "total_timestamps": total_timestamps,
        "duration_sec": duration,
        "warnings": warnings,
        "output": str(out_path.relative_to(workdir)).replace("\\", "/"),
    }
    write_json(workdir / "notes" / "讲义.meta.json", meta)
    print(
        f"[assemble] {len(chapters)} chapters, {total_chars:,} chars, "
        f"{total_timestamps} timestamps -> {out_path}"
    )
    for warning in warnings:
        print(f"[assemble] WARN: {warning}")
    return meta


def main() -> int:
    parser = argparse.ArgumentParser(description="Assemble study guide from chapters")
    parser.add_argument("--workdir", required=True)
    args = parser.parse_args()
    meta = assemble(Path(args.workdir).resolve())
    print(f"OK chapters={len(meta['chapters'])} chars={meta['total_chars']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
