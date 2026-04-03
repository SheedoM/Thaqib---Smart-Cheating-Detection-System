"""Video processing module for Thaqib."""

from thaqib.video.camera import CameraStream, FrameData
from thaqib.video.detector import HumanDetector, Detection, DetectionResult
from thaqib.video.tracker import ObjectTracker, TrackedObject, TrackingResult
from thaqib.video.head_pose import HeadPoseEstimator, HeadPose, HeadPoseResult
from thaqib.video.neighbor import NeighborModeler, StudentSpatialContext, RiskAngleRange
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
    "HeadPoseEstimator",
    "HeadPose",
    "HeadPoseResult",
    "NeighborModeler",
    "StudentSpatialContext",
    "RiskAngleRange",
    "VideoPipeline",
    "PipelineFrame",
    "StudentState",
]
