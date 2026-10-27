"""Shared helpers for the speech-to-text engines (Vosk and faster-whisper).

Holds everything that is engine independent: language/locale handling, the Vosk
model registry, hardware detection and the default-model policy, model download,
word -> speech-block merging and the read/write of the project json.
"""

import json
import os
import shutil
import subprocess
import urllib.request
import zipfile
from dataclasses import dataclass
from datetime import datetime
from functools import lru_cache
from pathlib import Path

from src.Dubla_Config import (
    INPUT_LANGUAGE,
    OUTPUT_LANGUAGE,
    STT_MAX_SEGMENT,
    STT_MIN_PAUSE,
    STT_MIN_SEGMENT,
    STT_OFFLINE,
    VoskModelPath,
    WhisperModelPath,
)
from etc.Logger import (
    clear_progress,
    log_error,
    log_info,
    log_ok,
    log_progress,
    log_warning,
)

VOSK_BASE_URL = "https://alphacephei.com/vosk/models"

# language -> tier -> (model name, download size in MB)
VOSK_MODELS: dict[str, dict[str, tuple[str, int]]] = {
    "en": {"small": ("vosk-model-small-en-us-0.15", 40), "large": ("vosk-model-en-us-0.22", 1800)},
    "pt": {"small": ("vosk-model-small-pt-0.3", 31), "large": ("vosk-model-pt-fb-v0.1.1-20220516_2113", 1615)},
    "es": {"small": ("vosk-model-small-es-0.42", 39), "large": ("vosk-model-es-0.42", 1400)},
    "fr": {"small": ("vosk-model-small-fr-0.22", 41), "large": ("vosk-model-fr-0.22", 1400)},
    "de": {"small": ("vosk-model-small-de-0.15", 45), "large": ("vosk-model-de-0.21", 1900)},
    "it": {"small": ("vosk-model-small-it-0.22", 48), "large": ("vosk-model-it-0.22", 1200)},
    "ru": {"small": ("vosk-model-small-ru-0.22", 45), "large": ("vosk-model-ru-0.42", 1800)},
    "zh": {"small": ("vosk-model-small-cn-0.22", 42), "large": ("vosk-model-cn-0.22", 1300)},
    "ja": {"small": ("vosk-model-small-ja-0.22", 48), "large": ("vosk-model-ja-0.22", 1000)},
    "ko": {"small": ("vosk-model-small-ko-0.22", 82)},
    "nl": {"small": ("vosk-model-small-nl-0.22", 39)},
    "tr": {"small": ("vosk-model-small-tr-0.3", 35)},
    "vi": {"small": ("vosk-model-small-vn-0.4", 32), "large": ("vosk-model-vn-0.4", 78)},
    "hi": {"small": ("vosk-model-small-hi-0.22", 42), "large": ("vosk-model-hi-0.22", 1500)},
    "pl": {"small": ("vosk-model-small-pl-0.22", 50)},
    "cs": {"small": ("vosk-model-small-cs-0.4-rhasspy", 44)},
    "uk": {"small": ("vosk-model-small-uk-v3-small", 133), "large": ("vosk-model-uk-v3", 343)},
    "fa": {"small": ("vosk-model-small-fa-0.42", 53), "large": ("vosk-model-fa-0.42", 1600)},
    "ca": {"small": ("vosk-model-small-ca-0.4", 42)},
    "sv": {"small": ("vosk-model-small-sv-rhasspy-0.15", 289)},
    "eo": {"small": ("vosk-model-small-eo-0.42", 42)},
    "uz": {"small": ("vosk-model-small-uz-0.22", 49)},
    "ky": {"small": ("vosk-model-small-ky-0.42", 49)},
    "ka": {"small": ("vosk-model-small-ka-0.42", 45)},
    "tg": {"small": ("vosk-model-small-tg-0.22", 50)},
    "te": {"small": ("vosk-model-small-te-0.42", 58)},
    "gu": {"small": ("vosk-model-small-gu-0.42", 100)},
    "tl": {"small": ("vosk-model-tl-ph-generic-0.6", 320)},
    "br": {"small": ("vosk-model-br-0.8", 70)},
    "ar": {"small": ("vosk-model-ar-mgb2-0.4", 318)},
    "el": {"small": ("vosk-model-el-gr-0.7", 1100)},
}

WHISPER_SIZES = ("tiny", "base", "small", "medium", "large-v3")
WHISPER_REPO = "Systran/faster-whisper-{size}"

# Locales/aliases that map onto a base language code
LANGUAGE_ALIASES = {
    "pt-br": "pt",
    "pt-pt": "pt",
    "en-us": "en",
    "en-gb": "en",
    "zh-cn": "zh",
    "zh-tw": "zh",
    "es-es": "es",
    "es-mx": "es",
    "fr-fr": "fr",
    "de-de": "de",
    "it-it": "it",
    "ja-jp": "ja",
    "ko-kr": "ko",
    "ru-ru": "ru",
    "hi-in": "hi",
}

# Languages supported by whisper (ISO 639-1)
WHISPER_LANGUAGES = frozenset(
    """af am ar as az ba be bg bn bo br bs ca cs cy da de el en eo es et eu fa fi fo fr
    gl gu ha haw he hi hr hu hy id is it ja jw ka kk km kn ko la lb ln lo lt lv mg mi mk
    ml mn mr ms mt my ne nl nn no oc pa pl ps pt ro ru sa sd si sk sl sn so sq sr su sv
    sw ta te tg th tk tl tr tt uk ur uz vi yi yo zh""".split()
)

# Languages written without spaces between words
NO_SPACE_LANGUAGES = frozenset({"zh", "ja", "th", "lo", "km", "my"})
SENTENCE_ENDINGS = (".", "!", "?", "…", "。", "！", "？")
# Tokens starting with these attach to the previous word (whisper splits "high-level" into "high" + "-level")
ATTACH_TO_PREVIOUS = ("-", "'", "’", ",", ".", "!", "?", ";", ":", ")", "]", "…", "%")


def normalize_language(value) -> str | None:
    """Reduce a locale tag to its base code ('pt-BR', 'pt_br' -> 'pt'; '' -> 'auto')."""
    if value is None:
        return None
    text = str(value).strip().lower().replace("_", "-")
    if text in ("", "auto"):
        return "auto"
    if text in LANGUAGE_ALIASES:
        return LANGUAGE_ALIASES[text]
    return text.split("-")[0] or None


def is_whisper_language(language: str) -> bool:
    return normalize_language(language) == "auto" or normalize_language(language) in WHISPER_LANGUAGES


# --------------------------------------------------------------------------- #
# Hardware detection and default model policy
# --------------------------------------------------------------------------- #
@dataclass(frozen=True)
class Hardware:
    cpu_threads: int
    ram_gb: float
    cuda: bool
    vram_gb: float

    def describe(self) -> str:
        gpu = f"CUDA GPU {self.vram_gb:.1f} GB" if self.cuda else "no GPU"
        return f"{self.cpu_threads} threads, {self.ram_gb:.1f} GB RAM, {gpu}"


@lru_cache(maxsize=1)
def detect_hardware() -> Hardware:
    """Detect CPU/RAM/GPU without requiring torch."""
    cpu_threads = os.cpu_count() or 1
    try:
        ram_gb = os.sysconf("SC_PAGE_SIZE") * os.sysconf("SC_PHYS_PAGES") / (1024 ** 3)
    except (ValueError, OSError, AttributeError):
        ram_gb = 0.0

    cuda = False
    vram_gb = 0.0
    try:
        import ctranslate2

        cuda = ctranslate2.get_cuda_device_count() > 0
    except Exception:
        cuda = shutil.which("nvidia-smi") is not None

    if cuda:
        try:
            out = subprocess.run(
                ["nvidia-smi", "--query-gpu=memory.total", "--format=csv,noheader,nounits"],
                capture_output=True, text=True, timeout=5, check=True,
            ).stdout
            vram_gb = max((int(line) for line in out.split() if line.isdigit()), default=0) / 1024
        except Exception:
            vram_gb = 0.0

    return Hardware(cpu_threads=cpu_threads, ram_gb=ram_gb, cuda=cuda, vram_gb=vram_gb)


def default_whisper_size(hw: Hardware) -> str:
    """Pick a whisper model that fits the machine."""
    if hw.cuda:
        if hw.vram_gb >= 10:
            return "large-v3"
        if hw.vram_gb >= 6:
            return "medium"
        if hw.vram_gb >= 4:
            return "small"
        return "base"

    if hw.cpu_threads >= 8 and hw.ram_gb >= 16:
        return "small"
    if hw.cpu_threads >= 8 and hw.ram_gb >= 8:
        return "base"
    return "tiny"


def default_whisper_compute(hw: Hardware) -> tuple[str, str]:
    """Return (device, compute_type) for faster-whisper."""
    if hw.cuda:
        return "cuda", "float16"
    return "cpu", "int8"


def vosk_model_name(language, choice: str | None = "auto") -> str | None:
    """Resolve the Vosk model name for a language/tier, or None when unsupported."""
    lang = normalize_language(language)
    if lang in (None, "auto"):
        return None

    tier = (choice or "auto").strip()
    if tier.lower().startswith("vosk-model"):
        return tier  # explicit model name from config

    models = VOSK_MODELS.get(lang)
    if not models:
        return None

    tier = tier.lower()
    if tier in models:
        return models[tier][0]
    return (models.get("small") or models.get("large") or (None,))[0]


def pick_engine(language, configured: str = "auto") -> str:
    """Choose between vosk and whisper from the language and the hardware."""
    configured = (configured or "auto").strip().lower()
    if configured in ("vosk", "whisper"):
        return configured

    lang = normalize_language(language)
    if lang in (None, "auto"):
        return "whisper"  # only whisper can detect the language

    hw = detect_hardware()
    if vosk_model_name(lang) is None:
        return "whisper"
    if hw.cuda:
        return "whisper"
    if hw.cpu_threads >= 8 and hw.ram_gb >= 16:
        return "whisper"
    return "vosk"


# --------------------------------------------------------------------------- #
# Model download
# --------------------------------------------------------------------------- #
def _progress(block_count: int, block_size: int, total_size: int) -> None:
    if total_size <= 0:
        return
    done = min(block_count * block_size, total_size)
    percent = done * 100 / total_size
    log_progress(f"  downloading... {percent:5.1f}% ({done / 1048576:.1f}/{total_size / 1048576:.1f} MB)")


def _safe_extract(archive: Path, destination: Path) -> None:
    """Extract a zip while refusing entries that would escape the destination."""
    destination = destination.resolve()
    with zipfile.ZipFile(archive) as zf:
        bad = zf.testzip()
        if bad is not None:
            raise ValueError(f"corrupted archive member: {bad}")
        for member in zf.infolist():
            target = (destination / member.filename).resolve()
            if target != destination and not target.is_relative_to(destination):
                raise ValueError(f"unsafe path in archive: {member.filename}")
        zf.extractall(destination)


def _vosk_ready(path: Path) -> bool:
    return (path / "am").is_dir() and (path / "conf").is_dir()


def _vosk_size_mb(name: str) -> int:
    for models in VOSK_MODELS.values():
        for model_name, size_mb in models.values():
            if model_name == name:
                return size_mb
    return 0


def ensure_vosk_model(language, choice: str | None = "auto") -> Path | None:
    """Return the local Vosk model directory, downloading it when missing."""
    name = vosk_model_name(language, choice)
    if name is None:
        log_error(f"No Vosk model registered for language: {language}")
        return None

    destination = VoskModelPath / name
    if _vosk_ready(destination):
        return destination

    if STT_OFFLINE:
        log_warning(f"Vosk model missing and stt_offline=true: {destination}")
        return None

    url = f"{VOSK_BASE_URL}/{name}.zip"
    downloads = VoskModelPath / ".downloads"
    archive = downloads / f"{name}.zip"
    staging = VoskModelPath / f".tmp-{name}"

    try:
        downloads.mkdir(parents=True, exist_ok=True)
        if staging.exists():
            shutil.rmtree(staging)
        log_info(f"Downloading Vosk model {name} (~{_vosk_size_mb(name)} MB)")
        log_info(f"source: {url}")
        urllib.request.urlretrieve(url, archive, reporthook=_progress)
        clear_progress()

        staging.mkdir(parents=True)
        _safe_extract(archive, staging)

        # Zips normally contain a single top level folder
        extracted = staging / name
        if not extracted.is_dir():
            candidates = [p for p in staging.iterdir() if p.is_dir()]
            if len(candidates) != 1:
                raise ValueError("unexpected archive layout")
            extracted = candidates[0]

        if destination.exists():
            shutil.rmtree(destination)
        shutil.move(str(extracted), str(destination))
        shutil.rmtree(staging, ignore_errors=True)
        archive.unlink(missing_ok=True)

        if not _vosk_ready(destination):
            raise ValueError("downloaded model is incomplete")
        return destination
    except Exception as e:
        log_error(f"Error downloading Vosk model: {e}")
        shutil.rmtree(staging, ignore_errors=True)
        return None


def _whisper_ready(path: Path) -> bool:
    return (path / "model.bin").is_file() and (path / "config.json").is_file()


def whisper_size(choice: str | None = "auto") -> str:
    """Resolve the whisper size from the config ('auto' uses the hardware policy)."""
    choice = (choice or "auto").strip().lower()
    if choice in WHISPER_SIZES:
        return choice
    return default_whisper_size(detect_hardware())


def ensure_whisper_model(size: str | None = "auto") -> Path | None:
    """Return the local faster-whisper model directory, downloading it when missing."""
    size = whisper_size(size)
    destination = WhisperModelPath / size
    if _whisper_ready(destination):
        return destination

    if STT_OFFLINE:
        log_warning(f"Whisper model missing and stt_offline=true: {destination}")
        return None

    try:
        from huggingface_hub import snapshot_download
    except ImportError:
        log_error("huggingface_hub is not installed: pip install huggingface_hub")
        return None

    repo = WHISPER_REPO.format(size=size)
    try:
        WhisperModelPath.mkdir(parents=True, exist_ok=True)
        log_info(f"Downloading whisper model {size} from {repo}")
        snapshot_download(repo_id=repo, local_dir=str(destination))
        if not _whisper_ready(destination):
            raise ValueError("downloaded model is incomplete")
        return destination
    except Exception as e:
        log_error(f"Error downloading whisper model: {e}")
        return None


# --------------------------------------------------------------------------- #
# Words -> speech blocks
# --------------------------------------------------------------------------- #
def _join_words(block: list[dict], separator: str) -> str:
    """Join the words of one block without breaking hyphenation or punctuation."""
    text = ""
    for word in block:
        token = word["word"]
        if not text:
            text = token
        elif separator and token[0] not in ATTACH_TO_PREVIOUS:
            text += separator + token
        else:
            text += token
    return text.strip()


def build_segments(
    words: list[dict],
    language: str | None = None,
    min_pause: float = STT_MIN_PAUSE,
    min_segment: float = STT_MIN_SEGMENT,
    max_segment: float = STT_MAX_SEGMENT,
) -> list[dict]:
    """Group word timestamps into speech blocks used later for translation and dubbing."""
    cleaned: list[dict] = []
    for word in words:
        text = str(word.get("word") or "").strip()
        if not text:
            continue
        start = max(0.0, float(word.get("start") or 0.0))
        end = max(start, float(word.get("end") or start))
        cleaned.append(
            {
                "start": start,
                "end": end if end > start else start + 0.001,
                "word": text,
                "conf": float(word.get("conf") or 0.0),
            }
        )

    cleaned.sort(key=lambda w: (w["start"], w["end"]))

    blocks: list[list[dict]] = []
    current: list[dict] = []
    for word in cleaned:
        if current:
            gap = word["start"] - current[-1]["end"]
            too_long = (word["end"] - current[0]["start"]) > max_segment
            sentence_done = current[-1]["word"].endswith(SENTENCE_ENDINGS)
            if gap > min_pause or too_long or sentence_done:
                blocks.append(current)
                current = []
        current.append(word)
    if current:
        blocks.append(current)

    separator = "" if normalize_language(language) in NO_SPACE_LANGUAGES else " "
    segments: list[dict] = []
    for block in blocks:
        start = round(block[0]["start"], 3)
        end = round(block[-1]["end"], 3)
        text = _join_words(block, separator)
        if not text or end <= start:
            continue
        # Skip noise blips; set stt_min_segment=0 to keep everything
        if min_segment and (end - start) < min_segment:
            continue
        segments.append({"start": start, "end": end, "text": text})

    return segments


# --------------------------------------------------------------------------- #
# Metadata json
# --------------------------------------------------------------------------- #
def load_meta(path: Path) -> dict:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def save_meta(path: Path, data: dict) -> None:
    """Write the json atomically so a crash never leaves it half written."""
    temp = path.with_suffix(path.suffix + ".tmp")
    with open(temp, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=4, ensure_ascii=False)
    os.replace(temp, path)


class BaseStt:
    """Common pipeline: validate json/wav, resolve/download model, transcribe, merge, save."""

    engine = ""

    def __init__(self, wav_path, language=None, model=None, force: bool = False):
        self.wav_path = Path(wav_path).expanduser().resolve()
        self.language = normalize_language(INPUT_LANGUAGE if language is None else language)
        self.model_choice = model
        self.force = force
        self.meta_path = self.wav_path.with_suffix(".json")
        self.meta: dict = {}
        self.model_name: str | None = None
        self.model_path: Path | None = None
        self.detected_language: str | None = None
        self.device = "cpu"

    # -- hooks implemented by the engines ---------------------------------- #
    def _resolve_model(self) -> bool:
        raise NotImplementedError

    def _prepare_model(self) -> bool:
        raise NotImplementedError

    def _transcribe(self) -> list[dict] | None:
        raise NotImplementedError

    # -- shared pipeline ---------------------------------------------------- #
    def run(self) -> Path | None:
        """Transcribe the wav and store the speech blocks in <id>.json."""
        if not self.wav_path.is_file():
            log_error(f"Audio not found: {self.wav_path}")
            return None
        if not self.meta_path.is_file():
            log_error(f"Metadata not found (run Dubla_Input first): {self.meta_path}")
            return None
        if self.language == "auto" and self.engine == "vosk":
            log_warning("Vosk cannot detect the language: set input_language or use the whisper engine")
            return None
        if not self._resolve_model():
            return None

        self.meta = load_meta(self.meta_path)
        if not self.force and self._is_done():
            log_info(f"Already transcribed with {self.engine}/{self.model_name}: {self.meta_path}")
            return self.meta_path

        if not self._prepare_model():
            return None

        log_info(f"{self.engine} / {self.model_name} / language={self.language or 'auto'}")
        words = self._transcribe()
        if words is None:
            return None

        segments = build_segments(words, self.detected_language or self.language)
        self._save(words, segments)
        log_ok(f"{len(segments)} speech blocks saved to {self.meta_path}")
        return self.meta_path

    def _is_done(self) -> bool:
        stt = self.meta.get("stt") or {}
        if not stt.get("segments"):
            return False
        if stt.get("engine") != self.engine or stt.get("model") != self.model_name:
            return False
        audio = stt.get("audio") or {}
        try:
            stat = self.wav_path.stat()
        except OSError:
            return False
        return audio.get("size") == stat.st_size and audio.get("mtime_ns") == stat.st_mtime_ns

    def _save(self, words: list[dict], segments: list[dict]) -> None:
        stat = self.wav_path.stat()
        self.meta["languages"] = {"input": INPUT_LANGUAGE, "output": OUTPUT_LANGUAGE}
        self.meta["stt"] = {
            "engine": self.engine,
            "model": self.model_name,
            "language": self.language if self.language != "auto" else self.detected_language,
            "language_detected": self.detected_language,
            "device": self.device,
            "audio": {
                "path": str(self.wav_path),
                "size": stat.st_size,
                "mtime_ns": stat.st_mtime_ns,
            },
            "created_at": datetime.now().astimezone().isoformat(timespec="seconds"),
            "segments": segments,
            "words": words,
        }
        save_meta(self.meta_path, self.meta)
