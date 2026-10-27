import json
from pathlib import Path

import src.Dubla_MovieManager.Dubla_Movie_Publish as publish_module


def test_publish_moves_renames_and_rewrites(tmp_path, monkeypatch):
    movie_id = "abc123"
    work = tmp_path / "temp" / movie_id
    (work / "voice").mkdir(parents=True)
    (work / f"{movie_id}.mp4").write_bytes(b"muted")
    (work / f"{movie_id}.wav").write_bytes(b"audio")
    (work / "dub.wav").write_bytes(b"dub")
    (work / "voice" / "0000.wav").write_bytes(b"voice")
    (work / f"{movie_id}_dublado.mp4").write_bytes(b"final")

    meta = {
        "id": movie_id,
        "title": "My Movie",
        "video_path": str(work / f"{movie_id}.mp4"),
        "audio_path": str(work / f"{movie_id}.wav"),
        "voice": {"segments": [{"path": str(work / "voice" / "0000.wav")}]},
        "movie": {"muxed_path": str(work / f"{movie_id}_dublado.mp4")},
    }
    (work / f"{movie_id}.json").write_text(json.dumps(meta), encoding="utf-8")

    output = tmp_path / "Movies"
    monkeypatch.setattr(publish_module, "OutputPath", output)

    final = publish_module.publish(work / f"{movie_id}.json", force=True)

    assert final == output / movie_id / "My_Movie_Dubla_pt-BR.mp4"
    folder = final.parent
    assert final.is_file()
    assert (folder / f"{movie_id}_original_mudo.mp4").is_file()
    assert not (folder / "dub.wav").exists()
    assert (folder / "voice" / "0000.wav").is_file()

    data = json.loads((folder / f"{movie_id}.json").read_text(encoding="utf-8"))
    assert data["video_path"].endswith(f"{movie_id}_original_mudo.mp4")
    assert data["audio_path"].endswith(f"{movie_id}.wav")
    assert data["voice"]["segments"][0]["path"].endswith("voice/0000.wav")
    assert data["movie"]["path"] == str(final)
    assert data["movie"]["output_dir"] == str(folder)
    assert Path(data["video_path"]).is_file()
    assert Path(data["voice"]["segments"][0]["path"]).is_file()
