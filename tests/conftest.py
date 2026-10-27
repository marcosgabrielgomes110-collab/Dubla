import json
import os
import shutil
import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
os.environ.pop("DUBLA_API_TOKEN", None)

from src.Dubla_Api.main import app  # noqa: E402


@pytest.fixture
def client():
    return TestClient(app)


@pytest.fixture
def tmp_config(tmp_path, monkeypatch):
    from src.Dubla_Api import settings

    source = ROOT / "configs.json"
    target = tmp_path / "configs.json"
    shutil.copy(source, target)
    monkeypatch.setattr(settings, "CONFIG_PATH", target)
    monkeypatch.setattr(settings, "BACKUP_PATH", target.with_suffix(".json.bak"))
    return target


@pytest.fixture
def movies_root(tmp_path, monkeypatch):
    import src.Dubla_Config as cfg

    root = tmp_path / "Movies"
    root.mkdir()
    monkeypatch.setattr(cfg, "OutputPath", root)
    return root


def write_json(path: Path, data: dict) -> None:
    path.write_text(json.dumps(data, indent=4), encoding="utf-8")
