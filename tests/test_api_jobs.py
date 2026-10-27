import sys
import time


def _wait(client, job_id, timeout=10.0):
    deadline = time.time() + timeout
    while time.time() < deadline:
        data = client.get(f"/api/v1/jobs/{job_id}").json()
        if data["status"] in ("succeeded", "failed", "cancelled"):
            return data
        time.sleep(0.1)
    raise AssertionError("job did not finish")


def test_job_lifecycle(client, monkeypatch, tmp_path):
    from src.Dubla_Api import jobs

    monkeypatch.setattr(jobs, "JOBS_DIR", tmp_path)
    monkeypatch.setattr(jobs, "ROOT", tmp_path)
    monkeypatch.setattr(
        jobs,
        "build_command",
        lambda kind, params: [
            sys.executable,
            "-u",
            "-c",
            "print('hello'); print('pipeline done: /tmp/fake.mp4')",
        ],
    )

    response = client.post("/api/v1/jobs", json={"type": "script", "name": "fake"})
    assert response.status_code == 201
    job_id = response.json()["id"]

    data = _wait(client, job_id)
    assert data["status"] == "succeeded"
    assert data["result"] == "/tmp/fake.mp4"

    logs = client.get(f"/api/v1/jobs/{job_id}/logs").json()["logs"]
    messages = [item.get("message") for item in logs]
    assert "hello" in messages


def test_job_validation(client):
    assert client.post("/api/v1/jobs", json={"type": "pipeline"}).status_code == 400
    assert client.post("/api/v1/jobs", json={"type": "script"}).status_code == 400
    assert (
        client.post("/api/v1/jobs", json={"type": "pipeline", "url": "ftp://x"}).status_code
        == 400
    )
    assert client.get("/api/v1/jobs/does-not-exist").status_code == 404


def test_job_cancel(client, monkeypatch, tmp_path):
    from src.Dubla_Api import jobs

    monkeypatch.setattr(jobs, "JOBS_DIR", tmp_path)
    monkeypatch.setattr(jobs, "ROOT", tmp_path)
    monkeypatch.setattr(
        jobs,
        "build_command",
        lambda kind, params: [sys.executable, "-c", "import time; time.sleep(30)"],
    )

    response = client.post("/api/v1/jobs", json={"type": "script", "name": "slow"})
    job_id = response.json()["id"]
    for _ in range(30):
        if client.get(f"/api/v1/jobs/{job_id}").json()["status"] == "running":
            break
        time.sleep(0.1)

    assert client.post(f"/api/v1/jobs/{job_id}/cancel").status_code == 200
    data = _wait(client, job_id, timeout=10)
    assert data["status"] == "cancelled"
