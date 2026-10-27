import time

from etc.Logger import log_info, log_warning
from src.Dubla_Config import (
    DEEP_TRANSLATOR_BACKEND,
    INPUT_LANGUAGE,
    OUTPUT_LANGUAGE,
    TRANSLATION_DELAY,
    TRANSLATION_RETRIES,
)
from src.Dubla_Translate.Dubla_Translate_Common import (
    BaseTranslator,
    TranslationError,
    chunked,
    normalize_language,
)

# GoogleTranslator rejects anything above this per request
GOOGLE_MAX_CHARS = 4500

# MyMemory needs a full locale tag, not a bare language code
DEFAULT_LOCALES = {
    "en": "en-US",
    "pt": "pt-BR",
    "es": "es-ES",
    "fr": "fr-FR",
    "de": "de-DE",
    "it": "it-IT",
    "nl": "nl-NL",
    "ru": "ru-RU",
    "ja": "ja-JP",
    "ko": "ko-KR",
    "zh": "zh-CN",
    "ar": "ar-SA",
    "hi": "hi-IN",
    "tr": "tr-TR",
    "pl": "pl-PL",
    "sv": "sv-SE",
    "uk": "uk-UA",
    "vi": "vi-VN",
    "id": "id-ID",
    "th": "th-TH",
    "cs": "cs-CZ",
    "el": "el-GR",
    "he": "he-IL",
    "fi": "fi-FI",
    "da": "da-DK",
    "no": "nb-NO",
    "ro": "ro-RO",
    "hu": "hu-HU",
    "bg": "bg-BG",
    "fa": "fa-IR",
    "ca": "ca-ES",
}


def locale_tag(code: str | None, preferred: str | None = None) -> str:
    """Return a full locale tag ('pt-BR') for a base code ('pt')."""
    base = normalize_language(code)
    preferred_base = normalize_language(preferred)
    if preferred and base == preferred_base:
        return preferred
    return DEFAULT_LOCALES.get(base or "", code or "")


class DeepTranslator(BaseTranslator):
    """deep-translator: Google (batch) or MyMemory (per block), no API key."""

    engine = "deep-translator"
    default_model = "mymemory"

    def __init__(self, meta_path, **kwargs):
        super().__init__(meta_path, **kwargs)
        self.backend = (DEEP_TRANSLATOR_BACKEND or "mymemory").strip().lower()
        self.model_name = self.backend

    def translate_texts(self, texts: list[str]) -> list[str]:
        if self.backend == "auto":
            try:
                return self._run_google(texts)
            except TranslationError as e:
                log_warning(f"google backend failed ({e}); falling back to mymemory")
                return self._run_mymemory(texts)
        if self.backend == "google":
            return self._run_google(texts)
        if self.backend in ("mymemory", "memory"):
            return self._run_mymemory(texts)
        raise TranslationError(f"unknown deep-translator backend: {self.backend}")

    def _is_done(self, stt: dict) -> bool:
        # With "auto" the backend is only known after the first run
        if self.backend != "auto":
            return super()._is_done(stt)
        saved = (self.meta.get("translation") or {}).get("model")
        if saved not in ("google", "mymemory"):
            return False
        self.model_name = saved
        return super()._is_done(stt)

    # -- google (batches joined with newlines) ------------------------------ #
    def _run_google(self, texts: list[str]) -> list[str]:
        try:
            from deep_translator import GoogleTranslator
        except ImportError as e:
            raise TranslationError("deep-translator is not installed: pip install deep-translator") from e

        translator = GoogleTranslator(source=self.source, target=self.target)
        self.model_name = "google"
        batches = list(chunked(texts, self.batch_size))
        results: list[str] = []

        for number, batch in enumerate(batches, start=1):
            log_info(f"google batch {number}/{len(batches)} ({len(batch)} blocks)")
            results.extend(self._translate_google_batch(translator, batch))
            if TRANSLATION_DELAY:
                time.sleep(TRANSLATION_DELAY)

        return results

    def _translate_google_batch(self, translator, batch: list[str]) -> list[str]:
        if len(batch) == 1:
            return [self._call_google(translator, batch[0])]

        joined = "\n".join(batch)
        if len(joined) > GOOGLE_MAX_CHARS:
            return self._split_google(translator, batch)

        result = self._call_google(translator, joined)
        parts = [part.strip() for part in result.split("\n")]

        if len(parts) != len(batch) or any(not part for part in parts):
            return self._split_google(translator, batch)
        return parts

    def _split_google(self, translator, batch: list[str]) -> list[str]:
        if len(batch) == 1:
            raise TranslationError(f"block too long for deep-translator ({len(batch[0])} chars)")
        middle = len(batch) // 2
        return self._translate_google_batch(translator, batch[:middle]) + self._translate_google_batch(
            translator, batch[middle:]
        )

    def _call_google(self, translator, text: str) -> str:
        from deep_translator.exceptions import LanguageNotSupportedException, TooManyRequests

        last_error = None
        for attempt in range(1, TRANSLATION_RETRIES + 1):
            try:
                result = translator.translate(text)
                if result and result.strip():
                    return result
                last_error = TranslationError("empty answer")
            except (TooManyRequests, LanguageNotSupportedException) as e:
                raise TranslationError(f"google refused the request: {e}") from e
            except Exception as e:  # network/parser errors from the scraper
                last_error = e
            time.sleep(min(2 ** attempt, 10))

        raise TranslationError(
            f"google backend failed after {TRANSLATION_RETRIES} attempts: {last_error}"
        )

    # -- mymemory (one request per block, full locale tags) ----------------- #
    def _run_mymemory(self, texts: list[str]) -> list[str]:
        try:
            from deep_translator import MyMemoryTranslator
        except ImportError as e:
            raise TranslationError("deep-translator is not installed: pip install deep-translator") from e

        source = locale_tag(self.source, INPUT_LANGUAGE)
        target = locale_tag(self.target, OUTPUT_LANGUAGE)
        translator = MyMemoryTranslator(source=source, target=target)
        self.model_name = "mymemory"
        delay = TRANSLATION_DELAY or 0.2
        results: list[str] = []

        log_info(f"mymemory ({source} -> {target}), {len(texts)} blocks")
        for index, text in enumerate(texts, start=1):
            results.append(self._call_mymemory(translator, text))
            if index % 20 == 0:
                log_info(f"mymemory: {index}/{len(texts)} blocks")
            time.sleep(delay)

        return results

    def _call_mymemory(self, translator, text: str) -> str:
        from deep_translator.exceptions import LanguageNotSupportedException, TooManyRequests

        last_error = None
        for attempt in range(1, TRANSLATION_RETRIES + 1):
            try:
                result = translator.translate(text)
                if result and "MYMEMORY WARNING" in result.upper():
                    # The free quota reply comes back as text instead of an error
                    raise TranslationError(f"mymemory quota reached: {result.strip()[:80]}")
                if result and result.strip():
                    return result
                last_error = TranslationError("empty answer")
            except (TooManyRequests, LanguageNotSupportedException) as e:
                raise TranslationError(f"mymemory refused the request: {e}") from e
            except TranslationError:
                raise
            except Exception as e:
                last_error = e
            time.sleep(min(2 ** attempt, 10))

        raise TranslationError(
            f"mymemory failed after {TRANSLATION_RETRIES} attempts: {last_error}"
        )
