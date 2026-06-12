import json
import math
import os
import threading
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple


@dataclass
class MicPin:
    mic_id: str
    camera_id: str
    norm_pos: Tuple[float, float]  # Normalized coordinates [0.0, 1.0]


class MicLayout:
    def __init__(self, layout_file: str = "mic_layout.json"):
        self.layout_file = layout_file
        self.pins: Dict[str, MicPin] = {}
        self._lock = threading.Lock()
        self.load()

    def load(self):
        with self._lock:
            if not os.path.exists(self.layout_file):
                return
            try:
                with open(self.layout_file, 'r') as f:
                    data = json.load(f)
                    for mic_id, info in data.items():
                        # Backward compatibility: if it has pixel_pos, we can't easily convert without frame size, 
                        # so we assume it was already norm_pos or we just read norm_pos
                        if "norm_pos" in info:
                            pos = tuple(info["norm_pos"])
                        elif "pixel_pos" in info:
                            # If it was saved with old format, we assume 1280x720 for migration or it breaks
                            # Let's just read it as norm_pos and hope for the best, or migrate it
                            pos = (info["pixel_pos"][0] / 1280.0, info["pixel_pos"][1] / 720.0)
                        else:
                            pos = (0.5, 0.5)
                        
                        self.pins[mic_id] = MicPin(
                            mic_id=mic_id,
                            camera_id=info["camera_id"],
                            norm_pos=pos
                        )
            except Exception as e:
                print(f"Error loading mic layout: {e}")

    def save(self):
        with self._lock:
            data = {
                mic_id: {
                    "camera_id": pin.camera_id,
                    "norm_pos": pin.norm_pos
                }
                for mic_id, pin in self.pins.items()
            }
            try:
                with open(self.layout_file, 'w') as f:
                    json.dump(data, f, indent=4)
            except Exception as e:
                print(f"Error saving mic layout: {e}")

    def add_pin(self, mic_id: str, camera_id: str, norm_pos: Tuple[float, float]):
        with self._lock:
            self.pins[mic_id] = MicPin(mic_id, camera_id, norm_pos)
        self.save()

    def get_pins_for_camera(self, camera_id: str) -> List[MicPin]:
        with self._lock:
            return [pin for pin in self.pins.values() if pin.camera_id == camera_id]

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

    def camera_for_mic(self, mic_id: str) -> Optional[str]:
        with self._lock:
            pin = self.pins.get(mic_id)
            return pin.camera_id if pin else None
