import logging
import math
import threading
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


@dataclass
class MicPin:
    mic_id: str
    camera_id: str
    norm_pos: Tuple[float, float]  # Normalized coordinates [0.0, 1.0]


class MicLayout:
    def __init__(self):
        self.pins: Dict[str, List[MicPin]] = {}
        self._lock = threading.Lock()

    def add_pin(self, mic_id: str, camera_id: str, norm_pos: Tuple[float, float]):
        with self._lock:
            if mic_id not in self.pins:
                self.pins[mic_id] = []
            for i, pin in enumerate(self.pins[mic_id]):
                if pin.camera_id == camera_id:
                    self.pins[mic_id][i] = MicPin(mic_id, camera_id, norm_pos)
                    return
            self.pins[mic_id].append(MicPin(mic_id, camera_id, norm_pos))

    def get_pins_for_camera(self, camera_id: str) -> List[MicPin]:
        with self._lock:
            result = []
            for pin_list in self.pins.values():
                for pin in pin_list:
                    if pin.camera_id == camera_id:
                        result.append(pin)
            return result

    def nearest_mic_for_point(self, point_xy: Tuple[int, int], camera_id: str, frame_size: Tuple[int, int]) -> Optional[MicPin]:
        """
        point_xy: absolute pixel coordinates (x, y)
        frame_size: (width, height) of the frame
        """
        camera_pins = self.get_pins_for_camera(camera_id)
        if not camera_pins:
            return None

        w, h = frame_size

        def dist(p1, p2):
            return math.hypot(p1[0] - p2[0], p1[1] - p2[1])

        # Convert pin norm_pos to absolute pixel coords for distance calculation
        def get_pixel_pos(pin: MicPin):
            return (pin.norm_pos[0] * w, pin.norm_pos[1] * h)

        nearest_pin = min(camera_pins, key=lambda p: dist(point_xy, get_pixel_pos(p)))
        return nearest_pin

    def cameras_for_mic(self, mic_id: str) -> List[str]:
        with self._lock:
            pin_list = self.pins.get(mic_id, [])
            return [pin.camera_id for pin in pin_list]

    def camera_for_mic(self, mic_id: str) -> Optional[str]:
        cameras = self.cameras_for_mic(mic_id)
        return cameras[0] if cameras else None
