"""System info, logs, voice previews and secret management."""

import importlib.util
import os
import shutil
import socket
import sys

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel

import src.Dubla_Config as cfg

router = APIRouter(tags=["system"])

PREVIEWS_DIR = cfg.ROOT / "voices_preview"
LOGS_DIR = cfg.ROOT / "Data" / "logs"

SECRET_KEYS = (
    "LLM_PROVIDER",
    "LLM_MODEL",
    "LLM_API_KEY",
    "LLM_BASE_URL",
    "ELEVENLABS_API_KEY",
    "ELEVENLABS_MODEL",
    "ELEVENLABS_VOICE_ID_PT",
    "ELEVENLABS_VOICE_ID_EN",
)


def _mask(value: str) -> str:
    if not value:
        return ""
    if len(value) <= 8:
        return "***"
    return f"{value[:4]}...{value[-4:]}"


def _read_env() -> dict[str, str]:
    data: dict[str, str] = {}
    if not cfg.ENV_PATH.is_file():
        return data
    for line in cfg.ENV_PATH.read_text(encoding="utf-8").splitlines():
        if "=" not in line or line.strip().startswith("#"):
            continue
        key, value = line.split("=", 1)
        data[key.strip()] = value.strip()
    return data


def _write_env(data: dict[str, str]) -> None:
    lines = [f"{key}={value}" for key, value in data.items()]
    cfg.ENV_PATH.write_text("\n".join(lines) + ("\n" if lines else ""), encoding="utf-8")
    try:
        os.chmod(cfg.ENV_PATH, 0o600)
    except OSError:
        pass


@router.get("/health")
def health() -> dict:
    return {"status": "ok", "service": "dubla-api"}


@router.get("/system/info")
def system_info() -> dict:
    packages = {}
    for name in (
        "vosk",
        "faster_whisper",
        "argostranslate",
        "piper",
        "pocket_tts",
        "elevenlabs",
        "qwen_tts",
    ):
        packages[name] = importlib.util.find_spec(name) is not None

    usage = shutil.disk_usage(cfg.ROOT)
    mem_total = os.sysconf("SC_PAGE_SIZE") * os.sysconf("SC_PHYS_PAGES") if hasattr(os, "sysconf") else 0
    mem_available = 0
    try:
        with open("/proc/meminfo", "r", encoding="utf-8") as handle:
            for line in handle:
                if line.startswith("MemAvailable:"):
                    mem_available = int(line.split()[1]) * 1024
    except OSError:
        pass

    return {
        "python": sys.version.split()[0],
        "hostname": socket.gethostname(),
        "root": str(cfg.ROOT),
        "binaries": {
            "ffmpeg": shutil.which("ffmpeg"),
            "ffprobe": shutil.which("ffprobe"),
            "mpv": shutil.which("mpv"),
            "espeak-ng": shutil.which("espeak-ng") or shutil.which("espeak"),
        },
        "packages": packages,
        "disk": {"total": usage.total, "used": usage.used, "free": usage.free},
        "memory": {"total": mem_total, "available": mem_available},
    }


@router.get("/system/logs")
def logs(date: str | None = None, tail: int = 200) -> dict:
    if date:
        path = LOGS_DIR / f"dubla-{date}.log"
        if not path.is_file():
            raise HTTPException(status_code=404, detail="log not found")
        lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
        return {"file": path.name, "lines": lines[-max(1, min(tail, 2000)):]}
    files = sorted(LOGS_DIR.glob("dubla-*.log")) if LOGS_DIR.is_dir() else []
    return {"files": [item.name for item in files]}


@router.get("/system/previews")
def list_previews() -> list[dict]:
    if not PREVIEWS_DIR.is_dir():
        return []
    return [
        {"name": item.name, "size": item.stat().st_size}
        for item in sorted(PREVIEWS_DIR.glob("*.wav"))
    ]


@router.get("/system/previews/{name}")
def get_preview(name: str):
    if "/" in name or ".." in name or not name.endswith(".wav"):
        raise HTTPException(status_code=400, detail="invalid preview")
    path = (PREVIEWS_DIR / name).resolve()
    try:
        path.relative_to(PREVIEWS_DIR.resolve())
    except ValueError:
        raise HTTPException(status_code=400, detail="invalid preview")
    if not path.is_file():
        raise HTTPException(status_code=404, detail="preview not found")
    return FileResponse(path, media_type="audio/wav")


@router.get("/secrets")
def list_secrets() -> dict:
    data = _read_env()
    return {
        key: {"set": bool(data.get(key)), "preview": _mask(data.get(key, ""))}
        for key in SECRET_KEYS
    }


class SecretValue(BaseModel):
    value: str


@router.put("/secrets/{key}")
def set_secret(key: str, payload: SecretValue) -> dict:
    if key not in SECRET_KEYS:
        raise HTTPException(status_code=400, detail="unknown secret")
    data = _read_env()
    data[key] = payload.value.strip()
    _write_env(data)
    return {"key": key, "set": bool(data[key])}


@router.delete("/secrets/{key}")
def delete_secret(key: str) -> dict:
    if key not in SECRET_KEYS:
        raise HTTPException(status_code=400, detail="unknown secret")
    data = _read_env()
    data.pop(key, None)
    _write_env(data)
    return {"key": key, "deleted": True}
