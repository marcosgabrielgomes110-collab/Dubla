# Contributing

Thanks for helping with Dubla.

## Setup

```bash
git clone git@github.com:marcosgabrielgomes110-collab/Dubla.git
cd Dubla
make install          # pip install -e .[dev] + npm install
```

System binaries: `ffmpeg`, `ffprobe`, `mpv` and (optional) `espeak-ng`.

## Running

```bash
make up               # API :8000 + Vite :5173
make up-prod          # build + API serving the SPA
make logs             # follow both logs
make stop
```

## Tests

```bash
pytest                # backend (28 tests)
make test
cd frontend && npm run build
make all              # install + build + test
```

CI runs pytest on Python 3.12 and the frontend build on Node 22.

## Code style

- Python: 4 spaces, type hints where practical, `ruff` config in `pyproject.toml`.
- Frontend: TypeScript strict, Tailwind utility classes, components in `src/components`.
- Keep user-facing strings in Portuguese in the UI and English in code/logs (consistent with
  the existing modules).
- Never commit secrets, `Data/`, `Models/`, `frontend/node_modules` or `frontend/dist`.

## Pull requests

- One logical change per PR, with a clear description.
- Update the relevant docs (`docs/`, module `.md`, `README.md`).
- Add or adjust tests when behavior changes.
- Use the PR template checklist.

## Dependencies

Canonical dependencies live in `pyproject.toml`:

- runtime: `[project].dependencies`
- dev/test: `[project.optional-dependencies].dev`
- Qwen3-TTS: `.[qwen]`

`requirements*.txt` are compatibility shims.
