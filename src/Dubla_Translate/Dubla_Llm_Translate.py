import json
import os
import time

from etc.Logger import log_info, log_warning
from src.Dubla_Config import ENV_PATH, LLM_MAX_RETRIES, LLM_TIMEOUT, TRANSLATION_RETRIES
from src.Dubla_Translate.Dubla_Translate_Common import (
    BaseTranslator,
    TranslationError,
    chunked,
    looks_like_explanation,
)

# OpenAI-compatible endpoints (any other provider needs LLM_BASE_URL)
PROVIDER_BASE_URLS = {
    "openai": "https://api.openai.com/v1",
    "deepseek": "https://api.deepseek.com/v1",
    "groq": "https://api.groq.com/openai/v1",
    "openrouter": "https://openrouter.ai/api/v1",
    "together": "https://api.together.xyz/v1",
    "ollama": "http://localhost:11434/v1",
    "lmstudio": "http://localhost:1234/v1",
}

SYSTEM_PROMPT = """You are a professional subtitle translator.
Translate each string from {source} to {target}.
Return ONLY a JSON array of {count} strings with the translations, in the same order.
Do not add explanations, notes, quotes, labels, markdown or any extra text.
Preserve names, numbers, punctuation and tone; use natural spoken language."""

SINGLE_PROMPT = """You are a professional subtitle translator.
Translate the text from {source} to {target}.
Return ONLY the translation, with no explanations, notes, quotes, labels or markdown.
Preserve names, numbers, punctuation and tone; use natural spoken language."""


class LlmTranslate(BaseTranslator):
    """LLM translation through any OpenAI-compatible endpoint (openai SDK)."""

    engine = "llm"

    def __init__(self, meta_path, **kwargs):
        super().__init__(meta_path, **kwargs)
        self.provider = ""
        self.model_id = ""
        self.api_key = ""
        self.base_url = ""
        self.temperature = 0.0
        self.config_error: TranslationError | None = None
        self._client = None

        try:
            self._load_settings()
        except TranslationError as e:
            self.config_error = e

        self.model_name = f"{self.provider}/{self.model_id}" if self.provider else (self.model_id or "unconfigured")

    # -- configuration ------------------------------------------------------ #
    def _load_settings(self) -> None:
        try:
            from dotenv import load_dotenv
        except ImportError as e:
            raise TranslationError(
                "python-dotenv is not installed: pip install python-dotenv"
            ) from e

        load_dotenv(ENV_PATH, override=False)

        self.provider = (os.getenv("LLM_PROVIDER") or "").strip().lower()
        self.model_id = (os.getenv("LLM_MODEL") or "").strip()
        self.api_key = (os.getenv("LLM_API_KEY") or "").strip()
        self.base_url = (os.getenv("LLM_BASE_URL") or "").strip()

        if not self.base_url and self.provider:
            self.base_url = PROVIDER_BASE_URLS.get(self.provider, "")
        if not self.model_id:
            raise TranslationError("LLM_MODEL is not set; fill .env (see .env.example)")
        if not self.base_url:
            raise TranslationError(
                f"LLM_BASE_URL is not set for provider {self.provider!r}; "
                f"known providers: {', '.join(PROVIDER_BASE_URLS)}"
            )
        if not self.api_key and self.provider not in ("ollama", "lmstudio"):
            raise TranslationError("LLM_API_KEY is not set in .env")
        try:
            self.temperature = float(os.getenv("LLM_TEMPERATURE") or 0)
        except ValueError:
            self.temperature = 0.0

    def _ensure_client(self):
        if self.config_error is not None:
            raise self.config_error
        if self._client is None:
            try:
                from openai import OpenAI
            except ImportError as e:
                raise TranslationError("openai is not installed: pip install openai") from e
            self._client = OpenAI(
                api_key=self.api_key or "not-needed",
                base_url=self.base_url,
                timeout=LLM_TIMEOUT,
                max_retries=LLM_MAX_RETRIES,
            )
        return self._client

    # -- translation -------------------------------------------------------- #
    def translate_texts(self, texts: list[str]) -> list[str]:
        client = self._ensure_client()
        batches = list(chunked(texts, self.batch_size))
        results: list[str] = []

        for number, batch in enumerate(batches, start=1):
            log_info(f"llm batch {number}/{len(batches)} ({len(batch)} blocks)")
            results.extend(self._translate_batch(client, batch))

        return results

    def _translate_batch(self, client, batch: list[str]) -> list[str]:
        system = SYSTEM_PROMPT.format(source=self.source, target=self.target, count=len(batch))
        attempt = 0
        last_error: Exception | None = None

        while attempt < max(1, TRANSLATION_RETRIES):
            attempt += 1
            try:
                content = self._chat(client, system, json.dumps(batch, ensure_ascii=False))
                return self._parse_array(content, len(batch))
            except Exception as e:
                last_error = e
                time.sleep(min(2 ** attempt, 8))

        log_warning(f"llm batch failed ({last_error}); retrying one block at a time")
        return [self._translate_single(client, text) for text in batch]

    def _translate_single(self, client, text: str) -> str:
        system = SINGLE_PROMPT.format(source=self.source, target=self.target)
        last_error: Exception | None = None

        for attempt in range(1, max(1, TRANSLATION_RETRIES) + 1):
            try:
                content = self._chat(client, system, text).strip()
                clean = content.strip().strip('"').strip("'").strip()
                if not clean:
                    raise TranslationError("empty answer")
                if looks_like_explanation(clean):
                    raise TranslationError("answer contains an explanation")
                return clean
            except Exception as e:
                last_error = e
                time.sleep(min(2 ** attempt, 8))

        raise TranslationError(f"llm failed on a single block: {last_error}")

    def _chat(self, client, system: str, user: str) -> str:
        response = client.chat.completions.create(
            model=self.model_id,
            temperature=self.temperature,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
        )
        content = response.choices[0].message.content if response.choices else None
        if not content:
            raise TranslationError("empty response from the provider")
        return content

    def _parse_array(self, content: str, expected: int) -> list[str]:
        text = content.strip()
        if text.startswith("```"):
            text = text.strip("`")
            if text.lower().startswith("json"):
                text = text[4:]
            text = text.strip()

        start, end = text.find("["), text.rfind("]")
        if start == -1 or end <= start:
            raise TranslationError("response is not a JSON array")

        try:
            data = json.loads(text[start:end + 1])
        except json.JSONDecodeError as e:
            raise TranslationError(f"invalid JSON from the provider: {e}") from e

        if not isinstance(data, list) or len(data) != expected:
            raise TranslationError(f"expected {expected} items, got {len(data) if isinstance(data, list) else type(data).__name__}")
        if not all(isinstance(item, str) for item in data):
            raise TranslationError("response array contains non-string items")

        return [item.strip() for item in data]
