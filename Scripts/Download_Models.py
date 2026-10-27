"""Download and validate the STT models (Vosk and faster-whisper).

Examples:
    python Scripts/Download_Models.py --list
    python Scripts/Download_Models.py --language en-US
    python Scripts/Download_Models.py --language pt-BR --engine whisper --model small
    python Scripts/Download_Models.py --all
"""

import argparse
import shutil
import sys
from pathlib import Path

__root__ = Path(__file__).parent.parent
if str(__root__) not in sys.path:
    sys.path.insert(0, str(__root__))

from src.Dubla_Config import (  # noqa: E402
    INPUT_LANGUAGE,
    STT_VOSK_MODEL,
    STT_WHISPER_MODEL,
    VoskModelPath,
    WhisperModelPath,
)
from src.Dubla_Transcribe.Dubla_Stt_Common import (  # noqa: E402
    VOSK_MODELS,
    WHISPER_SIZES,
    default_whisper_size,
    detect_hardware,
    ensure_vosk_model,
    ensure_whisper_model,
    normalize_language,
    pick_engine,
    vosk_model_name,
    whisper_size,
)
from etc.Logger import log_error, log_info, log_ok, log_warning  # noqa: E402


def list_models() -> None:
    hw = detect_hardware()
    log_info(f"Hardware: {hw.describe()}")
    log_info(f"Default whisper model for this hardware: {default_whisper_size(hw)}")
    log_info(f"Vosk ({VoskModelPath}):")
    for lang, models in sorted(VOSK_MODELS.items()):
        tiers = ", ".join(f"{tier}={name} ({size} MB)" for tier, (name, size) in models.items())
        log_info(f"  {lang}: {tiers}")

    log_info(f"Whisper ({WhisperModelPath}): {', '.join(WHISPER_SIZES)}")


def download_language(language: str, engine: str, model: str, force: bool) -> bool:
    lang = normalize_language(language)
    chosen = engine if engine != "auto" else pick_engine(lang)
    log_info(f"=== {language} (base code: {lang}) -> engine {chosen}")

    if chosen == "vosk":
        name = vosk_model_name(lang, model or STT_VOSK_MODEL)
        if name is None:
            log_warning(f"no Vosk model for {lang}; downloading whisper instead")
            chosen = "whisper"
        else:
            path = VoskModelPath / name
            if force and path.exists():
                shutil.rmtree(path)
            ok = ensure_vosk_model(lang, model or STT_VOSK_MODEL) is not None
            (log_ok if ok else log_error)(f"vosk: {'ok' if ok else 'failed'} ({name})")
            return ok

    size = whisper_size(model or STT_WHISPER_MODEL)
    if force and (WhisperModelPath / size).exists():
        shutil.rmtree(WhisperModelPath / size)
    ok = ensure_whisper_model(model or STT_WHISPER_MODEL) is not None
    (log_ok if ok else log_error)(f"whisper: {'ok' if ok else 'failed'} ({size})")
    return ok


def main() -> int:
    parser = argparse.ArgumentParser(description="Download STT models for Dubla")
    parser.add_argument("--list", action="store_true", help="list available languages and models")
    parser.add_argument("--language", action="append", help="input language (e.g. pt-BR); defaults to input_language")
    parser.add_argument("--all", action="store_true", help="download every language that has a small Vosk model")
    parser.add_argument("--engine", choices=("auto", "vosk", "whisper"), default="auto")
    parser.add_argument("--model", default="auto", help="Vosk tier (small/large) or whisper size")
    parser.add_argument("--force", action="store_true", help="delete and download again")
    args = parser.parse_args()

    if args.list:
        list_models()
        return 0

    if args.all:
        languages = sorted(VOSK_MODELS)
    elif args.language:
        languages = args.language
    else:
        languages = [INPUT_LANGUAGE]

    results = [
        download_language(lang, args.engine, args.model, args.force)
        for lang in languages
    ]
    return 0 if all(results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
