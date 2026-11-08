import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_skill_frontmatter_and_files():
    text = (ROOT / "SKILL.md").read_text(encoding="utf-8")
    match = re.match(r"^---\n(.+?)\n---\n", text, re.S)
    assert match, "SKILL.md must start with YAML frontmatter"
    assert "name: lecture-video-to-notes" in match.group(1)
    assert "description:" in match.group(1)

    required = [
        "references/research.md",
        "references/note-spec.md",
        "references/ppt-spec.md",
        "references/asr-playbook.md",
        "references/troubleshooting.md",
        "templates/note-template.md",
        "templates/slides.example.json",
        "scripts/lecture.py",
        "scripts/probe.py",
        "scripts/slides.py",
        "scripts/validate_notes.py",
        "scripts/setup.ps1",
        "scripts/run.cmd",
    ]
    for item in required:
        assert (ROOT / item).exists(), item


def test_example_slides_json_is_valid():
    payload = json.loads((ROOT / "templates" / "slides.example.json").read_text(encoding="utf-8"))
    assert payload["meta"]["course"]
    assert len(payload["slides"]) >= 10
    assert all("type" in slide and "title" in slide for slide in payload["slides"])
