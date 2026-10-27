# Dubla_Translate — translation

Turns the speech blocks produced by `Dubla_Transcribe` (`stt.segments`) into translated
blocks written back to the **same `<id>.json`** as `segments_traduct`. The timings are copied
from the transcription so the voice stage can paste each translated line at the right moment.

## Summary

| File | Role |
| --- | --- |
| `__init__.py` | `translate()` dispatcher and engine aliases |
| `Dubla_Translate_Common.py` | json IO, batching, validation, idempotency, cleanup on failure |
| `Dubla_Deep_Translator.py` | `deep-translator`: Google and MyMemory backends |
| `Dubla_Argo_Translate.py` | Argos Translate, fully offline |
| `Dubla_Llm_Translate.py` | any OpenAI-compatible endpoint through the `openai` SDK |

| | |
| --- | --- |
| **Input** | path to `Data/temp/<id>/<id>.json` (or the `.wav`, the `.json` is derived) |
| **Return of `run()`** | `Path` of the json — or `None` on failure |
| **Requires** | a non-empty `stt.segments` in the json |

## Usage

```python
from src.Dubla_Translate import translate

translate("Data/temp/<id>/<id>.json")                          # engine from configs.json
translate(meta, engine="argos")                                # offline
translate(meta, engine="llm")                                  # OpenAI-compatible endpoint
translate(meta, engine="deep-translator", batch_size=10)
translate(meta, force=True)                                    # translate again
```

```bash
python Scripts/Translate.py Data/temp/<id>/<id>.json
python Scripts/Translate.py Data/temp/<id>/<id>.json --engine argos --force
```

Aliases: `google`, `mymemory`, `deep` → `deep-translator`; `offline`, `argostranslate` → `argos`;
`openai`, `openai-like`, `openai-compatible` → `llm`.

## Configuration (`configs.json`)

| Key | Default | Meaning |
| --- | --- | --- |
| `translation_engine` | `deep-translator` | `deep-translator`, `argos` or `llm` |
| `deep_translator_backend` | `mymemory` | `mymemory`, `google` or `auto` |
| `translation_batch_size` | `20` | blocks per request (deep-translator/google and llm) |
| `translation_retries` | `3` | attempts per batch/block |
| `translation_delay` | `0.0` | extra sleep between batches (MyMemory uses at least 0.2 s) |
| `translation_cleanup_on_error` | `true` | delete `Data/temp/<id>` when the translation fails |
| `llm_timeout` | `60` | seconds, passed to the OpenAI client |
| `llm_max_retries` | `2` | HTTP retries inside the OpenAI SDK |

Source/target come from the pipeline: **source** = `stt.language` (detected) with fallback to
`input_language`; **target** = `output_language`. Base codes (`en`, `pt`) are used for the
engines; `target_tag` keeps the full tag (`pt-BR`) for the voice stage.

## LLM setup (`.env`)

The `llm` engine talks to any OpenAI-compatible endpoint through `base_url`:

```dotenv
LLM_PROVIDER=deepseek
LLM_MODEL=deepseek-chat
LLM_API_KEY=sk-...
LLM_BASE_URL=            # optional, overrides the provider preset
LLM_TEMPERATURE=0
```

| Provider | Default `base_url` |
| --- | --- |
| `openai` | `https://api.openai.com/v1` |
| `deepseek` | `https://api.deepseek.com/v1` |
| `groq` | `https://api.groq.com/openai/v1` |
| `openrouter` | `https://openrouter.ai/api/v1` |
| `together` | `https://api.together.xyz/v1` |
| `ollama` | `http://localhost:11434/v1` |
| `lmstudio` | `http://localhost:1234/v1` |

Any other provider requires `LLM_BASE_URL`. Environment variables take precedence over `.env`;
the API key is never logged or written to the json.

Create and validate the file with:

```bash
python Scripts/Setup_Llm.py           # creates .env from .env.example
python Scripts/Setup_Llm.py --ping    # sends a minimal request and prints the masked key
```

`.env` is git-ignored; `.env.example` is versioned with empty fields.

## Engines

| Engine | How | Upside | Limits |
| --- | --- | --- | --- |
| `deep-translator` / `google` | Google web endpoint | free, good quality, batched | often blocked per IP (`TooManyRequests`) |
| `deep-translator` / `mymemory` | MyMemory API | free, no key | ~5,000 characters/day anonymous, slower, lower quality |
| `argos` | local CTranslate2 model | fully offline after install | downloads a language package (~100 MB), needs `torch`, slower start |
| `llm` | `openai` SDK + `base_url` | best context/quality, multi-provider | needs `.env`, costs tokens, network |

- **Batching:** Google/LLM translate up to `translation_batch_size` blocks per request, joined
  with newlines (Google) or as a JSON array (LLM). A mismatch in the returned count splits the
  batch recursively; the LLM also falls back to one block per request.
- **Validation:** every original block must have a non-empty translation, and answers starting
  with “Here is…”, “Translation:”, “Sure,” etc. are rejected.
- **Argos** installs the `from -> to` package automatically on first use
  (`update_package_index` → download → `install_from_path`), then translates block by block.

## LLM prompt

```text
You are a professional subtitle translator.
Translate each string from {source} to {target}.
Return ONLY a JSON array of {count} strings with the translations, in the same order.
Do not add explanations, notes, quotes, labels, markdown or any extra text.
Preserve names, numbers, punctuation and tone; use natural spoken language.
```

Single-block fallback uses the same rules and returns only the translated text.

## JSON written

```json
"segments_traduct": [
    {
        "start": 0.0,
        "end": 0.46,
        "text": "Python,",
        "text_original": "Python,"
    },
    {
        "start": 0.9,
        "end": 5.1,
        "text": "uma linguagem de programação interpretada de alto nível...",
        "text_original": "a high-level, interpreted programming language..."
    }
],
"translation": {
    "engine": "argos",
    "model": "argos",
    "source": "en",
    "target": "pt",
    "target_tag": "pt-BR",
    "segments_count": 28,
    "stt_created_at": "2026-10-26T19:39:00-05:00",
    "created_at": "2026-10-26T20:15:37-05:00"
}
```

- `start`/`end` are copied from `stt.segments`; `text_original` preserves the transcription.
- The `stt` block is never modified.
- The json is written atomically (`<id>.json.tmp` + `os.replace`).

## Idempotency and failure

`run()` returns immediately when `segments_traduct` exists for the same engine/model/languages
and the transcription did not change (`translation.stt_created_at`). Use `force=True` to redo it.

When translation fails **and** `translation_cleanup_on_error` is `true`, the whole working folder
`Data/temp/<id>/` (video, wav, json) is removed to avoid leftovers — this also throws away a valid
download/transcription, so set it to `false` if you prefer to fix the engine and retry.
The removal is refused for any path outside the configured `temp_path`.

## Measured on this machine (12 threads, 7.4 GB RAM, no GPU, 28 blocks / 143 s)

| Engine | Result |
| --- | --- |
| `deep-translator` / Google | blocked: `TooManyRequests` even for one sentence |
| `deep-translator` / MyMemory | 6 blocks in 14 s; 28 blocks hit the daily quota |
| `argos` | 28 blocks in 18.1 s (including the package download), timings preserved |
| `llm` (mock OpenAI server) | 28 blocks in 2 batches (20 + 8), JSON validated |

## Requirements

`deep-translator`, `argostranslate`, `openai`, `python-dotenv` (see `requirements.txt`).
Argos pulls `stanza` → `torch`; on CPU-only machines install torch from the CPU index first:

```bash
pip install torch --index-url https://download.pytorch.org/whl/cpu
pip install argostranslate
```
