from etc.Logger import log_info
from src.Dubla_Translate.Dubla_Translate_Common import BaseTranslator, TranslationError


class ArgoTranslate(BaseTranslator):
    """Argos Translate: fully offline after the language package is installed."""

    engine = "argos"
    default_model = "argos"

    def translate_texts(self, texts: list[str]) -> list[str]:
        try:
            import argostranslate.package  # noqa: F401
            import argostranslate.translate  # noqa: F401
        except ImportError as e:
            raise TranslationError(
                "argostranslate is not installed: pip install argostranslate"
            ) from e

        translation = self._ensure_translation()
        results: list[str] = []
        for index, text in enumerate(texts, start=1):
            try:
                results.append(translation.translate(text))
            except Exception as e:
                raise TranslationError(f"argos failed on block {index}: {e}") from e
            if index % 20 == 0:
                log_info(f"argos: {index}/{len(texts)} blocks")
        return results

    def _ensure_translation(self):
        import argostranslate.package as package
        import argostranslate.translate as translate

        translation = self._find_translation(translate)
        if translation is not None:
            return translation

        log_info(f"installing argos package {self.source} -> {self.target}")
        try:
            package.update_package_index()
            available = package.get_available_packages()
            match = next(
                (
                    item
                    for item in available
                    if item.from_code == self.source and item.to_code == self.target
                ),
                None,
            )
            if match is None:
                raise TranslationError(f"no argos package for {self.source} -> {self.target}")
            package.install_from_path(match.download())
        except TranslationError:
            raise
        except Exception as e:
            raise TranslationError(f"could not install the argos package: {e}") from e

        translation = self._find_translation(translate)
        if translation is None:
            raise TranslationError("argos package installed but no translation is available")
        return translation

    def _find_translation(self, translate):
        languages = translate.get_installed_languages()
        source = next((item for item in languages if item.code == self.source), None)
        target = next((item for item in languages if item.code == self.target), None)
        if source is None or target is None:
            return None
        return source.get_translation(target)
