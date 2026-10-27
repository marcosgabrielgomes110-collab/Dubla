"""Configure and validate ElevenLabs (.env) for the "elevenlabs" voice engine.

Examples:
    python Scripts/Setup_ElevenLabs.py                  # create .env keys if missing
    python Scripts/Setup_ElevenLabs.py --list-voices    # list voice ids of the account
    python Scripts/Setup_ElevenLabs.py --ping           # synthesize a tiny sample
"""

import argparse
import shutil
import sys
from pathlib import Path

__root__ = Path(__file__).parent.parent
if str(__root__) not in sys.path:
    sys.path.insert(0, str(__root__))

from etc.Logger import log_error, log_info, log_ok, log_warning  # noqa: E402
from src.Dubla_Config import ENV_PATH, voice_setting  # noqa: E402

REQUIRED_KEYS = (
    "ELEVENLABS_API_KEY",
    "ELEVENLABS_MODEL",
    "ELEVENLABS_VOICE_ID_PT",
    "ELEVENLABS_VOICE_ID_EN",
    "ELEVENLABS_OUTPUT_FORMAT",
)


def mask(value: str) -> str:
    if not value:
        return "(empty)"
    if len(value) <= 8:
        return "***"
    return f"{value[:4]}...{value[-4:]}"


def ensure_env() -> None:
    if not ENV_PATH.exists():
        example = __root__ / ".env.example"
        if example.is_file():
            shutil.copy(example, ENV_PATH)
            log_ok(f".env created from .env.example: {ENV_PATH}")
        else:
            ENV_PATH.write_text("", encoding="utf-8")
            log_info(f".env created: {ENV_PATH}")

    text = ENV_PATH.read_text(encoding="utf-8")
    existing = {line.split("=", 1)[0].strip() for line in text.splitlines() if "=" in line and not line.strip().startswith("#")}
    defaults = {
        "ELEVENLABS_MODEL": voice_setting("elevenlabs", "model", "eleven_multilingual_v2"),
        "ELEVENLABS_OUTPUT_FORMAT": voice_setting("elevenlabs", "output_format", "mp3_44100_128"),
    }

    missing = [key for key in REQUIRED_KEYS if key not in existing]
    if not missing:
        log_info(f"all ElevenLabs keys present in {ENV_PATH}")
        return

    with ENV_PATH.open("a", encoding="utf-8") as handle:
        if text and not text.endswith("\n"):
            handle.write("\n")
        handle.write("\n# ElevenLabs voice engine\n")
        for key in missing:
            handle.write(f"{key}={defaults.get(key, '')}\n")
    log_ok(f"added missing keys to .env: {', '.join(missing)}")


def main() -> int:
    parser = argparse.ArgumentParser(description="Setup the ElevenLabs voice engine")
    parser.add_argument("--list-voices", action="store_true", help="list voice ids from the account")
    parser.add_argument("--ping", action="store_true", help="synthesize a tiny sample")
    args = parser.parse_args()

    ensure_env()

    try:
        from dotenv import load_dotenv
        import os
    except ImportError:
        log_error("python-dotenv is not installed: pip install python-dotenv")
        return 1

    load_dotenv(ENV_PATH, override=True)
    api_key = (os.getenv("ELEVENLABS_API_KEY") or "").strip()
    model_id = (os.getenv("ELEVENLABS_MODEL") or "").strip()
    output_format = (os.getenv("ELEVENLABS_OUTPUT_FORMAT") or "").strip()
    pt_voice = (os.getenv("ELEVENLABS_VOICE_ID_PT") or "").strip()
    en_voice = (os.getenv("ELEVENLABS_VOICE_ID_EN") or "").strip()

    log_info(f"model:        {model_id or '(empty)'}")
    log_info(f"output:       {output_format or '(empty)'}")
    log_info(f"api_key:      {mask(api_key)}")
    log_info(f"voice pt-BR:  {pt_voice or '(empty)'}")
    log_info(f"voice en-US:  {en_voice or '(empty)'}")

    if not api_key:
        log_error("ELEVENLABS_API_KEY is empty in .env")
        return 1

    try:
        from elevenlabs.client import ElevenLabs
    except ImportError:
        log_error("elevenlabs is not installed: pip install elevenlabs")
        return 1

    client = ElevenLabs(api_key=api_key)

    if args.list_voices:
        try:
            response = client.voices.search(page_size=100)
            for voice in response.voices:
                labels = voice.labels or {}
                language = labels.get("language") or labels.get("accent") or ""
                log_info(f"  {voice.voice_id} | {voice.name} | {voice.category or ''} | {language}")
            log_ok(f"{len(response.voices)} voices listed")
            library = [voice for voice in response.voices if voice.category == "professional"]
            if library:
                log_warning(
                    "library/professional voices need a paid plan through the API; "
                    "premade voices work on the free tier"
                )
        except Exception as e:
            log_error(f"could not list voices: {e}")
            return 1

    if args.ping:
        voice = pt_voice or en_voice
        if not voice:
            log_error("set ELEVENLABS_VOICE_ID_PT or ELEVENLABS_VOICE_ID_EN before --ping")
            return 1
        try:
            chunks = client.text_to_speech.convert(
                voice_id=voice,
                text="Teste de voz.",
                model_id=model_id or "eleven_multilingual_v2",
                output_format=output_format or "mp3_44100_128",
            )
            size = sum(len(chunk) for chunk in chunks)
            log_ok(f"ping ok ({size} bytes)")
        except Exception as e:
            log_error(f"ping failed: {e}")
            return 1

    if not args.list_voices and not args.ping:
        log_warning("edit .env with your voice ids, then run --list-voices / --ping")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
