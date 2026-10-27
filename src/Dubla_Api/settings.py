"""Settings endpoints: read, patch and validate configs.json atomically."""

import json
import shutil
from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from src.Dubla_Config import CONFIG_PATH

router = APIRouter(prefix="/settings", tags=["settings"])

BACKUP_PATH = CONFIG_PATH.with_suffix(".json.bak")

# key -> (type, options/range, description)
SCHEMA: dict[str, dict[str, Any]] = {
    "quality_ytdlp": {"type": "string", "description": "yt-dlp max height (e.g. 720)"},
    "temp_path": {"type": "string"},
    "output_path": {"type": "string"},
    "Vosk_model_path": {"type": "string"},
    "Whisper_model_path": {"type": "string"},
    "input_language": {"type": "string", "description": "locale, e.g. en-US"},
    "output_language": {"type": "string", "description": "locale, e.g. pt-BR"},
    "stt_engine": {"type": "enum", "options": ["auto", "vosk", "whisper"]},
    "stt_vosk_model": {"type": "string"},
    "stt_whisper_model": {
        "type": "enum",
        "options": ["auto", "tiny", "base", "small", "medium", "large-v3"],
    },
    "stt_whisper_device": {"type": "enum", "options": ["auto", "cpu", "cuda"]},
    "stt_whisper_compute": {
        "type": "enum",
        "options": ["auto", "int8", "float16", "int8_float16", "float32"],
    },
    "stt_min_pause": {"type": "number", "min": 0, "max": 10},
    "stt_min_segment": {"type": "number", "min": 0, "max": 10},
    "stt_max_segment": {"type": "number", "min": 1, "max": 120},
    "stt_offline": {"type": "boolean"},
    "translation_engine": {"type": "enum", "options": ["deep-translator", "argos", "llm"]},
    "deep_translator_backend": {"type": "enum", "options": ["mymemory", "google", "auto"]},
    "translation_batch_size": {"type": "integer", "min": 1, "max": 200},
    "translation_retries": {"type": "integer", "min": 0, "max": 10},
    "translation_delay": {"type": "number", "min": 0, "max": 60},
    "translation_cleanup_on_error": {"type": "boolean"},
    "llm_timeout": {"type": "number", "min": 1, "max": 600},
    "llm_max_retries": {"type": "integer", "min": 0, "max": 10},
    "voice_engine": {"type": "enum", "options": ["piper", "pocket", "qwen", "elevenlabs", "espeak"]},
    "voice_fit_speedup_max": {"type": "number", "min": 1, "max": 3},
    "voice_pad_silence": {"type": "boolean"},
    "voice_sample_rate": {"type": "integer", "min": 8000, "max": 48000},
    "voice_parallel": {"type": "boolean"},
    "voice_workers": {"type": "integer", "min": 1, "max": 16},
    "mux_overlap": {"type": "enum", "options": ["mix", "shift", "trim"]},
    "mux_video_codec": {"type": "enum", "options": ["copy", "h264"]},
    "mux_audio_bitrate": {"type": "string"},
    "mux_audio_sample_rate": {"type": "integer", "min": 8000, "max": 48000},
    "mux_audio_channels": {"type": "integer", "min": 1, "max": 2},
    "mux_loudnorm": {"type": "boolean"},
    "publish_overwrite": {"type": "boolean"},
    "voices": {"type": "object", "description": "per engine/language voice ids"},
}


class PatchRequest(BaseModel):
    values: dict[str, Any]


def load_config() -> dict:
    with open(CONFIG_PATH, "r", encoding="utf-8") as handle:
        data = json.load(handle)
    if isinstance(data, list):
        data = data[0]
    return data


def save_config(data: dict) -> None:
    CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
    if CONFIG_PATH.is_file():
        shutil.copy2(CONFIG_PATH, BACKUP_PATH)
    temp = CONFIG_PATH.with_suffix(".json.tmp")
    with open(temp, "w", encoding="utf-8") as handle:
        json.dump(data, handle, indent=4, ensure_ascii=False)
    temp.replace(CONFIG_PATH)


def validate_value(key: str, value: Any) -> Any:
    rule = SCHEMA.get(key)
    if rule is None:
        raise HTTPException(status_code=400, detail=f"unknown setting: {key}")

    kind = rule["type"]
    if kind == "enum":
        if value not in rule["options"]:
            raise HTTPException(
                status_code=400,
                detail=f"{key} must be one of {rule['options']}",
            )
    elif kind == "string":
        if not isinstance(value, str):
            raise HTTPException(status_code=400, detail=f"{key} must be a string")
    elif kind == "boolean":
        if not isinstance(value, bool):
            raise HTTPException(status_code=400, detail=f"{key} must be a boolean")
    elif kind == "integer":
        if isinstance(value, bool) or not isinstance(value, int):
            raise HTTPException(status_code=400, detail=f"{key} must be an integer")
        if "min" in rule and value < rule["min"]:
            raise HTTPException(status_code=400, detail=f"{key} must be >= {rule['min']}")
        if "max" in rule and value > rule["max"]:
            raise HTTPException(status_code=400, detail=f"{key} must be <= {rule['max']}")
    elif kind == "number":
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise HTTPException(status_code=400, detail=f"{key} must be a number")
        if "min" in rule and value < rule["min"]:
            raise HTTPException(status_code=400, detail=f"{key} must be >= {rule['min']}")
        if "max" in rule and value > rule["max"]:
            raise HTTPException(status_code=400, detail=f"{key} must be <= {rule['max']}")
    elif kind == "object":
        if not isinstance(value, dict):
            raise HTTPException(status_code=400, detail=f"{key} must be an object")
    return value


@router.get("")
def get_settings() -> dict:
    return load_config()


@router.get("/schema")
def get_schema() -> dict:
    return {"settings": SCHEMA}


@router.patch("")
def patch_settings(payload: PatchRequest) -> dict:
    if not payload.values:
        raise HTTPException(status_code=400, detail="empty patch")
    data = load_config()
    for key, value in payload.values.items():
        data[key] = validate_value(key, value)
    save_config(data)
    return data
