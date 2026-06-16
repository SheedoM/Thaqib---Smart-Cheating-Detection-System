import importlib


def test_tracker_module_imports_with_installed_boxmot_layout():
    tracker = importlib.import_module("src.thaqib.video.tracker")
    assert tracker.BotSort is not None


def test_object_tracker_factory_filters_unsupported_boxmot_kwargs(monkeypatch):
    tracker = importlib.import_module("src.thaqib.video.tracker")
    captured = {}
    sentinel = object()

    class DummyBotSort:
        def __init__(
            self,
            reid_weights,
            device,
            half,
            per_class=False,
            track_high_thresh=0.5,
            track_low_thresh=0.1,
            new_track_thresh=0.6,
            track_buffer=30,
            match_thresh=0.8,
            proximity_thresh=0.5,
            appearance_thresh=0.25,
            cmc_method=sentinel,
            frame_rate=30,
            fuse_first_associate=False,
            with_reid=True,
        ):
            captured.update(locals())

    monkeypatch.setattr(tracker, "BotSort", DummyBotSort)

    tracker.ObjectTracker(max_age=42)

    assert captured["track_buffer"] == 42
    assert "max_age" not in captured
    assert "max_obs" not in captured
    assert captured["cmc_method"] is sentinel
