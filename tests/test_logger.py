import json


def test_json_logger(monkeypatch, capfd):
    monkeypatch.setenv("DUBLA_LOG_JSON", "1")
    from etc.Logger import log_info

    log_info("hello json")
    output = capfd.readouterr().out
    lines = [line for line in output.splitlines() if line.strip()]
    data = json.loads(lines[-1])
    assert data["level"] == "info"
    assert data["message"] == "hello json"
    assert "ts" in data
