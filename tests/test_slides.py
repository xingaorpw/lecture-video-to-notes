from pathlib import Path

import numpy as np
import pytest

pytest.importorskip("av")
import av

from slides import extract


def test_extract_frames_from_synthetic_video(tmp_path: Path):
    video = tmp_path / "sample.mp4"
    container = av.open(str(video), "w")
    stream = container.add_stream("mpeg4", rate=5)
    stream.width = 64
    stream.height = 48
    stream.pix_fmt = "yuv420p"
    for i in range(10):
        arr = np.full((48, 64, 3), i * 20, dtype=np.uint8)
        frame = av.VideoFrame.from_ndarray(arr, format="rgb24")
        for packet in stream.encode(frame):
            container.mux(packet)
    for packet in stream.encode():
        container.mux(packet)
    container.close()

    out = tmp_path / "slides"
    meta = extract(video, out, interval=1.0)
    assert meta["frames"] == 2
    assert len(list(out.glob("*.jpg"))) == 2
