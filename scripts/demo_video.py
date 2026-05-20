"""
Demo script for video detection pipeline.
Supports webcam/video input and interactive monitoring controls.
"""

import argparse
import logging
import sys

import cv2

# Add src to path for development
sys.path.insert(0, str(__file__).replace("\\", "/").rsplit("/", 2)[0] + "/src")

from thaqib.video.pipeline import VideoPipeline
from thaqib.video.visualizer import VideoVisualizer
from thaqib.video.timestamps import draw_timestamp_overlay


# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


# --- Deselect mode state (module-level so mouse callback can access it) ---
_deselect_mode = False
_latest_pipeline_frame = None
_pipeline_ref = None


def _mouse_callback(event, x, y, flags, param):
    """Mouse callback: in deselect mode, click a student's bbox to remove them."""
    global _deselect_mode

    if event != cv2.EVENT_LBUTTONDOWN:
        return
    if not _deselect_mode:
        return
    if _latest_pipeline_frame is None or _pipeline_ref is None:
        return

    # Hit-test: find which tracked student was clicked
    for track in _latest_pipeline_frame.tracking_result.tracks:
        if not track.is_selected:
            continue
        x1, y1, x2, y2 = track.bbox
        if x1 <= x <= x2 and y1 <= y <= y2:
            # Remove from monitoring
            _pipeline_ref.remove_student(track.track_id)

            # Fully reset their cheating/recording state so they go back
            # to being an unmonitored gray box — as if never selected.
            registry = _latest_pipeline_frame.registry
            if registry:
                state = registry.get(track.track_id)
                if state:
                    state.is_cheating = False
                    state.cheating_cooldown = 0
                    state.suspicious_start_time = 0.0
                    state.cheating_target_paper = None
                    state.cheating_target_neighbor = None
                    state.is_using_phone = False
                    state.phone_bbox = None
                    state.is_alert_recording = False
                    state.recording_buffer.clear()
                    state.frames_to_record = 0

            logger.info(f"Deselected student ID:{track.track_id}")
            _deselect_mode = False
            logger.info("Deselect mode: OFF")
            return

    logger.info("No selected student at click position — try again")


def main():
    global _deselect_mode, _latest_pipeline_frame, _pipeline_ref

    parser = argparse.ArgumentParser(description="Thaqib Video Detection Demo")
    parser.add_argument(
        "--source",
        type=str,
        default="0",
        help="Video source: webcam index (0, 1, ...) or video file path",
    )
    parser.add_argument(
        "--interval",
        type=float,
        default=1.0,
        help="Detection interval in seconds",
    )
    args = parser.parse_args()

    # Parse source
    try:
        source = int(args.source)
    except ValueError:
        source = args.source

    logger.info(f"Starting demo with source: {source}")

    # Create pipeline (processing layer)
    pipeline = VideoPipeline(
        source=source,
        detection_interval=args.interval,
    )
    _pipeline_ref = pipeline

    # Create visualizer and register it with the pipeline so annotations
    # are rendered once per frame (inside _process_frame) and reused for
    # both archive writing and display.
    visualizer = VideoVisualizer()
    pipeline.set_visualizer(visualizer)

    # Create window with mouse callback
    window_name = "Thaqib - Video Detection Demo"
    cv2.namedWindow(window_name, cv2.WINDOW_NORMAL)
    cv2.setMouseCallback(window_name, _mouse_callback)

    try:
        with pipeline:
            for pipeline_frame in pipeline.run():
                _latest_pipeline_frame = pipeline_frame

                # Reuse the annotated frame rendered once inside _process_frame().
                # Falls back to calling draw() if no visualizer was attached
                # (e.g. testing/headless mode).
                if pipeline_frame.annotated_frame is not None:
                    annotated = pipeline_frame.annotated_frame
                else:
                    annotated = visualizer.draw(pipeline_frame, registry=pipeline_frame.registry)

                # Show deselect mode indicator
                if _deselect_mode:
                    cv2.putText(
                        annotated, "DESELECT MODE — click a student to remove",
                        (10, annotated.shape[0] - 45),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 0, 255), 2, cv2.LINE_AA,
                    )

                # Live timestamp — shown on screen only, toggleable via W key.
                # Archive and alert recordings always have timestamp from pipeline writers.
                display = annotated
                if visualizer.show_timestamp:
                    display = annotated.copy()
                    draw_timestamp_overlay(display)

                # Show frame
                cv2.imshow(window_name, display)

                # Handle key presses
                key = cv2.waitKey(1) & 0xFF

                if key == ord("q"):
                    logger.info("Quitting...")
                    break

                elif key == ord("s"):
                    # One-time Snapshot Selection
                    if pipeline_frame.registry:
                        active_ids = [state.track_id for state in pipeline_frame.registry.get_all() if getattr(state, "is_active", True)]
                        pipeline.select_students(active_ids)
                        logger.info(f"Snapshot taken: {len(active_ids)} students registered for monitoring.")

                elif key == ord("c"):
                    # Clear selection
                    pipeline.clear_selection()
                    logger.info("Cleared selection and disabled monitoring")

                elif key == ord("t"):
                    # Toggle neighbor graph
                    visualizer.toggle_neighbors()
                    logger.info(f"Neighbor graph: {'ON' if visualizer.show_neighbors else 'OFF'}")

                elif key == ord("p"):
                    # Toggle control panel
                    visualizer.toggle_control_panel()
                    logger.info(f"Control panel: {'ON' if visualizer.show_control_panel else 'OFF'}")

                elif key == ord("m"):
                    # Toggle deselect mode
                    _deselect_mode = not _deselect_mode
                    logger.info(f"Deselect mode: {'ON — click a student to remove' if _deselect_mode else 'OFF'}")

                elif key == ord("r"):
                    # Toggle archive recording mode (raw / annotated)
                    mode = pipeline.toggle_archive_mode()
                    logger.info(f"Archive recording mode: {mode.upper()} {'(original video)' if mode == 'raw' else '(with overlays)'}")

                elif key == ord("d"):
                    # Toggle paper bbox display (detection still runs)
                    visualizer.toggle_paper()
                    logger.info(f"Paper display: {'ON' if visualizer.show_paper else 'OFF'} (detection unaffected)")

                elif key == ord("f"):
                    # Toggle phone bbox display (detection still runs)
                    visualizer.toggle_phone()
                    logger.info(f"Phone display: {'ON' if visualizer.show_phone else 'OFF'} (detection unaffected)")

                elif key == ord("l"):
                    # Toggle student→paper link lines display
                    visualizer.toggle_gaze_lines()
                    logger.info(f"Paper link lines: {'ON' if visualizer.show_gaze_lines else 'OFF'}")

                elif key == ord("v"):
                    # Cycle video quality: LOW (50) → MED (75) → HIGH (90) → ...
                    pipeline.toggle_video_quality()
                    q = pipeline._video_quality
                    label = "HIGH" if q >= 90 else ("MED" if q >= 75 else "LOW")
                    logger.info(f"Video quality: {label} ({q}%) — applies to next recorded video")

                elif key == ord("g"):
                    # Cycle processing resolution: NATIVE → 1080p → 720p → ...
                    label = pipeline.toggle_processing_resolution()
                    logger.info(f"Processing resolution: {label} — takes effect next frame")

                elif key == ord("w"):
                    # Toggle live timestamp display (recordings always have it)
                    visualizer.toggle_timestamp()
                    state = "ON" if visualizer.show_timestamp else "OFF"
                    logger.info(f"Live timestamp: {state} (archive/alert recordings unaffected)")

    except KeyboardInterrupt:
        logger.info("Interrupted by user")

    finally:
        cv2.destroyAllWindows()


if __name__ == "__main__":
    # Required for multiprocessing on Windows (Fix 1: process pool)
    from multiprocessing import freeze_support
    freeze_support()
    main()
