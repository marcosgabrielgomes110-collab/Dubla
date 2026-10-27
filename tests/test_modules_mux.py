import json
import math
import shutil
import subprocess
import wave

import pytest

from src.Dubla_MovieManager.Dubla_Movie_Mux import mux_video


def _sine(path, seconds=1.0, rate=24000):
    frames = int(seconds * rate)
    with wave.open(str(path), "wb") as handle:
        handle.setnchannels(1)
        handle.setsampwidth(2)
        handle.setframerate(rate)
        data = bytearray()
        for index in range(frames):
            value = int(10000 * math.sin(2 * math.pi * 220 * index / rate))
            data += value.to_bytes(2, "little", signed=True)
        handle.writeframes(bytes(data))


@pytest.mark.skipif(shutil.which("ffmpeg") is None, reason="ffmpeg not installed")
def test_mux_adds_aac_audio(tmp_path):
    video = tmp_path / "vid.mp4"
    subprocess.run(
        [
            "ffmpeg", "-y", "-loglevel", "error",
            "-f", "lavfi", "-i", "testsrc=size=160x120:rate=10:duration=2",
            "-c:v", "libx264", "-pix_fmt", "yuv420p",
            str(video),
        ],
        check=True,
    )

    voice = tmp_path / "voice" / "0000.wav"
    voice.parent.mkdir()
    _sine(voice)

    meta_path = tmp_path / "abc.json"
    meta_path.write_text(
        json.dumps(
            {
                "id": "abc",
                "duration": 2.0,
                "video_path": str(video),
                "voice": {
                    "created_at": "2026-10-26T21:00:00-05:00",
                    "segments": [
                        {"index": 0, "start": 0.0, "end": 1.0, "path": str(voice)}
                    ],
                },
            }
        ),
        encoding="utf-8",
    )

    result = mux_video(meta_path, force=True)
    assert result is not None
    assert result.is_file()

    probe = subprocess.run(
        [
            "ffprobe", "-v", "error",
            "-show_entries", "stream=codec_type,codec_name",
            "-of", "csv=p=0",
            str(result),
        ],
        capture_output=True,
        text=True,
        check=True,
    ).stdout
    assert "aac" in probe
    assert "video" in probe

    data = json.loads(meta_path.read_text(encoding="utf-8"))
    assert data["movie"]["overlaps"] == 0
    assert data["movie"]["muxed_path"] == str(result)
