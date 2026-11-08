import json
from pathlib import Path

from validate import validate


def test_validate_no_ppt_skips_pptx(tmp_path: Path):
    (tmp_path / "course.json").write_text(
        json.dumps(
            {
                "course": "测试课",
                "lecture": "第1讲",
                "duration_sec": 600,
                "language": "zh",
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    result = validate(tmp_path, require_pptx=False)
    pptx = [c for c in result["checks"] if c["name"] == "PPTX"]
    assert pptx and pptx[0]["status"] == "PASS"
    assert "跳过" in pptx[0]["detail"]
