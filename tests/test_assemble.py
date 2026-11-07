import json
from pathlib import Path

from assemble import assemble


def test_assemble_builds_guide(tmp_path: Path):
    (tmp_path / "notes" / "chapters").mkdir(parents=True)
    (tmp_path / "notes" / "appendices").mkdir(parents=True)
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
    (tmp_path / "notes" / "chapters" / "ch01.md").write_text(
        "# 第 1 章 测试\n\n"
        "> 覆盖：00:00:00–00:10:00（chunk 1）\n\n"
        "## 本章目标\n\n目标。\n\n"
        "## 核心概念\n\n概念。\n\n"
        "## 详细讲解\n\n讲解 [00:01:00]。\n\n"
        "## 公式与推导\n\n公式。\n\n"
        "## 例题与证明\n\n例题。\n\n"
        "## 易错点与考试提示\n\n易错。\n\n"
        "## 本章小结\n\n小结。\n\n"
        "## 自测题\n\n1. 题。\n",
        encoding="utf-8",
    )
    for name in ("00_知识点总表", "01_公式与术语", "02_题库", "03_复习路径"):
        (tmp_path / "notes" / "appendices" / f"{name}.md").write_text(
            f"# {name}\n\n内容。\n", encoding="utf-8"
        )

    meta = assemble(tmp_path)
    text = (tmp_path / "notes" / "讲义.md").read_text(encoding="utf-8")
    assert meta["total_chars"] > 0
    assert "# 第 1 章 测试" in text
    assert "课程信息" in text
    assert "测试课" in text
