import hashlib
import json
import shutil
import subprocess
from pathlib import Path
from src.Dubla_Config import TempPath, OutputPath
from etc.Logger import log_error, log_info, log_ok


class GetLocalMovie:
    def __init__(self, source: str | Path):
        self.source = Path(source).expanduser().resolve()
        # Local files have no id, so build a stable one from the file content
        self.video_id = self._generate_id()
        self.path = TempPath / self.video_id
        self.meta = self.path / f"{self.video_id}.json"
        self.video_file = self.path / f"{self.video_id}.mp4"
        self.audio_file = self.path / f"{self.video_id}.wav"

    def _generate_id(self) -> str:
        """Hash the file content so the same movie always maps to the same folder."""
        if not self.source.is_file():
            raise FileNotFoundError(f"Local movie not found: {self.source}")

        digest = hashlib.sha256()
        with open(self.source, "rb") as f:
            for chunk in iter(lambda: f.read(1024 * 1024), b""):
                digest.update(chunk)
        return digest.hexdigest()[:16]

    def prepare(self) -> bool:
        """Create required directories and initialize metadata file."""
        try:
            # Create temp directory for this video ID
            self.path.mkdir(parents=True, exist_ok=True)

            # Initialize empty metadata file if it does not exist
            if not self.meta.exists():
                with open(self.meta, "w", encoding="utf-8") as f:
                    json.dump({}, f, indent=4)

            # Ensure output directory exists
            OutputPath.mkdir(parents=True, exist_ok=True)
            return True
        except Exception as e:
            log_error(f"Error preparing directories: {e}")
            return False

    def _probe(self) -> dict:
        """Read duration, resolution and stream list from the source file with ffprobe."""
        cmd = [
            "ffprobe",
            "-v", "error",
            "-print_format", "json",
            "-show_format",
            "-show_streams",
            str(self.source),
        ]
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, check=True)
            return json.loads(result.stdout)
        except (FileNotFoundError, subprocess.CalledProcessError, json.JSONDecodeError) as e:
            log_error(f"Error reading video info: {e}")
            return {}

    def _has_audio_stream(self, file: Path | None = None) -> bool:
        """Check whether a file has an audio track (videos are muted after a successful run)."""
        target = file or self.video_file
        cmd = [
            "ffprobe",
            "-v", "error",
            "-select_streams", "a",
            "-show_entries", "stream=index",
            "-of", "csv=p=0",
            str(target),
        ]
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        except (FileNotFoundError, subprocess.CalledProcessError):
            return False
        return bool(result.stdout.strip())

    def import_video(self):
        """Place the source in Temp/<id>/<id>.mp4, converting it when it is not an mp4 already."""
        if self.source == self.video_file:
            return self.video_file

        # Already the expected container: just copy it
        if self.source.suffix.lower() == ".mp4":
            try:
                shutil.copy2(self.source, self.video_file)
                return self.video_file
            except OSError as e:
                log_error(f"Error copying video: {e}")
                return None

        # Other containers (mkv, avi, mov, webm, ...) must be converted to mp4
        log_info(f"Converting {self.source.name} to mp4")
        base = ["ffmpeg", "-y", "-loglevel", "error", "-i", str(self.source)]
        attempts = [
            # Fast path: remux the video track and re-encode only the audio to AAC
            base + ["-c:v", "copy", "-c:a", "aac", "-b:a", "192k", "-movflags", "+faststart", str(self.video_file)],
            # Fallback: full re-encode when the source video codec does not fit an mp4 container
            base + ["-c:v", "libx264", "-preset", "fast", "-crf", "20", "-c:a", "aac", "-b:a", "192k", "-movflags", "+faststart", str(self.video_file)],
        ]

        for cmd in attempts:
            try:
                subprocess.run(cmd, check=True)
                return self.video_file
            except FileNotFoundError:
                log_error("Error converting video: ffmpeg not found")
                return None
            except subprocess.CalledProcessError:
                continue

        log_error(f"Error converting video: {self.source}")
        self.video_file.unlink(missing_ok=True)
        return None

    def extract_audio(self):
        """Extract audio from the video to Temp/<id>/<id>.wav (mono, 16 kHz PCM)."""
        if not self.video_file.exists():
            log_error(f"Video file not found: {self.video_file}")
            return None

        cmd = [
            "ffmpeg",
            "-y",
            "-loglevel", "error",
            "-i", str(self.video_file),
            "-vn",
            "-acodec", "pcm_s16le",
            "-ar", "16000",
            "-ac", "1",
            str(self.audio_file),
        ]

        try:
            subprocess.run(cmd, check=True)
            return self.audio_file
        except FileNotFoundError:
            log_error("Error extracting audio: ffmpeg not found")
            return None
        except subprocess.CalledProcessError as e:
            log_error(f"Error extracting audio: {e}")
            return None

    def mute_video(self):
        """Strip the audio track from the video, keeping only the video stream."""
        if not self.video_file.exists():
            log_error(f"Video file not found: {self.video_file}")
            return None

        # Temporary file must keep the container extension so ffmpeg can pick the format
        muted_file = self.path / f"{self.video_id}.muted{self.video_file.suffix}"
        cmd = [
            "ffmpeg",
            "-y",
            "-loglevel", "error",
            "-i", str(self.video_file),
            "-c", "copy",
            "-an",
            str(muted_file),
        ]

        try:
            subprocess.run(cmd, check=True)
            muted_file.replace(self.video_file)
            return self.video_file
        except FileNotFoundError:
            log_error("Error muting video: ffmpeg not found")
            return None
        except subprocess.CalledProcessError as e:
            log_error(f"Error muting video: {e}")
            muted_file.unlink(missing_ok=True)
            return None

    def process(self):
        """Import the local movie, split video/audio and record both paths in the json."""
        try:
            self.prepare()

            # Nothing to extract from a silent source, fail before copying anything
            if not self._has_audio_stream(self.source):
                log_error(f"Source has no audio track: {self.source}")
                return None

            if not self.import_video():
                return None

            # Extract audio to Temp/<id>/<id>.wav next to the video
            audio_file = self.extract_audio()

            # Only strip the audio once it is safely stored in the wav file
            if audio_file:
                self.mute_video()

            info = self._probe()
            fmt = info.get("format") or {}
            video_stream = next(
                (s for s in info.get("streams", []) if s.get("codec_type") == "video"),
                {},
            )

            # Save video + audio paths to json file
            with open(self.meta, "w", encoding="utf-8") as f:
                json.dump(
                    {
                        "id": self.video_id,
                        "title": self.source.stem,
                        "duration": float(fmt["duration"]) if fmt.get("duration") else None,
                        "uploader": None,
                        "resolution": f"{video_stream.get('width')}x{video_stream.get('height')}",
                        "ext": "mp4",
                        "source_path": str(self.source),
                        "video_path": str(self.video_file),
                        "audio_path": str(audio_file) if audio_file else None,
                        # Kept for backwards compatibility with older consumers
                        "file_path": str(self.video_file),
                    },
                    f,
                    indent=4
                )

            # Without the audio the pipeline is useless, so report failure to the caller
            if not audio_file:
                return None

            return self.video_file
        except Exception as e:
            log_error(f"Error processing local video: {e}")
            return None

    def _is_complete(self) -> bool:
        """True when a previous run already produced the video, the extracted audio and a filled json."""
        if not (self.video_file.exists() and self.audio_file.exists() and self.meta.exists()):
            return False

        try:
            with open(self.meta, "r", encoding="utf-8") as f:
                data = json.load(f)
        except (OSError, json.JSONDecodeError):
            return False

        return bool(data.get("video_path") and data.get("audio_path"))

    def run(self):
        """Run the full pipeline (import/convert, extract audio, mute video, write json).

        Returns only the path of the json file holding the video and audio paths,
        or None if any step fails.
        """
        if not self.prepare():
            return None

        # Already processed (video is muted, so never try to re-extract from it)
        if self._is_complete():
            log_info(f"Already processed: {self.meta}")
            return self.meta

        if not self.process():
            return None

        log_ok(f"Done: {self.meta}")
        return self.meta
