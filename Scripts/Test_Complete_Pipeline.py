import argparse
import json
import sys
from pathlib import Path


__root__ = Path(__file__).parent.parent
sys.path.append(str(__root__))

from etc.Logger import log_error, log_info, log_ok  # noqa: E402
from src.Dubla_Input import GetLinkMovie  # noqa: E402
from src.Dubla_MovieManager import mux_video, publish  # noqa: E402
from src.Dubla_Transcribe import transcribe  # noqa: E402
from src.Dubla_Translate import translate  # noqa: E402
from src.Dubla_Voicegen import synthesize  # noqa: E402

# Credit: Python in 100 seconds - Fireship (https://www.youtube.com/watch?v=x7X9w_GIm1s)
URL = "https://www.youtube.com/watch?v=446E-r0rXHI"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run the full Dubla pipeline: download -> STT -> translate -> voice -> mux -> publish",
        epilog="Examples:\n"
        "  python Scripts/Test_Complete_Pipeline.py\n"
        "  python Scripts/Test_Complete_Pipeline.py whisper base argos piper\n"
        "  python Scripts/Test_Complete_Pipeline.py whisper base llm espeak --force --json",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("stt_engine", nargs="?", help="vosk | whisper (default: configs.json)")
    parser.add_argument("stt_model", nargs="?", help="Vosk tier/name or whisper size")
    parser.add_argument("translate_engine", nargs="?", help="deep-translator | argos | llm")
    parser.add_argument("voice_engine", nargs="?", help="piper | pocket | qwen | elevenlabs | espeak")
    parser.add_argument("--force", action="store_true", help="redo every step and overwrite the output")
    parser.add_argument("--json", action="store_true", help="print the whole json at the end")
    return parser.parse_args()


def main() -> int:
    args = parse_args()

    movie = GetLinkMovie(URL)
    log_info(f"Video ID: {movie.video_id}")

    log_info("step 1/6: download + audio split")
    meta = movie.run()
    if meta is None:
        log_error("Input pipeline failed")
        return 1

    wav = Path(meta).with_suffix(".wav")
    if not wav.is_file():
        log_error(f"Audio not found: {wav}")
        return 1

    log_info(f"step 2/6: transcribe {wav.name}")
    transcribed = transcribe(wav, engine=args.stt_engine, model=args.stt_model, force=args.force)
    if transcribed is None:
        log_error("Transcription failed")
        return 1

    log_info("step 3/6: translate")
    translated = translate(transcribed, engine=args.translate_engine, force=args.force)
    if translated is None:
        log_error("Translation failed")
        return 1

    log_info("step 4/6: voice")
    voiced = synthesize(translated, engine=args.voice_engine, force=args.force)
    if voiced is None:
        log_error("Voice generation failed")
        return 1

    log_info("step 5/6: mux")
    muxed = mux_video(voiced, force=args.force)
    if muxed is None:
        log_error("Mux failed")
        return 1

    log_info("step 6/6: publish")
    final = publish(voiced, force=args.force)
    if final is None:
        log_error("Publish failed")
        return 1

    meta_after = final.parent / Path(voiced).name
    data = json.loads(meta_after.read_text(encoding="utf-8"))
    stt = data.get("stt") or {}
    info = data.get("translation") or {}
    blocks = data.get("segments_traduct") or []
    voice = data.get("voice") or {}
    voice_blocks = voice.get("segments") or []
    movie_info = data.get("movie") or {}
    overflow = sum(1 for block in voice_blocks if block.get("overflow"))

    log_ok(f"FINAL VIDEO: {final}")
    log_info(f"video: {data.get('id')} | {data.get('title')} ({data.get('duration')}s)")
    log_info(f"stt: {stt.get('engine')}/{stt.get('model')} | {len(stt.get('segments') or [])} blocks")
    log_info(
        f"translation: {info.get('engine')}/{info.get('model')} | "
        f"{info.get('source')} -> {info.get('target')} | {len(blocks)} blocks"
    )
    log_info(
        f"voice: {voice.get('engine')}/{voice.get('voice')} | "
        f"{voice.get('sample_rate')} Hz | {len(voice_blocks)} blocks | overflow={overflow}"
    )
    log_info(
        f"movie: {movie_info.get('video_codec')} | overlaps={movie_info.get('overlaps')} | "
        f"folder={final.parent}"
    )
    for block in blocks[:3]:
        log_info(f"  {block['start']:>7.2f} -> {block['end']:>7.2f} | {block['text']}")

    if args.json:
        print(json.dumps(data, indent=4, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
