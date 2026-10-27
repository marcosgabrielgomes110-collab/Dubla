"""Dubla voice generation: Piper, Pocket TTS, Qwen3-TTS, ElevenLabs and eSpeak NG.

Engines can run serially (default) or with a thread pool (`voice_parallel`).
Local models are serialized with a lock; API/CLI engines run concurrently.

Usage:
    from src.Dubla_Voicegen import synthesize

    synthesize("Data/temp/<id>/<id>.json")                # engine from configs.json
    synthesize(meta, engine="piper")                      # force an engine
    synthesize(meta, engine="espeak", voice="pt-br", force=True)
"""

from pathlib import Path

from etc.Logger import log_error
from src.Dubla_Config import VOICE_ENGINE
from src.Dubla_Voicegen.Dubla_Voice_elevenlabs import ElevenLabsVoiceGen
from src.Dubla_Voicegen.Dubla_Voice_espeak import EspeakVoiceGen
from src.Dubla_Voicegen.Dubla_Voice_piper import PiperVoiceGen
from src.Dubla_Voicegen.Dubla_Voice_pocket import PocketVoiceGen
from src.Dubla_Voicegen.Dubla_Voice_qwen import QwenVoiceGen

__all__ = [
    "synthesize",
    "PiperVoiceGen",
    "PocketVoiceGen",
    "QwenVoiceGen",
    "ElevenLabsVoiceGen",
    "EspeakVoiceGen",
    "ENGINES",
]

ENGINES = {
    "piper": PiperVoiceGen,
    "pocket": PocketVoiceGen,
    "qwen": QwenVoiceGen,
    "elevenlabs": ElevenLabsVoiceGen,
    "espeak": EspeakVoiceGen,
}

ENGINE_ALIASES = {
    "pocket-tts": "pocket",
    "pocket_tts": "pocket",
    "qwen3-tts": "qwen",
    "qwen3_tts": "qwen",
    "eleven": "elevenlabs",
    "eleven-labs": "elevenlabs",
    "espeak-ng": "espeak",
    "espeak_ng": "espeak",
    "robot": "espeak",
}


def synthesize(
    meta_path: str | Path,
    engine: str | None = None,
    language: str | None = None,
    voice: str | None = None,
    force: bool = False,
) -> Path | None:
    """Generate one audio file per translated block and store the `voice` block.

    Args:
        meta_path: path to Data/temp/<id>/<id>.json (a .wav path is accepted too).
        engine: "piper" (default), "pocket", "qwen", "elevenlabs" or "espeak".
        language: voice language override; defaults to output_language.
        voice: engine specific voice/speaker id; defaults to voices.<engine>.<language>.
        force: synthesize again even if a valid voice block already exists.

    Returns:
        Path of the json, or None on failure.
    """
    chosen = (engine or VOICE_ENGINE or "piper").strip().lower()
    chosen = ENGINE_ALIASES.get(chosen, chosen)

    if chosen not in ENGINES:
        log_error(f"Unknown voice engine: {chosen}")
        return None

    generator = ENGINES[chosen](
        meta_path,
        language=language,
        voice=voice,
        force=force,
    )
    return generator.run()
