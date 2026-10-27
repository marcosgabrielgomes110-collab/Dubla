from src.Dubla_MovieManager.Dubla_Movie_Publish import slugify
from src.Dubla_Transcribe.Dubla_Stt_Common import build_segments


def test_slugify():
    assert slugify("Python in 100 Seconds") == "Python_in_100_Seconds"
    assert slugify("a/b:c*d?") == "a_b_c_d"
    assert slugify("") == "movie"


def test_build_segments_groups_by_pause():
    words = [
        {"word": "hello", "start": 0.0, "end": 0.4},
        {"word": "world", "start": 0.5, "end": 0.9},
        {"word": "again", "start": 2.0, "end": 2.5},
    ]
    segments = build_segments(words, "en")
    assert len(segments) == 2
    assert segments[0]["text"] == "hello world"
    assert segments[1]["start"] == 2.0


def test_build_segments_attaches_hyphen_and_punctuation():
    words = [
        {"word": "high", "start": 0.0, "end": 0.3},
        {"word": "-level", "start": 0.3, "end": 0.6},
        {"word": "code", "start": 0.6, "end": 0.9},
        {"word": ".", "start": 0.9, "end": 0.9},
    ]
    segments = build_segments(words, "en")
    assert segments[0]["text"] == "high-level code."


def test_build_segments_no_space_language():
    words = [
        {"word": "你好", "start": 0.0, "end": 0.4},
        {"word": "世界", "start": 0.4, "end": 0.8},
    ]
    assert build_segments(words, "zh")[0]["text"] == "你好世界"


def test_build_segments_drops_noise():
    words = [
        {"word": "ok", "start": 0.0, "end": 0.1},
        {"word": "real", "start": 1.0, "end": 2.0},
    ]
    assert [item["text"] for item in build_segments(words, "en", min_segment=0.4)] == ["real"]
