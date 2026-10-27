"""Dubla translation: deep-translator, Argos Translate and any OpenAI-compatible LLM.

Usage:
    from src.Dubla_Translate import translate

    translate("Data/temp/<id>/<id>.json")                       # engine from configs.json
    translate(meta, engine="llm")                               # force an engine
    translate(meta, engine="argos", source="en", target="pt")
"""

from pathlib import Path

from etc.Logger import log_error
from src.Dubla_Config import TRANSLATION_ENGINE
from src.Dubla_Translate.Dubla_Argo_Translate import ArgoTranslate
from src.Dubla_Translate.Dubla_Deep_Translator import DeepTranslator
from src.Dubla_Translate.Dubla_Llm_Translate import LlmTranslate

__all__ = ["translate", "DeepTranslator", "ArgoTranslate", "LlmTranslate", "ENGINES"]

ENGINES = {
    "deep-translator": DeepTranslator,
    "argos": ArgoTranslate,
    "llm": LlmTranslate,
}

ENGINE_ALIASES = {
    "deep_translator": "deep-translator",
    "deepl-translator": "deep-translator",
    "google": "deep-translator",
    "mymemory": "deep-translator",
    "deep": "deep-translator",
    "argostranslate": "argos",
    "argos-translate": "argos",
    "offline": "argos",
    "openai": "llm",
    "openai-like": "llm",
    "openai-compatible": "llm",
}


def translate(
    meta_path: str | Path,
    engine: str | None = None,
    source: str | None = None,
    target: str | None = None,
    force: bool = False,
    batch_size: int | None = None,
) -> Path | None:
    """Translate the `stt.segments` of a project json into `segments_traduct`.

    Args:
        meta_path: path to Data/temp/<id>/<id>.json (a .wav path is accepted too).
        engine: "deep-translator" (default), "argos" or "llm".
        source: source language override; defaults to stt.language, then input_language.
        target: target language override; defaults to output_language.
        force: translate again even if a valid translation already exists.
        batch_size: blocks per request for the batch capable engines
            (defaults to translation_batch_size).

    Returns:
        Path of the json, or None on failure. On failure Data/temp/<id> may be
        removed, depending on translation_cleanup_on_error.
    """
    chosen = (engine or TRANSLATION_ENGINE or "deep-translator").strip().lower()
    chosen = ENGINE_ALIASES.get(chosen, chosen)

    if chosen not in ENGINES:
        log_error(f"Unknown translation engine: {chosen}")
        return None

    if batch_size is not None and batch_size < 1:
        log_error(f"Invalid batch_size: {batch_size}")
        return None

    translator = ENGINES[chosen](
        meta_path,
        source=source,
        target=target,
        force=force,
        batch_size=batch_size,
    )
    return translator.run()
