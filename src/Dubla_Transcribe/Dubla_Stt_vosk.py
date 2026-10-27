import json
import wave

from src.Dubla_Config import STT_VOSK_MODEL
from src.Dubla_Transcribe.Dubla_Stt_Common import (
    BaseStt,
    ensure_vosk_model,
    vosk_model_name,
)
from etc.Logger import log_error

SAMPLE_RATE = 16000


class VoskStt(BaseStt):
    """Vosk speech-to-text with word level timestamps."""

    engine = "vosk"

    def _resolve_model(self) -> bool:
        self.model_name = vosk_model_name(self.language, self.model_choice or STT_VOSK_MODEL)
        if not self.model_name:
            log_error(f"No Vosk model registered for language: {self.language}")
            return False
        return True

    def _prepare_model(self) -> bool:
        try:
            import vosk  # noqa: F401
        except ImportError:
            log_error("vosk is not installed: pip install vosk")
            return False

        self.model_path = ensure_vosk_model(self.language, self.model_choice or STT_VOSK_MODEL)
        if self.model_path is None:
            return False
        self.model_name = self.model_path.name
        self.device = "cpu"
        return True

    def _validate_wav(self) -> bool:
        """Vosk only accepts 16 kHz, mono, 16-bit PCM."""
        try:
            with wave.open(str(self.wav_path), "rb") as wav:
                channels = wav.getnchannels()
                width = wav.getsampwidth()
                rate = wav.getframerate()
        except (wave.Error, EOFError) as e:
            log_error(f"Error reading wav: {e}")
            return False

        if channels != 1 or width != 2 or rate != SAMPLE_RATE:
            log_error(
                f"Wav is incompatible with Vosk ({rate} Hz, {channels} channel(s), {width * 8} bits); "
                f"expected {SAMPLE_RATE} Hz mono 16 bits"
            )
            return False
        return True

    def _transcribe(self) -> list[dict] | None:
        from vosk import KaldiRecognizer, Model, SetLogLevel

        SetLogLevel(-1)
        if not self._validate_wav():
            return None

        model = Model(str(self.model_path))
        recognizer = KaldiRecognizer(model, SAMPLE_RATE)
        recognizer.SetWords(True)

        try:
            with wave.open(str(self.wav_path), "rb") as wav:
                while True:
                    chunk = wav.readframes(SAMPLE_RATE // 2)
                    if not chunk:
                        break
                    recognizer.AcceptWaveform(chunk)
                result = json.loads(recognizer.FinalResult())
        except Exception as e:
            log_error(f"Error transcribing with Vosk: {e}")
            return None

        return [
            {
                "start": float(word["start"]),
                "end": float(word["end"]),
                "word": str(word["word"]),
                "conf": float(word.get("conf", 1.0)),
            }
            for word in result.get("result", [])
        ]
