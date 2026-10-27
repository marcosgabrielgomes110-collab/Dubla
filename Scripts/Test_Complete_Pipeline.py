import argparse
import json
import sys
from pathlib import Path


__root__ = Path(__file__).parent.parent
sys.path.append(str(__root__))

from etc.Logger import log_error, log_info, log_ok  # noqa: E402
from src.Dubla_Input import GetLinkMovie  # noqa: E402
from src.Dubla_Transcribe import transcribe  # noqa: E402
from src.Dubla_Translate import translate  # noqa: E402

# Credit: Python in 100 seconds - Fireship (https://www.youtube.com/watch?v=x7X9w_GIm1s)
URL = "https://www.youtube.com/watch?v=x7X9w_GIm1s"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run the full Dubla pipeline: download -> transcribe -> translate",
        epilog="Examples:\n"
        "  python Scripts/Test_Complete_Pipeline.py\n"
        "  python Scripts/Test_Complete_Pipeline.py whisper base argos\n"
        "  python Scripts/Test_Complete_Pipeline.py whisper base llm --force --json",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("stt_engine", nargs="?", help="vosk | whisper (default: configs.json)")
    parser.add_argument("stt_model", nargs="?", help="Vosk tier/name or whisper size")
    parser.add_argument("translate_engine", nargs="?", help="deep-translator | argos | llm")
    parser.add_argument("--force", action="store_true", help="re-run transcription and translation")
    parser.add_argument("--json", action="store_true", help="print the whole json at the end")
    return parser.parse_args()


def main() -> int:
    args = parse_args()

    movie = GetLinkMovie(URL)
    log_info(f"Video ID: {movie.video_id}")

    log_info("step 1/3: download + audio split")
    meta = movie.run()
    if meta is None:
        log_error("Input pipeline failed")
        return 1

    wav = Path(meta).with_suffix(".wav")
    if not wav.is_file():
        log_error(f"Audio not found: {wav}")
        return 1

    log_info(f"step 2/3: transcribe {wav.name}")
    transcribed = transcribe(wav, engine=args.stt_engine, model=args.stt_model, force=args.force)
    if transcribed is None:
        log_error("Transcription failed")
        return 1

    log_info("step 3/3: translate")
    translated = translate(transcribed, engine=args.translate_engine, force=args.force)
    if translated is None:
        log_error("Translation failed")
        return 1

    data = json.loads(Path(translated).read_text(encoding="utf-8"))
    stt = data.get("stt") or {}
    info = data.get("translation") or {}
    blocks = data.get("segments_traduct") or []

    log_ok(f"JSON: {translated}")
    log_info(f"video: {data.get('id')} | {data.get('title')} ({data.get('duration')}s)")
    log_info(f"stt: {stt.get('engine')}/{stt.get('model')} | {len(stt.get('segments') or [])} blocks")
    log_info(
        f"translation: {info.get('engine')}/{info.get('model')} | "
        f"{info.get('source')} -> {info.get('target')} | {len(blocks)} blocks"
    )
    for block in blocks[:3]:
        log_info(f"  {block['start']:>7.2f} -> {block['end']:>7.2f} | {block['text']}")

    if args.json:
        print(json.dumps(data, indent=4, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
