from pathlib import Path

from etc.Logger import log_error
from src.Dubla_Voicegen.Dubla_Voice_Common import BaseVoice, VoiceError

# Pocket TTS model variant per language
LANGUAGE_MODELS = {
    "en": "english",
    "fr": "french",
    "de": "german",
    "pt": "portuguese",
    "it": "italian",
    "es": "spanish",
    "nl": "dutch",
}


class PocketVoiceGen(BaseVoice):
    """Pocket TTS (Kyutai): 100M params, CPU, 7 languages."""

    engine = "pocket"

    def prepare(self) -> bool:
        try:
            from pocket_tts import TTSModel
        except ImportError:
            log_error("pocket-tts is not installed: pip install pocket-tts")
            return False

        model_language = LANGUAGE_MODELS.get(self.language or "")
        if model_language is None:
            log_error(f"pocket-tts has no language model for {self.language!r} (supported: {', '.join(LANGUAGE_MODELS)})")
            return False

        try:
            self._model = TTSModel.load_model(language=model_language)
        except Exception as e:
            log_error(f"could not load pocket-tts model ({model_language}): {e}")
            return False

        try:
            self._state = self._model.get_state_for_audio_prompt(self.voice)
        except Exception as e:
            log_error(f"could not load pocket-tts voice {self.voice!r}: {e}")
            return False
        return True

    def synthesize(self, text: str, out_path: Path) -> bool:
        import scipy.io.wavfile

        try:
            audio = self._model.generate_audio(self._state, text)
            data = audio.detach().cpu().numpy() if hasattr(audio, "detach") else audio
            scipy.io.wavfile.write(str(out_path), self._model.sample_rate, data)
        except Exception as e:
            raise VoiceError(f"pocket-tts failed: {e}") from e
        return True
