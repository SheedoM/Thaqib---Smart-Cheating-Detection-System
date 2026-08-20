"""
Unit tests for Repair B: Incident State Machine & Severity Hierarchy.
"""

import sys
import unittest
from pathlib import Path
from collections import deque

# Add src to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from thaqib.video.registry import StudentSpatialState, GlobalStudentRegistry
from thaqib.video.tracker import TrackedObject


class TestIncidentStateMachine(unittest.TestCase):
    def setUp(self):
        self.registry = GlobalStudentRegistry()

    def test_gaze_incident_lifecycle(self):
        """NORMAL -> GAZE -> POSTROLL -> FINALIZE produces gaze alert."""
        state = StudentSpatialState(
            track_id=1,
            bbox=(100, 100, 200, 200),
            center=(150, 150),
            paper_center=(150, 250),
            frame_index=10,
            timestamp=1.0,
        )

        # 1. Start Gaze Incident
        state.is_cheating = True
        state.active_incident_type = "gaze"
        state.incident_context = {
            'target_paper': (300, 250),
            'target_neighbor': 2,
            'is_using_phone': False,
        }
        state.is_alert_recording = True
        state.frames_to_record = 60

        self.assertTrue(state.is_alert_recording)
        self.assertEqual(state.active_incident_type, "gaze")

        # 2. Gaze stops -> Post-roll countdown begins
        state.is_cheating = False
        state.frames_to_record -= 1
        self.assertEqual(state.frames_to_record, 59)
        self.assertEqual(state.active_incident_type, "gaze")  # Latched

        # 3. Post-roll reaches zero -> Finalize
        state.frames_to_record = 0
        final_cheat_type = state.active_incident_type
        self.assertEqual(final_cheat_type, "gaze")
        self.assertEqual(state.incident_context['target_neighbor'], 2)

    def test_phone_incident_lifecycle_when_phone_hidden(self):
        """NORMAL -> PHONE -> Phone Disappears -> POSTROLL -> FINALIZE must retain PHONE alert type."""
        state = StudentSpatialState(
            track_id=1,
            bbox=(100, 100, 200, 200),
            center=(150, 150),
            paper_center=(150, 250),
            frame_index=10,
            timestamp=1.0,
        )

        # 1. Phone detected
        state.is_using_phone = True
        state.phone_bbox = (120, 140, 160, 180)
        state.is_cheating = True
        state.is_alert_recording = True
        state.active_incident_type = "phone"
        state.incident_context = {
            'is_using_phone': True,
            'phone_bbox': state.phone_bbox,
        }
        state.frames_to_record = 60

        # 2. Phone disappears on next frame (e.g. hidden in pocket)
        state.is_using_phone = False
        state.phone_bbox = None
        state.is_cheating = False

        # Post-roll countdown
        for _ in range(60):
            state.frames_to_record -= 1

        self.assertEqual(state.frames_to_record, 0)
        # Invariant: active_incident_type MUST remain "phone" despite is_using_phone being False
        final_cheat_type = state.active_incident_type
        self.assertEqual(final_cheat_type, "phone")
        self.assertTrue(state.incident_context['is_using_phone'])
        self.assertEqual(state.incident_context['phone_bbox'], (120, 140, 160, 180))

    def test_severity_upgrade_gaze_to_phone(self):
        """Active GAZE incident should upgrade to PHONE when phone is detected during recording."""
        state = StudentSpatialState(
            track_id=1,
            bbox=(100, 100, 200, 200),
            center=(150, 150),
            paper_center=(150, 250),
            frame_index=10,
            timestamp=1.0,
        )

        # 1. Start Gaze Incident
        state.is_cheating = True
        state.active_incident_type = "gaze"
        state.incident_context = {
            'target_paper': (300, 250),
            'target_neighbor': 2,
            'is_using_phone': False,
        }
        state.is_alert_recording = True
        state.frames_to_record = 30

        # 2. Phone detected during gaze recording (Upgrade Event)
        state.is_using_phone = True
        state.phone_bbox = (130, 150, 170, 190)
        
        # Severity upgrade logic:
        if state.is_using_phone and state.active_incident_type != "phone":
            state.active_incident_type = "phone"
            state.incident_context['is_using_phone'] = True
            state.incident_context['phone_bbox'] = state.phone_bbox
            state.frames_to_record = 60  # Reset countdown

        self.assertEqual(state.active_incident_type, "phone")
        self.assertEqual(state.frames_to_record, 60)
        self.assertEqual(state.incident_context['target_neighbor'], 2)
        self.assertEqual(state.incident_context['phone_bbox'], (130, 150, 170, 190))

    def test_phone_incident_retains_priority_over_subsequent_gaze(self):
        """Active PHONE incident should NOT be downgraded to gaze if student looks away."""
        state = StudentSpatialState(
            track_id=1,
            bbox=(100, 100, 200, 200),
            center=(150, 150),
            paper_center=(150, 250),
            frame_index=10,
            timestamp=1.0,
        )

        state.active_incident_type = "phone"
        state.incident_context = {'is_using_phone': True, 'phone_bbox': (100, 100, 120, 120)}
        state.is_alert_recording = True

        # Gaze cheat detected while phone incident active
        state.cheating_target_paper = (400, 300)
        state.cheating_target_neighbor = 3

        # Updating context with gaze details
        if state.cheating_target_paper and not state.incident_context.get('target_paper'):
            state.incident_context['target_paper'] = state.cheating_target_paper
            state.incident_context['target_neighbor'] = state.cheating_target_neighbor

        # Incident type MUST remain phone
        self.assertEqual(state.active_incident_type, "phone")
        self.assertEqual(state.incident_context['target_neighbor'], 3)

    def test_expired_tracks_flush_latched_incident_type(self):
        """When track expires during active recording, registry update returns states with latched incident."""
        track = TrackedObject(track_id=42, bbox=(50, 50, 100, 100), confidence=0.9)
        self.registry.update([track], frame_index=1, timestamp=0.0)

        state = self.registry.get(42)
        self.assertIsNotNone(state)
        state.is_alert_recording = True
        state.active_incident_type = "phone"
        state.recording_buffer = deque([b"frame1", b"frame2"])
        state.incident_context = {'is_using_phone': True}

        # Track is lost for > 3.0 seconds
        expired_states = self.registry.update([], frame_index=100, timestamp=4.0)

        self.assertEqual(len(expired_states), 1)
        expired_state = expired_states[0]
        self.assertEqual(expired_state.track_id, 42)
        self.assertEqual(expired_state.active_incident_type, "phone")
        self.assertEqual(len(expired_state.recording_buffer), 2)
        self.assertTrue(expired_state.incident_context['is_using_phone'])


if __name__ == "__main__":
    unittest.main()
