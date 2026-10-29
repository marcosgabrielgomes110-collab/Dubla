import json


def test_health_and_info(client):
    assert client.get("/api/v1/health").json()["status"] == "ok"
    info = client.get("/api/v1/system/info")
    assert info.status_code == 200
    assert "ffmpeg" in info.json()["binaries"]


def test_previews(client, monkeypatch, tmp_path):
    from src.Dubla_Api import system

    monkeypatch.setattr(system, "PREVIEWS_DIR", tmp_path)
    (tmp_path / "piper.wav").write_bytes(b"RIFFtest")

    listing = client.get("/api/v1/system/previews").json()
    assert listing[0]["name"] == "piper.wav"

    response = client.get("/api/v1/system/previews/piper.wav")
    assert response.status_code == 200
    assert response.content == b"RIFFtest"

    assert client.get("/api/v1/system/previews/..%2Fsecret.wav").status_code in (400, 404)


def test_secrets(client, monkeypatch, tmp_path):
    import src.Dubla_Config as cfg

    env = tmp_path / ".env"
    monkeypatch.setattr(cfg, "ENV_PATH", env)

    response = client.put(
        "/api/v1/secrets/LLM_API_KEY",
        json={"value": "sk-test-1234567890"},
    )
    assert response.status_code == 200
    assert env.read_text().strip() == "LLM_API_KEY=sk-test-1234567890"

    listing = client.get("/api/v1/secrets").json()
    assert listing["LLM_API_KEY"]["set"] is True
    assert "sk-test-1234567890" not in json.dumps(listing)

    assert client.delete("/api/v1/secrets/LLM_API_KEY").status_code == 200
    assert "LLM_API_KEY" not in env.read_text()

    assert client.put("/api/v1/secrets/NOPE", json={"value": "x"}).status_code == 400


def test_auth(client, monkeypatch, tmp_config):
    monkeypatch.setenv("DUBLA_API_TOKEN", "secret-token")

    assert client.get("/api/v1/settings").status_code == 401
    assert (
        client.get("/api/v1/settings", headers={"X-API-Token": "secret-token"}).status_code
        == 200
    )
    assert client.get("/api/v1/health").status_code == 200
