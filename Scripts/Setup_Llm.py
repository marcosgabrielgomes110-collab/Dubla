"""Create/validate the .env used by the "llm" translation engine.

Examples:
    python Scripts/Setup_Llm.py            # create .env if missing and ping the provider
    python Scripts/Setup_Llm.py --ping     # only ping the existing .env
"""

import argparse
import shutil
import sys
from pathlib import Path

__root__ = Path(__file__).parent.parent
if str(__root__) not in sys.path:
    sys.path.insert(0, str(__root__))

from etc.Logger import log_error, log_info, log_ok  # noqa: E402
from src.Dubla_Config import ENV_PATH, LLM_MAX_RETRIES, LLM_TIMEOUT  # noqa: E402
from src.Dubla_Translate.Dubla_Llm_Translate import PROVIDER_BASE_URLS  # noqa: E402


def mask(value: str) -> str:
    if not value:
        return "(empty)"
    if len(value) <= 8:
        return "***"
    return f"{value[:4]}...{value[-4:]}"


def main() -> int:
    parser = argparse.ArgumentParser(description="Setup the OpenAI-compatible LLM in .env")
    parser.add_argument("--ping", action="store_true", help="only validate the existing .env")
    args = parser.parse_args()

    if not ENV_PATH.exists():
        example = __root__ / ".env.example"
        if not example.is_file():
            log_error(f".env.example not found: {example}")
            return 1
        shutil.copy(example, ENV_PATH)
        log_ok(f".env created from .env.example: {ENV_PATH}")
        if args.ping:
            log_error("edit .env and run again")
            return 1
    else:
        log_info(f"using existing .env: {ENV_PATH}")

    try:
        from dotenv import load_dotenv
        import os
    except ImportError:
        log_error("python-dotenv is not installed: pip install python-dotenv")
        return 1

    load_dotenv(ENV_PATH, override=True)

    provider = (os.getenv("LLM_PROVIDER") or "").strip().lower()
    model = (os.getenv("LLM_MODEL") or "").strip()
    api_key = (os.getenv("LLM_API_KEY") or "").strip()
    base_url = (os.getenv("LLM_BASE_URL") or "").strip()

    if not base_url and provider:
        base_url = PROVIDER_BASE_URLS.get(provider, "")

    log_info(f"provider: {provider or '(custom)'}")
    log_info(f"model:    {model or '(empty)'}")
    log_info(f"base_url: {base_url or '(empty)'}")
    log_info(f"api_key:  {mask(api_key)}")

    if not model:
        log_error("LLM_MODEL is empty in .env")
        return 1
    if not base_url:
        known = ", ".join(PROVIDER_BASE_URLS)
        log_error(f"LLM_BASE_URL is empty; set it or use one of: {known}")
        return 1
    if not api_key and provider not in ("ollama", "lmstudio"):
        log_error("LLM_API_KEY is empty in .env")
        return 1

    try:
        from openai import OpenAI
    except ImportError:
        log_error("openai is not installed: pip install openai")
        return 1

    if not args.ping:
        log_info("run with --ping to test the endpoint")
        return 0

    try:
        client = OpenAI(
            api_key=api_key or "not-needed",
            base_url=base_url,
            timeout=LLM_TIMEOUT,
            max_retries=LLM_MAX_RETRIES,
        )
        response = client.chat.completions.create(
            model=model,
            temperature=0,
            max_tokens=5,
            messages=[{"role": "user", "content": "Reply with OK"}],
        )
        content = response.choices[0].message.content if response.choices else ""
        log_ok(f"provider answered: {content!r}")
        return 0
    except Exception as e:
        log_error(f"ping failed: {e}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
