# Dubla — HTTP API reference

FastAPI service for the future frontend. Base URL: `http://127.0.0.1:8000/api/v1`.
Interactive docs: `/docs` (Swagger) and `/redoc`.

```bash
python -m src.Dubla_Api --port 8000
# or
uvicorn src.Dubla_Api.main:app --host 127.0.0.1 --port 8000
```

Heavy work runs in a **single subprocess at a time**; the API stays responsive and streams
structured logs. Jobs are kept in memory (per-job logs remain in `Data/api/jobs/<id>.log`).

## Authentication

Optional. Set `DUBLA_API_TOKEN` and send `X-API-Token` on every request except `/health`.

```bash
curl -H "X-API-Token: $DUBLA_API_TOKEN" http://127.0.0.1:8000/api/v1/settings
```

CORS origins: `DUBLA_CORS_ORIGINS` (default `http://localhost:5173,http://localhost:3000`).

## System

| Method | Path | Description |
| --- | --- | --- |
| GET | `/health` | `{"status":"ok","service":"dubla-api"}` |
| GET | `/system/info` | python, ffmpeg/mpv/espeak paths, installed packages, disk, memory |
| GET | `/system/logs?date=YYYY-MM-DD&tail=200` | tail of `Data/logs/dubla-<date>.log` |
| GET | `/system/previews` | list of `voices_preview/*.wav` |
| GET | `/system/previews/{name}` | WAV audio |

## Settings

| Method | Path | Description |
| --- | --- | --- |
| GET | `/settings` | current `configs.json` |
| GET | `/settings/schema` | enums, ranges and descriptions for forms |
| PATCH | `/settings` | partial validated update |

```json
PATCH /api/v1/settings
{"values": {"stt_engine": "whisper", "voice_workers": 4}}
```

- Unknown keys → `400`.
- Enums/ranges are validated (`voice_workers` 1–16, `stt_engine` auto/vosk/whisper, ...).
- Write is atomic (`configs.json.tmp` + replace) and keeps `configs.json.bak`.
- Running jobs keep the settings they started with; the next job picks up the patch.

## Secrets

Keys never leave the server in clear text.

| Method | Path | Body | Effect |
| --- | --- | --- | --- |
| GET | `/secrets` | — | `{"LLM_API_KEY": {"set": true, "preview": "sk-t...abcd"}}` |
| PUT | `/secrets/{key}` | `{"value": "..."}` | writes `.env` (chmod 600) |
| DELETE | `/secrets/{key}` | — | removes the key |

Allowed keys: `LLM_PROVIDER`, `LLM_MODEL`, `LLM_API_KEY`, `LLM_BASE_URL`,
`ELEVENLABS_API_KEY`, `ELEVENLABS_MODEL`, `ELEVENLABS_VOICE_ID_PT`,
`ELEVENLABS_VOICE_ID_EN`.

## Jobs

| Method | Path | Description |
| --- | --- | --- |
| POST | `/jobs` | create a job |
| GET | `/jobs?limit=50&status=` | recent jobs |
| GET | `/jobs/{id}` | status, result, timings |
| GET | `/jobs/{id}/logs?tail=200` | last log events |
| GET | `/jobs/{id}/events` | SSE stream (logs + status) |
| POST | `/jobs/{id}/cancel` | terminate the process group |

### Create

```json
{"type": "pipeline", "url": "https://www.youtube.com/watch?v=...", "params": {"force": false}}
{"type": "script", "name": "test_pipeline", "params": {"force": true}}
{"type": "models", "params": {"engine": "piper", "languages": ["pt-BR"]}}
```

Allowed scripts: `test_pipeline`, `setup_voices`, `download_models`. Commands are built
server-side from the allowlist (no shell, no arbitrary argv).

### Status model

```
queued → running → succeeded | failed | cancelled
```

`result` is the final video path for pipeline jobs. `error` carries the exit code/message.

### SSE

```bash
curl -N -H "X-API-Token: $DUBLA_API_TOKEN" \
  http://127.0.0.1:8000/api/v1/jobs/<id>/events
```

```
data: {"ts": "...", "level": "info", "source": "MovieManager", "message": "pipeline start: ..."}

event: status
data: {"status": "running"}
```

The stream ends after a terminal status.

## Movies

| Method | Path | Description |
| --- | --- | --- |
| GET | `/movies` | published movies (id, title, language, duration, size, video) |
| GET | `/movies/{id}` | full project json |
| GET | `/movies/{id}/video` | MP4 streaming with `Range` |
| DELETE | `/movies/{id}` | removes `Data/Movies/<id>` |

`GET /movies/{id}/video` supports `Range: bytes=start-end` and answers `206` with
`Content-Range`, suitable for `<video>` in the browser.

```bash
curl -H "Range: bytes=0-1023" -o chunk.mp4 \
  http://127.0.0.1:8000/api/v1/movies/x7X9w_GIm1s/video
```

IDs are validated (`^[A-Za-z0-9_-]{1,64}$`) and resolved inside the output folder.

## Errors

| Code | When |
| --- | --- |
| 400 | invalid payload, unknown setting/secret, invalid movie id, script not allowed |
| 401 | missing/wrong `X-API-Token` |
| 404 | job/movie/preview/log not found |
| 416 | invalid `Range` header |

Errors use FastAPI's shape: `{"detail": "..."}`.

## Tests

```bash
pip install -e ".[dev]"
pytest
```

The suite covers settings, auth, jobs/cancel, SSE-adjacent logs, movies/Range/delete,
previews, secrets masking, logger JSON mode, mux and publish. ffmpeg builds the synthetic
media; no heavy model is loaded.

## Limitations

- One job at a time (RAM constraint).
- In-memory job history (logs persist on disk).
- No upload endpoint; input is a URL.
- When `frontend/dist` exists, the API serves the built SPA at `/` (fallback for client routes);
  in development run Vite separately with CORS.
