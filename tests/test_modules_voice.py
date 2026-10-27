import math
import wave

from src.Dubla_Voicegen.Dubla_Voice_Common import fit_to_slot, probe_duration


def make_wav(path, seconds: float, rate: int = 24000):
    frames = int(seconds * rate)
    with wave.open(str(path), "wb") as handle:
        handle.setnchannels(1)
        handle.setsampwidth(2)
        handle.setframerate(rate)
        samples = bytearray()
        for index in range(frames):
            value = int(12000 * math.sin(2 * math.pi * 220 * index / rate))
            samples += value.to_bytes(2, "little", signed=True)
        handle.writeframes(bytes(samples))


def test_fit_speeds_up_within_cap(tmp_path):
    wav = tmp_path / "voice.wav"
    make_wav(wav, 1.2)

    duration, speed, fits, overflow = fit_to_slot(wav, target=1.0, max_speed=1.35)
    assert fits is True
    assert overflow is False
    assert speed == 1.2
    assert abs(duration - 1.0) < 0.05
    assert abs(probe_duration(wav) - 1.0) < 0.05


def test_fit_marks_overflow_above_cap(tmp_path):
    wav = tmp_path / "voice.wav"
    make_wav(wav, 2.0)

    duration, speed, fits, overflow = fit_to_slot(wav, target=1.0, max_speed=1.35)
    assert fits is False
    assert overflow is True
    assert speed == 1.0
    assert duration == 2.0
