"""
Video visualization layer.
Responsible ONLY for drawing overlays onto frames.
"""

import cv2
import numpy as np
import functools

from thaqib.video.pipeline import PipelineFrame
from thaqib.video.registry import GlobalStudentRegistry
from thaqib.video.gaze import compute_gaze_direction


@functools.lru_cache(maxsize=1024)
def _track_color(track_id: int) -> tuple[int, int, int]:
    """Return a deterministic unique color for a given track_id."""
    rng = np.random.RandomState(track_id)
    return tuple(int(c) for c in rng.randint(60, 230, 3))


def _sc(frame: np.ndarray) -> float:
    """
    Compute a resolution scale factor relative to 720p.

    At 720p  -> sc = 1.0  (baseline — all hardcoded values are designed here)
    At 1080p -> sc = 1.5
    At 1440p -> sc = 2.0
    At 2160p -> sc = 3.0
    """
    return max(0.5, frame.shape[0] / 720.0)


def _fs(sc: float, base: float) -> float:
    """Scale a font size by sc."""
    return base * sc


def _th(sc: float, base: int) -> int:
    """Scale a thickness/radius by sc, minimum 1."""
    return max(1, int(round(base * sc)))


class VideoVisualizer:
    """
    Visualization layer for the video processing pipeline.

    Draws bounding boxes, IDs, neighbor graph lines, and HUD info onto frames.
    All UI elements are scaled proportionally to the frame resolution so that
    the on-screen size looks identical across 720p, 1080p, 2K, and 4K.
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
        sc = _sc(annotated)

        # Student overlays use a reduced scale so the face stays clearly visible
        ssc = sc * 0.65
        self._draw_unselected_tracks(annotated, pipeline_frame, ssc)
        self._draw_selected_students(annotated, pipeline_frame, ssc)

        self._draw_cheating_tools(annotated, pipeline_frame, ssc)
        self._draw_surrounding_papers(annotated, pipeline_frame, ssc)

        if self.show_neighbors and registry is not None:
            self.draw_neighbors(annotated, registry, sc)
            self._draw_legend_panel(annotated, pipeline_frame, sc)

        self._draw_hud(annotated, pipeline_frame, sc)

        if self.show_control_panel:
            self._draw_control_panel(annotated, pipeline_frame)

        self._draw_instructions(annotated, sc)

        return annotated

    # ------------------------------------------------------------------
    # Feature 1 — bounding boxes & IDs
    # ------------------------------------------------------------------

    def _draw_unselected_tracks(self, frame: np.ndarray, pipeline_frame: PipelineFrame, sc: float) -> None:
        """Draw all unselected tracks in gray."""
        for track in pipeline_frame.tracking_result.tracks:
            if track.is_selected:
                continue
            x1, y1, x2, y2 = track.bbox
            cv2.rectangle(frame, (x1, y1), (x2, y2), (128, 128, 128), _th(sc, 2))
            cv2.putText(
                frame,
                f"ID:{track.track_id}",
                (x1, max(0, y1 - _th(sc, 8))),
                cv2.FONT_HERSHEY_SIMPLEX,
                _fs(sc, 0.5),
                (128, 128, 128),
                _th(sc, 1),
                cv2.LINE_AA,
            )

    def _draw_selected_students(self, frame: np.ndarray, pipeline_frame: PipelineFrame, sc: float) -> None:
        """Draw selected students with unique per-ID colors."""
        for state in pipeline_frame.student_states:
            x1, y1, x2, y2 = state.bbox

            if getattr(state, "is_cheating", False):
                color = (0, 0, 255)  # RED
                thickness = _th(sc, 3)
            else:
                color = _track_color(state.track_id)
                thickness = _th(sc, 2)

            cv2.rectangle(frame, (x1, y1), (x2, y2), color, thickness)
            cv2.putText(
                frame,
                f"ID:{state.track_id}",
                (x1, max(0, y1 - _th(sc, 8))),
                cv2.FONT_HERSHEY_SIMPLEX,
                _fs(sc, 0.6),
                color,
                thickness,
                cv2.LINE_AA,
            )

            # Center dot
            cx, cy = state.center
            cv2.circle(frame, (cx, cy), _th(sc, 4), color, -1, cv2.LINE_AA)

            # Face mesh overlay
            self._draw_face_mesh(frame, state, sc)

            # Iris center + gaze arrow
            self._draw_gaze(frame, state, sc)

    # ------------------------------------------------------------------
    # Feature 2 — Cheating Tools & Spatial Papers
    # ------------------------------------------------------------------

    _PHONE_LABELS = frozenset(['phone', 'Using_phone', 'cell phone'])

    def _draw_cheating_tools(self, frame: np.ndarray, pipeline_frame: PipelineFrame, sc: float) -> None:
        """Draw bounding boxes for detected tools (documents/papers, phones)."""
        if pipeline_frame.tools_result is None:
            return

        for tool in pipeline_frame.tools_result.tools:
            x1, y1, x2, y2 = tool.bbox
            label = f"{tool.label} {tool.confidence:.2f}"

            if tool.label in self._PHONE_LABELS and self.show_phone:
                cv2.rectangle(frame, (x1, y1), (x2, y2), (0, 0, 255), _th(sc, 2))
                cv2.putText(
                    frame, label, (x1, max(0, y1 - _th(sc, 8))),
                    cv2.FONT_HERSHEY_SIMPLEX, _fs(sc, 0.5), (0, 0, 255), _th(sc, 2), cv2.LINE_AA
                )
            elif tool.label not in self._PHONE_LABELS and self.show_paper:
                cv2.rectangle(frame, (x1, y1), (x2, y2), (0, 255, 255), _th(sc, 2))
                cv2.putText(
                    frame, label, (x1, max(0, y1 - _th(sc, 8))),
                    cv2.FONT_HERSHEY_SIMPLEX, _fs(sc, 0.5), (0, 255, 255), _th(sc, 2), cv2.LINE_AA
                )

    def _draw_surrounding_papers(self, frame: np.ndarray, pipeline_frame: PipelineFrame, sc: float) -> None:
        """Draw cyan lines connecting a student to their k-nearest surrounding papers."""
        if not self.show_paper:
            return

        for state in pipeline_frame.student_states:
            cx, cy = state.center
            for paper_coord in state.surrounding_papers:
                px, py = paper_coord
                cv2.line(frame, (cx, cy), (px, py), (255, 255, 0), _th(sc, 1), cv2.LINE_AA)
                cv2.circle(frame, (px, py), _th(sc, 3), (255, 255, 0), -1, cv2.LINE_AA)

    # ------------------------------------------------------------------
    # Feature 3a — face mesh
    # ------------------------------------------------------------------

    def _draw_face_mesh(self, frame: np.ndarray, state, sc: float) -> None:
        """Draw all face mesh landmarks as green dots on the student's face."""
        if state.face_mesh is None:
            return
        r = max(1, int(sc))  # 1px at 720p, 2px at 1440p, 3px at 2160p
        for (x, y) in state.face_mesh.landmarks_2d:
            cv2.circle(frame, (int(x), int(y)), r, (0, 255, 0), -1)

    def _draw_gaze(self, frame: np.ndarray, state, sc: float) -> None:
        """Draw a combined 3D gaze arrow using the shared gaze computation module."""
        if state.face_mesh is None:
            return

        lm2d = state.face_mesh.landmarks_2d
        if len(lm2d) < 474:
            return

        gaze_dir = compute_gaze_direction(state.face_mesh)
        if gaze_dir is None:
            return

        dir_x, dir_y = gaze_dir[0], gaze_dir[1]

        bbox_height = state.bbox[3] - state.bbox[1]
        base_scale = bbox_height * 1.0 if bbox_height < 100 * sc else bbox_height * 0.6
        SCALE = int(max(60 * sc, min(base_scale, 200 * sc)))

        if not hasattr(state, "_gaze_scale"):
            state._gaze_scale = SCALE
        else:
            state._gaze_scale = int(0.8 * state._gaze_scale + 0.2 * SCALE)
        SCALE = state._gaze_scale

        GAZE_COLOR = (0, 0, 255)
        ox, oy = int(lm2d[168][0]), int(lm2d[168][1])
        origin = (ox, oy)
        end = (int(origin[0] + dir_x * SCALE), int(origin[1] + dir_y * SCALE))

        cv2.circle(frame, origin, _th(sc, 4), GAZE_COLOR, -1, cv2.LINE_AA)
        cv2.line(frame, origin, end, GAZE_COLOR, _th(sc, 5), cv2.LINE_AA)
        cv2.line(frame, origin, end, (0, 255, 255), _th(sc, 2), cv2.LINE_AA)
        cv2.circle(frame, end, _th(sc, 4), GAZE_COLOR, -1, cv2.LINE_AA)

    # ------------------------------------------------------------------
    # Feature 3 — neighbor graph
    # ------------------------------------------------------------------

    def draw_neighbors(self, frame: np.ndarray, registry: GlobalStudentRegistry, sc: float = 1.0) -> None:
        """Draw neighbor connection lines between students."""
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
                cv2.line(frame, src_center, neighbor_state.center, src_color, _th(sc, 2), cv2.LINE_AA)

            cv2.circle(frame, src_center, _th(sc, 6), src_color, _th(sc, 2), cv2.LINE_AA)

    # ------------------------------------------------------------------
    # HUD & panels
    # ------------------------------------------------------------------

    def _draw_hud(self, frame: np.ndarray, pipeline_frame: PipelineFrame, sc: float) -> None:
        """Draw compact top-left stats (FPS + frame counter)."""
        fps = 1000 / max(pipeline_frame.processing_time_ms, 1)
        cheating_count = sum(1 for s in pipeline_frame.student_states if s.is_cheating)

        lines = [
            (f"FPS: {fps:.1f}", (0, 230, 120) if fps >= 20 else (0, 100, 255)),
            (f"Frame: {pipeline_frame.frame_index}", (180, 180, 180)),
        ]
        if cheating_count > 0:
            lines.append((f"!! {cheating_count} CHEATING ALERT{'S' if cheating_count > 1 else ''} !!", (0, 0, 255)))

        lh = int(24 * sc)
        for i, (text, color) in enumerate(lines):
            cv2.putText(frame, text, (int(10 * sc), int(28 * sc) + i * lh),
                        cv2.FONT_HERSHEY_SIMPLEX, _fs(sc, 0.6), color, _th(sc, 2), cv2.LINE_AA)

    def _draw_instructions(self, frame: np.ndarray, sc: float) -> None:
        """Draw slim bottom instruction bar."""
        bar_h = int(26 * sc)
        h, w = frame.shape[:2]
        roi = frame[h - bar_h:h, 0:w]
        overlay = roi.copy()
        cv2.rectangle(overlay, (0, 0), (w, bar_h), (10, 10, 10), -1)
        cv2.addWeighted(overlay, 0.70, roi, 0.30, 0, roi)
        text = "[S] Select  [M] Deselect-click  [C] Clear  [T] Neighbors  [R] Archive  [P] Panel  [Q] Quit"
        cv2.putText(frame, text, (int(10 * sc), h - int(7 * sc)),
                    cv2.FONT_HERSHEY_SIMPLEX, _fs(sc, 0.42), (200, 200, 200), _th(sc, 1), cv2.LINE_AA)

    def _draw_control_panel(self, frame: np.ndarray, pipeline_frame: PipelineFrame) -> None:
        """Draw a two-column panel: STATUS (left) and CONTROLS (right). Fully scaled."""
        h, w = frame.shape[:2]
        sc = _sc(frame)

        # ── geometry ───────────────────────────────────────────────────
        col_w   = int(270 * sc)
        line_h  = int(22 * sc)
        pad     = int(10 * sc)
        title_h = int(28 * sc)
        margin  = int(10 * sc)
        dot_r   = int(5 * sc)
        rows    = 9

        panel_h = title_h + pad + rows * line_h + pad
        panel_x = margin
        panel_y = h - panel_h - int(30 * sc)
        panel_y = max(0, panel_y)

        # ── background ─────────────────────────────────────────────────
        for col in range(2):
            bx = panel_x + col * (col_w + margin)
            roi = frame[panel_y: panel_y + panel_h, bx: bx + col_w]
            if roi.size == 0:
                continue
            ov = roi.copy()
            cv2.rectangle(ov, (0, 0), (col_w, panel_h), (12, 12, 12), -1)
            cv2.addWeighted(ov, 0.80, roi, 0.20, 0, roi)
            cv2.rectangle(frame, (bx, panel_y), (bx + col_w, panel_y + panel_h), (70, 70, 70), _th(sc, 1))

        fs_label = _fs(sc, 0.42)
        fs_title = _fs(sc, 0.52)
        fs_sub   = _fs(sc, 0.38)
        fs_key   = _fs(sc, 0.40)
        tw       = _th(sc, 1)
        col_off  = int(120 * sc)
        badge_w  = int(22 * sc)
        badge_h  = int(17 * sc)

        # ── helpers ────────────────────────────────────────────────────
        def row(x, y, label, value, val_color=(200, 200, 200), bullet_color=None):
            if bullet_color:
                cv2.circle(frame, (x + dot_r + pad // 2, y - dot_r), dot_r, bullet_color, -1)
                lx = x + dot_r * 2 + pad
            else:
                lx = x + pad
            cv2.putText(frame, label, (lx, y), cv2.FONT_HERSHEY_SIMPLEX, fs_label, (150, 150, 150), tw, cv2.LINE_AA)
            cv2.putText(frame, value, (lx + col_off, y), cv2.FONT_HERSHEY_SIMPLEX, fs_label, val_color, tw, cv2.LINE_AA)

        def key_row(x, y, key, desc, state_str="", state_color=(200, 200, 200)):
            bx0 = x + pad
            by0 = y - badge_h + int(4 * sc)
            bx1 = bx0 + badge_w
            by1 = y + int(4 * sc)
            cv2.rectangle(frame, (bx0, by0), (bx1, by1), (50, 50, 50), -1)
            cv2.rectangle(frame, (bx0, by0), (bx1, by1), (120, 120, 120), tw)
            cv2.putText(frame, key, (bx0 + int(4 * sc), y), cv2.FONT_HERSHEY_SIMPLEX, fs_label, (255, 230, 100), tw, cv2.LINE_AA)
            cv2.putText(frame, desc, (bx1 + int(4 * sc), y), cv2.FONT_HERSHEY_SIMPLEX, fs_label, (190, 190, 190), tw, cv2.LINE_AA)
            if state_str:
                sx = x + col_w - pad - len(state_str) * int(7 * sc) - int(4 * sc)
                cv2.putText(frame, state_str, (sx, y), cv2.FONT_HERSHEY_SIMPLEX, fs_key, state_color, tw, cv2.LINE_AA)

        # ══════════════════════════════════════════════════════════════
        # LEFT COLUMN — STATUS
        # ══════════════════════════════════════════════════════════════
        lx = panel_x

        cv2.putText(frame, "  STATUS", (lx + pad, panel_y + int(20 * sc)),
                    cv2.FONT_HERSHEY_SIMPLEX, fs_title, (0, 200, 255), _th(sc, 2), cv2.LINE_AA)
        cv2.line(frame, (lx + pad, panel_y + title_h),
                 (lx + col_w - pad, panel_y + title_h), (50, 50, 50), tw)

        y = panel_y + title_h + pad + line_h

        tracked = pipeline_frame.tracked_count
        row(lx, y, "Tracked:", str(tracked), bullet_color=(0, 220, 0) if tracked > 0 else (80, 80, 80))
        y += line_h

        selected = pipeline_frame.selected_count
        sel_color = (0, 255, 255) if selected > 0 else (80, 80, 80)
        row(lx, y, "Monitoring:", str(selected), val_color=sel_color, bullet_color=sel_color)
        y += line_h

        cheating = sum(1 for s in pipeline_frame.student_states if s.is_cheating)
        if cheating > 0:
            row(lx, y, "Alerts:", f"{cheating} CHEATING!", val_color=(0, 60, 255), bullet_color=(0, 0, 255))
        else:
            row(lx, y, "Alerts:", "None", val_color=(0, 180, 0), bullet_color=(0, 180, 0))
        y += line_h + int(4 * sc)

        sep_y = y - int(6 * sc)
        cv2.line(frame, (lx + pad, sep_y), (lx + col_w - pad, sep_y), (40, 40, 40), tw)
        cv2.putText(frame, "  SETTINGS", (lx + pad, y + int(2 * sc)),
                    cv2.FONT_HERSHEY_SIMPLEX, fs_sub, (120, 120, 120), tw, cv2.LINE_AA)
        y += line_h

        arc_mode = pipeline_frame.archive_mode
        arc_color = (0, 200, 255) if arc_mode == "annotated" else (160, 160, 160)
        row(lx, y, "Archive:", arc_mode.upper(), val_color=arc_color)
        y += line_h

        nb_color = (0, 255, 0) if self.show_neighbors else (100, 100, 100)
        row(lx, y, "Neighbors:", "ON" if self.show_neighbors else "OFF", val_color=nb_color)
        y += line_h

        pp_color = (0, 255, 255) if self.show_paper else (100, 100, 100)
        row(lx, y, "Papers:", "ON" if self.show_paper else "OFF", val_color=pp_color)
        y += line_h

        ph_color = (0, 160, 255) if self.show_phone else (100, 100, 100)
        row(lx, y, "Phone det.:", "ON" if self.show_phone else "OFF", val_color=ph_color)

        # ══════════════════════════════════════════════════════════════
        # RIGHT COLUMN — CONTROLS
        # ══════════════════════════════════════════════════════════════
        rx = panel_x + col_w + margin

        cv2.putText(frame, "  CONTROLS", (rx + pad, panel_y + int(20 * sc)),
                    cv2.FONT_HERSHEY_SIMPLEX, fs_title, (0, 200, 255), _th(sc, 2), cv2.LINE_AA)
        cv2.line(frame, (rx + pad, panel_y + title_h),
                 (rx + col_w - pad, panel_y + title_h), (50, 50, 50), tw)

        y = panel_y + title_h + pad + line_h

        key_row(rx, y, "S", "Select all students")
        y += line_h
        key_row(rx, y, "M", "Deselect (click bbox)")
        y += line_h
        key_row(rx, y, "C", "Clear all selections")
        y += line_h
        key_row(rx, y, "T", "Toggle neighbors",
                "ON" if self.show_neighbors else "OFF",
                (0, 255, 0) if self.show_neighbors else (100, 100, 100))
        y += line_h
        key_row(rx, y, "R", "Toggle archive mode",
                arc_mode.upper(),
                (0, 200, 255) if arc_mode == "annotated" else (160, 160, 160))
        y += line_h
        key_row(rx, y, "P", "Toggle this panel",
                "ON" if self.show_control_panel else "OFF",
                (0, 255, 0) if self.show_control_panel else (100, 100, 100))
        y += line_h + int(4 * sc)
        sep_y2 = y - int(6 * sc)
        cv2.line(frame, (rx + pad, sep_y2), (rx + col_w - pad, sep_y2), (40, 40, 40), tw)
        key_row(rx, y, "Q", "Quit / Stop system")

    def _draw_legend_panel(self, frame: np.ndarray, pipeline_frame: PipelineFrame, sc: float) -> None:
        """Draw a transparent color legend on the right side of the screen."""
        if not pipeline_frame.tracking_result.tracks:
            return

        h, w = frame.shape[:2]
        panel_w = int(180 * sc)
        panel_x = w - panel_w

        roi = frame[0:h, panel_x:w]
        overlay_roi = roi.copy()
        cv2.rectangle(overlay_roi, (0, 0), (panel_w, h), (20, 20, 20), -1)
        cv2.addWeighted(overlay_roi, 0.6, roi, 0.4, 0, roi)

        cv2.putText(frame, "STUDENTS", (panel_x + int(15 * sc), int(30 * sc)),
                    cv2.FONT_HERSHEY_SIMPLEX, _fs(sc, 0.6), (255, 255, 255), _th(sc, 2), cv2.LINE_AA)
        cv2.line(frame, (panel_x + int(15 * sc), int(40 * sc)),
                 (w - int(15 * sc), int(40 * sc)), (100, 100, 100), _th(sc, 1))

        y_pos = int(70 * sc)
        row_h  = int(30 * sc)
        dot_r  = int(8 * sc)
        dot_cx = panel_x + int(30 * sc)

        for track in pipeline_frame.tracking_result.tracks:
            color = _track_color(track.track_id)
            cy = y_pos - int(5 * sc)
            cv2.circle(frame, (dot_cx, cy), dot_r, color, -1, cv2.LINE_AA)
            cv2.circle(frame, (dot_cx, cy), dot_r, (255, 255, 255), _th(sc, 1), cv2.LINE_AA)

            alpha = "(*)" if track.is_selected else ""
            text = f"ID: {track.track_id} {alpha}"
            txt_color = (255, 255, 255) if track.is_selected else (150, 150, 150)
            cv2.putText(frame, text, (panel_x + int(55 * sc), y_pos),
                        cv2.FONT_HERSHEY_SIMPLEX, _fs(sc, 0.5), txt_color, _th(sc, 1), cv2.LINE_AA)
            y_pos += row_h
