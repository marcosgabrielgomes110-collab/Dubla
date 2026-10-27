"""Dubla MovieManager: full pipeline, mux and publication (main entry point).

Runs download -> STT -> translation -> voice -> mux -> publish and returns the
final dubbed video inside Data/Movies/<id>/.

Usage:
    from src.Dubla_MovieManager import run

    final = run("https://www.youtube.com/watch?v=...")

CLI:
    python -m src.Dubla_MovieManager "<url>"
"""

from pathlib import Path

from etc.Logger import log_error, log_info, log_ok
from src.Dubla_Input import GetLinkMovie
from src.Dubla_MovieManager.Dubla_Movie_Mux import mux_video
from src.Dubla_MovieManager.Dubla_Movie_Publish import publish
from src.Dubla_Transcribe import transcribe
from src.Dubla_Translate import translate
from src.Dubla_Voicegen import synthesize

__all__ = ["run", "mux_video", "publish"]


def run(url: str, force: bool = False) -> Path | None:
    """Run download -> STT -> translation -> voice -> mux -> publish.

    Args:
        url: video URL (the only required input).
        force: redo the cached steps and overwrite an existing publication.

    Returns:
        Path of the final dubbed video, or None on failure.
    """
    log_info(f"pipeline start: {url}")

    movie = GetLinkMovie(url)
    meta = movie.run()
    if meta is None:
        log_error("pipeline failed: input/download")
        return None

    wav = Path(meta).with_suffix(".wav")
    if not wav.is_file():
        log_error(f"pipeline failed: audio not found ({wav})")
        return None

    transcribed = transcribe(wav, force=force)
    if transcribed is None:
        log_error("pipeline failed: transcription")
        return None

    translated = translate(transcribed, force=force)
    if translated is None:
        log_error("pipeline failed: translation")
        return None

    voiced = synthesize(translated, force=force)
    if voiced is None:
        log_error("pipeline failed: voice")
        return None

    muxed = mux_video(voiced, force=force)
    if muxed is None:
        log_error("pipeline failed: mux")
        return None

    final = publish(voiced, force=force)
    if final is None:
        log_error("pipeline failed: publish")
        return None

    log_ok(f"pipeline done: {final}")
    return final
