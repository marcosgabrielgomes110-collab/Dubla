import json


def _make_movie(root, movie_id="abc123"):
    folder = root / movie_id
    folder.mkdir()
    video = folder / "My_Movie_Dubla_pt-BR.mp4"
    video.write_bytes(b"0123456789")
    (folder / f"{movie_id}_original_mudo.mp4").write_bytes(b"muted")
    (folder / "dub.wav").write_bytes(b"x")
    (folder / "voice").mkdir()
    (folder / "voice" / "0000.wav").write_bytes(b"x")
    data = {
        "id": movie_id,
        "title": "My Movie",
        "duration": 10,
        "translation": {"target": "pt"},
        "movie": {"mux_created_at": "2026-10-26T21:00:00-05:00"},
    }
    (folder / f"{movie_id}.json").write_text(json.dumps(data), encoding="utf-8")
    return folder, video


def test_list_and_detail(client, movies_root):
    _make_movie(movies_root)
    response = client.get("/api/v1/movies")
    assert response.status_code == 200
    movies = response.json()
    assert len(movies) == 1
    assert movies[0]["id"] == "abc123"
    assert movies[0]["title"] == "My Movie"
    assert movies[0]["video"].endswith("_Dubla_pt-BR.mp4")

    detail = client.get("/api/v1/movies/abc123")
    assert detail.status_code == 200
    assert detail.json()["title"] == "My Movie"


def test_video_range(client, movies_root):
    _make_movie(movies_root)

    full = client.get("/api/v1/movies/abc123/video")
    assert full.status_code == 200
    assert full.content == b"0123456789"

    part = client.get("/api/v1/movies/abc123/video", headers={"Range": "bytes=2-5"})
    assert part.status_code == 206
    assert part.content == b"2345"
    assert part.headers["content-range"] == "bytes 2-5/10"


def test_invalid_id(client, movies_root):
    assert client.get("/api/v1/movies/abc.def").status_code == 400
    assert client.get("/api/v1/movies/..%2Fetc").status_code in (400, 404)
    assert client.get("/api/v1/movies/doesnotexist").status_code == 404


def test_delete(client, movies_root):
    folder, _ = _make_movie(movies_root)
    response = client.delete("/api/v1/movies/abc123")
    assert response.status_code == 200
    assert not folder.exists()
