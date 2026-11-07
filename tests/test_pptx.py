import json
import shutil
from pathlib import Path

from pptx import Presentation
from pptx_build import build_pptx


def test_build_pptx_from_example(tmp_path: Path):
    root = Path(__file__).resolve().parents[1]
    (tmp_path / "notes" / "assets").mkdir(parents=True)
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
    shutil.copy(root / "templates" / "slides.example.json", tmp_path / "output" / "slides.json")

    result = build_pptx(tmp_path)
    assert result["slides"] == 12
    assert result["notes"] == 12
    prs = Presentation(result["path"])
    assert len(prs.slides) == 12
