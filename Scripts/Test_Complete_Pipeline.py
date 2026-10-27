import json
import sys
from pathlib import Path


__root__ = Path(__file__).parent.parent
sys.path.append(str(__root__))

from etc.Logger import log_error, log_info, log_ok  # noqa: E402
from src.Dubla_Input import GetLinkMovie  # noqa: E402
from src.Dubla_Transcribe import transcribe  # noqa: E402

# Credit: Python in 100 seconds - Fireship (https://www.youtube.com/watch?v=x7X9w_GIm1s)
URL = "https://www.youtube.com/watch?v=x7X9w_GIm1s"

# Optional args: python Scripts/Test_Complete_Pipeline.py [engine] [model]
ENGINE = sys.argv[1] if len(sys.argv) > 1 else None
MODEL = sys.argv[2] if len(sys.argv) > 2 else None


def main() -> int:
    movie = GetLinkMovie(URL)
    log_info(f"Video ID: {movie.video_id}")

    log_info("step 1/2: download + audio split")
    meta = movie.run()
    if meta is None:
        log_error("Input pipeline failed")
        return 1

    wav = Path(meta).with_suffix(".wav")
    if not wav.is_file():
        log_error(f"Audio not found: {wav}")
        return 1

    log_info(f"step 2/2: transcribe {wav.name}")
    transcribed = transcribe(wav, engine=ENGINE, model=MODEL)
    if transcribed is None:
        log_error("Transcription failed")
        return 1

    log_ok(f"Metadata file path: {transcribed}")
    log_info("json:\n" + json.dumps(
        json.loads(Path(transcribed).read_text(encoding="utf-8")),
        indent=4,
        ensure_ascii=False,
    ))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
