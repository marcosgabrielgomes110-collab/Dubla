# Dubla — documentation

| Document | Content |
| --- | --- |
| [SYSTEM.md](SYSTEM.md) | architecture, modules, data layout, configuration, install and commands |
| [API.md](API.md) | HTTP API reference (FastAPI), jobs, SSE, settings, secrets, movies |

Per-module documents live next to the code:

- `src/Dubla_Input/Downloads-Local.md`
- `src/Dubla_Transcribe/Transcribe.md`
- `src/Dubla_Translate/translate.md`
- `src/Dubla_Voicegen/Voicegen.md`
- `src/Dubla_MovieManager/MovieManager.md`
- `src/Dubla_Api/Api.md`

---

## Quick start

```bash
make install                # python + npm deps
make up                     # API + Vite dev in background
make logs                   # follow both logs
make stop                   # stop both

make up-prod                # build frontend and serve it from the API
make all                    # install + build + pytest
```

Manual:

```bash
pip install -r requirements.txt
pip install -r requirements-dev.txt        # tests only

# one-shot pipeline from a URL
python -m src.Dubla_MovieManager "https://www.youtube.com/watch?v=..."

# API + docs at http://127.0.0.1:8000/docs
python -m src.Dubla_Api

# frontend (dev) at http://localhost:5173
cd frontend && npm install && npm run dev

# tests
pytest
```

Default engines: **Whisper `base`** (STT), **Argos** (translation) and **Piper** (voice).
