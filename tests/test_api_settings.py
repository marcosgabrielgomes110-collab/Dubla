import json


def test_get_settings(client, tmp_config):
    response = client.get("/api/v1/settings")
    assert response.status_code == 200
    assert response.json()["output_path"] == "Data/Movies/"


def test_schema(client):
    response = client.get("/api/v1/settings/schema")
    assert response.status_code == 200
    assert "stt_engine" in response.json()["settings"]
    assert "whisper" in response.json()["settings"]["stt_engine"]["options"]


def test_patch_settings(client, tmp_config):
    response = client.patch(
        "/api/v1/settings",
        json={"values": {"voice_workers": 2, "translation_engine": "argos"}},
    )
    assert response.status_code == 200
    assert response.json()["voice_workers"] == 2
    assert json.loads(tmp_config.read_text())["voice_workers"] == 2
    assert tmp_config.with_suffix(".json.bak").is_file()


def test_patch_unknown_key(client, tmp_config):
    response = client.patch("/api/v1/settings", json={"values": {"nope": 1}})
    assert response.status_code == 400


def test_patch_invalid_enum(client, tmp_config):
    response = client.patch(
        "/api/v1/settings",
        json={"values": {"stt_engine": "magic"}},
    )
    assert response.status_code == 400


def test_patch_invalid_range(client, tmp_config):
    response = client.patch(
        "/api/v1/settings",
        json={"values": {"voice_workers": 99}},
    )
    assert response.status_code == 400


def test_patch_empty(client, tmp_config):
    response = client.patch("/api/v1/settings", json={"values": {}})
    assert response.status_code == 400
