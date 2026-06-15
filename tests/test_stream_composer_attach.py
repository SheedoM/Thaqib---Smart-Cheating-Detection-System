from pathlib import Path

from src.thaqib.api.routes import stream


def test_attach_composer_clip_moves_file_to_latest_camera_alert(tmp_path, monkeypatch):
    monkeypatch.setattr(stream, "ALERTS_DIR", tmp_path)
    monkeypatch.setattr(stream, "_ROOT_ALERTS_DIR", tmp_path.resolve())
    output = tmp_path / "composer-output.mp4"
    output.write_bytes(b"mp4")

    stream._alerts.clear()
    stream._alerts.append(
        {
            "id": "not-this-one",
            "camera_id": "camera-2",
            "timestamp": "2026-06-15T10:00:00+00:00",
            "rel_prefix": "20260615/Hall/camera-2",
            "video_file": None,
        }
    )
    stream._alerts.append(
        {
            "id": "alert-1",
            "camera_id": "camera-1",
            "timestamp": "2026-06-15T10:01:00+00:00",
            "rel_prefix": "20260615/Hall/camera-1",
            "video_file": None,
        }
    )

    rel_path = stream._attach_composer_clip("camera-1", output)

    assert rel_path == "20260615/Hall/camera-1/clips/composer-output.mp4"
    assert stream._alerts[1]["video_file"] == rel_path
    assert (tmp_path / rel_path).read_bytes() == b"mp4"
