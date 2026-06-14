import argparse
import logging
import threading
import time
import sys
import subprocess
from collections import deque

# Check ffmpeg at startup
try:
    subprocess.run(["ffmpeg", "-version"],
                   stdout=subprocess.DEVNULL,
                   stderr=subprocess.DEVNULL,
                   check=True)
except (FileNotFoundError, subprocess.CalledProcessError):
    print("ERROR: ffmpeg not found on PATH. AV alert muxing will fail.")
    print("Install ffmpeg or add it to PATH before running.")
    sys.exit(1)

from thaqib.mic_layout import MicLayout
from thaqib.sim_clock import SimClock
from thaqib.av_alert_composer import AVAlertComposer

# Video
import cv2
import platform as _platform
if _platform.system() == "Darwin":
    # macOS: register the Cocoa event-loop handler so cv2.imshow() windows
    # remain responsive when called from background threads.
    cv2.startWindowThread()
from thaqib.video.pipeline import VideoPipeline
from thaqib.video.visualizer import VideoVisualizer
from thaqib.video.timestamps import draw_timestamp_overlay
from thaqib.video.video_logger import get_video_logger

# Audio
from thaqib.audio.pipeline import AudioPipeline
from thaqib.audio.source import FileAudioSource, AudioSource

# Need audio source with multiple mics support, using FileAudioSource assuming the user provides files for testing
# Also need to create a custom source if live mic is needed, but the prompt says:
# python run.py --video cam0=hall.mp4 cam1=door.mp4 --audio mic0=front.wav mic1=back.wav
# So we just pass the file paths.

logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(name)s: %(message)s')
logger = logging.getLogger(__name__)

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--video", nargs='+', help="Video sources in format cam0=hall.mp4", required=True)
    parser.add_argument("--audio", nargs='+', help="Audio sources in format mic0=front.wav", required=True)
    args = parser.parse_args()

    # 1. Parse arguments
    video_sources = {}
    for arg in args.video:
        k, v = arg.split("=", 1)
        video_sources[k] = v

    audio_sources = {}
    mic_sources = []
    audio_paths = []
    for arg in args.audio:
        k, v = arg.split("=", 1)
        audio_sources[k] = v
        mic_sources.append(k)
        audio_paths.append(v)

    # 2. Load MicLayout
    layout = MicLayout("mic_layout.json")

    # 3. Create SimClock
    clock = SimClock()

    # 4. Create shared rolling buffers
    audio_buffers = {mic_id: deque(maxlen=200) for mic_id in mic_sources}
    # 1800 frames = 60 seconds at 30fps — must be long enough to cover
    # the full VAD+Whisper latency so on_audio_alert still finds frames.
    video_buffers = {cam_id: deque(maxlen=1800) for cam_id in video_sources.keys()}
    video_registries = {}

    # 5. Create Composer
    from thaqib.config import get_settings as _gs
    _s = _gs()
    composer = AVAlertComposer(
        layout=layout,
        audio_buffers=audio_buffers,
        video_buffers=video_buffers,
        video_registries=video_registries,
        output_dir="alerts",
        video_fps=float(_s.camera_fps),
        audio_sample_rate=int(_s.audio_sample_rate),
    )

    # 6. Create Pipelines
    video_pipelines = []
    for cam_id, source in video_sources.items():
        vp = VideoPipeline(
            source=source,
            camera_id=cam_id,
            composer=composer,
            frame_buffer=video_buffers[cam_id],
            clock=clock
        )
        video_pipelines.append(vp)
        video_registries[cam_id] = vp._registry

    source = FileAudioSource(audio_paths, clock=clock)
    ap = AudioPipeline(
        source=source,
        composer=composer,
        audio_buffers=audio_buffers,
        mic_ids=mic_sources,
        clock=clock
    )

    total_pipeline_count = len(video_pipelines) + 1
    barrier = threading.Barrier(total_pipeline_count)

    def run_video(vp, barrier, layout, available_mic_ids):
        visualizer = VideoVisualizer()
        vp.set_visualizer(visualizer)
        
        # Inject layout info into visualizer for mic placement
        visualizer._layout = layout
        visualizer._camera_id = vp._camera_id
        visualizer._available_mic_ids = available_mic_ids

        window_name = f"Thaqib - {vp._camera_id}"
        cv2.namedWindow(window_name, cv2.WINDOW_NORMAL)
        
        # Combined mouse callback: handles both deselect mode and mic placement
        _deselect_mode = [False]
        _latest_frame = [None]

        def mouse_callback(event, x, y, flags, param):
            if event != cv2.EVENT_LBUTTONDOWN:
                return
            # Mic placement takes priority when active
            if visualizer._mic_placement_mode:
                visualizer.handle_mouse(event, x, y, flags, param)
                return
            # Deselect mode
            if _deselect_mode[0] and _latest_frame[0] is not None:
                for state in _latest_frame[0].student_states:
                    x1, y1, x2, y2 = state.bbox
                    if x1 <= x <= x2 and y1 <= y <= y2:
                        vp.remove_student(state.track_id)
                        _deselect_mode[0] = False
                        return

        cv2.setMouseCallback(window_name, mouse_callback)

        barrier.wait()
        
        try:
            with vp:
                for pipeline_frame in vp.run():
                    _latest_frame[0] = pipeline_frame
                    
                    if pipeline_frame.annotated_frame is not None:
                        annotated = pipeline_frame.annotated_frame
                    else:
                        annotated = visualizer.draw(pipeline_frame, registry=pipeline_frame.registry)

                    display = annotated
                    if visualizer.show_timestamp:
                        display = annotated.copy()
                        draw_timestamp_overlay(display)

                    if _deselect_mode[0]:
                        if display is annotated:
                            display = annotated.copy()
                        cv2.putText(
                            display,
                            "DESELECT MODE: Click a student to stop monitoring",
                            (20, 60),
                            cv2.FONT_HERSHEY_SIMPLEX,
                            1.0,
                            (0, 0, 255),
                            2,
                            cv2.LINE_AA
                        )

                    cv2.imshow(window_name, display)
                    key = cv2.waitKey(1) & 0xFF

                    if key == ord('q'):
                        break
                    elif key == ord('s'):
                        if pipeline_frame.registry:
                            active_ids = [s.track_id for s in pipeline_frame.registry.get_all() if getattr(s, 'is_active', True)]
                            vp.select_students(active_ids)
                    elif key == ord('c'):
                        vp.clear_selection()
                    elif key == ord('t'):
                        visualizer.toggle_neighbors()
                    elif key == ord('p'):
                        visualizer.toggle_control_panel()
                    elif key == ord('m'):
                        _deselect_mode[0] = not _deselect_mode[0]
                    elif key == ord('i'):
                        visualizer.toggle_mic_placement_mode()
                    elif key == ord('r'):
                        vp.toggle_archive_mode()
                    elif key == ord('d'):
                        visualizer.toggle_paper()
                    elif key == ord('f'):
                        visualizer.toggle_phone()
                    elif key == ord('l'):
                        visualizer.toggle_gaze_lines()
                    elif key == ord('v'):
                        vp.toggle_video_quality()
                    elif key == ord('g'):
                        vp.toggle_processing_resolution()
                    elif key == ord('w'):
                        visualizer.toggle_timestamp()
                    elif key == ord('k'):
                        visualizer.toggle_face_mesh()
        except Exception as e:
            logger.error(f"Video pipeline {vp._camera_id} error: {e}")
        finally:
            cv2.destroyWindow(window_name)

    def run_audio(ap):
        logger.info("Loading audio models...")
        ap.load_models()
        logger.info("Audio models ready.")
        barrier.wait()
        try:
            ap.run_sync()
        except Exception as e:
            logger.error(f"Audio pipeline error: {e}")
        finally:
            ap.stop()

    threads = []
    for vp in video_pipelines:
        t = threading.Thread(target=run_video, args=(vp, barrier, layout, mic_sources))
        t.start()
        threads.append(t)

    t = threading.Thread(target=run_audio, args=(ap,))
    t.start()
    threads.append(t)

    try:
        for t in threads:
            t.join()
    except KeyboardInterrupt:
        logger.info("Keyboard interrupt received, stopping pipelines...")
        for vp in video_pipelines:
            vp.stop()
        ap.stop()
        for t in threads:
            t.join()

if __name__ == "__main__":
    main()
