"""Move the working folder to Data/Movies/<id>/ and rename the final video."""

import re
import shutil
from pathlib import Path

from etc.Logger import log_error, log_ok, log_warning
from src.Dubla_Config import OUTPUT_LANGUAGE, OutputPath, PUBLISH_OVERWRITE
from src.Dubla_Transcribe.Dubla_Stt_Common import load_meta, save_meta


def slugify(text: str, fallback: str = "movie") -> str:
    slug = re.sub(r"[^A-Za-z0-9._-]+", "_", text or "").strip("._-")
    slug = re.sub(r"_+", "_", slug)
    return slug or fallback


def _destination(work: Path, force: bool) -> Path:
    base = OutputPath / work.name
    if not base.exists():
        return base
    if force or PUBLISH_OVERWRITE:
        shutil.rmtree(base)
        return base
    index = 2
    while True:
        candidate = OutputPath / f"{work.name}_{index}"
        if not candidate.exists():
            return candidate
        index += 1


def _rewrite_paths(meta: dict, destination: Path, final_video: Path) -> dict:
    def moved(value: str | None, subfolder: str = "") -> str | None:
        if not value:
            return value
        name = Path(value).name
        return str(destination / subfolder / name if subfolder else destination / name)

    meta["video_path"] = moved(meta.get("video_path"))
    meta["file_path"] = meta.get("video_path")
    meta["audio_path"] = moved(meta.get("audio_path"))

    voice = meta.get("voice") or {}
    for segment in voice.get("segments") or []:
        segment["path"] = moved(segment.get("path"), "voice")

    movie = meta.get("movie") or {}
    movie["muxed_path"] = str(final_video)
    movie["path"] = str(final_video)
    movie["output_dir"] = str(destination)
    meta["movie"] = movie
    return meta


def publish(meta_path, force: bool = False) -> Path | None:
    """Move the working folder into Data/Movies/<id>/ and expose the final video."""
    path = Path(meta_path).expanduser()
    if path.suffix == ".json":
        meta_path = path.resolve()
    else:
        # Accept the muxed video too: the json lives next to it, named after the folder
        candidate = path.parent / f"{path.parent.name}.json"
        meta_path = (candidate if candidate.is_file() else path.with_suffix(".json")).resolve()
    if not meta_path.is_file():
        log_error(f"Metadata not found: {meta_path}")
        return None

    work = meta_path.parent
    try:
        meta = load_meta(meta_path)
    except Exception as e:
        log_error(f"Error reading {meta_path}: {e}")
        return None

    movie = meta.get("movie") or {}
    muxed = Path(movie.get("muxed_path") or work / f"{meta_path.stem}_dublado.mp4")
    if not muxed.is_file():
        log_error(f"Muxed video not found: {muxed}")
        return None

    slug = slugify(str(meta.get("title") or meta_path.stem), meta_path.stem)
    final_name = f"{slug}_Dubla_{OUTPUT_LANGUAGE}.mp4"

    destination = _destination(work, force)
    destination.parent.mkdir(parents=True, exist_ok=True)

    try:
        shutil.move(str(work), str(destination))
    except OSError as e:
        log_error(f"Could not move the working folder: {e}")
        return None

    moved_muxed = destination / muxed.name
    final_video = destination / final_name
    try:
        moved_muxed.replace(final_video)
    except OSError as e:
        log_error(f"Could not rename the final video: {e}")
        return None

    # Rename the muted source so it cannot be confused with the dubbed movie
    original_name = Path(meta.get("video_path") or "").name
    original = destination / original_name if original_name else None
    if original is not None and original.is_file() and original != final_video:
        renamed = original.with_name(f"{original.stem}_original_mudo{original.suffix}")
        try:
            original.replace(renamed)
            meta["video_path"] = str(renamed)
            meta["file_path"] = str(renamed)
        except OSError as e:
            log_warning(f"could not rename the muted original: {e}")

    # The full dubbed track is an intermediate artifact; the MP4 already carries the audio
    (destination / "dub.wav").unlink(missing_ok=True)

    meta = _rewrite_paths(meta, destination, final_video)
    save_meta(destination / meta_path.name, meta)

    log_ok(f"movie published: {final_video}")
    if destination.name != work.name:
        log_warning(f"output folder already existed; wrote to {destination.name}")
    return final_video
