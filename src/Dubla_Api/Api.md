# Dubla_Api — HTTP API

FastAPI service for the future frontend: settings, pipeline jobs, scripts, published movies,
logs and voice previews. Heavy work runs in **subprocesses** (one at a time) so a crash/OOM
never takes the API down, and every job streams structured logs.

## Run

```bash
python -m src.Dubla_Api                 # 127.0.0.1:8000
python -m src.Dubla_Api --port 9000 --reload
# or
uvicorn src.Dubla_Api.main:app --host 127.0.0.1 --port 8000
```

OpenAPI docs: `http://127.0.0.1:8000/docs`.

Environment:

| Variable | Default | Meaning |
| --- | --- | --- |
| `DUBLA_API_TOKEN` | empty | if set, every `/api/v1/*` request needs `X-API-Token` (except `/health`) |
| `DUBLA_CORS_ORIGINS` | `http://localhost:5173,http://localhost:3000,http://127.0.0.1:5173` | comma-separated origins |

## Endpoints (`/api/v1`)

| Method | Path | Description |
| --- | --- | --- |
| GET | `/health` | liveness |
| GET | `/system/info` | python, binaries, packages, disk and memory |
| GET | `/system/logs?date=&tail=` | `Data/logs` listing/tail |
| GET | `/system/previews` | WAV previews per voice engine |
| GET | `/system/previews/{name}` | preview audio |
| GET | `/settings` | current `configs.json` |
| PATCH | `/settings` | `{"values": {...}}` validated patch (atomic + `.bak`) |
| GET | `/settings/schema` | enums/ranges for the frontend forms |
| GET | `/secrets` | masked status of LLM/ElevenLabs keys |
| PUT | `/secrets/{key}` | `{"value": "..."}` writes `.env` |
| DELETE | `/secrets/{key}` | removes the key |
| POST | `/jobs` | create a job |
| GET | `/jobs?limit=&status=` | job history |
| GET | `/jobs/{id}` | status/result |
| GET | `/jobs/{id}/logs?tail=` | last log events |
| GET | `/jobs/{id}/events` | **SSE** log + status stream |
| POST | `/jobs/{id}/cancel` | terminate the subprocess |
| GET | `/movies` | published movies |
| GET | `/movies/{id}` | project json |
| GET | `/movies/{id}/video` | MP4 streaming with `Range` |
| DELETE | `/movies/{id}` | removes the folder |
| POST | `/models` (job) | downloads voices/models |

### Job types

```json
{"type": "pipeline", "url": "https://...", "params": {"force": false}}
{"type": "script", "name": "test_pipeline", "params": {"force": false}}
{"type": "models", "params": {"engine": "piper", "languages": ["pt-BR"]}}
```

Allowed scripts: `test_pipeline`, `setup_voices`, `download_models`. Commands are built
server-side (no `shell=True`, no arbitrary argv).

### SSE example

```bash
curl -N -H "X-API-Token: $DUBLA_API_TOKEN" \
  http://127.0.0.1:8000/api/v1/jobs/<id>/events
```

Each line is a JSON log event (`ts`, `level`, `source`, `message`); `event: status` announces
`queued|running|succeeded|failed|cancelled`.

## Settings

`PATCH /settings` accepts any key from `GET /settings/schema`; unknown keys or invalid values
return `400`. The write is atomic (`configs.json.tmp` + replace) and keeps a `.bak`.
Jobs read the settings when they start, so a patch affects the next job.

## Movies

- `GET /movies` scans `Data/Movies/<id>/`.
- The final video is `<title>_Dubla_<lang>.mp4`; the muted source is
  `<id>_original_mudo.mp4`; `dub.wav` is removed on publish.
- `GET /movies/{id}/video` supports `Range` (206) for browser players.
- IDs are validated (`^[A-Za-z0-9_-]{1,64}$`) and resolved under the output root.

## Security

- Binds to `127.0.0.1` by default.
- Optional token via `DUBLA_API_TOKEN`; health/docs/root stay public, CORS preflight allowed.
- Path traversal blocked for movies and previews.
- Secrets are written to `.env` (chmod 600) and never returned in clear text.

## Tests

```bash
pip install -r requirements-dev.txt
pytest
```

Coverage: settings validation/atomic write, jobs lifecycle/cancel, movies list/range/delete,
previews, secrets masking, auth, video mux, publish (rename/paths/dub cleanup), segment merge,
timing fit and JSON logging. Heavy ML is not executed in tests.

## Limitations

- Jobs are kept in memory (history is lost on restart); per-job logs remain in `Data/api/jobs/`.
- A single job runs at a time by design (RAM).
- The API does not serve the frontend bundle; use CORS during development.
