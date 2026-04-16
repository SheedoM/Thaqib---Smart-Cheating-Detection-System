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
        self.show_phone: bool = True
        self.show_paper: bool = True
        self.show_control_panel: bool = True

    def toggle_neighbors(self) -> None:
        """Toggle neighbor graph rendering on/off."""
        self.show_neighbors = not self.show_neighbors

    def toggle_control_panel(self) -> None:
        """Toggle control panel visibility on/off."""
        self.show_control_panel = not self.show_control_panel

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

        self._draw_cheating_tools(annotated, pipeline_frame)
        self._draw_surrounding_papers(annotated, pipeline_frame)

        if self.show_neighbors and registry is not None:
            self.draw_neighbors(annotated, registry)
            self._draw_legend_panel(annotated, pipeline_frame)

        self._draw_hud(annotated, pipeline_frame)

        if self.show_control_panel:
            self._draw_control_panel(annotated, pipeline_frame)

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
            
            if getattr(state, "is_cheating", False):
                color = (0, 0, 255)  # RED
                thickness = 3
            else:
                color = _track_color(state.track_id)
                thickness = 2

            cv2.rectangle(frame, (x1, y1), (x2, y2), color, thickness)
            cv2.putText(
                frame,
                f"ID:{state.track_id}",
                (x1, y1 - 8),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.6,
                color,
                thickness,
                cv2.LINE_AA,
            )

            # Center dot
            cv2.circle(frame, state.center, 4, color, -1, cv2.LINE_AA)

            # Face mesh overlay
            self._draw_face_mesh(frame, state)

            # Iris center + gaze arrow
            self._draw_gaze(frame, state)

    # ------------------------------------------------------------------
    # Feature 2 — Cheating Tools & Spatial Papers
    # ------------------------------------------------------------------

    def _draw_cheating_tools(self, frame: np.ndarray, pipeline_frame: PipelineFrame) -> None:
        """Draw bounding boxes for detected tools (books, phones)."""
        if pipeline_frame.tools_result is None:
            return

        for tool in pipeline_frame.tools_result.tools:
            x1, y1, x2, y2 = tool.bbox
            
            # Format label with confidence
            label = f"{tool.label} {tool.confidence:.2f}"
            
            if tool.label in ['phone', 'Using_phone'] and self.show_phone:
                cv2.rectangle(frame, (x1, y1), (x2, y2), (0, 0, 255), 2)  # RED for phone
                cv2.putText(
                    frame, label, (x1, y1 - 8),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 255), 2, cv2.LINE_AA
                )
            elif tool.label == 'book' and self.show_paper:
                cv2.rectangle(frame, (x1, y1), (x2, y2), (0, 255, 255), 2) # YELLOW for book
                cv2.putText(
                    frame, label, (x1, y1 - 8),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 255), 2, cv2.LINE_AA
                )

    def _draw_surrounding_papers(self, frame: np.ndarray, pipeline_frame: PipelineFrame) -> None:
        """Draw cyan lines connecting a student to their k-nearest surrounding papers."""
        if not self.show_paper:
            return

        for state in pipeline_frame.student_states:
            for paper_coord in state.surrounding_papers:
                # Draw a thin Cyan line
                cv2.line(
                    frame,
                    state.center,
                    paper_coord,
                    (255, 255, 0),  # Cyan
                    1,
                    cv2.LINE_AA,
                )
                # Draw a small circle at the paper coordinate to mark it
                cv2.circle(frame, paper_coord, 3, (255, 255, 0), -1, cv2.LINE_AA)

    # ------------------------------------------------------------------
    # Feature 3a — face mesh
    # ------------------------------------------------------------------

    def _draw_face_mesh(self, frame: np.ndarray, state) -> None:
        """Draw all face mesh landmarks as green dots on the student's face."""
        if state.face_mesh is None:
            return
        for (x, y) in state.face_mesh.landmarks_2d:
            cv2.circle(frame, (x, y), 1, (0, 255, 0), -1)

    def _draw_gaze(self, frame: np.ndarray, state) -> None:
        """
        Draw a combined 3D gaze arrow using the shared gaze computation module.
        """
        if state.face_mesh is None:
            return

        lm2d = state.face_mesh.landmarks_2d
        if len(lm2d) < 474:
            return

        # Use shared gaze computation (single source of truth with pipeline)
        from thaqib.video.gaze import compute_gaze_direction
        gaze_dir = compute_gaze_direction(state.face_mesh)
        if gaze_dir is None:
            return

        dir_x, dir_y = gaze_dir[0], gaze_dir[1]

        # Draw (Improved non-linear scale)
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
        instructions = "s: select all  |  c: clear  |  t: neighbors  |  p: panel  |  q: quit"
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

    def _draw_control_panel(self, frame: np.ndarray, pipeline_frame: PipelineFrame) -> None:
        """Draw a control panel on the bottom-left showing system status."""
        h, w = frame.shape[:2]
        panel_h = 130
        panel_w = 320
        panel_x = 10
        panel_y = h - panel_h - 40  # Above the instruction bar

        # Semi-transparent background (ROI-only copy to avoid full-frame duplication)
        roi = frame[panel_y:panel_y + panel_h, panel_x:panel_x + panel_w]
        overlay_roi = roi.copy()
        cv2.rectangle(overlay_roi, (0, 0), (panel_w, panel_h), (15, 15, 15), -1)
        cv2.addWeighted(overlay_roi, 0.75, roi, 0.25, 0, roi)

        # Border
        cv2.rectangle(frame, (panel_x, panel_y), (panel_x + panel_w, panel_y + panel_h), (80, 80, 80), 1)

        # Title
        cv2.putText(frame, "THAQIB CONTROL PANEL", (panel_x + 10, panel_y + 22),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.55, (0, 200, 255), 2, cv2.LINE_AA)
        cv2.line(frame, (panel_x + 10, panel_y + 30), (panel_x + panel_w - 10, panel_y + 30), (60, 60, 60), 1)

        # Status rows
        y = panel_y + 50
        line_h = 22

        # Tracked count
        tracked = pipeline_frame.tracked_count
        cv2.circle(frame, (panel_x + 20, y - 5), 5, (0, 255, 0) if tracked > 0 else (80, 80, 80), -1)
        cv2.putText(frame, f"Tracked: {tracked}", (panel_x + 35, y),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.45, (200, 200, 200), 1, cv2.LINE_AA)

        # Selected count
        y += line_h
        selected = pipeline_frame.selected_count
        sel_color = (0, 255, 255) if selected > 0 else (80, 80, 80)
        cv2.circle(frame, (panel_x + 20, y - 5), 5, sel_color, -1)
        cv2.putText(frame, f"Monitoring: {selected}", (panel_x + 35, y),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.45, (200, 200, 200), 1, cv2.LINE_AA)

        # Cheating alerts
        y += line_h
        cheating_count = sum(1 for s in pipeline_frame.student_states if s.is_cheating)
        if cheating_count > 0:
            alert_color = (0, 0, 255)
            cv2.circle(frame, (panel_x + 20, y - 5), 5, alert_color, -1)
            cv2.putText(frame, f"ALERTS: {cheating_count} cheating!", (panel_x + 35, y),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.45, alert_color, 1, cv2.LINE_AA)
        else:
            cv2.circle(frame, (panel_x + 20, y - 5), 5, (0, 180, 0), -1)
            cv2.putText(frame, "No alerts", (panel_x + 35, y),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.45, (0, 180, 0), 1, cv2.LINE_AA)

        # Neighbors status
        y += line_h
        nb_color = (0, 255, 0) if self.show_neighbors else (100, 100, 100)
        cv2.putText(frame, f"Neighbors: {'ON' if self.show_neighbors else 'OFF'}", (panel_x + 35, y),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.4, nb_color, 1, cv2.LINE_AA)

    def _draw_legend_panel(self, frame: np.ndarray, pipeline_frame: PipelineFrame) -> None:
        """Draw a transparent color legend on the right side of the screen."""
        if not pipeline_frame.tracking_result.tracks:
            return

        h, w = frame.shape[:2]
        panel_w = 180
        panel_x = w - panel_w
        
        # Draw transparent dark background (ROI-only copy)
        roi = frame[0:h, panel_x:w]
        overlay_roi = roi.copy()
        cv2.rectangle(overlay_roi, (0, 0), (panel_w, h), (20, 20, 20), -1)
        cv2.addWeighted(overlay_roi, 0.6, roi, 0.4, 0, roi)

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

