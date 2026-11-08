import math
import struct
import wave
from pathlib import Path

from common import preflight_media, probe_media


def make_wav(path: Path, seconds: float, rate: int = 16000) -> None:
    with wave.open(str(path), "wb") as fh:
        fh.setnchannels(1)
        fh.setsampwidth(2)
        fh.setframerate(rate)
        frames = []
        for i in range(int(seconds * rate)):
            value = int(12000 * math.sin(2 * math.pi * 440 * i / rate))
            frames.append(struct.pack("<h", value))
        fh.writeframes(b"".join(frames))


def test_probe_media_sees_audio(tmp_path: Path):
    path = tmp_path / "ok.wav"
    make_wav(path, 12)
    info = probe_media(path)
    assert info["has_audio"] is True
    assert info["audio_duration"] >= 11.5
    assert preflight_media(path)["ok"] is True


def test_short_audio_is_fatal(tmp_path: Path):
    path = tmp_path / "short.wav"
    make_wav(path, 2)
    result = preflight_media(path)
    assert result["ok"] is False
    assert any("音轨" in item for item in result["fatal"])
