"""CLI entry point: python -m src.Dubla_MovieManager "<url>"."""

import argparse
import sys

from etc.Logger import log_error
from src.Dubla_MovieManager import run


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Dubla pipeline: download -> STT -> translate -> voice -> mux -> publish",
    )
    parser.add_argument("url", help="video URL")
    parser.add_argument("--force", action="store_true", help="redo cached steps and overwrite the output")
    args = parser.parse_args()

    final = run(args.url, force=args.force)
    if final is None:
        log_error("pipeline failed")
        return 1
    print(final)
    return 0


if __name__ == "__main__":
    sys.exit(main())
