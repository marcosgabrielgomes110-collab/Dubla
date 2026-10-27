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
pip install -r requirements.txt
pip install -r requirements-dev.txt        # tests only

# one-shot pipeline from a URL
python -m src.Dubla_MovieManager "https://www.youtube.com/watch?v=..."

# API + docs at http://127.0.0.1:8000/docs
python -m src.Dubla_Api

# tests
pytest
```

Default engines: **Whisper `base`** (STT), **Argos** (translation) and **Piper** (voice).
