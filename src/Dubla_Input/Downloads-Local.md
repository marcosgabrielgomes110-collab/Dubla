# Dubla_Input — video inputs

Everything that turns a video (remote or local) into the format the rest of Dubla consumes:
for each video a folder `Data/temp/<id>/` is created with

| File | Content |
| --- | --- |
| `<id>.mp4` | video **without audio** (the audio track is removed at the end of the pipeline) |
| `<id>.wav` | separated audio, mono, 16 kHz, PCM s16le |
| `<id>.json` | metadata + `video_path` and `audio_path` |

Paths come from `configs.json` (`temp_path`, `output_path`), resolved from the project root.

## Summary

| File | Class | Input | `run()` return |
| --- | --- | --- | --- |
| `Link_Movie.py` | `GetLinkMovie` | YouTube URL (`str`) | `Path` of `<id>.json` — or `None` on error |
| `Local_Movie.py` | `GetLocalMovie` | path to a local video (`str` or `Path`) | `Path` of `<id>.json` — or `None` on error |

Usage:

```python
from src.Dubla_Input import GetLinkMovie, GetLocalMovie

meta = GetLinkMovie("https://www.youtube.com/watch?v=x7X9w_GIm1s").run()
meta = GetLocalMovie("~/Videos/movie.mkv").run()
```

## `Link_Movie.py` — YouTube download

- **Input:** URL. `__init__` already queries yt-dlp just to get the video ID (downloads nothing).
- **Flow:** `prepare()` → download at the `configs.json` quality (`quality_ytdlp`) → extract `<id>.wav` → remove the audio from the `.mp4` → write the JSON.
- **ID:** the YouTube ID itself (e.g. `x7X9w_GIm1s`).
- **Recovery:** if the local `.mp4` is already muted (previous run), yt-dlp is forced to download it again, because the original audio no longer exists on disk.
- **Cache:** if video + WAV + JSON already exist, `run()` returns the JSON right away, without network.

## `Local_Movie.py` — local video

- **Input:** file path. `__init__` validates it exists (`FileNotFoundError` if missing) and computes the ID.
- **ID:** SHA-256 of the content, 16 hex characters — the same file always lands in the same folder, even if renamed.
- **Flow:** `prepare()` → validate that the source has audio → copy the `.mp4` or **convert** other containers (`.mkv`, `.avi`, `.mov`, `.webm`; remux when the codec fits mp4, otherwise re-encode H.264/AAC) → extract `<id>.wav` → remove the audio from the `.mp4` → write the JSON.
- **Original file:** never deleted or moved, only copied.
- **Cache:** same rule as `Link_Movie.py`.

## Generated JSON

```json
{
    "id": "x7X9w_GIm1s",
    "title": "Python in 100 Seconds",
    "duration": 143,
    "uploader": "Fireship",
    "resolution": "1280x720",
    "ext": "mp4",
    "video_path": ".../Data/temp/x7X9w_GIm1s/x7X9w_GIm1s.mp4",
    "audio_path": ".../Data/temp/x7X9w_GIm1s/x7X9w_GIm1s.wav",
    "file_path": ".../Data/temp/x7X9w_GIm1s/x7X9w_GIm1s.mp4"
}
```

- `Local_Movie.py` also includes `source_path` (original file) and uses `uploader: null`.
- `file_path` is an old alias of `video_path`, kept for compatibility.

## Requirements

`ffmpeg` and `ffprobe` on the `PATH` (used to convert, extract the audio, mute the video and read duration/resolution), plus `yt-dlp` for `Link_Movie.py`.
