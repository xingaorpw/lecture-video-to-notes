"""Build a teachable 16:9 PPTX from a structured slides.json."""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any

from pptx import Presentation
from pptx.dml.color import RGBColor
from pptx.enum.shapes import MSO_SHAPE
from pptx.enum.text import MSO_ANCHOR, PP_ALIGN
from pptx.oxml.ns import qn
from pptx.util import Emu, Inches, Pt

from common import ensure_dir, load_course, read_json, write_json

# Academic Blue theme
NAVY = RGBColor(0x0F, 0x27, 0x42)
ACCENT = RGBColor(0x2E, 0x86, 0xDE)
GOLD = RGBColor(0xF2, 0xB8, 0x4B)
BG = RGBColor(0xF7, 0xF9, 0xFC)
WHITE = RGBColor(0xFF, 0xFF, 0xFF)
TEXT = RGBColor(0x17, 0x21, 0x2B)
MUTED = RGBColor(0x5B, 0x6B, 0x7C)
LIGHT_LINE = RGBColor(0xD9, 0xE4, 0xF0)
SOFT_BLUE = RGBColor(0xE8, 0xF1, 0xFB)

FONT_CN = "Microsoft YaHei"
FONT_EN = "Arial"
ALLOWED_TYPES = {
    "title",
    "agenda",
    "section",
    "content",
    "two_col",
    "formula",
    "table",
    "quote",
    "summary",
    "end",
}


def set_run_font(run, size: float, bold: bool = False, color: RGBColor = TEXT, name: str = FONT_CN):
    run.font.name = name
    run.font.size = Pt(size)
    run.font.bold = bold
    run.font.color.rgb = color
    rpr = run._r.get_or_add_rPr()
    ea = rpr.find(qn("a:ea"))
    if ea is None:
        from pptx.oxml.xmlchemy import OxmlElement

        ea = OxmlElement("a:ea")
        rpr.append(ea)
    ea.set("typeface", name)


def set_background(slide, color: RGBColor):
    fill = slide.background.fill
    fill.solid()
    fill.fore_color.rgb = color


def add_rect(slide, left, top, width, height, color: RGBColor, shape=MSO_SHAPE.RECTANGLE):
    shp = slide.shapes.add_shape(shape, Inches(left), Inches(top), Inches(width), Inches(height))
    shp.fill.solid()
    shp.fill.fore_color.rgb = color
    shp.line.fill.background()
    return shp


def add_textbox(
    slide,
    left: float,
    top: float,
    width: float,
    height: float,
    text: str = "",
    *,
    size: float = 20,
    bold: bool = False,
    color: RGBColor = TEXT,
    align: PP_ALIGN = PP_ALIGN.LEFT,
    anchor: MSO_ANCHOR = MSO_ANCHOR.TOP,
    name: str = FONT_CN,
):
    box = slide.shapes.add_textbox(Inches(left), Inches(top), Inches(width), Inches(height))
    tf = box.text_frame
    tf.word_wrap = True
    tf.margin_left = 0
    tf.margin_right = 0
    tf.margin_top = 0
    tf.margin_bottom = 0
    tf.vertical_anchor = anchor
    p = tf.paragraphs[0]
    p.alignment = align
    run = p.add_run()
    run.text = text
    set_run_font(run, size, bold, color, name)
    return box


def add_bullets(
    slide,
    left: float,
    top: float,
    width: float,
    height: float,
    bullets: list[str],
    *,
    size: float = 20,
    color: RGBColor = TEXT,
    bullet: str = "•",
):
    box = slide.shapes.add_textbox(Inches(left), Inches(top), Inches(width), Inches(height))
    tf = box.text_frame
    tf.word_wrap = True
    tf.margin_left = 0
    tf.margin_right = 0
    tf.margin_top = 0
    tf.margin_bottom = 0
    tf.clear()
    for index, item in enumerate(bullets):
        p = tf.paragraphs[0] if index == 0 else tf.add_paragraph()
        p.text = str(item)
        p.level = 0
        p.space_after = Pt(8)
        p.line_spacing = 1.15
        pPr = p._p.get_or_add_pPr()
        pPr.set("marL", str(Inches(0.30)))
        pPr.set("indent", str(-Inches(0.30)))
        from pptx.oxml.xmlchemy import OxmlElement

        bu_font = OxmlElement("a:buFont")
        bu_font.set("typeface", "Arial")
        bu_char = OxmlElement("a:buChar")
        bu_char.set("char", bullet)
        pPr.append(bu_font)
        pPr.append(bu_char)
        for run in p.runs:
            set_run_font(run, size, False, color)
    return box


def add_footer(slide, course: str, lecture: str, page: int, *, dark: bool = False):
    line_color = RGBColor(0x3A, 0x53, 0x70) if dark else LIGHT_LINE
    text_color = RGBColor(0xB8, 0xC7, 0xD9) if dark else MUTED
    add_rect(slide, 0.6, 7.05, 12.13, 0.012, line_color)
    add_textbox(slide, 0.6, 7.12, 9.4, 0.28, f"{course} ｜ {lecture}", size=9, color=text_color)
    add_textbox(
        slide,
        11.2,
        7.12,
        1.53,
        0.28,
        str(page),
        size=9,
        color=text_color,
        align=PP_ALIGN.RIGHT,
    )


def fit_title_size(text: str, base: int) -> int:
    length = len(text)
    if length <= 24:
        return base
    if length <= 34:
        return max(20, base - 4)
    if length <= 44:
        return max(18, base - 7)
    return max(16, base - 9)


def content_title(slide, title: str, subtitle: str | None = None):
    add_rect(slide, 0, 0, 13.333, 0.10, ACCENT)
    add_textbox(slide, 0.6, 0.42, 12.1, 0.78, title, size=fit_title_size(title, 28), bold=True, color=NAVY)
    if subtitle:
        add_textbox(slide, 0.6, 1.18, 12.1, 0.38, subtitle, size=15, color=MUTED)
    add_rect(slide, 0.6, 1.62 if subtitle else 1.30, 12.13, 0.018, LIGHT_LINE)


def add_notes(slide, notes: str | None):
    if notes:
        slide.notes_slide.notes_text_frame.text = notes.strip()


def split_bullets(bullets: list[str], *, max_items: int = 6, max_chars: int = 430):
    groups: list[list[str]] = []
    current: list[str] = []
    chars = 0
    for item in bullets:
        item = str(item).strip()
        if not item:
            continue
        if current and (len(current) >= max_items or chars + len(item) > max_chars):
            groups.append(current)
            current = []
            chars = 0
        current.append(item)
        chars += len(item)
    if current:
        groups.append(current)
    return groups or [["（本页无要点）"]]


def add_title_slide(prs, data: dict[str, Any], page: int, meta: dict[str, Any]):
    slide = prs.slides.add_slide(prs.slide_layouts[6])
    set_background(slide, NAVY)
    add_rect(slide, 0.75, 1.15, 0.10, 3.2, ACCENT)
    title = data.get("title", "")
    add_textbox(slide, 1.05, 1.05, 11.2, 1.7, title, size=fit_title_size(title, 44), bold=True, color=WHITE)
    if data.get("subtitle"):
        add_textbox(slide, 1.05, 2.85, 11.0, 0.8, data["subtitle"], size=21, color=RGBColor(0xC9, 0xD8, 0xEA))
    add_textbox(
        slide,
        1.05,
        4.35,
        10.8,
        0.5,
        data.get("caption", "课堂录播 · 完整讲义配套课件"),
        size=14,
        color=GOLD,
    )
    add_textbox(
        slide,
        1.05,
        6.65,
        11.0,
        0.4,
        data.get("footer") or f"{meta.get('course', '')} ｜ {meta.get('lecture', '')}",
        size=11,
        color=RGBColor(0x9F, 0xB4, 0xCC),
    )
    add_notes(slide, data.get("notes"))
    return slide


def add_agenda_slide(prs, data: dict[str, Any], page: int, meta: dict[str, Any]):
    slide = prs.slides.add_slide(prs.slide_layouts[6])
    set_background(slide, BG)
    content_title(slide, data.get("title", "本讲路线"))
    items = [str(x) for x in data.get("items", [])]
    if len(items) <= 5:
        columns = [items]
    else:
        mid = (len(items) + 1) // 2
        columns = [items[:mid], items[mid:]]
    width = 5.6 if len(columns) > 1 else 11.0
    for c_index, col in enumerate(columns):
        left = 0.8 + c_index * 6.0
        top = 1.75
        for i, item in enumerate(col):
            number = c_index * len(columns[0]) + i + 1 if len(columns) > 1 else i + 1
            add_rect(slide, left, top + i * 0.82, 0.46, 0.46, ACCENT, MSO_SHAPE.OVAL)
            add_textbox(
                slide,
                left,
                top + i * 0.82 + 0.02,
                0.46,
                0.42,
                str(number),
                size=14,
                bold=True,
                color=WHITE,
                align=PP_ALIGN.CENTER,
                anchor=MSO_ANCHOR.MIDDLE,
            )
            add_textbox(slide, left + 0.62, top + i * 0.82, width - 0.7, 0.5, item, size=18, color=TEXT)
    add_footer(slide, meta.get("course", ""), meta.get("lecture", ""), page)
    add_notes(slide, data.get("notes"))
    return slide


def add_section_slide(prs, data: dict[str, Any], page: int, meta: dict[str, Any], section_no: int):
    slide = prs.slides.add_slide(prs.slide_layouts[6])
    set_background(slide, NAVY)
    add_textbox(slide, 10.0, 0.8, 2.6, 1.6, f"{section_no:02d}", size=72, bold=True, color=RGBColor(0x25, 0x3F, 0x5C), align=PP_ALIGN.RIGHT)
    add_rect(slide, 0.85, 2.05, 0.10, 1.8, GOLD)
    section_title = data.get("title", "")
    add_textbox(slide, 1.15, 1.95, 10.8, 1.2, section_title, size=fit_title_size(section_title, 34), bold=True, color=WHITE)
    if data.get("subtitle"):
        add_textbox(slide, 1.15, 3.15, 10.6, 0.8, data["subtitle"], size=19, color=RGBColor(0xC9, 0xD8, 0xEA))
    add_footer(slide, meta.get("course", ""), meta.get("lecture", ""), page, dark=True)
    add_notes(slide, data.get("notes"))
    return slide


def add_card_list(slide, bullets: list[str]):
    count = max(1, len(bullets))
    top = 1.72
    available = 4.9
    gap = 0.10 if count >= 6 else 0.14
    card_h = min(0.86, (available - gap * (count - 1)) / count)
    for i, text in enumerate(bullets):
        y = top + i * (card_h + gap)
        card = add_rect(slide, 0.72, y, 11.9, card_h, WHITE, MSO_SHAPE.ROUNDED_RECTANGLE)
        card.line.color.rgb = LIGHT_LINE
        add_rect(slide, 0.72, y, 0.08, card_h, ACCENT if i % 2 == 0 else GOLD)
        badge = add_rect(slide, 0.98, y + (card_h - 0.38) / 2, 0.38, 0.38, ACCENT if i % 2 == 0 else GOLD, MSO_SHAPE.OVAL)
        add_textbox(
            slide,
            0.98,
            y + (card_h - 0.38) / 2 + 0.01,
            0.38,
            0.36,
            str(i + 1),
            size=11,
            bold=True,
            color=WHITE,
            align=PP_ALIGN.CENTER,
            anchor=MSO_ANCHOR.MIDDLE,
        )
        add_textbox(
            slide,
            1.55,
            y + 0.06,
            10.75,
            card_h - 0.12,
            text,
            size=18 if len(text) <= 34 else 16,
            color=TEXT,
            anchor=MSO_ANCHOR.MIDDLE,
        )


def add_content_slides(prs, data: dict[str, Any], page_start: int, meta: dict[str, Any]):
    bullets = [str(x) for x in data.get("bullets", [])]
    groups = split_bullets(bullets)
    slides = []
    for index, group in enumerate(groups):
        slide = prs.slides.add_slide(prs.slide_layouts[6])
        set_background(slide, BG)
        title = data.get("title", "")
        if index > 0:
            title = title + "（续）"
        content_title(slide, title)
        total_chars = sum(len(x) for x in group)
        # Short, scannable points get a card layout; long text stays as bullets.
        if 2 <= len(group) <= 6 and max(len(x) for x in group) <= 44:
            add_card_list(slide, group)
        else:
            size = 21 if total_chars < 180 else 19 if total_chars < 300 else 17
            add_bullets(slide, 0.8, 1.72, 11.7, 4.9, group, size=size)
        notes = data.get("notes") or ""
        if index > 0:
            notes = notes + "\n\n（续页：接上一页，先回顾上一条，再继续。）"
        add_notes(slide, notes)
        add_footer(slide, meta.get("course", ""), meta.get("lecture", ""), page_start + index)
        slides.append(slide)
    return slides


def add_two_col_slide(prs, data: dict[str, Any], page: int, meta: dict[str, Any]):
    slide = prs.slides.add_slide(prs.slide_layouts[6])
    set_background(slide, BG)
    content_title(slide, data.get("title", ""))
    for index, key in enumerate(("left", "right")):
        col = data.get(key) or {}
        left = 0.7 + index * 6.05
        card = add_rect(slide, left, 1.7, 5.75, 4.9, WHITE, MSO_SHAPE.ROUNDED_RECTANGLE)
        card.line.color.rgb = LIGHT_LINE
        add_rect(slide, left, 1.7, 5.75, 0.10, ACCENT if index == 0 else GOLD)
        add_textbox(slide, left + 0.35, 1.95, 5.05, 0.55, col.get("heading", ""), size=20, bold=True, color=NAVY)
        add_bullets(slide, left + 0.4, 2.65, 5.0, 3.6, [str(x) for x in col.get("bullets", [])], size=17)
    add_footer(slide, meta.get("course", ""), meta.get("lecture", ""), page)
    add_notes(slide, data.get("notes"))
    return slide


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
    # Matplotlib mathtext has a smaller command set than LaTeX.
    cleaned = cleaned.replace(r"\iint", r"\int\int")
    cleaned = cleaned.replace(r"\iiint", r"\int\int\int")
    cleaned = re.sub(r"\\inf(?![A-Za-z])", r"\\mathrm{inf}", cleaned)
    cleaned = cleaned.replace(r"\mathbb{R}", r"\mathbf{R}")
    cleaned = cleaned.replace(r"\mathbb R", r"\mathbf R")
    try:
        fig = plt.figure(figsize=(10, 2.6))
        fig.patch.set_alpha(0)
        fig.text(0.5, 0.5, f"${cleaned}$", ha="center", va="center", fontsize=30, color="#17212B")
        ensure_dir(out_path.parent)
        fig.savefig(out_path, dpi=240, transparent=True, bbox_inches="tight", pad_inches=0.08)
        plt.close(fig)
        return out_path.exists() and out_path.stat().st_size > 500
    except Exception:
        try:
            plt.close("all")
        except Exception:
            pass
        return False


def add_formula_slide(prs, data: dict[str, Any], page: int, meta: dict[str, Any], index: int, workdir: Path):
    slide = prs.slides.add_slide(prs.slide_layouts[6])
    set_background(slide, BG)
    content_title(slide, data.get("title", "公式"))
    card = add_rect(slide, 0.72, 1.70, 11.9, 2.90, WHITE, MSO_SHAPE.ROUNDED_RECTANGLE)
    card.line.color.rgb = LIGHT_LINE
    add_textbox(slide, 1.0, 1.80, 2.0, 0.3, "核心公式", size=11, bold=True, color=GOLD)
    formula = str(data.get("formula", "")).strip()
    png = workdir / "notes" / "assets" / f"ppt_formula_{index:03d}.png"
    rendered = render_formula_png(formula, png) if formula else False
    if rendered:
        from PIL import Image

        with Image.open(png) as img:
            ratio = img.width / max(1, img.height)
        max_w, max_h = 11.0, 1.95
        width = min(max_w, max_h * ratio)
        height = width / max(0.1, ratio)
        left = (13.333 - width) / 2
        slide.shapes.add_picture(str(png), Inches(left), Inches(2.16), width=Inches(width), height=Inches(height))
        top = 2.16 + height + 0.12
    else:
        add_textbox(
            slide,
            0.8,
            2.1,
            11.7,
            2.1,
            formula or "（公式未填写）",
            size=24,
            color=NAVY,
            align=PP_ALIGN.CENTER,
            anchor=MSO_ANCHOR.MIDDLE,
            name="Cambria Math",
        )
        top = 4.55
    explain = [str(x) for x in data.get("explain", [])]
    if explain:
        body_top = max(4.78, min(top, 4.95))
        body_size = 14 if len(explain) > 4 else 15 if len(explain) > 3 else 16
        add_bullets(slide, 0.9, body_top, 11.5, 6.85 - body_top, explain, size=body_size)
    add_footer(slide, meta.get("course", ""), meta.get("lecture", ""), page)
    add_notes(slide, data.get("notes"))
    return slide


def add_table_slide(prs, data: dict[str, Any], page: int, meta: dict[str, Any]):
    headers = [str(x) for x in data.get("headers", [])]
    rows = [[str(cell) for cell in row] for row in data.get("rows", [])]
    if not headers or not rows:
        raise ValueError("table slide requires headers and rows")
    cols = len(headers)
    if cols > 6:
        raise ValueError(f"table has {cols} columns; max 6")
    if len(rows) > 8:
        raise ValueError(
            f"table has {len(rows)} rows; max 8. Split it into multiple table slides "
            "with repeated headers, or reduce the rows."
        )
    body_rows = rows
    slide = prs.slides.add_slide(prs.slide_layouts[6])
    set_background(slide, BG)
    content_title(slide, data.get("title", ""))
    row_h = 0.52
    table_h = row_h * (len(body_rows) + 1)
    shape = slide.shapes.add_table(
        len(body_rows) + 1, cols, Inches(0.7), Inches(1.8), Inches(11.9), Inches(table_h)
    )
    table = shape.table
    col_width = 11.9 / cols
    for c in range(cols):
        table.columns[c].width = Inches(col_width)
    for r in range(len(body_rows) + 1):
        table.rows[r].height = Inches(row_h)
    for c, header in enumerate(headers):
        cell = table.cell(0, c)
        cell.text = header
        cell.fill.solid()
        cell.fill.fore_color.rgb = NAVY
        cell.vertical_anchor = MSO_ANCHOR.MIDDLE
        cell.margin_left = Inches(0.08)
        cell.margin_right = Inches(0.08)
        cell.margin_top = Inches(0.03)
        cell.margin_bottom = Inches(0.03)
        for p in cell.text_frame.paragraphs:
            for run in p.runs:
                set_run_font(run, 12, True, WHITE)
    for r, row in enumerate(body_rows, start=1):
        for c in range(cols):
            cell = table.cell(r, c)
            cell.text = row[c] if c < len(row) else ""
            cell.fill.solid()
            cell.fill.fore_color.rgb = WHITE if r % 2 == 1 else SOFT_BLUE
            cell.vertical_anchor = MSO_ANCHOR.MIDDLE
            cell.margin_left = Inches(0.08)
            cell.margin_right = Inches(0.08)
            cell.margin_top = Inches(0.03)
            cell.margin_bottom = Inches(0.03)
            for p in cell.text_frame.paragraphs:
                for run in p.runs:
                    set_run_font(run, 11, False, TEXT)
    add_textbox(
        slide,
        0.8,
        1.8 + table_h + 0.18,
        11.5,
        0.4,
        "二维题第一步：先画图/列表，再选方法。",
        size=13,
        color=MUTED,
    )
    # A small three-step strip fills the lower half and reinforces the workflow.
    steps = ["① 判断类型", "② 画图 / 列表", "③ 套对应公式"]
    for i, step in enumerate(steps):
        x = 0.72 + i * 3.98
        chip = add_rect(slide, x, 4.55, 3.78, 0.95, WHITE, MSO_SHAPE.ROUNDED_RECTANGLE)
        chip.line.color.rgb = LIGHT_LINE
        add_rect(slide, x, 4.55, 0.08, 0.95, ACCENT if i != 1 else GOLD)
        add_textbox(
            slide,
            x + 0.28,
            4.55,
            3.3,
            0.95,
            step,
            size=16,
            bold=True,
            color=NAVY,
            anchor=MSO_ANCHOR.MIDDLE,
        )
    add_footer(slide, meta.get("course", ""), meta.get("lecture", ""), page)
    add_notes(slide, data.get("notes"))
    return slide


def add_quote_slide(prs, data: dict[str, Any], page: int, meta: dict[str, Any]):
    slide = prs.slides.add_slide(prs.slide_layouts[6])
    set_background(slide, BG)
    content_title(slide, data.get("title", "老师强调"))
    card = add_rect(slide, 0.85, 1.85, 11.6, 3.8, WHITE, MSO_SHAPE.ROUNDED_RECTANGLE)
    card.line.color.rgb = LIGHT_LINE
    add_rect(slide, 0.85, 1.85, 0.12, 3.8, GOLD)
    quote = str(data.get("quote", ""))
    quote_size = 25 if len(quote) <= 80 else 21 if len(quote) <= 140 else 18
    add_textbox(slide, 1.25, 2.1, 10.7, 2.6, f"“{quote}”", size=quote_size, color=NAVY, anchor=MSO_ANCHOR.MIDDLE)
    if data.get("source"):
        add_textbox(slide, 1.25, 4.9, 10.6, 0.4, str(data["source"]), size=13, color=MUTED, align=PP_ALIGN.RIGHT)
    add_footer(slide, meta.get("course", ""), meta.get("lecture", ""), page)
    add_notes(slide, data.get("notes"))
    return slide


def add_summary_slide(prs, data: dict[str, Any], page: int, meta: dict[str, Any]):
    slide = prs.slides.add_slide(prs.slide_layouts[6])
    set_background(slide, BG)
    add_rect(slide, 0, 0, 13.333, 7.5, SOFT_BLUE)
    add_rect(slide, 0, 0, 0.16, 7.5, ACCENT)
    add_textbox(slide, 0.9, 0.55, 11.9, 0.8, data.get("title", "本讲小结"), size=30, bold=True, color=NAVY)
    add_bullets(slide, 0.95, 1.7, 11.7, 4.9, [str(x) for x in data.get("bullets", [])], size=20)
    add_footer(slide, meta.get("course", ""), meta.get("lecture", ""), page)
    add_notes(slide, data.get("notes"))
    return slide


def add_end_slide(prs, data: dict[str, Any], page: int, meta: dict[str, Any]):
    slide = prs.slides.add_slide(prs.slide_layouts[6])
    set_background(slide, NAVY)
    add_textbox(slide, 1.0, 2.2, 11.3, 1.2, data.get("title", "谢谢"), size=46, bold=True, color=WHITE)
    if data.get("subtitle"):
        add_textbox(slide, 1.0, 3.55, 11.0, 0.9, data["subtitle"], size=21, color=GOLD)
    add_textbox(
        slide,
        1.0,
        6.55,
        11.0,
        0.4,
        f"{meta.get('course', '')} ｜ {meta.get('lecture', '')}",
        size=11,
        color=RGBColor(0x9F, 0xB4, 0xCC),
    )
    add_notes(slide, data.get("notes"))
    return slide


def validate_slides(payload: dict[str, Any]):
    if not isinstance(payload, dict):
        raise ValueError("slides.json must be an object")
    meta = payload.get("meta")
    slides = payload.get("slides")
    if not isinstance(meta, dict) or not meta.get("course") or not meta.get("lecture"):
        raise ValueError("meta.course and meta.lecture are required")
    if not isinstance(slides, list) or not slides:
        raise ValueError("slides must be a non-empty list")
    for index, slide in enumerate(slides, start=1):
        if not isinstance(slide, dict):
            raise ValueError(f"slide {index} is not an object")
        kind = slide.get("type")
        if kind not in ALLOWED_TYPES:
            raise ValueError(f"slide {index}: unknown type {kind!r}")
        if not str(slide.get("title", "")).strip():
            raise ValueError(f"slide {index}: title is required")
        if kind in {"content", "section", "agenda", "two_col", "formula", "table", "quote", "summary"}:
            if not str(slide.get("notes", "")).strip():
                raise ValueError(f"slide {index} ({kind}): notes (speaker script) is required")
        if kind == "content" and not slide.get("bullets"):
            raise ValueError(f"slide {index}: content requires bullets")
        if kind == "agenda" and not slide.get("items"):
            raise ValueError(f"slide {index}: agenda requires items")
        if kind == "two_col" and (not slide.get("left") or not slide.get("right")):
            raise ValueError(f"slide {index}: two_col requires left and right")
        if kind == "formula" and not str(slide.get("formula", "")).strip():
            raise ValueError(f"slide {index}: formula requires formula")
        if kind == "table":
            if not slide.get("headers") or not slide.get("rows"):
                raise ValueError(f"slide {index}: table requires headers and rows")
            if len(slide["headers"]) > 6:
                raise ValueError(f"slide {index}: table has >6 columns")
            if len(slide["rows"]) > 8:
                raise ValueError(f"slide {index}: table has >8 rows; split it")


def build_pptx(workdir: Path, *, input_json: Path | None = None) -> dict[str, Any]:
    input_path = input_json or (workdir / "output" / "slides.json")
    if not input_path.exists():
        raise FileNotFoundError(f"slides.json not found: {input_path}")
    payload = read_json(input_path)
    validate_slides(payload)
    meta = payload["meta"]
    course = load_course(workdir)

    prs = Presentation()
    prs.slide_width = Inches(13.333)
    prs.slide_height = Inches(7.5)
    prs.core_properties.title = f"{meta.get('course', '')} · {meta.get('lecture', '')}"
    prs.core_properties.subject = "课堂录播配套课件"
    prs.core_properties.author = str(meta.get("instructor") or "")
    page = 1
    section_no = 0
    formula_no = 0
    for slide_data in payload["slides"]:
        kind = slide_data["type"]
        if kind == "title":
            add_title_slide(prs, slide_data, page, meta)
        elif kind == "agenda":
            add_agenda_slide(prs, slide_data, page, meta)
        elif kind == "section":
            section_no += 1
            add_section_slide(prs, slide_data, page, meta, section_no)
        elif kind == "content":
            slides = add_content_slides(prs, slide_data, page, meta)
            page += len(slides) - 1
        elif kind == "two_col":
            add_two_col_slide(prs, slide_data, page, meta)
        elif kind == "formula":
            formula_no += 1
            add_formula_slide(prs, slide_data, page, meta, formula_no, workdir)
        elif kind == "table":
            add_table_slide(prs, slide_data, page, meta)
        elif kind == "quote":
            add_quote_slide(prs, slide_data, page, meta)
        elif kind == "summary":
            add_summary_slide(prs, slide_data, page, meta)
        elif kind == "end":
            add_end_slide(prs, slide_data, page, meta)
        page += 1

    output_dir = ensure_dir(workdir / "output")
    out_path = output_dir / "课件.pptx"
    prs.save(str(out_path))

    # Verify.
    check = Presentation(str(out_path))
    notes_count = sum(
        1
        for s in check.slides
        if s.has_notes_slide and s.notes_slide.notes_text_frame.text.strip()
    )
    result = {
        "ok": True,
        "path": str(out_path),
        "slides": len(check.slides),
        "notes": notes_count,
        "bytes": out_path.stat().st_size,
        "source": str(input_path),
    }
    write_json(output_dir / "pptx-report.json", result)
    print(f"[pptx] {len(check.slides)} slides, {notes_count} with speaker notes -> {out_path}")
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description="Build PPTX from slides.json")
    parser.add_argument("--workdir", required=True)
    parser.add_argument("--input", default=None)
    args = parser.parse_args()
    workdir = Path(args.workdir).resolve()
    input_path = Path(args.input).resolve() if args.input else None
    result = build_pptx(workdir, input_json=input_path)
    print(f"OK slides={result['slides']} path={result['path']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
