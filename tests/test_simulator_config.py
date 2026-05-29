from pathlib import Path

import yaml


def test_hall101_simulator_uses_docker_video_mount_paths():
    config = yaml.safe_load(Path("simulator/config.yaml").read_text())

    assert config["cameras"]["hall101_cam_front"]["video_path"] == "/app/videos/cam1.mp4"
    assert config["cameras"]["hall101_cam_back"]["video_path"] == "/app/videos/cam2.mp4"
    assert config["cameras"]["hall101_cam_side"]["video_path"] == "/app/videos/cam1.mp4"


def test_simulator_resolves_docker_video_paths_for_local_runs(tmp_path, monkeypatch):
    from simulator import main as simulator_main

    video_file = tmp_path / "cam1.mp4"
    video_file.write_bytes(b"not-a-real-video")
    monkeypatch.setattr(simulator_main, "DEFAULT_VIDEOS_DIR", tmp_path)

    assert simulator_main.resolve_video_path("/app/videos/cam1.mp4") == str(video_file)
