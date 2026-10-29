# Security policy

## Supported versions

Only the latest commit on `main` is supported.

## Reporting a vulnerability

Please **do not** open a public issue. Use GitHub Security Advisories:

https://github.com/marcosgabrielgomes110-collab/Dubla/security/advisories/new

Include reproduction steps, affected files/endpoints and impact.

## Secrets

- API keys (LLM, ElevenLabs) live only in `.env`, which is git-ignored and created by
  `Scripts/Setup_Llm.py` / `Scripts/Setup_ElevenLabs.py`.
- The HTTP API can require `DUBLA_API_TOKEN`; keep the default bind `127.0.0.1`.
- Logs never include key values; if you find a leak, report it as a vulnerability.
