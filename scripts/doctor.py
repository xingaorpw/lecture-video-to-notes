"""Environment doctor for lecture-video-to-notes."""
from __future__ import annotations

import argparse
import importlib.util
import json
import os
import platform
import shutil
import sys
from pathlib import Path
from typing import Any

from common import (
    SKILL_DIR,
    TOOLS_DIR,
    find_ffmpeg,
    find_ffprobe,
    find_pandoc,
    find_soffice,
    print_json,
    run,
    which,
)


def package_ok(name: str) -> bool:
    try:
        return importlib.util.find_spec(name) is not None
    except (ImportError, ValueError):
        return False


def tool_version(path: str | None, args: list[str]) -> str | None:
    if not path:
        return None
    try:
        proc = run([path, *args], check=False, timeout=15)
        text = (proc.stdout or proc.stderr or "").strip().splitlines()
        return text[0] if text else None
    except Exception:
        return None


def disk_free_gb(path: Path) -> float:
    try:
        usage = shutil.disk_usage(path)
        return round(usage.free / (1024**3), 1)
    except OSError:
        return 0.0


def build_report() -> dict[str, Any]:
    ffmpeg = find_ffmpeg()
    ffprobe = find_ffprobe()
    pandoc = find_pandoc()
    soffice = find_soffice()

    packages = {
        "faster_whisper": package_ok("faster_whisper"),
        "docx": package_ok("docx"),
        "pptx": package_ok("pptx"),
        "PIL": package_ok("PIL"),
        "av": package_ok("av"),
        "matplotlib": package_ok("matplotlib"),
        "zhconv": package_ok("zhconv"),
        "pypandoc": package_ok("pypandoc"),
    }
    required_packages = ["faster_whisper", "docx", "pptx", "PIL", "av"]
    missing_packages = [name for name in required_packages if not packages[name]]

    model_roots = [
        TOOLS_DIR / "models",
        Path.home() / ".cache" / "huggingface" / "hub",
    ]
    model_cache: list[str] = []
    for root in model_roots:
        if root.exists():
            model_cache.extend(
                p.name for p in root.glob("models--Systran--faster-whisper-*") if p.is_dir()
            )
    model_cache = sorted(set(model_cache))

    checks = {
        "python": {
            "ok": sys.version_info >= (3, 10),
            "value": sys.version.split()[0],
            "detail": "需要 Python 3.10+；推荐 3.12/3.13",
        },
        "ffmpeg": {
            "ok": bool(ffmpeg) or packages["av"],
            "value": ffmpeg,
            "version": tool_version(ffmpeg, ["-version"]),
            "fallback": "PyAV (av)" if not ffmpeg and packages["av"] else None,
            "detail": "可选；没有 ffmpeg 时用 PyAV 解码音频（faster-whisper 自带 av）",
        },
        "ffprobe": {
            "ok": bool(ffprobe) or packages["av"],
            "value": ffprobe,
            "version": tool_version(ffprobe, ["-version"]),
            "fallback": "PyAV (av)" if not ffprobe and packages["av"] else None,
            "detail": "可选；没有 ffprobe 时用 PyAV 读时长",
        },
        "pandoc": {
            "ok": bool(pandoc),
            "value": pandoc,
            "version": tool_version(pandoc, ["--version"]),
            "detail": "可选但强烈建议；DOCX 公式保真依赖它",
        },
        "libreoffice": {
            "ok": bool(soffice),
            "value": soffice,
            "detail": "可选；用于 DOCX→PDF、PPTX 渲染抽查",
        },
        "packages": {
            "ok": not missing_packages,
            "value": packages,
            "missing": missing_packages,
            "detail": "运行 setup.ps1 或 pip install -r requirements.txt",
        },
        "disk": {
            "ok": disk_free_gb(SKILL_DIR) >= 3,
            "value_gb": disk_free_gb(SKILL_DIR),
            "detail": "模型/音频/输出建议至少 3 GB 空闲",
        },
        "model_cache": {
            "ok": True,
            "value": model_cache,
            "detail": "首次运行会自动下载；tiny≈75MB，small≈460MB",
        },
    }

    required_ok = all(
        checks[name]["ok"] for name in ("python", "ffmpeg", "ffprobe", "packages", "disk")
    )
    warnings = []
    if not ffmpeg:
        warnings.append("ffmpeg 未安装：用 PyAV 兜底解码；setup.ps1 可补装便携版")
    if not pandoc:
        warnings.append("Pandoc 缺失：DOCX 将使用降级生成，复杂公式保真度下降；可 pip install pypandoc-binary")
    if not packages["matplotlib"]:
        warnings.append("matplotlib 缺失：PPT 公式无法渲染为图片，将显示 LaTeX 文本")
    if not soffice:
        warnings.append("LibreOffice 缺失：无法自动渲染 PPTX/PDF 做视觉抽查")

    return {
        "ok": required_ok,
        "platform": {
            "system": platform.system(),
            "release": platform.release(),
            "machine": platform.machine(),
            "python": sys.executable,
        },
        "skill_dir": str(SKILL_DIR),
        "tools_dir": str(TOOLS_DIR),
        "checks": checks,
        "warnings": warnings,
        "next": (
            "环境就绪，可以开始 init/transcribe"
            if required_ok
            else "先运行 setup.ps1，或按 checks 里的 missing 修复"
        ),
    }


def print_human(report: dict[str, Any]) -> None:
    print("lecture-video-to-notes doctor")
    print("=" * 52)
    print(f"skill: {report['skill_dir']}")
    print(f"python: {report['platform']['python']}")
    print("-" * 52)
    for name, item in report["checks"].items():
        mark = "OK " if item.get("ok") else "MISS"
        value = item.get("value")
        if isinstance(value, dict):
            value = ", ".join(f"{k}={'OK' if v else 'MISS'}" for k, v in value.items())
        print(f"[{mark}] {name:12s} {value if value is not None else ''}")
    if report["warnings"]:
        print("-" * 52)
        for warning in report["warnings"]:
            print(f"WARN: {warning}")
    print("-" * 52)
    print(report["next"])
    print()
    print("JSON:")
    print_json(report)


def main() -> int:
    parser = argparse.ArgumentParser(description="Check lecture-video-to-notes environment")
    parser.add_argument("--json", action="store_true", help="print JSON only")
    args = parser.parse_args()
    report = build_report()
    if args.json:
        print_json(report)
    else:
        print_human(report)
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
