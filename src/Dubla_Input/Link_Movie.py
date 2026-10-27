import json
import subprocess
from pathlib import Path
import yt_dlp
from src.Dubla_Config import Quality, TempPath, OutputPath
from etc.Logger import log_error, log_info, log_ok

class GetLinkMovie:
    def __init__(self, url: str):
        self.url = url
        # Extract YouTube video ID from URL via yt_dlp without downloading
        self.video_id = self._extract_video_id()
        self.path = TempPath / self.video_id
        self.meta = self.path / f"{self.video_id}.json"
        self.video_file = self.path / f"{self.video_id}.mp4"
        self.audio_file = self.path / f"{self.video_id}.wav"

    def _extract_video_id(self) -> str:
        """Extract the video ID using yt_dlp metadata extraction."""
        ydl_opts = {
            "quiet": True,
            "no_warnings": True,
            "skip_download": True,
        }
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(self.url, download=False)
            return info.get("id")

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

    def extract_audio(self):
        """Extract audio from the downloaded video to Temp/<id>/<id>.wav (mono, 16 kHz PCM)."""
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
        """Strip the audio track from the downloaded video, keeping only the video stream."""
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

    def _has_audio_stream(self) -> bool:
        """Check whether the local video still has an audio track (it is muted after a successful run)."""
        cmd = [
            "ffprobe",
            "-v", "error",
            "-select_streams", "a",
            "-show_entries", "stream=index",
            "-of", "csv=p=0",
            str(self.video_file),
        ]
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        except (FileNotFoundError, subprocess.CalledProcessError):
            return False
        return bool(result.stdout.strip())

    def download(self):
        """Download video (MP4) plus extracted audio (WAV) to Temp/<id>/ and record both paths in the JSON."""
        try:
            self.prepare()

            # Normalize resolution (e.g., '720' or '720p' -> 720)
            resolution = str(Quality).replace("p", "").strip() if Quality else "720"

            ydl_opts = {
                # Select best video up to configured height and best audio, fallback to best overall
                "format": f"bestvideo[height<={resolution}]+bestaudio/best[height<={resolution}]/best",
                # Merge into mp4 container using ffmpeg
                "merge_output_format": "mp4",
                # Output filename format: Temp/<id>/<id>.mp4
                "outtmpl": str(self.path / f"{self.video_id}.%(ext)s"),
                "quiet": False,
                "no_warnings": True,
            }

            # A previous run mutes the video in place, so a muted local file cannot provide
            # the audio again: force yt-dlp to download it instead of reusing the file.
            if self.video_file.exists() and not self._has_audio_stream():
                ydl_opts["overwrites"] = True

            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info_dict = ydl.extract_info(self.url, download=True)

                # Use the real final path reported by yt-dlp (merge/remux can change extension)
                requested = info_dict.get("requested_downloads") or [{}]
                if requested[0].get("filepath"):
                    self.video_file = Path(requested[0]["filepath"])

                # Extract audio to Temp/<id>/<id>.wav next to the video
                audio_file = self.extract_audio()

                # Only strip the audio once it is safely stored in the wav file
                if audio_file:
                    self.mute_video()

                # Save video + audio paths to json file
                with open(self.meta, "w", encoding="utf-8") as f:
                    json.dump(
                        {
                            "id": info_dict.get("id"),
                            "title": info_dict.get("title"),
                            "duration": info_dict.get("duration"),
                            "uploader": info_dict.get("uploader"),
                            "resolution": info_dict.get("resolution") or f"{info_dict.get('height')}p",
                            "ext": "mp4",
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
            log_error(f"Error downloading video: {e}")
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
        """Run the full pipeline (download, extract audio, mute video, write json).

        Returns only the path of the json file holding the video and audio paths,
        or None if any step fails.
        """
        if not self.prepare():
            return None

        # Already processed (video is muted, so never try to re-extract from it)
        if self._is_complete():
            log_info(f"Already processed: {self.meta}")
            return self.meta

        if not self.download():
            return None

        log_ok(f"Done: {self.meta}")
        return self.meta