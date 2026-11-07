from chunk import coverage_stats, make_chunks


def make_segments(n=30, chars=100):
    return [
        {
            "id": i,
            "start": i * 2.0,
            "end": i * 2.0 + 1.8,
            "text": "字" * chars,
        }
        for i in range(1, n + 1)
    ]


def test_chunks_cover_every_segment():
    segments = make_segments()
    chunks = make_chunks(segments, target_chars=500, max_chars=800, overlap=2)
    assert len(chunks) > 2
    coverage = coverage_stats(chunks, segments)
    assert coverage["ratio"] == 1.0
    assert coverage["missing_segment_ids"] == []
    assert coverage["time_ratio"] > 0.99


def test_overlap_is_limited_and_progresses():
    segments = make_segments()
    chunks = make_chunks(segments, target_chars=500, max_chars=800, overlap=2)
    for left, right in zip(chunks, chunks[1:]):
        assert right["segment_start"] <= left["segment_end"]
        assert right["segment_end"] > left["segment_end"]
