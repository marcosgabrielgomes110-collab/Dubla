# Dubla frontend

React 19 + Vite + TypeScript + Tailwind CSS v4 (shadcn-style components), React Router,
TanStack Query and SSE for live job logs.

## Pages

| Route | Content |
| --- | --- |
| `/` | dashboard: system info, disk/RAM, recent jobs, voice previews |
| `/pipeline` | URL + engine/model/voice form, live logs (SSE), cancel |
| `/movies` | published movies, range-streamed player, download, delete |
| `/models` | model/voice downloads and voice previews |
| `/settings` | configs.json form generated from `/settings/schema` |
| `/secrets` | masked LLM/ElevenLabs keys |

## Development

```bash
npm install
npm run dev          # http://localhost:5173 (proxies /api to 127.0.0.1:8000)
```

Or from the repository root:

```bash
make up              # API + Vite dev
make logs
make stop
```

Start the API separately:

```bash
python -m src.Dubla_Api --port 8000
```

If the API uses `DUBLA_API_TOKEN`, paste the token in **Configurações → Token da API**
(stored in localStorage; sent as `X-API-Token` and as `?token=` for media URLs).

## Build (served by FastAPI)

```bash
npm run build        # tsc --noEmit && vite build -> dist/
python -m src.Dubla_Api --port 8000
# UI at http://127.0.0.1:8000/ (SPA fallback enabled when frontend/dist exists)
```

`VITE_API_BASE` can override the API prefix at build time (default `/api/v1`).

## Notes

- The video player uses the API's `Range` support.
- Jobs are created with `POST /jobs`; logs arrive via `GET /jobs/{id}/events` (SSE).
- Settings changes are applied to the **next** job.
