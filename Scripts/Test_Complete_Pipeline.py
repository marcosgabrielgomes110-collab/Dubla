import json
import sys
from pathlib import Path


__root__ = Path(__file__).parent.parent
print(f"Adding {__root__} to sys.path")
sys.path.append(str(__root__))

from src.Dubla_Input.Link_Movie import GetLinkMovie

# Credit: Python in 100 seconds - Fireship (https://www.youtube.com/watch?v=x7X9w_GIm1s)
URL = "https://www.youtube.com/watch?v=x7X9w_GIm1s"

movie = GetLinkMovie(URL)
print("=" * 40)
print(f"Video ID: {movie.video_id}\n")
print("=" * 40)

meta = movie.run()

if meta is None:
    print("Pipeline failed")
    raise SystemExit(1)

print(f"Metadata file path: {meta}\n")
print("=" * 40)
print(json.dumps(json.loads(Path(meta).read_text(encoding="utf-8")), indent=4))
