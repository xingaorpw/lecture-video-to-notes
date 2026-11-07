import json
from pathlib import Path

import pytest
from docx import Document

from common import find_pandoc
from docx_build import build_docx


@pytest.mark.skipif(not find_pandoc(), reason="Pandoc not installed")
def test_build_docx_with_omml(tmp_path: Path):
    (tmp_path / "notes").mkdir(parents=True)
    (tmp_path / "output").mkdir(parents=True)
    (tmp_path / "course.json").write_text(
        json.dumps(
            {
                "course": "测试课",
                "lecture": "第1讲",
                "instructor": "老师",
                "duration_sec": 600,
                "source_video": "demo.mp4",
                "language": "zh",
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    markdown = """---
title: "测试课 · 第1讲"
subtitle: "课堂录播完整学习讲义"
author: "老师"
date: "2026-11-07"
lang: zh-CN
---
## 课程信息

| 项目 | 内容 |
| --- | --- |
| 课程 | 测试课 |

# 第 1 章 测试

> 覆盖：00:00:00–00:10:00（chunk 1）

## 本章目标

学完这一章，你应该能写出 $E(X)=\\int x f(x)dx$。

## 核心概念

设 $X\\sim N(0,1)$，则 $E(X)=0$。

## 详细讲解

详见 [00:01:00]。

## 公式与推导

$$
E(X)=\\int_{-\\infty}^{+\\infty} x f(x)\\,dx.
$$

## 例题与证明

略。

## 易错点与考试提示

注意绝对收敛。

## 本章小结

小结。

## 自测题

1. 题。
"""
    (tmp_path / "notes" / "讲义.md").write_text(markdown, encoding="utf-8")
    result = build_docx(tmp_path)
    assert Path(result["path"]).exists()
    doc = Document(result["path"])
    assert len(doc.paragraphs) > 10
    xml = doc.element.xml
    assert "<m:oMath" in xml or "<m:oMathPara" in xml
