# Dubla_Voicegen — voice generation

Turns every block of `segments_traduct` into an audio file with word-level timing already
fixed by the transcription, fits it into the original slot and writes the `voice` block back
to the same `<id>.json`.

## Summary

| File | Role |
| --- | --- |
| `__init__.py` | `synthesize()` dispatcher and engine aliases |
| `Dubla_Voice_Common.py` | config, voice catalog, timeline fit, parallel pool, json IO |
| `Dubla_Voice_piper.py` | Piper (local, CPU) |
| `Dubla_Voice_pocket.py` | Pocket TTS (local, CPU, 7 languages) |
| `Dubla_Voice_qwen.py` | Qwen3-TTS 0.6B CustomVoice (local, heavy) |
| `Dubla_Voice_elevenlabs.py` | ElevenLabs (cloud) |
| `Dubla_Voice_espeak.py` | eSpeak NG (robotic fallback) |

| | |
| --- | --- |
| **Input** | `Data/temp/<id>/<id>.json` with `segments_traduct` (or the `.wav` path) |
| **Return** | `Path` of the json — or `None` on failure |
| **Output files** | `Data/temp/<id>/voice/0000.wav`, `0001.wav`, ... (WAV PCM, mono, 24 kHz) |

## Usage

```python
from src.Dubla_Voicegen import synthesize

synthesize("Data/temp/<id>/<id>.json")                 # engine from configs.json
synthesize(meta, engine="piper")
synthesize(meta, engine="elevenlabs", force=True)
synthesize(meta, engine="espeak", voice="pt-br")
```

```bash
python Scripts/Voicegen.py Data/temp/<id>/<id>.json --engine piper
```

Aliases: `pocket-tts` → `pocket`, `qwen3-tts` → `qwen`, `eleven` → `elevenlabs`,
`espeak-ng`/`robot` → `espeak`.

## Configuration (`configs.json`)

| Key | Default | Meaning |
| --- | --- | --- |
| `voice_engine` | `piper` | default engine |
| `voice_fit_speedup_max` | `1.35` | max `atempo` to fit the slot; beyond that = `overflow` |
| `voice_pad_silence` | `false` | pad short audio to the full slot |
| `voice_sample_rate` | `24000` | output sample rate for every engine |
| `voice_parallel` | `false` | use threads to synthesize blocks in parallel |
| `voice_workers` | `4` | thread workers (1–16) |
| `voices.<engine>.<lang>` | see below | voice/model per language |

Voice language comes from `output_language` (`pt-BR` → `pt`).

## Engines

| Engine | Setup | Voices | Limits |
| --- | --- | --- | --- |
| **Piper** | `pip install piper-tts`; voices via `python -m piper.download_voices <voice> --download-dir Models/piper` | 178 voices, 30+ languages | CPU, < 500 MB RAM, ~61 MB per medium voice |
| **Pocket TTS** | `pip install pocket-tts` (uses torch) | 7 languages: en, fr, de, pt, it, es, nl | CPU, 1–3 GB RAM, model downloaded on first use |
| **Qwen3-TTS** | `pip install -r requirements-voice-qwen.txt` + torch/torchaudio CPU | 10 languages, 9 speakers | 2.5 GB model, 4–8 GB RAM, slow on CPU |
| **ElevenLabs** | `pip install elevenlabs` + `Scripts/Setup_ElevenLabs.py` | 70+ languages (voice ids from the account) | cloud, API key, free plan: 2 concurrent requests, library voices need paid plan |
| **eSpeak NG** | `sudo pacman -S espeak-ng` | many languages, robotic | < 100 MB RAM, offline, lowest quality |

Catalog defaults (`configs.json → voices`):

| Lang | Piper | Pocket | Qwen | eSpeak |
| --- | --- | --- | --- | --- |
| pt | `pt_BR-faber-medium` | `rafael` | `Ryan` | `pt-br` |
| en | `en_US-lessac-medium` | `alba` | `Ryan` | `en-us` |
| es | `es_ES-davefx-medium` | `lola` | — | `es` |
| fr | `fr_FR-siwis-medium` | `estelle` | — | `fr-fr` |
| de | `de_DE-thorsten-medium` | — | — | `de` |
| it | `it_IT-paola-medium` | `giovanni` | — | `it` |
| ja | `ja_JP-hi_fi_captain-medium` | — | — | `ja` |
| zh | `zh_CN-huayan-medium` | — | — | `cmn` |

## Setup scripts

```bash
python Scripts/Setup_Voices.py --list
python Scripts/Setup_Voices.py --engine piper --language pt-BR
python Scripts/Setup_Voices.py --engine pocket --language pt-BR
python Scripts/Setup_Voices.py --engine qwen            # 2.5 GB
python Scripts/Setup_ElevenLabs.py                      # creates .env keys
python Scripts/Setup_ElevenLabs.py --list-voices
python Scripts/Setup_ElevenLabs.py --ping
```

ElevenLabs keys live in `.env` (git-ignored):

```dotenv
ELEVENLABS_API_KEY=
ELEVENLABS_MODEL=eleven_multilingual_v2
ELEVENLABS_VOICE_ID_PT=
ELEVENLABS_VOICE_ID_EN=
ELEVENLABS_OUTPUT_FORMAT=mp3_44100_128
ELEVENLABS_MAX_CONCURRENCY=2
```

## Timing fit

- `target = end - start` of the translated block.
- If the generated audio is longer: `atempo = duration / target` up to
  `voice_fit_speedup_max`; if it still does not fit, the block is marked `overflow` and the
  audio is kept intact (the mux decides what to do).
- If shorter: left untouched (optional silence pad with `voice_pad_silence`).
- 10 ms fades are applied when the dub timeline is built (mux), not in the WAV files.

## Parallelism

`voice_parallel=true` uses `ThreadPoolExecutor` with `voice_workers`:

- **Piper / Pocket / Qwen:** local inference is serialized with a lock (parallel runs were
  slower and produced different durations).
- **ElevenLabs:** real concurrency, capped by `ELEVENLABS_MAX_CONCURRENCY` (free plan = 2) and
  retried on HTTP 429.
- **eSpeak:** real concurrency (each block is a subprocess).

## JSON written

```json
"voice": {
    "engine": "piper",
    "voice": "pt_BR-faber-medium",
    "language": "pt-BR",
    "sample_rate": 24000,
    "translation_created_at": "2026-10-26T20:15:37-05:00",
    "created_at": "2026-10-26T21:19:26-05:00",
    "segments": [
        {"index": 0, "start": 0.0, "end": 0.46, "path": ".../voice/0000.wav",
         "duration": 0.47, "speed": 1.312, "fits": true, "overflow": false}
    ]
}
```

`stt` and `segments_traduct` are never modified. Idempotency compares engine, voice,
language, `translation_created_at` and the existence of every WAV.

## Measured on this machine (12 threads, 7.4 GB RAM, no GPU)

| Engine | Test | Result |
| --- | --- | --- |
| Piper | 28 blocks / 143 s | 15.8 s, 22 fits, 6 overflow |
| Pocket | 28 blocks / 143 s | 66.5 s, 12 fits, 16 overflow |
| eSpeak | 28 blocks | 4.3 s serial, 1.45 s with 4 workers |
| ElevenLabs | 3 blocks | 4.0 s with 2 workers (free plan) |
| Qwen3-TTS | 1 phrase | 112.5 s on CPU (bfloat16, `max_new_tokens=256`) |
| one phrase each | previews | Piper 1.7 s, Pocket 5.2 s, ElevenLabs 4.2 s, eSpeak 0.1 s |

`voices_preview/` keeps one WAV per engine with the same sentence for comparison.

## Requirements

`piper-tts`, `pocket-tts`, `elevenlabs`, `scipy`, plus `torch` (already required by Argos).
eSpeak NG is a system package. Qwen is optional (`requirements-voice-qwen.txt`).
