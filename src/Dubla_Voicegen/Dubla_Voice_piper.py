import subprocess
import sys
import wave
from pathlib import Path

from etc.Logger import log_error, log_info
from src.Dubla_Voicegen.Dubla_Voice_Common import BaseVoice, voice_dir


class PiperVoiceGen(BaseVoice):
    """Piper: small local neural voices, CPU only."""

    engine = "piper"
    # Local model: keep inference serialized (parallel runs were slower and unstable)
    thread_safe = False

    def prepare(self) -> bool:
        try:
            from piper import PiperVoice
        except ImportError:
            log_error("piper-tts is not installed: pip install piper-tts")
            return False

        directory = voice_dir("piper")
        directory.mkdir(parents=True, exist_ok=True)
        model = directory / f"{self.voice}.onnx"

        if not model.is_file():
            log_info(f"downloading piper voice {self.voice}")
            try:
                subprocess.run(
                    [
                        sys.executable, "-m", "piper.download_voices", self.voice,
                        "--download-dir", str(directory),
                    ],
                    check=True,
                )
            except subprocess.CalledProcessError as e:
                log_error(f"could not download piper voice {self.voice}: {e}")
                return False

        if not model.is_file():
            log_error(f"piper voice file not found: {model}")
            return False

        try:
            self._engine = PiperVoice.load(str(model))
        except Exception as e:
            log_error(f"could not load piper voice {self.voice}: {e}")
            return False
        return True

    def synthesize(self, text: str, out_path: Path) -> bool:
        with wave.open(str(out_path), "wb") as wav_file:
            self._engine.synthesize_wav(text, wav_file)
        return True
