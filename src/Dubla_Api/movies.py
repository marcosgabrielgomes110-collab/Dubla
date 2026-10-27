"""Published movies: listing, metadata, range streaming and deletion."""

import json
import re
import shutil
from pathlib import Path

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import StreamingResponse

import src.Dubla_Config as cfg

router = APIRouter(prefix="/movies", tags=["movies"])

ID_PATTERN = re.compile(r"^[A-Za-z0-9_-]{1,64}$")
CHUNK = 1024 * 256


def _root() -> Path:
    return Path(cfg.OutputPath).resolve()


def _folder(movie_id: str) -> Path:
    if not ID_PATTERN.fullmatch(movie_id):
        raise HTTPException(status_code=400, detail="invalid movie id")
    folder = (_root() / movie_id).resolve()
    try:
        folder.relative_to(_root())
    except ValueError:
        raise HTTPException(status_code=400, detail="invalid movie id")
    if not folder.is_dir():
        raise HTTPException(status_code=404, detail="movie not found")
    return folder


def _final_video(folder: Path) -> Path | None:
    candidates = sorted(folder.glob("*_Dubla_*.mp4"))
    if not candidates:
        candidates = sorted(folder.glob("*_dublado.mp4"))
    return candidates[0] if candidates else None


def _meta(folder: Path) -> dict:
    path = folder / f"{folder.name}.json"
    if not path.is_file():
        return {}
    try:
        with open(path, "r", encoding="utf-8") as handle:
            return json.load(handle)
    except (OSError, json.JSONDecodeError):
        return {}


@router.get("")
def list_movies() -> list[dict]:
    root = _root()
    if not root.is_dir():
        return []
    movies: list[dict] = []
    for folder in sorted(root.iterdir()):
        if not folder.is_dir() or not ID_PATTERN.fullmatch(folder.name):
            continue
        video = _final_video(folder)
        if video is None:
            continue
        meta = _meta(folder)
        movie = meta.get("movie") or {}
        movies.append(
            {
                "id": folder.name,
                "title": meta.get("title"),
                "language": (meta.get("translation") or {}).get("target"),
                "duration": meta.get("duration"),
                "size": video.stat().st_size,
                "video": video.name,
                "created_at": movie.get("mux_created_at"),
            }
        )
    return movies


@router.get("/{movie_id}")
def get_movie(movie_id: str) -> dict:
    folder = _folder(movie_id)
    data = _meta(folder)
    if not data:
        raise HTTPException(status_code=404, detail="metadata not found")
    data["_folder"] = str(folder)
    return data


def _stream(path: Path, start: int, end: int):
    with open(path, "rb") as handle:
        handle.seek(start)
        remaining = end - start + 1
        while remaining > 0:
            chunk = handle.read(min(CHUNK, remaining))
            if not chunk:
                break
            remaining -= len(chunk)
            yield chunk


@router.get("/{movie_id}/video")
def stream_video(movie_id: str, request: Request):
    folder = _folder(movie_id)
    video = _final_video(folder)
    if video is None:
        raise HTTPException(status_code=404, detail="final video not found")

    size = video.stat().st_size
    range_header = request.headers.get("range")
    if range_header and range_header.startswith("bytes="):
        try:
            raw = range_header.split("=", 1)[1].split(",", 1)[0]
            start_text, end_text = raw.split("-", 1)
            start = int(start_text) if start_text else 0
            end = int(end_text) if end_text else size - 1
        except ValueError:
            raise HTTPException(status_code=416, detail="invalid range")
        start = max(0, min(start, size - 1))
        end = max(start, min(end, size - 1))
        return StreamingResponse(
            _stream(video, start, end),
            status_code=206,
            media_type="video/mp4",
            headers={
                "Content-Range": f"bytes {start}-{end}/{size}",
                "Accept-Ranges": "bytes",
                "Content-Length": str(end - start + 1),
            },
        )

    return StreamingResponse(
        _stream(video, 0, size - 1),
        media_type="video/mp4",
        headers={"Content-Length": str(size), "Accept-Ranges": "bytes"},
    )


@router.delete("/{movie_id}")
def delete_movie(movie_id: str) -> dict:
    folder = _folder(movie_id)
    shutil.rmtree(folder)
    return {"deleted": movie_id}
