import json
import logging
import math
import os
import tempfile
import threading
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


@dataclass
class MicPin:
    mic_id: str
    camera_id: str
    norm_pos: Tuple[float, float]  # Normalized coordinates [0.0, 1.0]


class MicLayout:
    def __init__(self, config_path: str | Path | None = None):
        self.pins: Dict[str, List[MicPin]] = {}
        self._lock = threading.Lock()
        self.config_path = Path(config_path) if config_path else Path("mic_layout.json")

        # Auto-load layout from file if it exists
        if self.config_path.exists():
            try:
                self.load(self.config_path)
            except Exception as e:
                logger.warning(f"Could not auto-load mic layout from {self.config_path}: {e}")

    def add_pin(self, mic_id: str, camera_id: str, norm_pos: Tuple[float, float], auto_save: bool = False):
        with self._lock:
            if mic_id not in self.pins:
                self.pins[mic_id] = []
            for i, pin in enumerate(self.pins[mic_id]):
                if pin.camera_id == camera_id:
                    self.pins[mic_id][i] = MicPin(mic_id, camera_id, (float(norm_pos[0]), float(norm_pos[1])))
                    if auto_save:
                        self._save_unlocked(self.config_path)
                    return
            self.pins[mic_id].append(MicPin(mic_id, camera_id, (float(norm_pos[0]), float(norm_pos[1]))))
            if auto_save:
                self._save_unlocked(self.config_path)

    def remove_pin(self, mic_id: str, camera_id: str, auto_save: bool = False):
        with self._lock:
            if mic_id in self.pins:
                self.pins[mic_id] = [p for p in self.pins[mic_id] if p.camera_id != camera_id]
                if not self.pins[mic_id]:
                    del self.pins[mic_id]
                if auto_save:
                    self._save_unlocked(self.config_path)

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

    def save(self, path: str | Path | None = None) -> None:
        """Atomically save the current layout configuration to a JSON file."""
        target_path = Path(path) if path else self.config_path
        with self._lock:
            self._save_unlocked(target_path)

    def _save_unlocked(self, target_path: Path) -> None:
        target_path.parent.mkdir(parents=True, exist_ok=True)
        data = {
            mic_id: [
                {"camera_id": pin.camera_id, "norm_pos": list(pin.norm_pos)}
                for pin in pin_list
            ]
            for mic_id, pin_list in self.pins.items()
        }
        
        # Write to temp file then rename atomically
        temp_fd, temp_file = tempfile.mkstemp(
            prefix="mic_layout_", suffix=".tmp", dir=str(target_path.parent)
        )
        try:
            with os.fdopen(temp_fd, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)
            os.replace(temp_file, target_path)
            logger.info(f"Mic layout successfully saved to {target_path}")
        except Exception as e:
            if os.path.exists(temp_file):
                os.remove(temp_file)
            logger.error(f"Failed to save mic layout to {target_path}: {e}")
            raise

    def load(self, path: str | Path | None = None) -> None:
        """Load layout configuration from a JSON file."""
        target_path = Path(path) if path else self.config_path
        with self._lock:
            if not target_path.exists():
                logger.warning(f"Mic layout file {target_path} does not exist.")
                return

            with open(target_path, "r", encoding="utf-8") as f:
                data = json.load(f)

            new_pins: Dict[str, List[MicPin]] = {}
            for mic_id, pin_list in data.items():
                new_pins[mic_id] = [
                    MicPin(
                        mic_id=mic_id,
                        camera_id=item["camera_id"],
                        norm_pos=(float(item["norm_pos"][0]), float(item["norm_pos"][1]))
                    )
                    for item in pin_list
                ]
            self.pins = new_pins
            logger.info(f"Loaded {len(self.pins)} mic layout pins from {target_path}")
