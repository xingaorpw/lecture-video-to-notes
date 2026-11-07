"""Build a styled DOCX from the assembled Markdown study guide."""
from __future__ import annotations

import argparse
import os
import re
import sys
from pathlib import Path
from typing import Any

from docx import Document
from docx.enum.style import WD_STYLE_TYPE
from docx.enum.table import WD_CELL_VERTICAL_ALIGNMENT, WD_TABLE_ALIGNMENT
from docx.enum.text import WD_ALIGN_PARAGRAPH, WD_BREAK
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Cm, Inches, Pt, RGBColor

from common import (
    ensure_dir,
    find_pandoc,
    find_soffice,
    load_course,
    run,
    write_json,
)

NAVY = RGBColor(0x0F, 0x27, 0x42)
ACCENT = RGBColor(0x2E, 0x86, 0xDE)
GRAY = RGBColor(0x5B, 0x6B, 0x7C)
DARK = RGBColor(0x17, 0x21, 0x2B)


def set_run_font(run, name: str = "宋体", size: float = 11, bold: bool | None = None, color=None):
    run.font.name = name
    rpr = run._element.get_or_add_rPr()
    rfonts = rpr.find(qn("w:rFonts"))
    if rfonts is None:
        rfonts = OxmlElement("w:rFonts")
        rpr.append(rfonts)
    rfonts.set(qn("w:eastAsia"), name)
    rfonts.set(qn("w:ascii"), name)
    rfonts.set(qn("w:hAnsi"), name)
    run.font.size = Pt(size)
    if bold is not None:
        run.font.bold = bold
    if color is not None:
        run.font.color.rgb = color


def set_style_font(style, name: str, size: float, bold: bool = False, color=None):
    style.font.name = name
    style.font.size = Pt(size)
    style.font.bold = bold
    if color is not None:
        style.font.color.rgb = color
    rpr = style.element.get_or_add_rPr()
    rfonts = rpr.find(qn("w:rFonts"))
    if rfonts is None:
        rfonts = OxmlElement("w:rFonts")
        rpr.append(rfonts)
    rfonts.set(qn("w:eastAsia"), name)
    rfonts.set(qn("w:ascii"), name)
    rfonts.set(qn("w:hAnsi"), name)


def add_page_number_footer(section):
    footer = section.footer
    paragraph = footer.paragraphs[0]
    paragraph.alignment = WD_ALIGN_PARAGRAPH.CENTER
    run = paragraph.add_run()
    fld_begin = OxmlElement("w:fldChar")
    fld_begin.set(qn("w:fldCharType"), "begin")
    instr = OxmlElement("w:instrText")
    instr.set(qn("xml:space"), "preserve")
    instr.text = " PAGE "
    fld_end = OxmlElement("w:fldChar")
    fld_end.set(qn("w:fldCharType"), "end")
    run._r.append(fld_begin)
    run._r.append(instr)
    run._r.append(fld_end)
    set_run_font(run, "宋体", 9, color=GRAY)


def make_reference_docx(path: Path) -> Path:
    ensure_dir(path.parent)
    doc = Document()
    section = doc.sections[0]
    section.page_width = Cm(21)
    section.page_height = Cm(29.7)
    section.top_margin = Cm(2.2)
    section.bottom_margin = Cm(2.2)
    section.left_margin = Cm(2.4)
    section.right_margin = Cm(2.4)

    styles = doc.styles
    normal = styles["Normal"]
    set_style_font(normal, "宋体", 11, color=DARK)
    normal.paragraph_format.line_spacing = 1.5
    normal.paragraph_format.space_after = Pt(6)

    body = styles["Body Text"]
    set_style_font(body, "宋体", 10.5, color=DARK)
    body.paragraph_format.line_spacing = 1.6
    body.paragraph_format.space_after = Pt(6)
    body.paragraph_format.first_line_indent = Pt(0)

    title = styles["Title"]
    set_style_font(title, "黑体", 24, bold=True, color=NAVY)
    title.paragraph_format.alignment = WD_ALIGN_PARAGRAPH.CENTER
    title.paragraph_format.space_before = Pt(30)
    title.paragraph_format.space_after = Pt(8)

    subtitle = styles["Subtitle"]
    set_style_font(subtitle, "楷体", 14, color=GRAY)
    subtitle.paragraph_format.alignment = WD_ALIGN_PARAGRAPH.CENTER
    subtitle.paragraph_format.space_after = Pt(18)

    for name, size, color, before, after in (
        ("Heading 1", 20, NAVY, 0, 14),
        ("Heading 2", 14.5, ACCENT, 14, 7),
        ("Heading 3", 12, NAVY, 10, 4),
    ):
        style = styles[name]
        set_style_font(style, "黑体", size, bold=True, color=color)
        style.paragraph_format.space_before = Pt(before)
        style.paragraph_format.space_after = Pt(after)
        style.paragraph_format.keep_with_next = True
    # Every chapter/appendix starts on a fresh page.
    styles["Heading 1"].paragraph_format.page_break_before = True

    block_text = styles["Block Text"] if "Block Text" in styles else styles.add_style("Block Text", WD_STYLE_TYPE.PARAGRAPH)
    set_style_font(block_text, "楷体", 10.5, color=GRAY)
    block_text.paragraph_format.left_indent = Cm(0.5)
    block_text.paragraph_format.right_indent = Cm(0.3)
    block_text.paragraph_format.space_before = Pt(4)
    block_text.paragraph_format.space_after = Pt(4)
    block_text.paragraph_format.line_spacing = 1.35

    for name in ("List Bullet", "List Number", "Compact"):
        if name not in styles:
            continue
        style = styles[name]
        set_style_font(style, "宋体", 10.5, color=DARK)
        style.paragraph_format.line_spacing = 1.35
        style.paragraph_format.space_after = Pt(2)

    caption = styles["Caption"]
    set_style_font(caption, "宋体", 9, color=GRAY)

    # Header: course line + thin rule.
    header = section.header
    hp = header.paragraphs[0]
    hp.text = ""
    hp.alignment = WD_ALIGN_PARAGRAPH.RIGHT
    run = hp.add_run("课堂讲义 · 课堂录播完整学习资料")
    set_run_font(run, "宋体", 8.5, color=GRAY)
    ppr = hp._p.get_or_add_pPr()
    pbdr = OxmlElement("w:pBdr")
    bottom = OxmlElement("w:bottom")
    bottom.set(qn("w:val"), "single")
    bottom.set(qn("w:sz"), "4")
    bottom.set(qn("w:space"), "4")
    bottom.set(qn("w:color"), "D9E4F0")
    pbdr.append(bottom)
    ppr.append(pbdr)

    add_page_number_footer(section)
    doc.save(str(path))
    return path


def empty_document_from_reference(ref_path: Path) -> Document:
    doc = Document(str(ref_path))
    body = doc.element.body
    for child in list(body):
        if child.tag != qn("w:sectPr"):
            body.remove(child)
    return doc


def add_hr(paragraph):
    ppr = paragraph._p.get_or_add_pPr()
    pbdr = OxmlElement("w:pBdr")
    bottom = OxmlElement("w:bottom")
    bottom.set(qn("w:val"), "single")
    bottom.set(qn("w:sz"), "6")
    bottom.set(qn("w:space"), "1")
    bottom.set(qn("w:color"), "2E86DE")
    pbdr.append(bottom)
    ppr.append(pbdr)


def shade_cell(cell, hex_color: str):
    tc_pr = cell._tc.get_or_add_tcPr()
    shd = OxmlElement("w:shd")
    shd.set(qn("w:fill"), hex_color)
    tc_pr.append(shd)


def add_inline_runs(paragraph, text: str, base_size: float = 11, color=DARK):
    token_re = re.compile(r"(\*\*.+?\*\*|`[^`]+`|\*[^*]+\*|\$[^$]+\$)")
    pos = 0
    for match in token_re.finditer(text):
        if match.start() > pos:
            run = paragraph.add_run(text[pos : match.start()])
            set_run_font(run, "宋体", base_size, color=color)
        token = match.group(0)
        if token.startswith("**") and token.endswith("**") and len(token) > 4:
            run = paragraph.add_run(token[2:-2])
            set_run_font(run, "宋体", base_size, bold=True, color=color)
        elif token.startswith("`") and token.endswith("`") and len(token) > 2:
            run = paragraph.add_run(token[1:-1])
            set_run_font(run, "Consolas", base_size - 1, color=RGBColor(0x8B, 0x1A, 0x1A))
        elif token.startswith("*") and token.endswith("*") and len(token) > 2:
            run = paragraph.add_run(token[1:-1])
            set_run_font(run, "宋体", base_size, color=color)
            run.font.italic = True
        else:
            run = paragraph.add_run(token)
            set_run_font(run, "宋体", base_size, color=GRAY)
        pos = match.end()
    if pos < len(text):
        run = paragraph.add_run(text[pos:])
        set_run_font(run, "宋体", base_size, color=color)


def parse_table_block(lines: list[str]) -> list[list[str]]:
    rows: list[list[str]] = []
    for line in lines:
        stripped = line.strip().strip("|")
        if not stripped:
            continue
        cells = [cell.strip() for cell in stripped.split("|")]
        if all(re.fullmatch(r":?-{2,}:?", cell or "-") for cell in cells):
            continue
        rows.append(cells)
    return rows


def add_markdown_table(doc: Document, rows: list[list[str]]):
    if not rows:
        return
    cols = max(len(row) for row in rows)
    table = doc.add_table(rows=len(rows), cols=cols)
    table.style = "Table Grid"
    table.alignment = WD_TABLE_ALIGNMENT.CENTER
    table.autofit = True
    for r_index, row in enumerate(rows):
        for c_index in range(cols):
            cell = table.cell(r_index, c_index)
            cell.text = ""
            paragraph = cell.paragraphs[0]
            value = row[c_index] if c_index < len(row) else ""
            add_inline_runs(paragraph, value, base_size=9.5)
            if r_index == 0:
                shade_cell(cell, "E8F1FB")
                for run in paragraph.runs:
                    run.font.bold = True
    doc.add_paragraph()


def render_formula_png(latex: str, out_path: Path) -> bool:
    try:
        import matplotlib

        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except Exception:
        return False
    cleaned = latex.strip()
    cleaned = re.sub(r"^\$\$?", "", cleaned)
    cleaned = re.sub(r"\$\$?$", "", cleaned)
    try:
        fig = plt.figure(figsize=(8, 2.2))
        fig.patch.set_alpha(0)
        fig.text(0.5, 0.5, f"${cleaned}$", ha="center", va="center", fontsize=26, color="#17212B")
        ensure_dir(out_path.parent)
        fig.savefig(out_path, dpi=220, transparent=True, bbox_inches="tight", pad_inches=0.08)
        plt.close(fig)
        return out_path.exists() and out_path.stat().st_size > 500
    except Exception:
        try:
            plt.close("all")
        except Exception:
            pass
        return False


def build_fallback(markdown: str, out_path: Path, workdir: Path, ref_path: Path) -> dict[str, Any]:
    doc = empty_document_from_reference(ref_path)
    lines = markdown.splitlines()
    if lines and lines[0].strip() == "---":
        for raw in lines[1:]:
            if raw.strip() == "---":
                break
            match = re.match(r"^(title|author|subtitle):\s*(.+)$", raw.strip())
            if match:
                value = match.group(2).strip().strip('"')
                if match.group(1) == "title":
                    doc.core_properties.title = value
                elif match.group(1) == "author":
                    doc.core_properties.author = value
                elif match.group(1) == "subtitle":
                    doc.core_properties.subject = value
    in_code = False
    in_formula = False
    formula_buffer: list[str] = []
    code_buffer: list[str] = []
    table_buffer: list[str] = []
    first_h1 = True
    formula_index = 0

    def flush_table():
        nonlocal table_buffer
        if table_buffer:
            rows = parse_table_block(table_buffer)
            if rows:
                add_markdown_table(doc, rows)
            table_buffer = []

    def add_formula_block(latex_block: str):
        nonlocal formula_index
        formula_index += 1
        latex = latex_block.strip()
        latex = re.sub(r"^\$\$", "", latex)
        latex = re.sub(r"\$\$$", "", latex).strip()
        png = workdir / "notes" / "assets" / f"formula_{formula_index:03d}.png"
        if render_formula_png(latex, png):
            doc.add_picture(str(png), width=Inches(5.4))
            doc.paragraphs[-1].alignment = WD_ALIGN_PARAGRAPH.CENTER
        else:
            paragraph = doc.add_paragraph()
            paragraph.alignment = WD_ALIGN_PARAGRAPH.CENTER
            run = paragraph.add_run(latex_block.strip())
            set_run_font(run, "Cambria Math", 11, color=DARK)

    for raw in lines:
        line = raw.rstrip()
        stripped = line.strip()
        if in_formula:
            formula_buffer.append(raw)
            if stripped.endswith("$$"):
                in_formula = False
                add_formula_block("\n".join(formula_buffer))
                formula_buffer = []
            continue
        if stripped.startswith("$$"):
            flush_table()
            if stripped.endswith("$$") and len(stripped) > 2:
                add_formula_block(stripped)
            else:
                in_formula = True
                formula_buffer = [raw]
            continue
        if line.strip().startswith("```"):
            if in_code:
                paragraph = doc.add_paragraph()
                paragraph.style = doc.styles["No Spacing"]
                for code_line in code_buffer:
                    run = paragraph.add_run(code_line + "\n")
                    set_run_font(run, "Consolas", 9, color=RGBColor(0x33, 0x33, 0x33))
                code_buffer = []
                in_code = False
            else:
                flush_table()
                in_code = True
            continue
        if in_code:
            code_buffer.append(raw)
            continue

        if line.strip().startswith("|") and "|" in line.strip()[1:]:
            table_buffer.append(line)
            continue
        if table_buffer:
            flush_table()

        stripped = line.strip()
        if not stripped:
            continue
        if stripped in ("---", "***", "___"):
            add_hr(doc.add_paragraph())
            continue
        if stripped.startswith("<!--"):
            continue
        image_match = re.match(r"!\[(.*?)\]\((.+?)\)", stripped)
        if image_match:
            image_path = Path(image_match.group(2))
            if not image_path.is_absolute():
                candidates = [workdir / image_path, workdir / "notes" / image_path, workdir / "notes" / "assets" / image_path.name]
                image_path = next((p for p in candidates if p.exists()), image_path)
            if image_path.exists():
                try:
                    doc.add_picture(str(image_path), width=Inches(5.8))
                    caption = doc.add_paragraph(image_match.group(1))
                    caption.style = doc.styles["Caption"]
                    caption.alignment = WD_ALIGN_PARAGRAPH.CENTER
                except Exception:
                    doc.add_paragraph(f"[图片无法插入：{image_match.group(2)}]")
            continue
        heading = re.match(r"^(#{1,6})\s+(.+)$", stripped)
        if heading:
            level = len(heading.group(1))
            text = heading.group(2).strip()
            if level == 1:
                if not first_h1:
                    doc.add_page_break()
                first_h1 = False
            doc.add_heading(text, level=min(level, 4))
            continue
        if stripped.startswith(">"):
            content = re.sub(r"^>\s*", "", stripped)
            content = content.replace("[!note]", "📎").replace("[!warning]", "⚠️").replace("[!tip]", "💡")
            paragraph = doc.add_paragraph()
            paragraph.style = doc.styles["Quote"]
            add_inline_runs(paragraph, content, base_size=10.5, color=GRAY)
            continue
        list_match = re.match(r"^[-*+]\s+(.+)$", stripped)
        if list_match:
            paragraph = doc.add_paragraph(style="List Bullet")
            add_inline_runs(paragraph, list_match.group(1))
            continue
        ordered_match = re.match(r"^\d+[.)]\s+(.+)$", stripped)
        if ordered_match:
            paragraph = doc.add_paragraph(style="List Number")
            add_inline_runs(paragraph, ordered_match.group(1))
            continue
        paragraph = doc.add_paragraph()
        paragraph.style = doc.styles["Body Text"]
        add_inline_runs(paragraph, stripped)

    if table_buffer:
        flush_table()
    if in_code and code_buffer:
        paragraph = doc.add_paragraph()
        for code_line in code_buffer:
            run = paragraph.add_run(code_line + "\n")
            set_run_font(run, "Consolas", 9)

    doc.save(str(out_path))
    return {"engine": "python-docx", "path": str(out_path)}


def _add_bottom_border(paragraph, color: str = "2E86DE", size: int = 8, space: int = 4):
    ppr = paragraph._p.get_or_add_pPr()
    pbdr = ppr.find(qn("w:pBdr"))
    if pbdr is None:
        pbdr = OxmlElement("w:pBdr")
        ppr.append(pbdr)
    bottom = OxmlElement("w:bottom")
    bottom.set(qn("w:val"), "single")
    bottom.set(qn("w:sz"), str(size))
    bottom.set(qn("w:space"), str(space))
    bottom.set(qn("w:color"), color)
    pbdr.append(bottom)


def _shade_paragraph(paragraph, fill: str):
    ppr = paragraph._p.get_or_add_pPr()
    shd = OxmlElement("w:shd")
    shd.set(qn("w:val"), "clear")
    shd.set(qn("w:color"), "auto")
    shd.set(qn("w:fill"), fill)
    ppr.append(shd)


def _add_left_border(paragraph, color: str = "2E86DE", size: int = 18):
    ppr = paragraph._p.get_or_add_pPr()
    pbdr = ppr.find(qn("w:pBdr"))
    if pbdr is None:
        pbdr = OxmlElement("w:pBdr")
        ppr.append(pbdr)
    left = OxmlElement("w:left")
    left.set(qn("w:val"), "single")
    left.set(qn("w:sz"), str(size))
    left.set(qn("w:space"), "8")
    left.set(qn("w:color"), color)
    pbdr.append(left)


def _insert_before(anchor, paragraph):
    anchor._p.addprevious(paragraph._p)


def _cover_paragraph(doc, anchor, text, *, size=11, bold=False, color=DARK, before=0, after=0, align=WD_ALIGN_PARAGRAPH.LEFT, font="宋体"):
    p = doc.add_paragraph()
    p.alignment = align
    p.paragraph_format.space_before = Pt(before)
    p.paragraph_format.space_after = Pt(after)
    p.paragraph_format.line_spacing = 1.2
    run = p.add_run(text)
    set_run_font(run, font, size, bold=bold, color=color)
    _insert_before(anchor, p)
    return p


def polish_docx(path: Path, course: dict[str, Any], workdir: Path) -> dict[str, Any]:
    """Turn Pandoc's functional DOCX into a readable, designed study guide."""
    doc = Document(str(path))
    body = doc.element.body

    # Remove Pandoc's metadata block; we build a proper cover.
    for p in list(doc.paragraphs[:12]):
        if p.style.name in {"Title", "Subtitle", "Author", "Date"}:
            p._element.getparent().remove(p._element)

    # Find the anchor where the actual body starts.
    anchor = None
    for p in doc.paragraphs:
        if p.text.strip() == "课程信息":
            anchor = p
            break
    if anchor is None:
        anchor = doc.paragraphs[0] if doc.paragraphs else None
    if anchor is not None:
        # Remove everything Pandoc placed before the body (title/author/date/blank).
        before = list(doc.paragraphs)
        cut = next((i for i, p in enumerate(before) if p._p is anchor._p), 0)
        for p in before[:cut]:
            p._element.getparent().remove(p._element)
        # Cover block.
        top = _cover_paragraph(
            doc,
            anchor,
            "同济大学 · 概率论与数理统计",
            size=10,
            color=GRAY,
            before=42,
            after=18,
        )
        _add_bottom_border(top, color="2E86DE", size=10, space=8)
        _cover_paragraph(
            doc,
            anchor,
            str(course.get("course") or "课堂讲义"),
            size=30,
            bold=True,
            color=NAVY,
            before=10,
            after=6,
        )
        _cover_paragraph(
            doc,
            anchor,
            str(course.get("lecture") or ""),
            size=16,
            color=ACCENT,
            before=0,
            after=26,
        )
        meta = [
            ("授课教师", str(course.get("instructor") or "—")),
            ("课程时长", f"{float(course.get('duration_sec') or 0)/60:.0f} 分钟"),
            ("资料来源", "课堂录播 · 智慧教学平台"),
            ("生成日期", str(course.get("updated") or course.get("created") or "")[:10]),
        ]
        for label, value in meta:
            p = doc.add_paragraph()
            p.paragraph_format.space_before = Pt(0)
            p.paragraph_format.space_after = Pt(4)
            p.paragraph_format.line_spacing = 1.3
            r1 = p.add_run(f"{label}  ")
            set_run_font(r1, "宋体", 10.5, color=GRAY)
            r2 = p.add_run(value)
            set_run_font(r2, "宋体", 10.5, bold=True, color=DARK)
            _insert_before(anchor, p)
        _cover_paragraph(
            doc,
            anchor,
            "完整讲义  ·  逐字稿  ·  授课课件",
            size=10,
            color=GRAY,
            before=34,
            after=0,
        )
        brk = doc.add_paragraph()
        brk.add_run().add_break(WD_BREAK.PAGE)
        _insert_before(anchor, brk)

    # Headings, callouts, and page flow.
    in_toc = False
    for p in doc.paragraphs:
        if p.text.strip() == "目录":
            in_toc = True
        if p.style.name == "Heading 1":
            in_toc = False
            p.paragraph_format.page_break_before = True
            _add_bottom_border(p, color="2E86DE", size=8, space=4)
        elif p.style.name == "Block Text":
            _add_left_border(p, color="2E86DE", size=18)
            _shade_paragraph(p, "F3F8FE")
        if p.text.strip() == "覆盖核对":
            in_toc = False
            p.paragraph_format.page_break_before = True
        if p.text.strip() == "附录" and p.style.name != "Heading 1":
            p.paragraph_format.space_before = Pt(10)
            p.paragraph_format.space_after = Pt(2)
        if in_toc:
            p.paragraph_format.line_spacing = 1.0
            p.paragraph_format.space_before = Pt(0)
            p.paragraph_format.space_after = Pt(0)
        elif p.style.name in {"List Number", "List Bullet", "Compact"}:
            p.paragraph_format.line_spacing = 1.15
            p.paragraph_format.space_after = Pt(1)

    # Tables: fixed widths, header shading, readable font, no row splitting.
    def set_cell_margins(cell, top=40, bottom=40, left=80, right=80):
        tc = cell._tc
        tc_pr = tc.get_or_add_tcPr()
        mar = OxmlElement("w:tcMar")
        for name, value in (("top", top), ("bottom", bottom), ("left", left), ("right", right)):
            el = OxmlElement(f"w:{name}")
            el.set(qn("w:w"), str(value))
            el.set(qn("w:type"), "dxa")
            mar.append(el)
        tc_pr.append(mar)

    def set_table_fixed(table):
        tbl_pr = table._tbl.tblPr
        layout = OxmlElement("w:tblLayout")
        layout.set(qn("w:type"), "fixed")
        tbl_pr.append(layout)

    for table in doc.tables:
        cols = len(table.columns)
        if cols == 0:
            continue
        table.autofit = False
        set_table_fixed(table)
        table.alignment = WD_TABLE_ALIGNMENT.CENTER
        # A4 text width is about 16.2 cm.
        headers = [c.text.strip() for c in table.rows[0].cells] if table.rows else []
        if headers[:4] == ["章节", "时间范围", "字数", "时间戳"]:
            widths = [5.2, 4.0, 3.0, 3.2]
        elif headers[:4] == ["分布", "密度", "期望", "方差"]:
            widths = [3.4, 6.0, 3.2, 3.2]
        elif cols == 2:
            widths = [4.2, 11.8]
        elif cols == 3:
            widths = [4.0, 5.6, 6.4]
        elif cols == 4:
            widths = [3.4, 4.2, 4.2, 4.2]
        else:
            widths = [16.0 / cols] * cols
        for idx, width in enumerate(widths[:cols]):
            table.columns[idx].width = Cm(width)
        for r_idx, row in enumerate(table.rows):
            tr_pr = row._tr.get_or_add_trPr()
            cant_split = OxmlElement("w:cantSplit")
            tr_pr.append(cant_split)
            if r_idx == 0:
                tr_pr.append(OxmlElement("w:tblHeader"))
            for c_idx in range(cols):
                cell = table.cell(r_idx, c_idx)
                cell.width = Cm(widths[c_idx])
                cell.vertical_alignment = WD_CELL_VERTICAL_ALIGNMENT.CENTER
                set_cell_margins(cell)
                if r_idx == 0:
                    shade_cell(cell, "0F2742")
                elif r_idx % 2 == 0:
                    shade_cell(cell, "F5F8FC")
                for p in cell.paragraphs:
                    p.paragraph_format.space_before = Pt(0)
                    p.paragraph_format.space_after = Pt(0)
                    p.paragraph_format.line_spacing = 1.15
                    for run in p.runs:
                        set_run_font(run, "宋体", 9.0, bold=(r_idx == 0), color=(RGBColor(0xFF, 0xFF, 0xFF) if r_idx == 0 else DARK))

    # Header/footer: no header on cover; body pages numbered from 1.
    section = doc.sections[0]
    section.different_first_page_header_footer = True
    header = section.header
    hp = header.paragraphs[0]
    hp.text = ""
    hp.alignment = WD_ALIGN_PARAGRAPH.RIGHT
    r = hp.add_run(f"{course.get('course', '')} · {course.get('lecture', '')}")
    set_run_font(r, "宋体", 8.5, color=GRAY)
    _add_bottom_border(hp, color="D9E4F0", size=4, space=4)
    # Start numbering at 0 so the first content page shows 1.
    sect_pr = section._sectPr
    pg_num = sect_pr.find(qn("w:pgNumType"))
    if pg_num is None:
        pg_num = OxmlElement("w:pgNumType")
        sect_pr.append(pg_num)
    pg_num.set(qn("w:start"), "0")

    doc.core_properties.title = f"{course.get('course', '')} · {course.get('lecture', '')}"
    doc.core_properties.author = str(course.get("instructor") or "")
    doc.core_properties.subject = "课堂录播完整学习讲义"
    doc.save(str(path))
    return {"polished": True}


def build_docx(
    workdir: Path,
    *,
    engine: str = "auto",
    pdf: bool = False,
) -> dict[str, Any]:
    markdown_path = workdir / "notes" / "讲义.md"
    if not markdown_path.exists():
        raise FileNotFoundError(f"Study guide not found: {markdown_path}; run assemble first")
    output_dir = ensure_dir(workdir / "output")
    out_path = output_dir / "讲义.docx"
    ref_path = workdir / "notes" / "assets" / "reference.docx"
    if not ref_path.exists():
        make_reference_docx(ref_path)

    pandoc = find_pandoc()
    used = "python-docx"
    if engine in ("auto", "pandoc") and pandoc:
        resource_path = os.pathsep.join(
            [str(workdir / "notes"), str(workdir / "notes" / "assets"), str(workdir)]
        )
        cmd = [
            pandoc,
            str(markdown_path),
            "-f",
            "gfm+tex_math_dollars",
            "-t",
            "docx",
            "--reference-doc",
            str(ref_path),
            "--resource-path",
            resource_path,
            "--metadata",
            "lang=zh-CN",
            "-o",
            str(out_path),
        ]
        try:
            run(cmd, timeout=300)
            used = "pandoc"
        except Exception as exc:
            if engine == "pandoc":
                raise
            print(f"[docx] Pandoc failed, falling back to python-docx: {exc}", file=sys.stderr)
            build_fallback(markdown_path.read_text(encoding="utf-8"), out_path, workdir, ref_path)
    else:
        if engine == "pandoc" and not pandoc:
            raise RuntimeError("Pandoc not found; install it or use --engine python")
        build_fallback(markdown_path.read_text(encoding="utf-8"), out_path, workdir, ref_path)

    course = load_course(workdir)
    polish_docx(out_path, course, workdir)

    # Verify the file is a readable DOCX.
    from docx import Document as DocxDocument

    doc = DocxDocument(str(out_path))
    paragraphs = len(doc.paragraphs)
    headings = sum(1 for p in doc.paragraphs if p.style.name.startswith("Heading"))
    tables = len(doc.tables)
    if paragraphs < 10:
        raise RuntimeError(f"DOCX looks empty: {paragraphs} paragraphs")

    pdf_path = None
    if pdf:
        soffice = find_soffice()
        if soffice:
            proc = run(
                [soffice, "--headless", "--convert-to", "pdf", "--outdir", str(output_dir), str(out_path)],
                check=False,
                timeout=300,
            )
            candidate = output_dir / "讲义.pdf"
            if candidate.exists():
                pdf_path = str(candidate)
            else:
                print(f"[docx] PDF conversion failed: {proc.stderr}", file=sys.stderr)
        else:
            print("[docx] PDF requested but LibreOffice not found; skipped", file=sys.stderr)

    result = {
        "ok": True,
        "engine": used,
        "path": str(out_path),
        "pdf": pdf_path,
        "paragraphs": paragraphs,
        "headings": headings,
        "tables": tables,
        "bytes": out_path.stat().st_size,
    }
    write_json(output_dir / "docx-report.json", result)
    print(
        f"[docx] {used}: {paragraphs} paragraphs, {headings} headings, "
        f"{tables} tables -> {out_path}"
    )
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description="Build DOCX study guide")
    parser.add_argument("--workdir", required=True)
    parser.add_argument("--engine", default="auto", choices=["auto", "pandoc", "python"])
    parser.add_argument("--pdf", action="store_true")
    args = parser.parse_args()
    result = build_docx(Path(args.workdir).resolve(), engine=args.engine, pdf=args.pdf)
    print(f"OK engine={result['engine']} path={result['path']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
