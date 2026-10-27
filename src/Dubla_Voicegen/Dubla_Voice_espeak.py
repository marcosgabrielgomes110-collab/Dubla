import shutil
import subprocess
from pathlib import Path

from etc.Logger import log_error
from src.Dubla_Config import voice_setting
from src.Dubla_Voicegen.Dubla_Voice_Common import BaseVoice, VoiceError


class EspeakVoiceGen(BaseVoice):
    """eSpeak NG: robotic fallback, extremely light and offline."""

    engine = "espeak"
    thread_safe = True

    def prepare(self) -> bool:
        self._binary = shutil.which("espeak-ng") or shutil.which("espeak")
        if not self._binary:
            log_error("espeak-ng is not installed: sudo pacman -S espeak-ng")
            return False
        self._rate = int(voice_setting("espeak", "rate", 145) or 145)
        if not self.voice:
            log_error(f"no eSpeak voice configured for {self.language!r} (voices.espeak.<language>)")
            return False
        return True

    def synthesize(self, text: str, out_path: Path) -> bool:
        try:
            subprocess.run(
                [
                    self._binary,
                    "-v", self.voice,
                    "-s", str(self._rate),
                    "-w", str(out_path),
                    text,
                ],
                check=True,
            )
        except subprocess.CalledProcessError as e:
            raise VoiceError(f"espeak-ng failed: {e}") from e
        return True
