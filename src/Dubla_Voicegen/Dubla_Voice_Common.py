"""Shared helpers for the voice engines.

Reads `segments_traduct`, synthesizes one file per block into `Data/temp/<id>/voice/`,
normalizes everything to WAV PCM (mono, 24 kHz), fits the audio into the original
block duration and records the result in the `voice` block of the project json.
"""

import json
import subprocess
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from pathlib import Path

from etc.Logger import log_error, log_info, log_ok
from src.Dubla_Config import (
    OUTPUT_LANGUAGE,
    ROOT,
    VOICE_FIT_SPEEDUP_MAX,
    VOICE_PAD_SILENCE,
    VOICE_PARALLEL,
    VOICE_SAMPLE_RATE,
    VOICE_WORKERS,
    voice_setting,
)
from src.Dubla_Transcribe.Dubla_Stt_Common import load_meta, normalize_language, save_meta

ENGINES = ("piper", "pocket", "qwen", "elevenlabs", "espeak")


class VoiceError(RuntimeError):
    """Raised when an engine cannot synthesize a block."""


def voice_language_tag() -> str:
    return OUTPUT_LANGUAGE


def voice_language() -> str | None:
    return normalize_language(OUTPUT_LANGUAGE)


def resolve_voice(engine: str, language: str) -> str | None:
    """Voice configured for an engine/language in configs.json."""
    value = voice_setting(engine, language)
    return str(value) if value else None


def voice_dir(engine: str) -> Path:
    configured = voice_setting(engine, "path", f"Models/{engine}")
    return ROOT / configured


def probe_duration(path: Path) -> float:
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


def to_wav(src: Path, dest: Path) -> None:
    """Normalize any engine output to mono PCM at the configured sample rate."""
    subprocess.run(
        [
            "ffmpeg", "-y", "-loglevel", "error",
            "-i", str(src),
            "-ac", "1",
            "-ar", str(VOICE_SAMPLE_RATE),
            "-c:a", "pcm_s16le",
            str(dest),
        ],
        check=True,
    )


def write_silence(path: Path, duration: float) -> None:
    subprocess.run(
        [
            "ffmpeg", "-y", "-loglevel", "error",
            "-f", "lavfi",
            "-i", f"anullsrc=r={VOICE_SAMPLE_RATE}:cl=mono",
            "-t", f"{max(duration, 0.05):.3f}",
            "-c:a", "pcm_s16le",
            str(path),
        ],
        check=True,
    )


def fit_to_slot(path: Path, target: float, max_speed: float = VOICE_FIT_SPEEDUP_MAX):
    """Speed the audio up (up to max_speed) so it fits the slot; never cut it."""
    duration = probe_duration(path)
    speed = 1.0
    fits = True
    overflow = False

    if target <= 0:
        return duration, speed, False, False

    if duration > target + 0.01:
        speed = duration / target
        if speed <= max_speed + 1e-6:
            tmp = path.with_name(path.stem + ".fit.wav")
            subprocess.run(
                [
                    "ffmpeg", "-y", "-loglevel", "error",
                    "-i", str(path),
                    "-filter:a", f"atempo={speed:.4f}",
                    "-ac", "1",
                    "-ar", str(VOICE_SAMPLE_RATE),
                    "-c:a", "pcm_s16le",
                    str(tmp),
                ],
                check=True,
            )
            tmp.replace(path)
            duration = probe_duration(path)
            fits = duration <= target * 1.02
            if not fits:
                overflow = True
        else:
            # Too long to fix without sounding like a chipmunk
            speed = 1.0
            fits = False
            overflow = True
    elif VOICE_PAD_SILENCE and duration < target - 0.01:
        tmp = path.with_name(path.stem + ".pad.wav")
        subprocess.run(
            [
                "ffmpeg", "-y", "-loglevel", "error",
                "-i", str(path),
                "-filter:a", f"apad=whole_dur={target:.3f}",
                "-ac", "1",
                "-ar", str(VOICE_SAMPLE_RATE),
                "-c:a", "pcm_s16le",
                str(tmp),
            ],
            check=True,
        )
        tmp.replace(path)
        duration = probe_duration(path)

    return duration, round(speed, 3), fits, overflow


class BaseVoice:
    """Common pipeline: validate json, synthesize each block, fit and save."""

    engine = ""
    native_suffix = ".wav"
    # Local models are serialized with a lock; API/CLI engines can run concurrently
    thread_safe = False
    # Hard cap for engines with provider concurrency limits (None = use voice_workers)
    max_workers: int | None = None

    def __init__(
        self,
        meta_path,
        *,
        language: str | None = None,
        voice: str | None = None,
        force: bool = False,
    ):
        path = Path(meta_path).expanduser()
        self.meta_path = (path if path.suffix == ".json" else path.with_suffix(".json")).resolve()
        self.language_tag = language or voice_language_tag()
        self.language = normalize_language(self.language_tag)
        self.force = force
        self.voice = voice or (resolve_voice(self.engine, self.language or "") if self.language else None)
        self.meta: dict = {}
        self._lock = threading.Lock()

    # -- hooks ------------------------------------------------------------- #
    def prepare(self) -> bool:
        raise NotImplementedError

    def synthesize(self, text: str, out_path: Path) -> bool:
        raise NotImplementedError

    # -- pipeline ---------------------------------------------------------- #
    def run(self) -> Path | None:
        """Synthesize the translated blocks and store the `voice` block in the json."""
        if not self.meta_path.is_file():
            log_error(f"Metadata not found: {self.meta_path}")
            return None
        try:
            self.meta = load_meta(self.meta_path)
        except (OSError, json.JSONDecodeError) as e:
            log_error(f"Error reading {self.meta_path}: {e}")
            return None

        blocks = self.meta.get("segments_traduct") or []
        if not blocks:
            log_error(f"No segments_traduct to voice (run Dubla_Translate first): {self.meta_path}")
            return None
        if not self.language:
            log_error(f"Invalid voice language: {self.language_tag!r}")
            return None

        if not self.force and self._is_done():
            log_info(f"Already voiced with {self.engine}/{self.voice}: {self.meta_path}")
            return self.meta_path

        if not self.prepare():
            return None
        if not self.voice:
            log_error(f"No voice configured for {self.engine}/{self.language} (see voices in configs.json)")
            return None

        outdir = self.meta_path.parent / "voice"
        outdir.mkdir(parents=True, exist_ok=True)

        log_info(
            f"{self.engine} / {self.voice} | {self.language_tag} | {len(blocks)} blocks | "
            f"parallel={VOICE_PARALLEL} workers={VOICE_WORKERS}"
        )
        try:
            if VOICE_PARALLEL and VOICE_WORKERS > 1 and len(blocks) > 1:
                results = self._render_parallel(blocks, outdir)
            else:
                results = self._render_serial(blocks, outdir)
        except (VoiceError, subprocess.CalledProcessError, FileNotFoundError, OSError) as e:
            log_error(f"Voice generation failed ({self.engine}): {e}")
            return None

        self._save(results)
        overflow = sum(1 for item in results if item["overflow"])
        log_ok(f"voice saved to {self.meta_path} ({len(results)} blocks, {overflow} overflow)")
        return self.meta_path

    # -- block rendering ---------------------------------------------------- #
    def _render_block(self, index: int, block: dict, outdir: Path) -> dict:
        text = str(block.get("text") or "").strip()
        start = float(block.get("start") or 0.0)
        end = float(block.get("end") or start)
        target = max(0.0, end - start)
        out_path = outdir / f"{index:04d}.wav"

        if not text:
            write_silence(out_path, target)
        else:
            native = outdir / f"{index:04d}.native{self.native_suffix}"
            native.unlink(missing_ok=True)
            if self.thread_safe:
                ok = self.synthesize(text, native)
            else:
                with self._lock:
                    ok = self.synthesize(text, native)
            if not ok:
                raise VoiceError(f"engine failed on block {index}")
            to_wav(native, out_path)
            native.unlink(missing_ok=True)

        duration, speed, fits, overflow = fit_to_slot(out_path, target)
        return {
            "index": index,
            "start": round(start, 3),
            "end": round(end, 3),
            "path": str(out_path),
            "duration": round(duration, 3),
            "speed": speed,
            "fits": fits,
            "overflow": overflow,
        }

    def _render_serial(self, blocks: list[dict], outdir: Path) -> list[dict]:
        results: list[dict] = []
        for index, block in enumerate(blocks):
            results.append(self._render_block(index, block, outdir))
            if (index + 1) % 10 == 0:
                log_info(f"{self.engine}: {index + 1}/{len(blocks)} blocks")
        return results

    def _render_parallel(self, blocks: list[dict], outdir: Path) -> list[dict]:
        results: list[dict | None] = [None] * len(blocks)
        done = 0
        workers = min(VOICE_WORKERS, self.max_workers or VOICE_WORKERS)
        log_info(f"{self.engine}: using {workers} worker(s)")
        with ThreadPoolExecutor(max_workers=workers) as pool:
            futures = {
                pool.submit(self._render_block, index, block, outdir): index
                for index, block in enumerate(blocks)
            }
            try:
                for future in as_completed(futures):
                    index = futures[future]
                    results[index] = future.result()
                    done += 1
                    if done % 10 == 0:
                        log_info(f"{self.engine}: {done}/{len(blocks)} blocks")
            except Exception:
                for future in futures:
                    future.cancel()
                raise
        return [item for item in results if item is not None]

    def _is_done(self) -> bool:
        current = self.meta.get("voice") or {}
        blocks = current.get("segments") or []
        if not current or not blocks:
            return False
        if current.get("engine") != self.engine or current.get("voice") != self.voice:
            return False
        if normalize_language(current.get("language")) != self.language:
            return False
        if current.get("translation_created_at") != (self.meta.get("translation") or {}).get("created_at"):
            return False
        return all(Path(item.get("path", "")).is_file() for item in blocks)

    def _save(self, segments: list[dict]) -> None:
        self.meta["voice"] = {
            "engine": self.engine,
            "voice": self.voice,
            "language": self.language_tag,
            "sample_rate": VOICE_SAMPLE_RATE,
            "translation_created_at": (self.meta.get("translation") or {}).get("created_at"),
            "created_at": datetime.now().astimezone().isoformat(timespec="seconds"),
            "segments": segments,
        }
        save_meta(self.meta_path, self.meta)
