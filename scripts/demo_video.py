"""
Demo script for video detection pipeline.

Demonstrates the full video processing pipeline with webcam or video file.
Press 'q' to quit, 's' to select all visible persons, 't' to toggle neighbors.
"""

import argparse
import logging
import sys

import cv2

# Add src to path for development
sys.path.insert(0, str(__file__).replace("\\", "/").rsplit("/", 2)[0] + "/src")

from thaqib.video.pipeline import VideoPipeline
from thaqib.video.visualizer import VideoVisualizer


# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


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

    # Create pipeline (processing layer)
    pipeline = VideoPipeline(
        source=source,
        detection_interval=args.interval,
    )

    # Create visualizer (visualization layer)
    visualizer = VideoVisualizer()

    # Create window
    window_name = "Thaqib - Video Detection Demo"
    cv2.namedWindow(window_name, cv2.WINDOW_NORMAL)

    try:
        with pipeline:
            for pipeline_frame in pipeline.run():
                # Render frame via visualization layer
                annotated = visualizer.draw(pipeline_frame, registry=pipeline_frame.registry)

                # Show frame
                cv2.imshow(window_name, annotated)

                # Handle key presses
                key = cv2.waitKey(1) & 0xFF

                if key == ord("q"):
                    logger.info("Quitting...")
                    break

                elif key == ord("s"):
                    # Select all visible tracks
                    all_ids = [t.track_id for t in pipeline_frame.tracking_result.tracks]
                    pipeline.select_students(all_ids)
                    logger.info(f"Selected all {len(all_ids)} tracks")

                elif key == ord("c"):
                    # Clear selection
                    pipeline.select_students([])
                    logger.info("Cleared selection")

                elif key == ord("t"):
                    # Toggle neighbor graph
                    visualizer.toggle_neighbors()
                    logger.info(f"Neighbor graph: {'ON' if visualizer.show_neighbors else 'OFF'}")

    except KeyboardInterrupt:
        logger.info("Interrupted by user")

    finally:
        cv2.destroyAllWindows()


if __name__ == "__main__":
    main()
