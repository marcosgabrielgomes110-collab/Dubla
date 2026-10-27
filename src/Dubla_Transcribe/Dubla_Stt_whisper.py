import subprocess
import wave

from src.Dubla_Config import (
    STT_WHISPER_COMPUTE,
    STT_WHISPER_DEVICE,
    STT_WHISPER_MODEL,
    WhisperModelPath,
)
from src.Dubla_Transcribe.Dubla_Stt_Common import (
    BaseStt,
    default_whisper_compute,
    detect_hardware,
    ensure_whisper_model,
    is_whisper_language,
    whisper_size,
)
from etc.Logger import log_error, log_info


class WhisperStt(BaseStt):
    """faster-whisper speech-to-text with word level timestamps."""

    engine = "whisper"

    def __init__(self, wav_path, language=None, model=None, force: bool = False):
        super().__init__(wav_path, language=language, model=model, force=force)
        hw = detect_hardware()
        device, compute_type = default_whisper_compute(hw)
        if STT_WHISPER_DEVICE and STT_WHISPER_DEVICE != "auto":
            device = STT_WHISPER_DEVICE
        if STT_WHISPER_COMPUTE and STT_WHISPER_COMPUTE != "auto":
            compute_type = STT_WHISPER_COMPUTE
        self.device = device
        self.compute_type = compute_type

    def _resolve_model(self) -> bool:
        size = whisper_size(self.model_choice or STT_WHISPER_MODEL)
        self.model_name = f"faster-whisper-{size}"
        if not is_whisper_language(self.language):
            log_error(f"Language not supported by whisper: {self.language}")
            return False
        return True

    def _prepare_model(self) -> bool:
        try:
            import faster_whisper  # noqa: F401
        except ImportError:
            log_error("faster-whisper is not installed: pip install faster-whisper")
            return False

        self.model_path = ensure_whisper_model(self.model_choice or STT_WHISPER_MODEL)
        if self.model_path is None:
            return False
        self.model_name = f"faster-whisper-{self.model_path.name}"
        return True

    def _load_audio(self):
        """Decode to float32 16 kHz mono without PyAV.

        faster-whisper calls av.open(metadata_errors=...), which PyAV 19 (the wheel
        available for Python 3.14) no longer accepts. The pipeline audio is already
        16 kHz mono PCM, so we read it directly and only fall back to ffmpeg.
        """
        import numpy as np

        try:
            with wave.open(str(self.wav_path), "rb") as wav:
                if (wav.getnchannels(), wav.getsampwidth(), wav.getframerate()) == (1, 2, 16000):
                    data = wav.readframes(wav.getnframes())
                    return np.frombuffer(data, dtype=np.int16).astype(np.float32) / 32768.0
        except (wave.Error, EOFError):
            pass

        result = subprocess.run(
            [
                "ffmpeg", "-v", "error",
                "-i", str(self.wav_path),
                "-f", "f32le", "-ac", "1", "-ar", "16000",
                "pipe:1",
            ],
            capture_output=True,
            check=True,
        )
        return np.frombuffer(result.stdout, dtype=np.float32)

    def _transcribe(self) -> list[dict] | None:
        from faster_whisper import WhisperModel

        hw = detect_hardware()
        try:
            audio = self._load_audio()
            model = WhisperModel(
                str(self.model_path),
                device=self.device,
                compute_type=self.compute_type,
                cpu_threads=max(1, hw.cpu_threads - 1) if self.device == "cpu" else 0,
                download_root=str(WhisperModelPath),
            )
            segments, info = model.transcribe(
                audio,
                language=None if self.language == "auto" else self.language,
                beam_size=5,
                temperature=0.0,
                condition_on_previous_text=False,
                word_timestamps=True,
                vad_filter=True,
                vad_parameters={"min_silence_duration_ms": 300},
            )
        except Exception as e:
            log_error(f"Error transcribing with whisper: {e}")
            return None

        detected = getattr(info, "language", None)
        if self.language == "auto":
            self.detected_language = detected
            probability = getattr(info, "language_probability", None)
            if detected:
                log_info(f"detected language: {detected} (confidence {probability or 0:.2f})")

        words: list[dict] = []
        try:
            for segment in segments:
                # Whisper flags music/noise as no-speech; those words would pollute the timeline
                if getattr(segment, "no_speech_prob", 0.0) > 0.6:
                    continue
                for word in segment.words or []:
                    text = (word.word or "").strip()
                    if not text:
                        continue
                    words.append(
                        {
                            "start": float(word.start),
                            "end": float(word.end),
                            "word": text,
                            "conf": float(word.probability),
                        }
                    )
        except Exception as e:
            log_error(f"Error reading whisper segments: {e}")
            return None

        return words
