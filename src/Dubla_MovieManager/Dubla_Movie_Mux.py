"""Build the dubbed audio track and mux it with the muted video."""

import math
import subprocess
import wave
from datetime import datetime
from pathlib import Path

import numpy as np

from etc.Logger import log_error, log_info, log_ok, log_warning
from src.Dubla_Config import (
    MUX_AUDIO_BITRATE,
    MUX_AUDIO_CHANNELS,
    MUX_AUDIO_SAMPLE_RATE,
    MUX_LOUDNORM,
    MUX_OVERLAP,
    MUX_VIDEO_CODEC,
    OUTPUT_LANGUAGE,
    VOICE_SAMPLE_RATE,
)
from src.Dubla_Transcribe.Dubla_Stt_Common import load_meta, normalize_language, save_meta

FADE_SECONDS = 0.01


def _probe_duration(path: Path) -> float:
    result = subprocess.run(
        [
            "ffprobe", "-v", "error",
            "-show_entries", "format=duration",
            "-of", "default=nw=1:nk=1",
            str(path),
        ],
        capture_output=True,
        text=True,
        check=True,
    )
    return float(result.stdout.strip() or 0.0)


def _read_wav(path: Path) -> np.ndarray:
    """Read a voice block as float32 mono at the voice sample rate."""
    with wave.open(str(path), "rb") as wav_file:
        channels = wav_file.getnchannels()
        width = wav_file.getsampwidth()
        rate = wav_file.getframerate()
        frames = wav_file.readframes(wav_file.getnframes())

    if channels == 1 and width == 2 and rate == VOICE_SAMPLE_RATE:
        return np.frombuffer(frames, dtype=np.int16).astype(np.float32) / 32768.0

    # Unexpected format: normalize with ffmpeg first
    normalized = path.with_name(path.stem + ".mux.wav")
    subprocess.run(
        [
            "ffmpeg", "-y", "-loglevel", "error",
            "-i", str(path),
            "-ac", "1", "-ar", str(VOICE_SAMPLE_RATE), "-c:a", "pcm_s16le",
            str(normalized),
        ],
        check=True,
    )
    try:
        with wave.open(str(normalized), "rb") as wav_file:
            frames = wav_file.readframes(wav_file.getnframes())
        return np.frombuffer(frames, dtype=np.int16).astype(np.float32) / 32768.0
    finally:
        normalized.unlink(missing_ok=True)


def _fade(samples: np.ndarray) -> np.ndarray:
    length = min(len(samples), max(1, int(FADE_SECONDS * VOICE_SAMPLE_RATE)))
    if length <= 1 or len(samples) <= 2 * length:
        return samples
    ramp = np.linspace(0.0, 1.0, length, dtype=np.float32)
    samples[:length] *= ramp
    samples[-length:] *= ramp[::-1]
    return samples


def _build_dub(meta: dict, out_wav: Path) -> int:
    """Place every voice block on a silent timeline. Returns the overlap count."""
    voice = meta.get("voice") or {}
    segments = sorted(voice.get("segments") or [], key=lambda item: float(item.get("start") or 0.0))
    if not segments:
        raise ValueError("voice.segments is empty (run the voice step first)")

    duration = float(meta.get("duration") or 0.0)
    if duration <= 0:
        duration = _probe_duration(Path(meta["video_path"]))

    total = int(math.ceil(duration * VOICE_SAMPLE_RATE)) + VOICE_SAMPLE_RATE // 2
    buffer = np.zeros(total, dtype=np.float32)
    placed: list[tuple[int, int]] = []
    overlaps = 0

    for segment in segments:
        path = Path(segment.get("path") or "")
        if not path.is_file():
            log_warning(f"voice file missing, skipping block {segment.get('index')}: {path}")
            continue

        samples = _read_wav(path)
        if samples.size == 0:
            continue
        samples = _fade(samples.copy())

        start = max(0, int(round(float(segment.get("start") or 0.0) * VOICE_SAMPLE_RATE)))
        end = start + len(samples)
        if end > len(buffer):
            buffer = np.pad(buffer, (0, end - len(buffer)))

        for other_start, other_end in placed:
            if start < other_end and end > other_start:
                overlaps += 1
                break

        buffer[start:end] += samples
        placed.append((start, end))

    peak = float(np.abs(buffer).max()) if buffer.size else 0.0
    if peak > 1.0:
        log_warning(f"audio peak at {peak:.2f}; a limiter will handle it during mux")

    # Float WAV keeps the >1.0 peaks so ffmpeg's limiter can act on them
    import scipy.io.wavfile

    scipy.io.wavfile.write(str(out_wav), VOICE_SAMPLE_RATE, buffer.astype(np.float32))

    return overlaps


def mux_video(meta_path, force: bool = False) -> Path | None:
    """Create <id>_dublado.mp4 in the working folder (video copied, new audio)."""
    path = Path(meta_path).expanduser()
    meta_path = (path if path.suffix == ".json" else path.with_suffix(".json")).resolve()
    if not meta_path.is_file():
        log_error(f"Metadata not found: {meta_path}")
        return None

    try:
        meta = load_meta(meta_path)
    except Exception as e:
        log_error(f"Error reading {meta_path}: {e}")
        return None

    video = Path(meta.get("video_path") or "")
    if not video.is_file():
        log_error(f"Muted video not found: {video}")
        return None

    voice = meta.get("voice") or {}
    if not voice.get("segments"):
        log_error("No voice.segments to mux (run the voice step first)")
        return None

    work = meta_path.parent
    output = work / f"{meta_path.stem}_dublado.mp4"
    movie = meta.get("movie") or {}

    if not force and movie.get("mux_created_at") == voice.get("created_at") and output.is_file():
        log_info(f"Already muxed: {output}")
        return output

    if MUX_OVERLAP != "mix":
        log_warning(f"mux_overlap={MUX_OVERLAP!r} is not implemented; using 'mix'")

    dub = work / "dub.wav"
    log_info(f"building dubbed track: {len(voice['segments'])} blocks")
    try:
        overlaps = _build_dub(meta, dub)
    except Exception as e:
        log_error(f"Could not build the dubbed track: {e}")
        return None

    cmd = [
        "ffmpeg", "-y", "-loglevel", "error",
        "-i", str(video),
        "-i", str(dub),
        "-map", "0:v:0",
        "-map", "1:a:0",
        "-c:a", "aac",
        "-b:a", MUX_AUDIO_BITRATE,
        "-ar", str(MUX_AUDIO_SAMPLE_RATE),
        "-ac", str(MUX_AUDIO_CHANNELS),
        "-shortest",
        "-movflags", "+faststart",
    ]
    if MUX_VIDEO_CODEC == "copy":
        cmd += ["-c:v", "copy"]
    else:
        cmd += ["-c:v", "libx264", "-preset", "medium", "-crf", "20"]

    filters = []
    if MUX_LOUDNORM:
        filters.append("loudnorm=I=-16:TP=-1.5:LRA=11")
    filters.append("alimiter=limit=0.95")
    cmd += ["-af", ",".join(filters)]

    language = normalize_language(OUTPUT_LANGUAGE)
    if language and len(language) == 2:
        cmd += ["-metadata:s:a:0", f"language={language}"]
    cmd.append(str(output))

    try:
        subprocess.run(cmd, check=True)
    except subprocess.CalledProcessError as e:
        log_error(f"ffmpeg mux failed: {e}")
        output.unlink(missing_ok=True)
        return None

    meta["movie"] = {
        "muxed_path": str(output),
        "overlaps": overlaps,
        "audio_sample_rate": VOICE_SAMPLE_RATE,
        "video_codec": MUX_VIDEO_CODEC,
        "mux_created_at": datetime.now().astimezone().isoformat(timespec="seconds"),
    }
    save_meta(meta_path, meta)

    if overlaps:
        log_warning(f"{overlaps} block(s) overlap the next one")
    log_ok(f"muxed video: {output}")
    return output
