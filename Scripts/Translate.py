"""Translate the stt.segments of a project json.

Examples:
    python Scripts/Translate.py Data/temp/<id>/<id>.json
    python Scripts/Translate.py Data/temp/<id>/<id>.json --engine llm
    python Scripts/Translate.py Data/temp/<id>/<id>.json --engine argos --force
"""

import argparse
import json
import sys
from pathlib import Path

__root__ = Path(__file__).parent.parent
if str(__root__) not in sys.path:
    sys.path.insert(0, str(__root__))

from etc.Logger import log_error, log_info, log_ok  # noqa: E402
from src.Dubla_Translate import ENGINES, translate  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description="Translate the speech blocks of a Dubla json")
    parser.add_argument("meta", help="path to Data/temp/<id>/<id>.json")
    parser.add_argument("--engine", choices=sorted(ENGINES), default=None)
    parser.add_argument("--source", default=None, help="source language override")
    parser.add_argument("--target", default=None, help="target language override")
    parser.add_argument("--batch-size", type=int, default=None)
    parser.add_argument("--force", action="store_true", help="translate again")
    args = parser.parse_args()

    result = translate(
        args.meta,
        engine=args.engine,
        source=args.source,
        target=args.target,
        force=args.force,
        batch_size=args.batch_size,
    )
    if result is None:
        log_error("translation failed")
        return 1

    data = json.loads(Path(result).read_text(encoding="utf-8"))
    blocks = data.get("segments_traduct") or []
    info = data.get("translation") or {}
    log_ok(f"{len(blocks)} blocks translated -> {result}")
    log_info(f"engine={info.get('engine')} model={info.get('model')} {info.get('source')} -> {info.get('target')}")
    for block in blocks[:3]:
        log_info(f"  {block['start']:>7.2f} -> {block['end']:>7.2f} | {block['text']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
