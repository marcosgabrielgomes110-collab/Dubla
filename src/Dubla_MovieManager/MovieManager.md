# Dubla_MovieManager — pipeline, mux and publication

Final stage of Dubla and the project entry point: receives a URL, runs every previous stage
and publishes the dubbed movie under `Data/Movies/<id>/`.

## Summary

| File | Role |
| --- | --- |
| `__init__.py` | `run(url)` orchestrator (download → STT → translate → voice → mux → publish) |
| `Dubla_Movie_Mux.py` | builds the dubbed track and muxes it with the muted video |
| `Dubla_Movie_Publish.py` | moves the working folder, renames the video, rewrites json paths |
| `__main__.py` | CLI (`python -m src.Dubla_MovieManager`) |

| | |
| --- | --- |
| **Input** | a video URL (nothing else) |
| **Return** | `Path` of the final dubbed `.mp4` — or `None` on failure |

## Usage

```python
from src.Dubla_MovieManager import run

final = run("https://www.youtube.com/watch?v=x7X9w_GIm1s")
```

```bash
python -m src.Dubla_MovieManager "https://www.youtube.com/watch?v=x7X9w_GIm1s"
python -m src.Dubla_MovieManager "<url>" --force   # redo steps and overwrite the output
```

Engines come from `configs.json`: `stt_engine`, `translation_engine`, `voice_engine`.
Each step is idempotent, so a rerun resumes from the last incomplete stage.

## Output

```
Data/Movies/<id>/
├── <title>_Dubla_pt-BR.mp4     # final dubbed movie (video copied + new AAC audio)
├── <id>_original_mudo.mp4      # original muted video (renamed to avoid confusion)
├── <id>.wav                    # separated audio
├── <id>.json                   # project state (paths rewritten to this folder)
└── voice/                      # one WAV per translated block (0000.wav, ...)
```

- `<id>` is the YouTube id (or the local hash) — the folder requested for the publication.
- `<title>` is the slugified json title (`Python_in_100_Seconds`).
- If the folder already exists: `publish_overwrite=true`/`--force` replaces it, otherwise a
  `_2`, `_3` suffix is used.
- The working folder is **moved** out of `Data/temp`; `Data/temp` is left clean.

## Mux

1. Reads `voice.segments` and `duration`.
2. Builds a float32 timeline of `duration × 24000` samples (≈345 MB per hour).
3. Places each WAV at `round(start × 24000)`, with 10 ms fades.
4. Overlapping blocks are summed (`mux_overlap: "mix"`); the overlap count is logged and stored.
5. Peaks above 1.0 are handled by ffmpeg's `alimiter=limit=0.95` (no global volume drop).
6. Mux:

```bash
ffmpeg -i <id>.mp4 -i dub.wav -map 0:v:0 -map 1:a:0 \
       -c:v copy -c:a aac -b:a 192k -ar 48000 -ac 2 \
       -af alimiter=limit=0.95 -shortest -movflags +faststart <id>_dublado.mp4
```

- Video is copied (no re-encode): an AV1 source stays AV1.
- Audio becomes AAC 48 kHz stereo; the audio stream language tag is set from `output_language`.
- Optional `-16 LUFS` normalization (`mux_loudnorm=true`).
- `mux_created_at` makes the step idempotent.

## Publish

1. `slugify(title)` + `_Dubla_` + `output_language` → final filename.
2. Chooses `Data/Movies/<id>` (or `_2`, `_3`).
3. Moves the whole working folder there.
4. Renames `<id>_dublado.mp4` to the final name and `<id>.mp4` to `<id>_original_mudo.mp4`.
5. Removes the intermediate `dub.wav` (the MP4 already carries the dubbed AAC track).
6. Rewrites the json paths: `video_path`, `file_path`, `audio_path`,
   `voice.segments[].path`, `movie.muxed_path`, `movie.path`, `movie.output_dir`.
7. Writes the json atomically in the new folder and returns the final video path.

## Configuration

| Key | Default | Meaning |
| --- | --- | --- |
| `output_path` | `Data/Movies/` | publication root |
| `mux_overlap` | `mix` | overlap policy (only `mix` implemented) |
| `mux_video_codec` | `copy` | `copy` or re-encode to H.264 |
| `mux_audio_bitrate` | `192k` | AAC bitrate |
| `mux_audio_sample_rate` | `48000` | output audio sample rate |
| `mux_audio_channels` | `2` | output channels |
| `mux_loudnorm` | `false` | normalize to −16 LUFS |
| `publish_overwrite` | `false` | replace an existing output folder |

## Validated on the sample (28 blocks, 143 s, Piper)

- Output: `Python_in_100_Seconds_Dubla_pt-BR.mp4`, 6.5 MB.
- Streams: AV1 video (copied) + AAC 48 kHz stereo, duration 143.3 s.
- 6 overlapping blocks mixed, original peak 1.35 handled by the limiter.
- Working folder moved to `Data/Movies/x7X9w_GIm1s/`; `Data/temp` empty.
- json paths all point to existing files after the move.

## Notes

- The `run()` defaults come from `configs.json`: `whisper` (`base`), `argos` and `piper`.
  Vosk and deep-translator remain available but are not the default.
- AV1 in MP4 is valid but not supported by every old player; set `mux_video_codec` to
  re-encode H.264 if needed.
- The working folder is moved, not copied: a second run re-downloads the source.
