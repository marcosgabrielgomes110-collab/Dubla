"""Download and validate voice models (Piper voices, Pocket TTS, Qwen3-TTS).

Examples:
    python Scripts/Setup_Voices.py --list
    python Scripts/Setup_Voices.py --engine piper --language pt-BR
    python Scripts/Setup_Voices.py --engine pocket --language pt-BR
    python Scripts/Setup_Voices.py --engine qwen          # 2.5 GB model
"""

import argparse
import subprocess
import sys
from pathlib import Path

__root__ = Path(__file__).parent.parent
if str(__root__) not in sys.path:
    sys.path.insert(0, str(__root__))

from etc.Logger import log_error, log_info, log_ok, log_warning  # noqa: E402
from src.Dubla_Config import OUTPUT_LANGUAGE, VOICES, voice_setting  # noqa: E402
from src.Dubla_Transcribe.Dubla_Stt_Common import normalize_language  # noqa: E402
from src.Dubla_Voicegen.Dubla_Voice_Common import voice_dir  # noqa: E402


def list_voices() -> None:
    non_language_keys = {"path", "model", "rate", "output_format", "dtype"}
    for engine, values in VOICES.items():
        log_info(f"{engine}:")
        for key, value in values.items():
            if key in non_language_keys:
                continue
            extra = ""
            if engine == "piper":
                model = voice_dir("piper") / f"{value}.onnx"
                extra = " [downloaded]" if model.is_file() else " [missing]"
            log_info(f"  {key}: {value}{extra}")


def setup_piper(languages: list[str]) -> bool:
    ok = True
    directory = voice_dir("piper")
    directory.mkdir(parents=True, exist_ok=True)
    for language in languages:
        voice = voice_setting("piper", language)
        if not voice:
            log_warning(f"piper: no voice configured for {language}")
            ok = False
            continue
        model = directory / f"{voice}.onnx"
        if model.is_file():
            log_ok(f"piper {language}: {voice} (already downloaded)")
            continue
        log_info(f"piper {language}: downloading {voice}")
        try:
            subprocess.run(
                [
                    sys.executable, "-m", "piper.download_voices", voice,
                    "--download-dir", str(directory),
                ],
                check=True,
            )
            log_ok(f"piper {language}: {voice}")
        except subprocess.CalledProcessError as e:
            log_error(f"piper {language}: download failed ({e})")
            ok = False
    return ok


def setup_pocket(languages: list[str]) -> bool:
    try:
        from pocket_tts import TTSModel
    except ImportError:
        log_error("pocket-tts is not installed: pip install pocket-tts")
        return False

    from src.Dubla_Voicegen.Dubla_Voice_pocket import LANGUAGE_MODELS

    ok = True
    for language in languages:
        voice = voice_setting("pocket", language)
        model_language = LANGUAGE_MODELS.get(language)
        if not voice or not model_language:
            log_warning(f"pocket: no model/voice configured for {language}")
            ok = False
            continue
        try:
            model = TTSModel.load_model(language=model_language)
            model.get_state_for_audio_prompt(voice)
            log_ok(f"pocket {language}: {model_language} / {voice}")
        except Exception as e:
            log_error(f"pocket {language}: {e}")
            ok = False
    return ok


def setup_qwen() -> bool:
    model_id = voice_setting("qwen", "model")
    if not model_id:
        log_error("voices.qwen.model is not set in configs.json")
        return False
    try:
        from huggingface_hub import snapshot_download
    except ImportError:
        log_error("huggingface_hub is not installed")
        return False

    destination = voice_dir("qwen")
    destination.mkdir(parents=True, exist_ok=True)
    log_info(f"qwen: downloading {model_id} (~2.5 GB) to {destination}")
    try:
        snapshot_download(repo_id=model_id, local_dir=str(destination))
        log_ok(f"qwen: {model_id}")
        return True
    except Exception as e:
        log_error(f"qwen: download failed ({e})")
        return False


def main() -> int:
    parser = argparse.ArgumentParser(description="Download and validate Dubla voice models")
    parser.add_argument("--list", action="store_true", help="list configured voices")
    parser.add_argument("--engine", choices=("piper", "pocket", "qwen", "all"), default="all")
    parser.add_argument("--language", action="append", help="language code (default: output_language)")
    args = parser.parse_args()

    if args.list:
        list_voices()
        return 0

    languages = [normalize_language(item) for item in (args.language or [OUTPUT_LANGUAGE])]

    results = []
    if args.engine in ("piper", "all"):
        results.append(setup_piper(languages))
    if args.engine in ("pocket", "all"):
        results.append(setup_pocket(languages))
    if args.engine == "qwen":
        results.append(setup_qwen())

    return 0 if all(results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
