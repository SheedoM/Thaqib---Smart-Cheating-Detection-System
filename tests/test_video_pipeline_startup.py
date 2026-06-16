import sys
import types


def _install_tracker_stub() -> None:
    boxmot = types.ModuleType("boxmot")
    trackers = types.ModuleType("boxmot.trackers")
    bbox = types.ModuleType("boxmot.trackers.bbox")
    botsort_pkg = types.ModuleType("boxmot.trackers.bbox.botsort")
    botsort_mod = types.ModuleType("boxmot.trackers.bbox.botsort.botsort")

    class DummyBotSort:
        def __init__(self, *args, **kwargs):
            pass

    botsort_mod.BotSort = DummyBotSort
    sys.modules.setdefault("boxmot", boxmot)
    sys.modules.setdefault("boxmot.trackers", trackers)
    sys.modules.setdefault("boxmot.trackers.bbox", bbox)
    sys.modules.setdefault("boxmot.trackers.bbox.botsort", botsort_pkg)
    sys.modules.setdefault("boxmot.trackers.bbox.botsort.botsort", botsort_mod)


def test_video_pipeline_start_does_not_block_on_detector_warmup():
    _install_tracker_stub()

    from src.thaqib.video.pipeline import VideoPipeline

    pipeline = VideoPipeline(source=0)
    pipeline._camera.open = lambda: True

    def fail_if_called() -> None:
        raise AssertionError("detector warmup should not block pipeline.start()")

    pipeline._detector.load = fail_if_called
    pipeline._tools_detector.load = fail_if_called

    try:
        assert pipeline.start() is True
    finally:
        pipeline.stop()
