# Changelog

All notable changes to Dubla are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and
[Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.1.0] - 2026-10-27

### Added

- Input pipeline: YouTube download (`yt-dlp`) and local files, audio split to 16 kHz mono WAV,
  muted MP4, stable id per video.
- Speech-to-text with Vosk and faster-whisper, word-level timestamps and speech blocks.
- Translation with deep-translator (Google/MyMemory), Argos (offline) and any OpenAI-compatible
  LLM via the `openai` SDK.
- Voice generation with Piper, Pocket TTS, Qwen3-TTS, ElevenLabs and eSpeak NG; per-language
  voice catalog, timing fit and optional parallel workers.
- Final mux (copied video + AAC 48 kHz stereo, overlap mix, limiter) and publication under
  `Data/Movies/<id>/` with JSON path rewriting.
- FastAPI service: settings, secrets, jobs in subprocesses with JSON logs/SSE, movies with
  Range streaming, logs and voice previews.
- React 19 + Vite + TypeScript frontend (dashboard, pipeline live logs, movies, settings,
  secrets, voices).
- `Makefile` targets, pytest suite, docs and project tooling (MIT license, CI, templates).
