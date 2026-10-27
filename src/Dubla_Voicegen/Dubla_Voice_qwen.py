from pathlib import Path

from etc.Logger import log_error
from src.Dubla_Config import voice_setting
from src.Dubla_Voicegen.Dubla_Voice_Common import BaseVoice, VoiceError, voice_dir

LANGUAGE_NAMES = {
    "zh": "Chinese",
    "en": "English",
    "ja": "Japanese",
    "ko": "Korean",
    "de": "German",
    "fr": "French",
    "ru": "Russian",
    "pt": "Portuguese",
    "es": "Spanish",
    "it": "Italian",
}


class QwenVoiceGen(BaseVoice):
    """Qwen3-TTS 0.6B CustomVoice: heavy local model, 10 languages, 9 timbres."""

    engine = "qwen"

    def prepare(self) -> bool:
        try:
            import torch
            from qwen_tts import Qwen3TTSModel
        except ImportError:
            log_error("qwen-tts is not installed: pip install -r requirements-voice-qwen.txt")
            return False

        model_id = voice_setting("qwen", "model")
        if not model_id:
            log_error("voices.qwen.model is not set in configs.json")
            return False

        if not self.voice:
            self.voice = voice_setting("qwen", self.language or "", "")
        if not self.voice:
            log_error(
                f"no Qwen speaker configured for {self.language!r}; "
                "set voices.qwen.<language> to one of the model speakers"
            )
            return False

        model_language = LANGUAGE_NAMES.get(self.language or "")
        if model_language is None:
            log_error(f"Qwen3-TTS has no support for {self.language!r}")
            return False
        self.model_language = model_language

        try:
            local = voice_dir("qwen")
            model_source = str(local) if (local / "config.json").is_file() else model_id
            dtype_name = str(voice_setting("qwen", "dtype", "float32"))
            dtype = getattr(torch, dtype_name, torch.float32)
            self._model = Qwen3TTSModel.from_pretrained(
                model_source,
                device_map="cpu",
                dtype=dtype,
            )
        except Exception as e:
            log_error(f"could not load Qwen3-TTS {model_id}: {e}")
            return False
        return True

    def synthesize(self, text: str, out_path: Path) -> bool:
        import soundfile as sf

        try:
            wavs, sample_rate = self._model.generate_custom_voice(
                text=text,
                language=self.model_language,
                speaker=self.voice,
                max_new_tokens=int(voice_setting("qwen", "max_new_tokens", 256)),
            )
            sf.write(str(out_path), wavs[0], sample_rate)
        except Exception as e:
            raise VoiceError(f"Qwen3-TTS failed: {e}") from e
        return True
