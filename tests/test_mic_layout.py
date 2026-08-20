"""
Unit tests for Repair E: MicLayout Persistence & Spatial Mapping.
"""

import json
import os
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from thaqib.mic_layout import MicLayout, MicPin


class TestMicLayout(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.mkdtemp(prefix="thaqib_test_miclayout_")
        self.config_file = os.path.join(self.temp_dir, "test_mic_layout.json")

    def tearDown(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_add_and_query_pins(self):
        """Adding pins should allow querying by camera and nearest spatial lookup."""
        layout = MicLayout(config_path=self.config_file)
        layout.add_pin("mic0", "cam0", (0.25, 0.5))
        layout.add_pin("mic1", "cam0", (0.75, 0.5))

        pins = layout.get_pins_for_camera("cam0")
        self.assertEqual(len(pins), 2)

        # Nearest to (200, 500) on a (1000, 1000) frame -> normalized (0.2, 0.5) -> mic0
        nearest = layout.nearest_mic_for_point((200, 500), "cam0", (1000, 1000))
        self.assertIsNotNone(nearest)
        self.assertEqual(nearest.mic_id, "mic0")

        # Nearest to (800, 500) on a (1000, 1000) frame -> normalized (0.8, 0.5) -> mic1
        nearest2 = layout.nearest_mic_for_point((800, 500), "cam0", (1000, 1000))
        self.assertIsNotNone(nearest2)
        self.assertEqual(nearest2.mic_id, "mic1")

    def test_save_and_load_persistence(self):
        """Layout saved to JSON should reload with identical pins."""
        layout = MicLayout(config_path=self.config_file)
        layout.add_pin("mic_front", "cam_hall", (0.3, 0.4))
        layout.add_pin("mic_back", "cam_door", (0.8, 0.9))
        layout.save()

        self.assertTrue(os.path.exists(self.config_file))

        # Create fresh instance pointing to the same config file (auto-load)
        layout2 = MicLayout(config_path=self.config_file)
        self.assertEqual(len(layout2.pins), 2)
        self.assertEqual(layout2.camera_for_mic("mic_front"), "cam_hall")
        self.assertEqual(layout2.camera_for_mic("mic_back"), "cam_door")

    def test_unmapped_queries_are_safe(self):
        """Querying an unmapped mic or camera without pins must return None/[] safely."""
        layout = MicLayout(config_path=self.config_file)
        self.assertEqual(layout.cameras_for_mic("mic_unmapped"), [])
        self.assertIsNone(layout.camera_for_mic("mic_unmapped"))
        self.assertIsNone(layout.nearest_mic_for_point((100, 100), "cam_unmapped", (640, 480)))


if __name__ == "__main__":
    unittest.main()
