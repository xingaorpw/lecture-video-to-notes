"""Shared helpers for the lecture-video-to-notes skill."""
from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Iterable

SKILL_DIR = Path(__file__).resolve().parent.parent
TOOLS_DIR = Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData" / "Local")) / "lecture-video-to-notes"
SKILL_TOOLS_DIR = SKILL_DIR / "tools"


def is_windows() -> bool:
    return os.name == "nt"


def ensure_dir(path: Path) -> Path:
    path.mkdir(parents=True, exist_ok=True)
    return path


def read_json(path: Path) -> dict[str, Any]:
    # utf-8-sig tolerates Windows PowerShell 5.1's BOM when users hand-edit JSON.
    with path.open("r", encoding="utf-8-sig") as fh:
        return json.load(fh)


def write_json(path: Path, data: Any) -> None:
    ensure_dir(path.parent)
    tmp = path.with_suffix(path.suffix + ".tmp")
    with tmp.open("w", encoding="utf-8", newline="\n") as fh:
        json.dump(data, fh, ensure_ascii=False, indent=2)
        fh.write("\n")
    tmp.replace(path)


def write_text(path: Path, text: str) -> None:
    ensure_dir(path.parent)
    tmp = path.with_suffix(path.suffix + ".tmp")
    with tmp.open("w", encoding="utf-8", newline="\n") as fh:
        fh.write(text)
        if not text.endswith("\n"):
            fh.write("\n")
    tmp.replace(path)


def now_iso() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")


def which(name: str) -> str | None:
    found = shutil.which(name)
    if found:
        return found
    if is_windows():
        for suffix in (".exe", ".cmd", ".bat"):
            found = shutil.which(name + suffix)
            if found:
                return found
    return None


def _find_in_tree(root: Path, filename: str) -> str | None:
    if not root.exists():
        return None
    try:
        for candidate in root.rglob(filename):
            if candidate.is_file():
                return str(candidate)
    except OSError:
        return None
    return None


def find_ffmpeg() -> str | None:
    return (
        which("ffmpeg")
        or _find_in_tree(TOOLS_DIR / "ffmpeg", "ffmpeg.exe")
        or _find_in_tree(SKILL_TOOLS_DIR / "ffmpeg", "ffmpeg.exe")
        or _find_in_tree(TOOLS_DIR / "ffmpeg", "ffmpeg")
        or _find_in_tree(SKILL_TOOLS_DIR / "ffmpeg", "ffmpeg")
    )


def find_ffprobe() -> str | None:
    return (
        which("ffprobe")
        or _find_in_tree(TOOLS_DIR / "ffmpeg", "ffprobe.exe")
        or _find_in_tree(SKILL_TOOLS_DIR / "ffmpeg", "ffprobe.exe")
        or _find_in_tree(TOOLS_DIR / "ffmpeg", "ffprobe")
        or _find_in_tree(SKILL_TOOLS_DIR / "ffmpeg", "ffprobe")
    )


def find_pandoc() -> str | None:
    found = (
        which("pandoc")
        or _find_in_tree(TOOLS_DIR / "pandoc", "pandoc.exe")
        or _find_in_tree(SKILL_TOOLS_DIR / "pandoc", "pandoc.exe")
        or _find_in_tree(TOOLS_DIR / "pandoc", "pandoc")
        or _find_in_tree(SKILL_TOOLS_DIR / "pandoc", "pandoc")
    )
    if found:
        return found
    try:
        import pypandoc

        bundled = Path(pypandoc.get_pandoc_path())
        for candidate in (bundled, bundled.with_suffix(".exe")):
            if candidate.exists() and candidate.is_file():
                return str(candidate)
    except Exception:
        pass
    return None


def find_soffice() -> str | None:
    candidates = [
        which("soffice"),
        which("libreoffice"),
        r"C:\Program Files\LibreOffice\program\soffice.exe",
        r"C:\Program Files (x86)\LibreOffice\program\soffice.exe",
    ]
    for candidate in candidates:
        if candidate and Path(candidate).exists():
            return str(candidate)
    return None


def run(
    cmd: Iterable[str | Path],
    *,
    cwd: Path | None = None,
    timeout: int | None = None,
    check: bool = True,
    capture: bool = True,
) -> subprocess.CompletedProcess[str]:
    args = [str(part) for part in cmd]
    kwargs: dict[str, Any] = {
        "cwd": str(cwd) if cwd else None,
        "text": True,
        "encoding": "utf-8",
        "errors": "replace",
    }
    if capture:
        kwargs.update(stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    if timeout:
        kwargs["timeout"] = timeout
    proc = subprocess.run(args, **kwargs)
    if check and proc.returncode != 0:
        stderr = (proc.stderr or "").strip()
        stdout = (proc.stdout or "").strip()
        raise RuntimeError(
            f"Command failed ({proc.returncode}): {' '.join(args)}\n"
            f"STDOUT:\n{stdout[-4000:]}\nSTDERR:\n{stderr[-4000:]}"
        )
    return proc


def probe_duration(path: Path) -> float:
    ffprobe = find_ffprobe()
    if ffprobe:
        proc = run(
            [
                ffprobe,
                "-v",
                "error",
                "-show_entries",
                "format=duration",
                "-of",
                "default=noprint_wrappers=1:nokey=1",
                str(path),
            ],
            check=False,
        )
        try:
            value = float((proc.stdout or "").strip())
            if value > 0:
                return value
        except ValueError:
            pass
    # PyAV fallback: faster-whisper already depends on av, so this works without ffprobe.
    try:
        import av

        with av.open(str(path)) as container:
            if container.duration:
                return float(container.duration / av.time_base)
    except Exception:
        pass
    return 0.0


def probe_media(path: Path) -> dict[str, Any]:
    """Return stream metadata without trusting the container header alone.

    Real lecture recordings sometimes have a full video track and only a 1-2 s
    audio track (or no audio track at all).  Callers should check
    ``audio_duration`` before spending time on ASR.
    """
    info: dict[str, Any] = {
        "duration": 0.0,
        "video_duration": 0.0,
        "audio_duration": 0.0,
        "has_audio": False,
        "has_video": False,
        "audio_codec": "",
        "video_codec": "",
    }
    try:
        import av

        with av.open(str(path)) as container:
            if container.duration:
                info["duration"] = float(container.duration / av.time_base)
            for stream in container.streams:
                duration = float(stream.duration * stream.time_base) if stream.duration else 0.0
                if stream.type == "audio":
                    info["has_audio"] = True
                    info["audio_duration"] = max(info["audio_duration"], duration)
                    info["audio_codec"] = stream.codec_context.name
                elif stream.type == "video":
                    info["has_video"] = True
                    info["video_duration"] = max(info["video_duration"], duration)
                    info["video_codec"] = stream.codec_context.name
    except Exception as exc:
        info["error"] = f"{type(exc).__name__}: {exc}"
    return info


def audio_levels(path: Path, max_seconds: float = 30.0) -> dict[str, float]:
    """Measure RMS/peak of the first ``max_seconds`` of audio (dBFS)."""
    try:
        import av
        import numpy as np

        with av.open(str(path)) as container:
            stream = next((s for s in container.streams if s.type == "audio"), None)
            if stream is None:
                return {"rms_db": -120.0, "peak": 0.0, "samples": 0.0}
            chunks: list[Any] = []
            started = None
            for frame in container.decode(stream):
                if frame.pts is None:
                    continue
                t = float(frame.pts * stream.time_base)
                if started is None:
                    started = t
                if t - started > max_seconds:
                    break
                chunks.append(frame.to_ndarray().astype("float32").reshape(-1))
            if not chunks:
                return {"rms_db": -120.0, "peak": 0.0, "samples": 0.0}
            data = np.concatenate(chunks)
            rms = float(np.sqrt(np.mean(data**2))) if data.size else 0.0
            peak = float(np.max(np.abs(data))) if data.size else 0.0
            db = 20.0 * float(np.log10(max(rms, 1e-9)))
            return {"rms_db": db, "peak": peak, "samples": float(data.size)}
    except Exception:
        return {"rms_db": -120.0, "peak": 0.0, "samples": 0.0}


def preflight_media(
    path: Path,
    *,
    min_audio_seconds: float = 10.0,
    min_audio_ratio: float = 0.5,
    silence_db: float = -55.0,
) -> dict[str, Any]:
    """Check whether a recording is usable for ASR before transcribing it."""
    info = probe_media(path)
    warnings: list[str] = []
    fatal: list[str] = []
    if not info.get("has_audio"):
        fatal.append("没有音频流：无法转写，只能改用 PPT/画面视觉讲义")
    else:
        audio_duration = float(info.get("audio_duration") or 0.0)
        video_duration = float(info.get("video_duration") or info.get("duration") or 0.0)
        if audio_duration and audio_duration < min_audio_seconds:
            fatal.append(
                f"音轨只有 {audio_duration:.2f} s（视频 {video_duration:.0f} s）：音轨损坏，ASR 不可用"
            )
        elif video_duration and audio_duration and audio_duration < video_duration * min_audio_ratio:
            fatal.append(
                f"音轨 {audio_duration:.0f} s 明显短于视频 {video_duration:.0f} s：可能只录到开头"
            )
        levels = audio_levels(path)
        if levels["rms_db"] < silence_db:
            warnings.append(
                f"音频前段接近无声（RMS {levels['rms_db']:.1f} dBFS）：可能是静音/麦克风未开"
            )
    info["warnings"] = fatal + warnings
    info["fatal"] = fatal
    info["ok"] = not fatal
    return info


def format_ts(seconds: float, *, force_hours: bool = True) -> str:
    seconds = max(0.0, float(seconds))
    total = int(round(seconds))
    hours, rem = divmod(total, 3600)
    minutes, secs = divmod(rem, 60)
    if force_hours or hours:
        return f"{hours:02d}:{minutes:02d}:{secs:02d}"
    return f"{minutes:02d}:{secs:02d}"


def parse_ts(value: str) -> float:
    parts = value.strip().replace("，", ":").replace("：", ":").split(":")
    try:
        nums = [float(p) for p in parts]
    except ValueError as exc:
        raise ValueError(f"Invalid timestamp: {value!r}") from exc
    if len(nums) == 3:
        return nums[0] * 3600 + nums[1] * 60 + nums[2]
    if len(nums) == 2:
        return nums[0] * 60 + nums[1]
    return nums[0]


def srt_ts(seconds: float) -> str:
    seconds = max(0.0, float(seconds))
    millis = int(round(seconds * 1000))
    hours, rem = divmod(millis, 3600_000)
    minutes, rem = divmod(rem, 60_000)
    secs, ms = divmod(rem, 1000)
    return f"{hours:02d}:{minutes:02d}:{secs:02d},{ms:03d}"


def normalize_text(text: str) -> str:
    text = text.replace("\u3000", " ").replace("\xa0", " ")
    text = re.sub(r"[ \t]+", " ", text)
    # Whisper often inserts spaces between Chinese characters; drop only CJK-CJK gaps.
    text = re.sub(r"(?<=[\u3400-\u9fff])\s+(?=[\u3400-\u9fff])", "", text)
    text = re.sub(r"(?<=[\u3400-\u9fff])\s+(?=[，。！？；：、）】》”’])", "", text)
    text = re.sub(r"(?<=[（【《“‘])\s+(?=[\u3400-\u9fff])", "", text)
    # Drop the artificial space Whisper inserts between Latin and Chinese.
    text = re.sub(r"(?<=[A-Za-z0-9])\s+(?=[\u3400-\u9fff])", "", text)
    text = re.sub(r"(?<=[\u3400-\u9fff])\s+(?=[A-Za-z0-9])", "", text)
    return text.strip()


def safe_slug(text: str, max_len: int = 60) -> str:
    text = re.sub(r'[<>:"/\\|?*\x00-\x1f]', "_", text).strip(" ._")
    text = re.sub(r"\s+", "_", text)
    return (text or "lecture")[:max_len]


def chapter_sort_key(path: Path) -> tuple[int, str]:
    match = re.search(r"ch(\d+)", path.stem, re.IGNORECASE)
    return (int(match.group(1)) if match else 9999, path.name)


def appendix_sort_key(path: Path) -> tuple[int, str]:
    match = re.match(r"(\d+)", path.name)
    return (int(match.group(1)) if match else 9999, path.name)


def load_course(workdir: Path) -> dict[str, Any]:
    path = workdir / "course.json"
    if not path.exists():
        raise FileNotFoundError(f"course.json not found in {workdir}; run init first")
    return read_json(path)


def content_chars(text: str) -> int:
    return len(re.sub(r"\s", "", text))


def timestamp_count(text: str) -> int:
    pattern = r"\[\d{1,2}:\d{2}:\d{2}(?:\s*[–-]\s*\d{1,2}:\d{2}:\d{2})?\]"
    return len(re.findall(pattern, text))


def die(message: str, code: int = 2) -> None:
    print(f"ERROR: {message}", file=sys.stderr)
    raise SystemExit(code)


def print_json(data: Any) -> None:
    print(json.dumps(data, ensure_ascii=False, indent=2))
