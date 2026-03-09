"""
Video visualization layer.

Responsible ONLY for drawing overlays onto frames.
Does NOT perform detection, tracking, registry updates, or neighbor computation.
"""

import cv2
import numpy as np
import functools

from thaqib.video.pipeline import PipelineFrame
from thaqib.video.registry import GlobalStudentRegistry


@functools.lru_cache(maxsize=1024)
def _track_color(track_id: int) -> tuple[int, int, int]:
    """Return a deterministic unique color for a given track_id."""
    rng = np.random.RandomState(track_id)
    return tuple(int(c) for c in rng.randint(60, 230, 3))


class VideoVisualizer:
    """
    Visualization layer for the video processing pipeline.

    Draws bounding boxes, IDs, neighbor graph lines, and HUD info onto frames.
    Fully decoupled from all processing logic — only reads data, never mutates it.
    """

    def __init__(self) -> None:
        self.show_neighbors: bool = False

    def toggle_neighbors(self) -> None:
        """Toggle neighbor graph rendering on/off."""
        self.show_neighbors = not self.show_neighbors

    # ------------------------------------------------------------------
    # Public entry point
    # ------------------------------------------------------------------

    def draw(
        self,
        pipeline_frame: PipelineFrame,
        registry: GlobalStudentRegistry | None = None,
    ) -> np.ndarray:
        """
        Render all enabled overlays onto the frame.

        Args:
            pipeline_frame: The processed frame data from the pipeline.
            registry: Optional registry for neighbor graph rendering.

        Returns:
            A new annotated frame (the original is not modified).
        """
        annotated = pipeline_frame.frame.copy()

        self._draw_unselected_tracks(annotated, pipeline_frame)
        self._draw_selected_students(annotated, pipeline_frame)

        if self.show_neighbors and registry is not None:
            self.draw_neighbors(annotated, registry)
            self._draw_legend_panel(annotated, pipeline_frame)

        self._draw_hud(annotated, pipeline_frame)
        self._draw_instructions(annotated)

        return annotated

    # ------------------------------------------------------------------
    # Feature 1 — bounding boxes & IDs
    # ------------------------------------------------------------------

    def _draw_unselected_tracks(self, frame: np.ndarray, pipeline_frame: PipelineFrame) -> None:
        """Draw all unselected tracks in gray."""
        for track in pipeline_frame.tracking_result.tracks:
            if track.is_selected:
                continue
            x1, y1, x2, y2 = track.bbox
            cv2.rectangle(frame, (x1, y1), (x2, y2), (128, 128, 128), 2)
            cv2.putText(
                frame,
                f"ID:{track.track_id}",
                (x1, y1 - 8),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.5,
                (128, 128, 128),
                1,
                cv2.LINE_AA,
            )

    def _draw_selected_students(self, frame: np.ndarray, pipeline_frame: PipelineFrame) -> None:
        """Draw selected students with unique per-ID colors."""
        for state in pipeline_frame.student_states:
            x1, y1, x2, y2 = state.bbox
            color = _track_color(state.track_id)

            cv2.rectangle(frame, (x1, y1), (x2, y2), color, 2)
            cv2.putText(
                frame,
                f"ID:{state.track_id}",
                (x1, y1 - 8),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.6,
                color,
                2,
                cv2.LINE_AA,
            )

            # Center dot
            cv2.circle(frame, state.center, 4, color, -1, cv2.LINE_AA)

            # Face mesh overlay
            self._draw_face_mesh(frame, state)

            # Iris center + gaze arrow
            self._draw_gaze(frame, state)

    # ------------------------------------------------------------------
    # Feature 2a — face mesh
    # ------------------------------------------------------------------

    def _draw_face_mesh(self, frame: np.ndarray, state) -> None:
        """Draw all face mesh landmarks as green dots on the student's face."""
        if state.face_mesh is None:
            return
        for (x, y) in state.face_mesh.landmarks_2d:
            cv2.circle(frame, (x, y), 1, (0, 255, 0), -1)

    def _draw_gaze(self, frame: np.ndarray, state) -> None:
        """
        Draw a combined 3D gaze arrow using MediaPipe's rotation matrix
        and 2D iris landmarks, with strictly aligned coordinate systems.
        """
        if state.face_mesh is None:
            return

        lm2d = state.face_mesh.landmarks_2d
        if len(lm2d) < 474:
            return

        def pt2d(idx):
            return np.array(lm2d[idx], dtype=float)

        head_matrix = state.face_mesh.head_matrix
        if head_matrix is None:
            return

        # 1. Base 3D Head Direction (MediaPipe 3D Space: +X is Left, -X is Right)
        R = head_matrix[:3, :3]
        head_3d = R @ np.array([0.0, 0.0, -1.0])

        # 2. Eye Deviation (Screen Space: +X is Right, -X is Left)
        l_center = (pt2d(33) + pt2d(133)) / 2.0
        l_pupil = pt2d(468)
        l_dev = l_pupil - l_center
        
        r_center = (pt2d(263) + pt2d(362)) / 2.0
        r_pupil = pt2d(473)
        r_dev = r_pupil - r_center
        
        avg_eye_dev = (l_dev + r_dev) / 2.0
        
        # Normalize by eye width
        eye_width = np.linalg.norm(pt2d(33) - pt2d(133))
        if eye_width > 1e-6:
            avg_eye_dev /= eye_width

        # 3. Combine in 3D Space (Coordinate Alignment)
        # CRITICAL FIX: Invert Eye X-axis to match MediaPipe's 3D Space
        eye_x_3d = -avg_eye_dev[0] 
        eye_y_3d = avg_eye_dev[1]
        
        EYE_STRENGTH = 3.0 # Increase/Decrease to make eyes more/less sensitive
        eye_3d = np.array([eye_x_3d, eye_y_3d, 0.0]) * EYE_STRENGTH
        
        combined_3d = head_3d + eye_3d

        # Normalize to maintain the 3D unit vector property (Depth illusion)
        norm = np.linalg.norm(combined_3d)
        if norm > 1e-6:
            combined_3d /= norm

        # 4. Project to 2D Screen Space (Convert +X=Left back to +X=Right for drawing)
        dir_x = -combined_3d[0]
        dir_y = combined_3d[1]

        # 5. Draw (Improved non-linear scale)
        bbox_height = state.bbox[3] - state.bbox[1]
        
        # Enlarge arrow for far students (small bbox), scale down for close ones
        base_scale = bbox_height * 1.0 if bbox_height < 100 else bbox_height * 0.6
        SCALE = int(max(60, min(base_scale, 200))) # Clamp between 60 and 200

        if not hasattr(state, "_gaze_scale"):
            state._gaze_scale = SCALE
        else:
            # Smooth the scale to avoid flickering
            state._gaze_scale = int(0.8 * state._gaze_scale + 0.2 * SCALE)
        SCALE = state._gaze_scale
        
        GAZE_COLOR = (0, 0, 255) # Red

        origin = tuple(lm2d[168])
        end = (
            int(origin[0] + dir_x * SCALE),
            int(origin[1] + dir_y * SCALE)
        )

        cv2.circle(frame, origin, 4, GAZE_COLOR, -1, cv2.LINE_AA)
        cv2.line(frame, origin, end, GAZE_COLOR, 5, cv2.LINE_AA)
        cv2.line(frame, origin, end, (0, 255, 255), 2, cv2.LINE_AA)
        cv2.circle(frame, end, 4, GAZE_COLOR, -1, cv2.LINE_AA)
    # ------------------------------------------------------------------
    # Feature 3 — neighbor graph
    # ------------------------------------------------------------------

    def draw_neighbors(self, frame: np.ndarray, registry: GlobalStudentRegistry) -> None:
        """
        Draw neighbor connection lines between students.

        For each student, draws a line to each of its k-nearest neighbors.
        """
        all_states = [s for s in registry.get_all() if getattr(s, "is_active", True)]

        for state in all_states:
            if not state.neighbors:
                continue

            src_center = state.center
            src_color = _track_color(state.track_id)

            for neighbor_id in state.neighbors:
                neighbor_state = registry.get(neighbor_id)
                if neighbor_state is None or not getattr(neighbor_state, "is_active", True):
                    continue

                dst_center = neighbor_state.center

                # Draw connection line
                cv2.line(
                    frame,
                    src_center,
                    dst_center,
                    src_color,
                    2,
                    cv2.LINE_AA,
                )

            # Draw circle at student center
            cv2.circle(frame, src_center, 6, src_color, 2, cv2.LINE_AA)

    # ------------------------------------------------------------------
    # HUD & instructions
    # ------------------------------------------------------------------

    def _draw_hud(self, frame: np.ndarray, pipeline_frame: PipelineFrame) -> None:
        """Draw top-left HUD with runtime stats."""
        neighbors_label = "ON" if self.show_neighbors else "OFF"
        info_lines = [
            f"FPS: {1000 / max(pipeline_frame.processing_time_ms, 1):.1f}",
            f"Tracked: {pipeline_frame.tracked_count}",
            f"Selected: {pipeline_frame.selected_count}",
            f"Frame: {pipeline_frame.frame_index}",
            f"Neighbors: {neighbors_label}",
        ]

        for i, line in enumerate(info_lines):
            cv2.putText(
                frame,
                line,
                (10, 30 + i * 25),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.6,
                (255, 255, 255),
                2,
                cv2.LINE_AA,
            )

    def _draw_instructions(self, frame: np.ndarray) -> None:
        """Draw bottom instruction bar."""
        instructions = "s: select all  |  c: clear  |  t: toggle neighbors  |  q: quit"
        cv2.putText(
            frame,
            instructions,
            (10, frame.shape[0] - 15),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.5,
            (200, 200, 200),
            1,
            cv2.LINE_AA,
        )

    def _draw_legend_panel(self, frame: np.ndarray, pipeline_frame: PipelineFrame) -> None:
        """Draw a transparent color legend on the right side of the screen."""
        if not pipeline_frame.tracking_result.tracks:
            return

        h, w = frame.shape[:2]
        panel_w = 180
        panel_x = w - panel_w
        
        # Draw transparent dark background
        overlay = frame.copy()
        cv2.rectangle(overlay, (panel_x, 0), (w, h), (20, 20, 20), -1)
        cv2.addWeighted(overlay, 0.6, frame, 0.4, 0, frame)

        # Draw title
        cv2.putText(frame, "STUDENTS", (panel_x + 15, 30),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2, cv2.LINE_AA)
        cv2.line(frame, (panel_x + 15, 40), (w - 15, 40), (100, 100, 100), 1)

        # Draw legend items
        y_pos = 70
        for track in pipeline_frame.tracking_result.tracks:
            color = _track_color(track.track_id)
            
            # Circle marker
            cv2.circle(frame, (panel_x + 30, y_pos - 5), 8, color, -1, cv2.LINE_AA)
            cv2.circle(frame, (panel_x + 30, y_pos - 5), 8, (255, 255, 255), 1, cv2.LINE_AA)
            
            # ID text
            alpha = "" if not track.is_selected else "(*)"
            text = f"ID: {track.track_id} {alpha}"
            txt_color = (255, 255, 255) if track.is_selected else (150, 150, 150)
            
            cv2.putText(frame, text, (panel_x + 55, y_pos),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.5, txt_color, 1, cv2.LINE_AA)
            y_pos += 30
