# Dubla — system architecture

Dubla turns a video (YouTube URL or local file) into a dubbed movie: it separates the audio,
transcribes it with word-level timestamps, translates each speech block, generates a voice per
block, rebuilds the audio track and muxes everything back into the video.

```
URL / local file
   │
   ▼
Dubla_Input ──────────────► Data/temp/<id>/<id>.mp4 (muted) + <id>.wav + <id>.json
   │
   ▼
Dubla_Transcribe ─────────► stt.segments  (word timestamps → speech blocks)
   │
   ▼
Dubla_Translate ──────────► segments_traduct (start/end/text/text_original)
   │
   ▼
Dubla_Voicegen ───────────► voice.segments + Data/temp/<id>/voice/0000.wav ...
   │
   ▼
Dubla_MovieManager ───────► dub track + mux + publish
   │
   ▼
Data/Movies/<id>/
├── <title>_Dubla_pt-BR.mp4
├── <id>_original_mudo.mp4
├── <id>.wav / <id>.json
└── voice/
```

The JSON is the single source of truth and accumulates the stages:

```json
{
  "id": "...", "title": "...", "duration": 143,
  "languages": {"input": "en-US", "output": "pt-BR"},
  "video_path": "...", "audio_path": "...",
  "stt": {"segments": [...], "words": [...]},
  "segments_traduct": [{"start": ..., "end": ..., "text": "...", "text_original": "..."}],
  "voice": {"segments": [{"index": 0, "path": "...", "duration": ..., "overflow": false}]},
  "movie": {"path": "...", "overlaps": 5}
}
```

## Modules

| Module | Responsibility |
| --- | --- |
| `src/Dubla_Config.py` | loads `configs.json`, resolves paths against the project root |
| `src/Dubla_Input/` | YouTube download (`GetLinkMovie`) and local import (`GetLocalMovie`); extracts 16 kHz mono WAV and mutes the MP4 |
| `src/Dubla_Transcribe/` | Vosk and faster-whisper, word timestamps, speech blocks |
| `src/Dubla_Translate/` | deep-translator (Google/MyMemory), Argos (offline) and any OpenAI-compatible LLM |
| `src/Dubla_Voicegen/` | Piper, Pocket TTS, Qwen3-TTS, ElevenLabs, eSpeak NG; timing fit and voice previews |
| `src/Dubla_MovieManager/` | timeline mix, ffmpeg mux, publication and JSON path rewriting |
| `src/Dubla_Api/` | FastAPI app for the frontend (jobs, settings, movies, logs) |
| `etc/Logger.py` | colored terminal logs + daily file in `Data/logs`; JSON mode for the API |
| `Scripts/` | setup (models/voices/LLM/ElevenLabs), CLI helpers and the end-to-end test |

## Data layout

| Path | Content |
| --- | --- |
| `Data/temp/<id>/` | working folder: muted MP4, WAV, JSON, `voice/` |
| `Data/Movies/<id>/` | published movie + working folder (moved) |
| `Data/logs/dubla-YYYY-MM-DD.log` | all logs |
| `Data/api/jobs/<id>.log` | per-job logs from the API |
| `Models/` | Vosk/Whisper/Piper/Pocket/Qwen models (git-ignored) |
| `voices_preview/` | one WAV per voice engine for comparison |

`Data/`, `Models/` and `*.wav` (except the previews) are git-ignored.

## Configuration (`configs.json`)

Main groups:

- **input/output**: `quality_ytdlp`, `temp_path`, `output_path`, `input_language`, `output_language`
- **STT**: `stt_engine`, `stt_whisper_model`, `stt_vosk_model`, thresholds
- **translation**: `translation_engine`, `deep_translator_backend`, batches, retries
- **voice**: `voice_engine`, `voices.<engine>.<lang>`, `voice_fit_speedup_max`, `voice_parallel`
- **mux/publish**: `mux_video_codec`, `mux_overlap`, `publish_overwrite`

Defaults on a CPU-only machine: `whisper`/`base`, `argos`, `piper`.

Secrets are **not** in `configs.json`; they live in `.env` (ignored): `LLM_*` and `ELEVENLABS_*`.

## Install

```bash
pip install -r requirements.txt
sudo pacman -S ffmpeg espeak-ng mpv     # system binaries
pip install -r requirements-dev.txt      # pytest + httpx
```

Optional engines:

```bash
pip install -r requirements-voice-qwen.txt   # Qwen3-TTS (~2.5 GB model)
python Scripts/Setup_Voices.py --engine piper --language pt-BR
python Scripts/Download_Models.py --language en-US
```

## Commands

```bash
# full pipeline (main entry point)
python -m src.Dubla_MovieManager "<url>" [--force]

# end-to-end test with engine overrides
python Scripts/Test_Complete_Pipeline.py whisper base argos piper

# stage helpers
python Scripts/Translate.py Data/temp/<id>/<id>.json --engine argos
python Scripts/Voicegen.py Data/temp/<id>/<id>.json --engine piper

# API
python -m src.Dubla_Api --port 8000

# tests
pytest
```

## Runtime design

- Heavy stages run in a **single subprocess at a time** (`Dubla_MovieManager`), so an OOM or
  crash cannot take down the API.
- Jobs emit **JSON log lines** (`DUBLA_LOG_JSON=1`) that the API parses and streams over SSE.
- The working folder is **moved** on publish: a second run re-downloads the source.
- Video is copied at mux time (no re-encode); audio becomes AAC 48 kHz stereo. AV1 sources stay
  AV1 — mpv plays them, older players may not.
- Translation failures can delete `Data/temp/<id>` (`translation_cleanup_on_error`), by design.

## Tests

`pytest` covers settings validation/atomic write, API auth/jobs/movies/streaming/previews/
secrets, logger JSON mode, segment merging, timing fit, mux and publish. Heavy models are not
loaded in tests; ffmpeg generates the synthetic media.
