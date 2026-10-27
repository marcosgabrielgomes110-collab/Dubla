import os
import time
from pathlib import Path

from etc.Logger import log_error
from src.Dubla_Config import ENV_PATH, voice_setting
from src.Dubla_Voicegen.Dubla_Voice_Common import BaseVoice, VoiceError


class ElevenLabsVoiceGen(BaseVoice):
    """ElevenLabs cloud TTS (API key + voice ids per language)."""

    engine = "elevenlabs"
    native_suffix = ".mp3"
    thread_safe = True

    def __init__(self, meta_path, **kwargs):
        super().__init__(meta_path, **kwargs)
        self.max_workers = 2
        # Resolve the voice id early so the idempotency check can match it
        try:
            from dotenv import load_dotenv
            import os

            load_dotenv(ENV_PATH, override=False)
            env_voice = os.getenv(f"ELEVENLABS_VOICE_ID_{(self.language or '').upper()}", "").strip()
            if env_voice:
                self.voice = env_voice
            self.max_workers = max(1, int(os.getenv("ELEVENLABS_MAX_CONCURRENCY") or 2))
        except Exception:
            pass

    def prepare(self) -> bool:
        try:
            from dotenv import load_dotenv
        except ImportError:
            log_error("python-dotenv is not installed: pip install python-dotenv")
            return False

        load_dotenv(ENV_PATH, override=False)

        api_key = (os.getenv("ELEVENLABS_API_KEY") or "").strip()
        if not api_key:
            log_error("ELEVENLABS_API_KEY is empty; run: python Scripts/Setup_ElevenLabs.py")
            return False

        env_voice = os.getenv(f"ELEVENLABS_VOICE_ID_{(self.language or '').upper()}", "").strip()
        self.voice = env_voice or self.voice
        if not self.voice:
            log_error(
                f"no ElevenLabs voice id for {self.language!r}; "
                f"set ELEVENLABS_VOICE_ID_{(self.language or '').upper()} in .env "
                "(python Scripts/Setup_ElevenLabs.py --list-voices)"
            )
            return False

        self.model_id = (
            os.getenv("ELEVENLABS_MODEL") or voice_setting("elevenlabs", "model", "eleven_multilingual_v2")
        )
        self.output_format = (
            os.getenv("ELEVENLABS_OUTPUT_FORMAT")
            or voice_setting("elevenlabs", "output_format", "mp3_44100_128")
        )

        try:
            from elevenlabs.client import ElevenLabs
        except ImportError:
            log_error("elevenlabs is not installed: pip install elevenlabs")
            return False

        self._client = ElevenLabs(api_key=api_key)
        return True

    def synthesize(self, text: str, out_path: Path) -> bool:
        last_error: Exception | None = None
        for attempt in range(3):
            try:
                chunks = self._client.text_to_speech.convert(
                    voice_id=self.voice,
                    text=text,
                    model_id=self.model_id,
                    output_format=self.output_format,
                )
                out_path.write_bytes(b"".join(chunks))
                return True
            except Exception as e:
                # Free plans allow only a few concurrent requests (429)
                if getattr(e, "status_code", None) == 429:
                    last_error = e
                    time.sleep(1.5 * (attempt + 1))
                    continue
                raise VoiceError(f"ElevenLabs failed: {e}") from e
        raise VoiceError(f"ElevenLabs rate limited: {last_error}")
