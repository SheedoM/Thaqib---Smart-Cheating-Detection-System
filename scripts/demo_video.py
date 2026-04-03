"""
Demo script for video detection pipeline.

Demonstrates the full video processing pipeline with webcam or video file.
Press 'q' to quit, 's' to select all visible persons for monitoring.
"""

import argparse
import logging
import sys
import time

import cv2
import numpy as np

# Add src to path for development
sys.path.insert(0, str(__file__).replace("\\", "/").rsplit("/", 2)[0] + "/src")

from thaqib.video.pipeline import VideoPipeline, StudentState


# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


def draw_annotations(
    frame: np.ndarray,
    pipeline_frame,
    show_all_tracks: bool = True,
) -> np.ndarray:
    """Draw annotations on frame."""
    annotated = frame.copy()

    # Draw all tracks (unselected in gray)
    if show_all_tracks:
        for track in pipeline_frame.tracking_result.tracks:
            if not track.is_selected:
                x1, y1, x2, y2 = track.bbox
                cv2.rectangle(annotated, (x1, y1), (x2, y2), (128, 128, 128), 2)
                cv2.putText(
                    annotated,
                    f"ID:{track.track_id}",
                    (x1, y1 - 10),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.5,
                    (128, 128, 128),
                    1,
                )

    # Draw selected students with full annotations
    for state in pipeline_frame.student_states:
        x1, y1, x2, y2 = state.bbox

        # Color based on status
        if state.is_looking_at_neighbor:
            color = (0, 0, 255)  # Red for suspicious
            status = f"LOOKING AT #{state.looking_at_neighbor_id}"
        else:
            color = (0, 255, 0)  # Green for normal
            status = "OK"

        # Draw bounding box
        cv2.rectangle(annotated, (x1, y1), (x2, y2), color, 2)

        # Draw ID and status
        cv2.putText(
            annotated,
            f"ID:{state.track_id} [{status}]",
            (x1, y1 - 10),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.6,
            color,
            2,
        )

        # Draw head pose if available
        if state.head_pose and state.head_pose.has_pose:
            pose = state.head_pose.pose
            cx, cy = state.center

            # Draw yaw direction arrow
            arrow_length = 50
            yaw_rad = np.radians(pose.yaw)
            end_x = int(cx + arrow_length * np.cos(yaw_rad))
            end_y = int(cy + arrow_length * np.sin(yaw_rad))
            cv2.arrowedLine(annotated, (cx, cy), (end_x, end_y), (255, 0, 255), 2)

            # Draw pose text
            cv2.putText(
                annotated,
                f"Y:{pose.yaw:.0f} P:{pose.pitch:.0f}",
                (x1, y2 + 20),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.5,
                (255, 0, 255),
                1,
            )

        # Draw risk angles if available
        if state.spatial_context:
            for risk in state.spatial_context.risk_angles:
                cx, cy = state.center
                angle_rad = np.radians(risk.center_angle)
                end_x = int(cx + 40 * np.cos(angle_rad))
                end_y = int(cy + 40 * np.sin(angle_rad))
                cv2.line(annotated, (cx, cy), (end_x, end_y), (0, 165, 255), 1)

    # Draw info panel
    info_lines = [
        f"FPS: {1000 / max(pipeline_frame.processing_time_ms, 1):.1f}",
        f"Tracked: {pipeline_frame.tracked_count}",
        f"Selected: {pipeline_frame.selected_count}",
        f"Frame: {pipeline_frame.frame_index}",
    ]

    for i, line in enumerate(info_lines):
        cv2.putText(
            annotated,
            line,
            (10, 30 + i * 25),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.6,
            (255, 255, 255),
            2,
        )

    # Draw instructions
    instructions = "Press 's' to select all | 'c' to clear | 'q' to quit"
    cv2.putText(
        annotated,
        instructions,
        (10, annotated.shape[0] - 20),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.5,
        (200, 200, 200),
        1,
    )

    return annotated


def on_alert(state: StudentState) -> None:
    """Callback when suspicious behavior detected."""
    logger.warning(
        f"ALERT: Student {state.track_id} looking at neighbor {state.looking_at_neighbor_id}"
    )


def main():
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

    # Create pipeline
    pipeline = VideoPipeline(
        source=source,
        detection_interval=args.interval,
        on_alert=on_alert,
    )

    # Create window
    window_name = "Thaqib - Video Detection Demo"
    cv2.namedWindow(window_name, cv2.WINDOW_NORMAL)

    try:
        with pipeline:
            for frame_data in pipeline.run():
                # Draw annotations
                annotated = draw_annotations(frame_data.frame, frame_data)

                # Show frame
                cv2.imshow(window_name, annotated)

                # Handle key presses
                key = cv2.waitKey(1) & 0xFF

                if key == ord("q"):
                    logger.info("Quitting...")
                    break

                elif key == ord("s"):
                    # Select all visible tracks
                    all_ids = [t.track_id for t in frame_data.tracking_result.tracks]
                    pipeline.select_students(all_ids)
                    logger.info(f"Selected all {len(all_ids)} tracks")

                elif key == ord("c"):
                    # Clear selection
                    pipeline.select_students([])
                    logger.info("Cleared selection")

    except KeyboardInterrupt:
        logger.info("Interrupted by user")

    finally:
        cv2.destroyAllWindows()


if __name__ == "__main__":
    main()
