from common import content_chars, format_ts, normalize_text, parse_ts, timestamp_count


def test_format_and_parse_ts():
    assert format_ts(0) == "00:00:00"
    assert format_ts(65) == "00:01:05"
    assert format_ts(3661) == "01:01:01"
    assert parse_ts("01:01:01") == 3661
    assert parse_ts("01:05") == 65


def test_normalize_cjk_spaces():
    assert normalize_text("矩 阵 乘 法") == "矩阵乘法"
    assert normalize_text("A 的 列 数") == "A的列数"
    assert normalize_text("  hello   world  ") == "hello world"


def test_counts():
    text = "结论 [00:01:02]，再看 [00:02:03–00:03:04]。"
    assert content_chars(text) == len(text.replace(" ", "").replace("\n", ""))
    assert timestamp_count(text) == 2
