"""Video processing module for Thaqib."""

from thaqib.video.camera import CameraStream, FrameData
from thaqib.video.detector import HumanDetector, Detection, DetectionResult
from thaqib.video.tracker import ObjectTracker, TrackedObject, TrackingResult
from thaqib.video.pipeline import VideoPipeline, PipelineFrame, StudentState

__all__ = [
    "CameraStream",
    "FrameData",
    "HumanDetector",
    "Detection",
    "DetectionResult",
    "ObjectTracker",
    "TrackedObject",
    "TrackingResult",
    "VideoPipeline",
    "PipelineFrame",
    "StudentState",
]
