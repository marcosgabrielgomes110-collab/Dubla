# Dubla_Transcribe — speech to text

Turns the separated audio (`<id>.wav`, 16 kHz mono) into timestamped speech blocks and
writes them into the **same `<id>.json`** produced by `Dubla_Input`. Those blocks are the
input for the next stages: translate → generate voice → paste each line at its exact time.

## Summary

| File | Role |
| --- | --- |
| `Dubla_Stt_Common.py` | language/locale handling, Vosk model registry, hardware policy, model download, word → speech-block merge, json IO |
| `Dubla_Stt_vosk.py` | `VoskStt` engine |
| `Dubla_Stt_whisper.py` | `WhisperStt` engine (faster-whisper) |
| `__init__.py` | `transcribe()` dispatcher and exports |

| | |
| --- | --- |
| **Input** | path to `Data/temp/<id>/<id>.wav` (created by `Dubla_Input`) |
| **Return of `run()`** | `Path` of `<id>.json` — or `None` on failure |

The json must already exist next to the wav (it carries `audio_path`, `languages`, etc.).

## Usage

```python
from src.Dubla_Transcribe import transcribe, VoskStt, WhisperStt

# engine chosen from configs.json + hardware ("auto")
transcribe("Data/temp/<id>/<id>.wav")

# force a specific engine
VoskStt("Data/temp/<id>/<id>.wav").run()
WhisperStt("Data/temp/<id>/<id>.wav", model="base").run()

# detect the language with whisper (Vosk cannot detect it)
transcribe(wav, engine="whisper", language="auto")

# redo an existing transcription
transcribe(wav, force=True)
```

`transcribe(wav, engine=..., language=..., model=..., force=False)` accepts
`engine` = `auto` | `vosk` | `whisper` (also `faster-whisper`), `model` = Vosk tier/name
(`small`, `large`, `vosk-model-...`) or whisper size (`tiny`, `base`, `small`, `medium`, `large-v3`).

## Configuration (`configs.json`)

| Key | Default | Meaning |
| --- | --- | --- |
| `input_language` | `en-US` | spoken language of the video; decides which model is downloaded |
| `output_language` | `pt-BR` | target language for the later translation stage (not used by STT) |
| `stt_engine` | `auto` | `auto`, `vosk` or `whisper` |
| `stt_vosk_model` | `auto` | `small`, `large` or an explicit `vosk-model-...` |
| `stt_whisper_model` | `auto` | whisper size, or `auto` for the hardware policy |
| `stt_whisper_device` | `auto` | `cpu` or `cuda` |
| `stt_whisper_compute` | `auto` | `int8`, `float16`, `int8_float16`, `float32` |
| `stt_min_pause` | `0.35` | silence (s) that closes a speech block |
| `stt_min_segment` | `0.4` | blocks shorter than this are dropped (0 keeps everything) |
| `stt_max_segment` | `12.0` | maximum block length (s) |
| `stt_offline` | `false` | `true` forbids downloading models |
| `Vosk_model_path` | `Models/vosk` | Vosk models directory |
| `Whisper_model_path` | `Models/whisper` | faster-whisper models directory |

Locales are normalized: `pt-BR`, `pt_br`, `pt-pt` → `pt` for model choice, while the full
tag stays in `languages.input` for the voice stage. `input_language: "auto"` forces Whisper.

## Engine selection (`stt_engine: "auto"`)

1. `input_language == "auto"` → **whisper** (Vosk needs a fixed language).
2. No Vosk model for that language → **whisper**.
3. NVIDIA GPU present → **whisper**.
4. 8+ CPU threads and 16+ GB RAM → **whisper**.
5. Otherwise → **vosk** (low memory, fast on CPU).

Whisper size for `stt_whisper_model: "auto"`:

| Hardware | Model | compute |
| --- | --- | --- |
| GPU ≥ 10 GB VRAM | `large-v3` | float16 |
| GPU 6–10 GB | `medium` | float16 |
| GPU 4–6 GB | `small` | float16 |
| GPU < 4 GB | `base` | int8_float16 |
| CPU 8+ threads, RAM ≥ 16 GB | `small` | int8 |
| CPU 8+ threads, RAM 8–16 GB | `base` | int8 |
| weaker CPU | `tiny` | int8 |

## Models

- **Vosk:** registry with 30+ languages; each entry has the official download name, URL and
  size. Most small models are 30–80 MB (a few language packs are larger); `pt` also has a
  1.6 GB `large` model.
  Models are extracted to `Models/vosk/<model-name>/` (zip validated, zip-slip guarded).
- **Whisper:** `Systran/faster-whisper-<size>` from HuggingFace into `Models/whisper/<size>/`.
  The model itself is multilingual, so no per-language download.
- Downloads happen on the first `run()` when the model is missing, or ahead of time:

```bash
python Scripts/Download_Models.py --list
python Scripts/Download_Models.py --language pt-BR
python Scripts/Download_Models.py --engine whisper --model base
python Scripts/Download_Models.py --all
```

`Models/` is git-ignored.

## Timestamps

Both engines run with word-level timestamps:

- **Vosk:** `SetWords(True)`, WAV fed in 0.5 s chunks; frame-accurate (~30 ms) but the text
  comes lowercase and **without punctuation**.
- **Whisper:** `word_timestamps=True`, `vad_filter=True` (Silero), `beam_size=5`,
  `temperature=0`, `condition_on_previous_text=False` (avoids drift on long audio).

Then the words are merged into blocks:

- break when silence > `stt_min_pause`, when the block would exceed `stt_max_segment`,
  or right after `. ! ? …`;
- `start` = first word start, `end` = last word end, rounded to 3 decimals;
- blocks shorter than `stt_min_segment` are dropped as noise (`0` disables);
- hyphenated tokens stay attached (`high-level`) and CJK languages are joined without spaces.

## JSON written

```json
{
    "id": "x7X9w_GIm1s",
    "languages": {"input": "en-US", "output": "pt-BR"},
    "stt": {
        "engine": "whisper",
        "model": "faster-whisper-base",
        "language": "en",
        "language_detected": null,
        "device": "cpu",
        "audio": {"path": ".../<id>.wav", "size": 4586734, "mtime_ns": 1761...},
        "created_at": "2026-10-26T19:36:05-05:00",
        "segments": [
            {"start": 0.0, "end": 0.46, "text": "Python,"},
            {"start": 0.9, "end": 5.1, "text": "a high-level, interpreted programming language..."}
        ],
        "words": [
            {"start": 0.0, "end": 0.24, "word": "Python", "conf": 0.87}
        ]
    }
}
```

- `segments` is the dubbing timeline; `words` keeps per-word timings for fine alignment.
- `file_path` / `video_path` / `audio_path` from `Dubla_Input` are preserved.
- The json is written atomically (`<id>.json.tmp` + `os.replace`).

## Idempotency

`run()` returns immediately when `stt` already exists for the **same engine + model** and the
WAV did not change (`size` + `mtime_ns`). Use `force=True` to redo it — for example to compare
Vosk and Whisper on the same file (the last run wins).

## Measured on this machine (12 threads, 7.4 GB RAM, no GPU, 143 s sample)

| Engine | Model | Time | RTF | Blocks | Avg block |
| --- | --- | --- | --- | --- | --- |
| Vosk | `vosk-model-small-en-us-0.15` | 7.85 s | 0.055 | 12 | 11.8 s |
| Whisper | `faster-whisper-base` | 9.95 s | 0.07 | 28 | 4.8 s |
| Whisper | `faster-whisper-tiny` | 7.3 s | 0.05 | 28 | 4.8 s |

Vosk is marginally faster but produces lower-case, unpunctuated text with more errors and
longer blocks (it hits `stt_max_segment`). Whisper `base` gives punctuated, capitalized text
and ~5 s blocks for ~27% more time.

## Notes

- `faster-whisper` normally decodes audio with PyAV, but PyAV 19 (the wheel for Python 3.14)
  rejects the `metadata_errors` argument it passes. `WhisperStt` therefore decodes the WAV with
  `wave` + NumPy (falling back to `ffmpeg`) and feeds a float32 array to the model.
- Vosk only accepts 16 kHz mono 16-bit PCM — exactly what `Dubla_Input` produces.
- No punctuation restoration is applied to Vosk output (by design; the translation stage handles raw text).
