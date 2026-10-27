"""Shared helpers for the translation engines.

Reads the speech blocks from the project json (`stt.segments`), asks the selected
engine for the translations, writes `segments_traduct` plus a `translation`
metadata block and keeps everything else untouched.
"""

import json
import shutil
from datetime import datetime
from pathlib import Path

from etc.Logger import log_error, log_info, log_ok, log_warning
from src.Dubla_Config import (
    INPUT_LANGUAGE,
    OUTPUT_LANGUAGE,
    TRANSLATION_BATCH_SIZE,
    TRANSLATION_CLEANUP_ON_ERROR,
    TempPath,
)
from src.Dubla_Transcribe.Dubla_Stt_Common import load_meta, normalize_language, save_meta

# Engines that usually prepend a sentence instead of returning only the translation
EXPLANATION_PREFIXES = (
    "here is",
    "here's",
    "here are",
    "translation:",
    "tradução:",
    "traducao:",
    "sure,",
    "claro,",
    "aqui está",
    "aqui esta",
)


class TranslationError(RuntimeError):
    """Raised when an engine cannot produce a valid set of translations."""


def chunked(items: list, size: int):
    """Yield the list in chunks of at most `size` items."""
    size = max(1, int(size))
    for index in range(0, len(items), size):
        yield items[index:index + size]


def looks_like_explanation(text: str) -> bool:
    return text.strip().lower().startswith(EXPLANATION_PREFIXES)


def source_language(meta: dict) -> str | None:
    """Language actually spoken in the audio (from STT), falling back to the config."""
    stt = meta.get("stt") or {}
    detected = normalize_language(stt.get("language") or stt.get("language_detected"))
    if detected and detected != "auto":
        return detected
    return normalize_language(INPUT_LANGUAGE)


def target_language() -> str | None:
    return normalize_language(OUTPUT_LANGUAGE)


def cleanup_workdir(meta_path: Path) -> None:
    """Remove Data/temp/<id> after a failed translation (never outside TempPath)."""
    folder = meta_path.resolve().parent
    temp_root = TempPath.resolve()
    try:
        folder.relative_to(temp_root)
    except ValueError:
        log_warning(f"Not removing folder outside the temp path: {folder}")
        return
    if folder == temp_root:
        return
    shutil.rmtree(folder, ignore_errors=True)
    log_warning(f"Working folder removed after failure: {folder}")


class BaseTranslator:
    """Common pipeline: validate json, batch texts, validate output, save atomically."""

    engine = ""
    default_model = ""

    def __init__(
        self,
        meta_path,
        *,
        source: str | None = None,
        target: str | None = None,
        force: bool = False,
        batch_size: int | None = None,
    ):
        path = Path(meta_path).expanduser()
        self.meta_path = path if path.suffix == ".json" else path.with_suffix(".json")
        self.meta_path = self.meta_path.resolve()
        self.source_override = source
        self.target_override = target
        self.force = force
        self.batch_size = batch_size or TRANSLATION_BATCH_SIZE
        self.model_name = self.default_model
        self.meta: dict = {}
        self.source: str | None = None
        self.target: str | None = None

    # -- hooks ------------------------------------------------------------- #
    def translate_texts(self, texts: list[str]) -> list[str]:
        raise NotImplementedError

    # -- pipeline ---------------------------------------------------------- #
    def run(self) -> Path | None:
        """Translate every speech block and store `segments_traduct` in the json."""
        if not self.meta_path.is_file():
            log_error(f"Metadata not found: {self.meta_path}")
            return None

        try:
            self.meta = load_meta(self.meta_path)
        except (OSError, json.JSONDecodeError) as e:
            log_error(f"Error reading {self.meta_path}: {e}")
            return None

        stt = self.meta.get("stt") or {}
        segments = stt.get("segments") or []
        if not segments:
            log_error(f"No stt.segments to translate (run Dubla_Transcribe first): {self.meta_path}")
            return None

        self.source = normalize_language(self.source_override) if self.source_override else source_language(self.meta)
        self.target = normalize_language(self.target_override) if self.target_override else target_language()

        if not self.source or not self.target:
            log_error(f"Invalid language pair: source={self.source!r} target={self.target!r}")
            self._cleanup()
            return None
        if self.source == self.target:
            log_warning(f"Source and target are the same language ({self.source}); nothing to translate")
            return None

        if not self.force and self._is_done(stt):
            log_info(f"Already translated with {self.engine}/{self.model_name}: {self.meta_path}")
            return self.meta_path

        try:
            originals = [str(segment.get("text") or "") for segment in segments]
            indexes = [i for i, text in enumerate(originals) if text.strip()]
            payload = [originals[i] for i in indexes]

            log_info(f"{self.engine} / {self.model_name} | {self.source} -> {self.target} | {len(payload)} blocks")
            translated_payload = self.translate_texts(payload)
            if translated_payload is None:
                raise TranslationError("engine returned no result")
            if len(translated_payload) != len(payload):
                raise TranslationError(
                    f"expected {len(payload)} translations, got {len(translated_payload)}"
                )

            translated = [""] * len(originals)
            for index, text in zip(indexes, translated_payload):
                clean = str(text or "").strip()
                if not clean:
                    raise TranslationError(f"empty translation for block {index}")
                if looks_like_explanation(clean):
                    raise TranslationError(f"engine added an explanation to block {index}")
                translated[index] = clean

            self._save(stt, segments, translated)
        except Exception as e:
            log_error(f"Translation failed ({self.engine}): {e}")
            self._cleanup()
            return None

        log_ok(f"segments_traduct saved to {self.meta_path}")
        return self.meta_path

    def _cleanup(self) -> None:
        if TRANSLATION_CLEANUP_ON_ERROR:
            cleanup_workdir(self.meta_path)

    def _is_done(self, stt: dict) -> bool:
        current = self.meta.get("translation") or {}
        blocks = self.meta.get("segments_traduct") or []
        if not blocks:
            return False
        if current.get("engine") != self.engine or current.get("model") != self.model_name:
            return False
        if current.get("source") != self.source or current.get("target") != self.target:
            return False
        return current.get("stt_created_at") == stt.get("created_at")

    def _save(self, stt: dict, segments: list[dict], translated: list[str]) -> None:
        self.meta["segments_traduct"] = [
            {
                "start": segment.get("start"),
                "end": segment.get("end"),
                "text": translated[index],
                "text_original": segment.get("text"),
            }
            for index, segment in enumerate(segments)
        ]
        self.meta["translation"] = {
            "engine": self.engine,
            "model": self.model_name,
            "source": self.source,
            "target": self.target,
            "target_tag": OUTPUT_LANGUAGE,
            "segments_count": len(segments),
            "stt_created_at": stt.get("created_at"),
            "created_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        }
        save_meta(self.meta_path, self.meta)
