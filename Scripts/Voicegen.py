"""Generate the voice for the translated blocks of a project json.

Examples:
    python Scripts/Voicegen.py Data/temp/<id>/<id>.json
    python Scripts/Voicegen.py Data/temp/<id>/<id>.json --engine pocket
    python Scripts/Voicegen.py Data/temp/<id>/<id>.json --engine espeak --force
"""

import argparse
import json
import sys
from pathlib import Path

__root__ = Path(__file__).parent.parent
if str(__root__) not in sys.path:
    sys.path.insert(0, str(__root__))

from etc.Logger import log_error, log_info, log_ok  # noqa: E402
from src.Dubla_Voicegen import ENGINES, synthesize  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate voice for a Dubla json")
    parser.add_argument("meta", help="path to Data/temp/<id>/<id>.json")
    parser.add_argument("--engine", choices=sorted(ENGINES), default=None)
    parser.add_argument("--language", default=None, help="voice language override")
    parser.add_argument("--voice", default=None, help="engine specific voice/speaker")
    parser.add_argument("--force", action="store_true", help="synthesize again")
    args = parser.parse_args()

    result = synthesize(
        args.meta,
        engine=args.engine,
        language=args.language,
        voice=args.voice,
        force=args.force,
    )
    if result is None:
        log_error("voice generation failed")
        return 1

    data = json.loads(Path(result).read_text(encoding="utf-8"))
    voice = data.get("voice") or {}
    blocks = voice.get("segments") or []
    overflow = [block for block in blocks if block.get("overflow")]

    log_ok(f"{len(blocks)} blocks voiced -> {result}")
    log_info(f"engine={voice.get('engine')} voice={voice.get('voice')} language={voice.get('language')}")
    log_info(f"sample_rate={voice.get('sample_rate')} overflow={len(overflow)}")
    for block in blocks[:3]:
        log_info(f"  {block['start']:>7.2f} -> {block['end']:>7.2f} | {block['duration']:.2f}s | {block['path']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
