"""Background jobs: pipeline, scripts and model downloads in isolated subprocesses."""

import asyncio
import json
import os
import queue
import signal
import subprocess
import sys
import threading
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Literal

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from src.Dubla_Config import ROOT

router = APIRouter(prefix="/jobs", tags=["jobs"])

JOBS_DIR = ROOT / "Data" / "api" / "jobs"
MAX_LOG_LINES = 2000
TERMINAL = ("succeeded", "failed", "cancelled")


@dataclass
class Job:
    id: str
    type: str
    params: dict
    status: str = "queued"
    created_at: str = field(default_factory=lambda: datetime.now().astimezone().isoformat(timespec="seconds"))
    started_at: str | None = None
    finished_at: str | None = None
    return_code: int | None = None
    result: str | None = None
    error: str | None = None
    logs: list[dict] = field(default_factory=list)
    cancel_requested: bool = False
    process: subprocess.Popen | None = None

    def public(self) -> dict:
        return {
            "id": self.id,
            "type": self.type,
            "params": self.params,
            "status": self.status,
            "created_at": self.created_at,
            "started_at": self.started_at,
            "finished_at": self.finished_at,
            "return_code": self.return_code,
            "result": self.result,
            "error": self.error,
            "log_lines": len(self.logs),
        }


def _python() -> str:
    return sys.executable


def build_command(kind: str, params: dict) -> list[str]:
    """Build the subprocess argv. Only known kinds/scripts are allowed."""
    if kind == "pipeline":
        url = str(params.get("url") or "").strip()
        if not url.startswith(("http://", "https://")):
            raise ValueError("pipeline requires an http(s) url")
        cmd = [_python(), "-m", "src.Dubla_MovieManager", url]
        if params.get("force"):
            cmd.append("--force")
        return cmd

    if kind == "models":
        cmd = [_python(), "Scripts/Setup_Voices.py"]
        engine = params.get("engine")
        if engine in ("piper", "pocket", "qwen", "all"):
            cmd += ["--engine", engine]
        for language in params.get("languages") or []:
            cmd += ["--language", str(language)]
        if params.get("force"):
            cmd.append("--force")
        return cmd

    if kind == "script":
        name = params.get("name")
        force = bool(params.get("force"))
        if name == "test_pipeline":
            cmd = [_python(), "Scripts/Test_Complete_Pipeline.py"]
            if force:
                cmd.append("--force")
            return cmd
        if name == "download_models":
            cmd = [_python(), "Scripts/Download_Models.py"]
            for language in params.get("languages") or []:
                cmd += ["--language", str(language)]
            if params.get("engine") in ("auto", "vosk", "whisper"):
                cmd += ["--engine", params["engine"]]
            if params.get("all"):
                cmd.append("--all")
            return cmd
        if name == "setup_voices":
            cmd = [_python(), "Scripts/Setup_Voices.py"]
            if params.get("engine") in ("piper", "pocket", "qwen", "all"):
                cmd += ["--engine", params["engine"]]
            for language in params.get("languages") or []:
                cmd += ["--language", str(language)]
            return cmd
        raise ValueError(f"script not allowed: {name}")

    raise ValueError(f"unknown job type: {kind}")


class JobManager:
    def __init__(self) -> None:
        self.jobs: dict[str, Job] = {}
        self.lock = threading.Lock()
        self.queue: queue.Queue[Job | None] = queue.Queue()
        self.worker = threading.Thread(target=self._loop, name="dubla-jobs", daemon=True)
        self.worker.start()

    def create(self, kind: str, params: dict) -> Job:
        build_command(kind, params)  # validate before queueing
        job = Job(id=uuid.uuid4().hex, type=kind, params=params)
        with self.lock:
            self.jobs[job.id] = job
        self.queue.put(job)
        return job

    def get(self, job_id: str) -> Job | None:
        return self.jobs.get(job_id)

    def cancel(self, job_id: str) -> Job | None:
        job = self.get(job_id)
        if job is None:
            return None
        job.cancel_requested = True
        if job.status == "queued":
            job.status = "cancelled"
            job.finished_at = datetime.now().astimezone().isoformat(timespec="seconds")
        elif job.process is not None:
            try:
                os.killpg(os.getpgid(job.process.pid), signal.SIGTERM)
            except OSError:
                pass
        return job

    # -- worker --------------------------------------------------------- #
    def _append(self, job: Job, event: dict) -> None:
        job.logs.append(event)
        if len(job.logs) > MAX_LOG_LINES:
            del job.logs[: len(job.logs) - MAX_LOG_LINES]

    def _loop(self) -> None:
        while True:
            job = self.queue.get()
            if job is None:
                return
            if job.cancel_requested:
                continue
            try:
                self._run(job)
            except Exception as e:  # never kill the worker thread
                job.status = "failed"
                job.error = str(e)
                job.finished_at = datetime.now().astimezone().isoformat(timespec="seconds")

    def _run(self, job: Job) -> None:
        JOBS_DIR.mkdir(parents=True, exist_ok=True)
        log_path = JOBS_DIR / f"{job.id}.log"
        command = build_command(job.type, job.params)
        job.status = "running"
        job.started_at = datetime.now().astimezone().isoformat(timespec="seconds")

        env = os.environ.copy()
        env["DUBLA_LOG_JSON"] = "1"
        env["PYTHONPATH"] = str(ROOT)
        env.pop("DUBLA_API_TOKEN", None)

        with open(log_path, "a", encoding="utf-8") as log_file:
            log_file.write(json.dumps({"ts": job.started_at, "level": "info", "source": "api",
                                       "message": "command: " + " ".join(command)}) + "\n")
            try:
                process = subprocess.Popen(
                    command,
                    cwd=str(ROOT),
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    text=True,
                    bufsize=1,
                    env=env,
                    start_new_session=True,
                )
            except OSError as e:
                job.status = "failed"
                job.error = f"could not start: {e}"
                job.finished_at = datetime.now().astimezone().isoformat(timespec="seconds")
                return

            job.process = process
            assert process.stdout is not None
            for line in process.stdout:
                text = line.rstrip()
                if not text:
                    continue
                try:
                    event = json.loads(text)
                    if not isinstance(event, dict):
                        raise ValueError
                except (json.JSONDecodeError, ValueError):
                    event = {
                        "ts": datetime.now().astimezone().isoformat(timespec="seconds"),
                        "level": "info",
                        "source": "",
                        "message": text,
                    }
                event.setdefault("ts", datetime.now().astimezone().isoformat(timespec="seconds"))
                event.setdefault("level", "info")
                event.setdefault("source", "")
                event.setdefault("message", "")
                self._append(job, event)
                log_file.write(json.dumps(event, ensure_ascii=False) + "\n")

                message = str(event.get("message") or "")
                if "pipeline done:" in message:
                    job.result = message.split("pipeline done:", 1)[1].strip()
                elif message.endswith(".mp4") and Path(message).is_file():
                    job.result = message

            job.return_code = process.wait()
            job.process = None

        if job.cancel_requested:
            job.status = "cancelled"
        elif job.return_code == 0:
            job.status = "succeeded"
        else:
            job.status = "failed"
            job.error = f"process exited with code {job.return_code}"
        job.finished_at = datetime.now().astimezone().isoformat(timespec="seconds")


manager = JobManager()


class JobRequest(BaseModel):
    type: Literal["pipeline", "script", "models"]
    url: str | None = None
    name: str | None = None
    params: dict = Field(default_factory=dict)


@router.post("", status_code=201)
def create_job(payload: JobRequest) -> dict:
    params = dict(payload.params)
    if payload.type == "pipeline":
        if not payload.url:
            raise HTTPException(status_code=400, detail="url is required for pipeline jobs")
        params["url"] = payload.url
    elif payload.type == "script":
        if not payload.name:
            raise HTTPException(status_code=400, detail="name is required for script jobs")
        params["name"] = payload.name

    try:
        job = manager.create(payload.type, params)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    return job.public()


@router.get("")
def list_jobs(limit: int = 50, status: str | None = None) -> list[dict]:
    jobs = sorted(manager.jobs.values(), key=lambda item: item.created_at, reverse=True)
    if status:
        jobs = [job for job in jobs if job.status == status]
    return [job.public() for job in jobs[: max(1, min(limit, 200))]]


@router.get("/{job_id}")
def get_job(job_id: str) -> dict:
    job = manager.get(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="job not found")
    return job.public()


@router.get("/{job_id}/logs")
def get_logs(job_id: str, tail: int = 200) -> dict:
    job = manager.get(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="job not found")
    return {"id": job.id, "status": job.status, "logs": job.logs[-max(1, min(tail, 2000)):]}


@router.post("/{job_id}/cancel")
def cancel_job(job_id: str) -> dict:
    job = manager.cancel(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="job not found")
    return job.public()


@router.get("/{job_id}/events")
async def job_events(job_id: str):
    job = manager.get(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="job not found")

    async def stream():
        sent = 0
        while True:
            current = manager.get(job_id)
            if current is None:
                break
            while sent < len(current.logs):
                yield f"data: {json.dumps(current.logs[sent], ensure_ascii=False)}\n\n"
                sent += 1
            yield f"event: status\ndata: {json.dumps({'status': current.status})}\n\n"
            if current.status in TERMINAL:
                break
            await asyncio.sleep(0.4)

    return StreamingResponse(stream(), media_type="text/event-stream")
