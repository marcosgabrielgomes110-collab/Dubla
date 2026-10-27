"""Colored terminal logging persisted to Data/logs/.

Usage:
    from etc.Logger import log_info, log_ok, log_warning, log_error

    log_info("downloading model...")
    log_ok("download finished")
    log_warning("model missing")
    log_error("ffmpeg not found")

Every call also appends a line to Data/logs/dubla-<date>.log.
"""

import json
import os
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
LOG_DIR = ROOT / "Data" / "logs"

LEVELS = {
    "info": ("INFO ", "\033[36m"),   # cyan
    "ok": ("OK   ", "\033[32m"),     # green
    "warning": ("WARN ", "\033[33m"),  # yellow
    "error": ("ERROR", "\033[31m"),  # red
}
RESET = "\033[0m"
_progress_active = False


def _color_enabled() -> bool:
    if os.environ.get("NO_COLOR"):
        return False
    if os.environ.get("TERM") == "dumb":
        return False
    return sys.stdout.isatty()


def _caller() -> str:
    """Name of the file that called the log function (for the log file)."""
    this_file = Path(__file__).name
    frame = sys._getframe(2)
    while frame is not None and Path(frame.f_code.co_filename).name == this_file:
        frame = frame.f_back
    if frame is None:
        return "dubla"
    return Path(frame.f_code.co_filename).stem


def _write_file(level: str, source: str, message: str) -> None:
    try:
        LOG_DIR.mkdir(parents=True, exist_ok=True)
        now = datetime.now()
        path = LOG_DIR / f"dubla-{now:%Y-%m-%d}.log"
        with open(path, "a", encoding="utf-8") as f:
            f.write(f"{now:%Y-%m-%d %H:%M:%S} | {level.upper():<7} | {source} | {message}\n")
    except OSError:
        pass  # logging never breaks the pipeline


def _json_mode() -> bool:
    return os.environ.get("DUBLA_LOG_JSON") == "1"


def log(level: str, message, *, show_source: bool = False) -> None:
    """Write one log line. level: info | ok | warning | error."""
    global _progress_active
    level = (level or "info").strip().lower()
    tag, color = LEVELS.get(level, LEVELS["info"])
    message = str(message)
    source = _caller()

    if _json_mode():
        record = {
            "ts": datetime.now().isoformat(timespec="seconds"),
            "level": level,
            "source": source,
            "message": message,
        }
        try:
            sys.stdout.write(json.dumps(record, ensure_ascii=False) + "\n")
            sys.stdout.flush()
        except BrokenPipeError:
            pass
        _write_file(level, source, message)
        return

    if _progress_active:
        clear_progress()

    now = datetime.now().strftime("%H:%M:%S")
    prefix = f"[{now}] {tag} " + (f"({source}) " if show_source else "")
    if _color_enabled():
        line = f"\033[2m[{now}]\033[0m {color}{tag}{RESET} " + (f"\033[2m({source})\033[0m " if show_source else "") + message
    else:
        line = prefix + message

    stream = sys.stderr if level in ("warning", "error") else sys.stdout
    try:
        stream.write(line + "\n")
        stream.flush()
    except BrokenPipeError:
        pass  # output was piped into something that closed (e.g. | head)

    _write_file(level, source, message)


def log_info(message) -> None:
    log("info", message)


def log_ok(message) -> None:
    log("ok", message)


def log_warning(message) -> None:
    log("warning", message)


def log_error(message) -> None:
    log("error", message)


def log_progress(message) -> None:
    """Transient progress line (console only, no log file, no newline)."""
    global _progress_active
    text = str(message)
    if _json_mode():
        record = {
            "ts": datetime.now().isoformat(timespec="seconds"),
            "level": "progress",
            "source": "",
            "message": text.strip(),
        }
        try:
            sys.stdout.write(json.dumps(record, ensure_ascii=False) + "\n")
            sys.stdout.flush()
        except BrokenPipeError:
            pass
        return
    if _color_enabled():
        sys.stdout.write("\r\033[K" + f"\033[2m{text}{RESET}")
    else:
        sys.stdout.write("\r" + text)
    sys.stdout.flush()
    _progress_active = True


def clear_progress() -> None:
    global _progress_active
    if _progress_active:
        if _color_enabled():
            sys.stdout.write("\r\033[K")
        else:
            sys.stdout.write("\r" + " " * 100 + "\r")
        sys.stdout.flush()
        _progress_active = False
