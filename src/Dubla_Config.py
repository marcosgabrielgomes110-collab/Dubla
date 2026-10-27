import json
from pathlib import Path

from etc.Logger import log_error

# Absolute path to project root regardless of execution directory
CONFIG_PATH = Path(__file__).resolve().parent.parent / "configs.json"
ROOT = CONFIG_PATH.parent


def get_config(key: str, default=None):
    """Retrieve a configuration value from configs.json."""
    try:
        with open(CONFIG_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
            if isinstance(data, list) and len(data) > 0:
                data = data[0]
            value = data.get(key)
            return default if value is None else value
    except Exception as e:
        log_error(f"Error opening config.json: {e}")
        return default


# Download pipeline
Quality = get_config("quality_ytdlp")
# Resolve configured paths against the project root so they do not depend on the cwd
TempPath = ROOT / get_config("temp_path")
OutputPath = ROOT / get_config("output_path")

# Speech-to-text
INPUT_LANGUAGE = str(get_config("input_language", "en-US"))
OUTPUT_LANGUAGE = str(get_config("output_language", "pt-BR"))
STT_ENGINE = str(get_config("stt_engine", "auto"))
STT_VOSK_MODEL = str(get_config("stt_vosk_model", "auto"))
STT_WHISPER_MODEL = str(get_config("stt_whisper_model", "auto"))
STT_WHISPER_DEVICE = str(get_config("stt_whisper_device", "auto"))
STT_WHISPER_COMPUTE = str(get_config("stt_whisper_compute", "auto"))
STT_MIN_PAUSE = float(get_config("stt_min_pause", 0.35))
STT_MIN_SEGMENT = float(get_config("stt_min_segment", 0.4))
STT_MAX_SEGMENT = float(get_config("stt_max_segment", 12.0))
STT_OFFLINE = bool(get_config("stt_offline", False))

VoskModelPath = ROOT / get_config("Vosk_model_path", "Models/vosk")
WhisperModelPath = ROOT / get_config("Whisper_model_path", "Models/whisper")

# Translation
TRANSLATION_ENGINE = str(get_config("translation_engine", "deep-translator"))
DEEP_TRANSLATOR_BACKEND = str(get_config("deep_translator_backend", "mymemory"))
TRANSLATION_BATCH_SIZE = int(get_config("translation_batch_size", 20))
TRANSLATION_RETRIES = int(get_config("translation_retries", 3))
TRANSLATION_DELAY = float(get_config("translation_delay", 0.0))
TRANSLATION_CLEANUP_ON_ERROR = bool(get_config("translation_cleanup_on_error", True))
ENV_PATH = ROOT / ".env"
LLM_TIMEOUT = float(get_config("llm_timeout", 60))
LLM_MAX_RETRIES = int(get_config("llm_max_retries", 2))
