"""
Video visualization layer.

Responsible ONLY for drawing overlays onto frames.
Does NOT perform detection, tracking, registry updates, or neighbor computation.
"""

import cv2
import numpy as np

from thaqib.video.pipeline import PipelineFrame
from thaqib.video.registry import GlobalStudentRegistry


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
        Draw a single combined gaze arrow using:
          - head pose Z-axis from MediaPipe facial transformation matrix
          - eye gaze vector from 3D iris/eye-corner landmarks

        Landmark indexes:
          168 → midpoint between eyes   (2D screen origin)
          468 → left iris center        (3D eye gaze)
          33  → left eye outer corner   } 3D eye center average
          133 → left eye inner corner   }
        """
        if state.face_mesh is None:
            return

        lm2d = state.face_mesh.landmarks_2d
        lm3d = state.face_mesh.landmarks_3d
        if len(lm2d) < 474 or len(lm3d) < 474:
            return

        def pt3d(idx):
            return np.array(lm3d[idx], dtype=float)

        head_matrix = state.face_mesh.head_matrix
        if head_matrix is None:
            return

        # Step 1 — Local Eye Vector
        eye_center_local = (pt3d(33) + pt3d(133)) / 2.0
        eye_local = pt3d(468) - eye_center_local

        # Step 2 — Rotation Matrix
        R = head_matrix[:3, :3]

        # Step 3 — Transform into world space
        eye_world = R @ eye_local

        # Step 4 — Normalize
        norm = np.linalg.norm(eye_world)
        if norm < 1e-6:
            return
        eye_world /= norm

        # Step 5 — project onto screen from landmark 168 (2D origin)
        
        # ============================================
        # Production-grade adaptive gaze arrow length
        # ============================================

        # Height of face bounding box
        bbox_height = state.bbox[3] - state.bbox[1]

        # adaptive scale based on face size
        SCALE = bbox_height * 0.30

        # clamp to safe limits
        SCALE = max(25, min(SCALE, 80))

        # smoothing to prevent jitter
        if not hasattr(state, "_gaze_scale"):
            state._gaze_scale = SCALE
        else:
            state._gaze_scale = int(0.8 * state._gaze_scale + 0.2 * SCALE)

        SCALE = state._gaze_scale
        GAZE_COLOR = (0, 0, 255)

        origin = tuple(lm2d[168])
        end = (int(origin[0] + eye_world[0] * SCALE),
               int(origin[1] + eye_world[1] * SCALE))

        cv2.circle(frame, origin, 4, GAZE_COLOR, -1, cv2.LINE_AA)
        
        # Glow effect (thick background line)
        cv2.line(frame, origin, end, GAZE_COLOR, 6, cv2.LINE_AA)
        # Main arrow
        cv2.line(frame, origin, end, GAZE_COLOR, 3, cv2.LINE_AA)

        # draw arrow head manually
        cv2.circle(frame, end, 4, GAZE_COLOR, -1, cv2.LINE_AA)


    # ------------------------------------------------------------------
    # Feature 3 — neighbor graph
    # ------------------------------------------------------------------

    def draw_neighbors(self, frame: np.ndarray, registry: GlobalStudentRegistry) -> None:
        """
        Draw neighbor connection lines between students.

        For each student, draws a line to each of its k-nearest neighbors.
        """
        all_states = registry.get_all()

        for state in all_states:
            if not state.neighbors:
                continue

            src_center = state.center
            src_color = _track_color(state.track_id)

            for neighbor_id in state.neighbors:
                neighbor_state = registry.get(neighbor_id)
                if neighbor_state is None:
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
