"""Dubla speech-to-text: Vosk and faster-whisper.

Usage:
    from src.Dubla_Transcribe import transcribe, VoskStt, WhisperStt

    transcribe("Data/temp/<id>/<id>.wav")   # engine chosen from config/hardware
    VoskStt(wav).run()                      # force Vosk
    WhisperStt(wav, language="auto").run()  # force Whisper
"""

from pathlib import Path

from etc.Logger import log_error, log_info
from src.Dubla_Config import INPUT_LANGUAGE, STT_ENGINE
from src.Dubla_Transcribe.Dubla_Stt_Common import detect_hardware, normalize_language, pick_engine
from src.Dubla_Transcribe.Dubla_Stt_vosk import VoskStt
from src.Dubla_Transcribe.Dubla_Stt_whisper import WhisperStt

__all__ = ["transcribe", "VoskStt", "WhisperStt"]

ENGINES = {"vosk": VoskStt, "whisper": WhisperStt}
ENGINE_ALIASES = {"faster-whisper": "whisper", "faster_whisper": "whisper", "whisper-ct2": "whisper"}


def transcribe(
    wav_path: str | Path,
    engine: str | None = None,
    language: str | None = None,
    model: str | None = None,
    force: bool = False,
) -> Path | None:
    """Transcribe a 16 kHz mono wav and store the speech blocks in the sibling <id>.json.

    Args:
        wav_path: audio produced by Dubla_Input (Data/temp/<id>/<id>.wav).
        engine: "auto" (config + hardware), "vosk" or "whisper".
        language: input language/locale; defaults to configs.json input_language.
            "auto" is only supported by whisper (Vosk cannot detect a language).
        model: Vosk tier/name ("small", "large", "vosk-model-...") or whisper size
            ("tiny", "base", "small", "medium", "large-v3").
        force: transcribe again even if the json already has a valid stt block.

    Returns:
        Path of the json holding the transcription, or None on failure.
    """
    lang = normalize_language(INPUT_LANGUAGE if language is None else language)
    chosen = (engine or STT_ENGINE or "auto").strip().lower()
    chosen = ENGINE_ALIASES.get(chosen, chosen)

    if chosen == "auto":
        chosen = pick_engine(lang)
        log_info(f"engine auto -> {chosen} (language={lang or 'auto'}, {detect_hardware().describe()})")

    if chosen not in ENGINES:
        log_error(f"Unknown STT engine: {chosen}")
        return None

    return ENGINES[chosen](wav_path, language=lang, model=model, force=force).run()
