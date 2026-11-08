"""Validate notes-only / visual-fallback deliverables.

Use this when the recording has no usable audio (or PPT is the only source).
The normal ``validate.py`` gate expects a transcript and chunks; this gate does
not, but it still checks completeness, question count and DOCX structure.
"""
from __future__ import annotations

import argparse
import re
from pathlib import Path

from docx import Document

PLACEHOLDER = re.compile(r"TODO|待补充|此处省略|待完善|占位")


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate notes-only / visual lecture notes")
    parser.add_argument("--workdir", required=True)
    parser.add_argument("--min-chapters", type=int, default=5)
    parser.add_argument("--min-chars", type=int, default=8000)
    parser.add_argument("--min-questions", type=int, default=20)
    args = parser.parse_args()

    work = Path(args.workdir).expanduser().resolve()
    checks: list[tuple[str, str, str]] = []

    def add(name: str, ok: bool, detail: str) -> None:
        checks.append((name, "PASS" if ok else "FAIL", detail))

    guide = work / "notes" / "讲义.md"
    text = guide.read_text(encoding="utf-8") if guide.exists() else ""
    chapters = sorted((work / "notes" / "chapters").glob("ch*.md"))
    appendices = sorted((work / "notes" / "appendices").glob("*.md"))
    docx_path = work / "output" / "讲义.docx"

    add("讲义存在", guide.exists(), str(guide))
    add("章节数", len(chapters) >= args.min_chapters, f"{len(chapters)} 章")
    add("附录", len(appendices) >= 5, f"{len(appendices)} 个")
    chars = len(re.sub(r"\s", "", text))
    add("讲义字数", chars >= args.min_chars, f"{chars} 字（要求 ≥{args.min_chars}）")
    question_file = work / "notes" / "appendices" / "02_题库.md"
    qtext = question_file.read_text(encoding="utf-8") if question_file.exists() else ""
    questions = len(re.findall(r"(?m)^\s*\d+[.、)]", qtext))
    add("题量", questions >= args.min_questions, f"{questions} 题（要求 ≥{args.min_questions}）")
    add("无占位符", not PLACEHOLDER.search(text), "未发现 TODO/待补充")
    info = work / "notes" / "appendices" / "04_课堂信息.md"
    itext = info.read_text(encoding="utf-8") if info.exists() else ""
    add(
        "来源标注",
        ("不是课堂逐字稿" in itext) or ("视觉" in itext) or ("MOOC" in itext),
        "课堂信息已说明来源/限制",
    )

    if docx_path.exists():
        doc = Document(str(docx_path))
        add("DOCX 可打开", True, f"{len(doc.paragraphs)} 段 / {len(doc.tables)} 表")
        add("DOCX 段落", len(doc.paragraphs) >= 100, f"{len(doc.paragraphs)} 段")
    else:
        add("DOCX 存在", False, str(docx_path))

    fails = [c for c in checks if c[1] == "FAIL"]
    lines = [
        "# 校验报告（无音轨/视觉讲义模式）",
        "",
        f"- 工作目录：{work}",
        f"- 结论：**{'PASS' if not fails else 'FAIL'}**",
        "",
        "| 检查项 | 结果 | 说明 |",
        "| --- | --- | --- |",
    ]
    lines += [f"| {name} | {status} | {detail} |" for name, status, detail in checks]
    lines += [
        "",
        "> 说明：本模式不校验逐字稿/分块（录像无可用音轨）；讲义必须标注来源，不能伪装成课堂逐字稿。",
        "",
    ]
    report = work / "output" / "校验报告.md"
    report.parent.mkdir(parents=True, exist_ok=True)
    report.write_text("\n".join(lines), encoding="utf-8")
    print("\n".join(lines[:6]))
    return 0 if not fails else 1


if __name__ == "__main__":
    raise SystemExit(main())
