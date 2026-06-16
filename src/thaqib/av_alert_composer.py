import contextlib
import logging
import os
import subprocess
import tempfile
import threading
import time
from collections import deque
from concurrent.futures import ThreadPoolExecutor
from typing import Dict

import cv2
import numpy as np
import scipy.io.wavfile as wavfile

from thaqib.mic_layout import MicLayout
from thaqib.video.registry import GlobalStudentRegistry
from thaqib.video.timestamps import draw_timestamp_overlay
from thaqib.video.jpeg_buffer import decode_frame as jpeg_decode

logger = logging.getLogger(__name__)

VIDEO_ALERT_PAD_BEFORE_S = 2.0
VIDEO_ALERT_PAD_AFTER_S = 2.0
AUDIO_ALERT_PAD_BEFORE_S = 1.0
AUDIO_ALERT_PAD_AFTER_S = 1.0

class AVAlertComposer:
    def __init__(
        self,
        layout: MicLayout,
        audio_buffers: Dict[str, deque],   # mic_id -> deque of (timestamp_float, np.ndarray)
        video_buffers: Dict[str, deque],   # camera_id -> deque of (timestamp_float, np.ndarray frame)
        video_registries: Dict[str, GlobalStudentRegistry], # camera_id -> GlobalStudentRegistry
        output_dir: str,
        video_fps: float = 30.0,
        audio_sample_rate: int = 16000,
        video_buffer_locks: Dict[str, object] | None = None,  # C-2: per-camera lock for snapshot
        audio_buffer_locks: Dict[str, object] | None = None,  # C-3: per-mic lock for snapshot
        on_output=None,
    ):
        self.layout = layout
        self.audio_buffers = audio_buffers
        self.video_buffers = video_buffers
        self.video_registries = video_registries
        self.output_dir = output_dir
        self.video_fps = video_fps
        self.audio_sample_rate = audio_sample_rate
        self._mux_executor = ThreadPoolExecutor(max_workers=3, thread_name_prefix="ComposerMux")
        self._wait_executor = ThreadPoolExecutor(max_workers=10, thread_name_prefix="ComposerWait")
        self._video_buffer_locks: Dict[str, object] = video_buffer_locks or {}
        self._audio_buffer_locks: Dict[str, object] = audio_buffer_locks or {}
        self._on_output = on_output
        
        os.makedirs(self.output_dir, exist_ok=True)

    def stop(self):
        """Stop the composer and wait for pending mux operations to complete."""
        self._wait_executor.shutdown(wait=True)
        self._mux_executor.shutdown(wait=True)

    def shutdown(self, wait: bool = True):
        """Gracefully shut down the mux executor. Alias for stop() with cancel option."""
        self._wait_executor.shutdown(wait=wait, cancel_futures=not wait)
        self._mux_executor.shutdown(wait=wait, cancel_futures=not wait)

    # ------------------------------------------------------------------
    # Shared mic-pin overlay helper
    # ------------------------------------------------------------------

    def _draw_mic_pins(
        self,
        frame: np.ndarray,
        camera_id: str,
        source_mic_id: str | None,
    ) -> None:
        """Draw all configured mic pins for *camera_id* on *frame* in-place.

        The pin whose mic_id == source_mic_id is drawn RED (BGR 0,0,255);
        every other pin for that camera is drawn GREEN (BGR 0,255,0).
        If source_mic_id is None all pins are drawn GREEN (no source known).
        Does nothing if no pins are configured for this camera.
        """
        pins = self.layout.get_pins_for_camera(camera_id)
        if not pins:
            return
        h, w = frame.shape[:2]
        for pin in pins:
            px = int(pin.norm_pos[0] * w)
            py = int(pin.norm_pos[1] * h)
            color = (0, 0, 255) if pin.mic_id == source_mic_id else (0, 255, 0)
            cv2.circle(frame, (px, py), 9, color, -1, cv2.LINE_AA)
            cv2.circle(frame, (px, py), 9, (255, 255, 255), 1, cv2.LINE_AA)  # white outline
            cv2.putText(
                frame, pin.mic_id,
                (px + 12, py + 5),
                cv2.FONT_HERSHEY_SIMPLEX, 0.45, color, 1, cv2.LINE_AA
            )

    def on_video_alert(
        self,
        frames: list[np.ndarray],
        alert_type: str,
        subject_point: tuple[int, int],
        camera_id: str,
        timestamp_start: float,
        timestamp_end: float,
    ):
        # Fallback helper to save video only (with mic-pin overlay, no source)
        def save_video_only():
            timestamp = time.time()
            output_path = os.path.join(self.output_dir, f"{alert_type}_{camera_id}_{timestamp:.1f}.mp4")
            # Still draw all pins green so the viewer knows mic layout even without audio
            for ev_f in frames:
                self._draw_mic_pins(ev_f, camera_id, source_mic_id=None)
            self._save_video_only(frames, output_path)
            self._emit_output(output_path, {"camera_id": camera_id, "alert_type": alert_type, "has_audio": False})

        mic_pin = None
        if frames:
            h, w = frames[0].shape[:2]
            mic_pin = self.layout.nearest_mic_for_point(subject_point, camera_id, (w, h))
        
        if not mic_pin:
            logger.info(f"No mic mapped near subject point {subject_point} in camera {camera_id}. Saving video-only alert.")
            save_video_only()
            return
            
        mic_id = mic_pin.mic_id
        audio_buffer = self.audio_buffers.get(mic_id)
        
        # Buffer identity debug logging requested by user
        if audio_buffer is not None:
            logger.info(f"[DEBUG] on_video_alert - audio_buffer id: {id(audio_buffer)}, len: {len(audio_buffer)}")
            
        if not audio_buffer:
            logger.info(f"No audio buffer found for mic {mic_id}. Saving video-only alert.")
            save_video_only()
            return

        # Expand window for video alerts
        window_start = timestamp_start - VIDEO_ALERT_PAD_BEFORE_S
        window_end = timestamp_end + VIDEO_ALERT_PAD_AFTER_S

        video_buffer = self.video_buffers.get(camera_id)
        if video_buffer and len(video_buffer) > 0:
            lock = self._video_buffer_locks.get(camera_id)
            with lock if lock else contextlib.nullcontext():
                buffer_snapshot = list(video_buffer)
            oldest_ts = buffer_snapshot[0][0]
            newest_ts = buffer_snapshot[-1][0]
            
            # Clamp to buffer bounds
            window_start = max(window_start, oldest_ts)
            window_end = min(window_end, newest_ts)

            # Determine target shape from the first annotated frame
            target_shape = frames[0].shape[:2] if frames else None

            pre_frames = []
            for ts, f in buffer_snapshot:
                if window_start <= ts < timestamp_start:
                    # f is JPEG bytes (from jpeg_buffer) or a raw ndarray (legacy).
                    out_f = jpeg_decode(f) if isinstance(f, (bytes, bytearray)) else f.copy()
                    if target_shape and out_f.shape[:2] != target_shape:
                        out_f = cv2.resize(out_f, (target_shape[1], target_shape[0]))
                    draw_timestamp_overlay(out_f)
                    # mic-pin overlay — resize first, draw second (correct pixel coords)
                    self._draw_mic_pins(out_f, camera_id, mic_pin.mic_id)
                    pre_frames.append(out_f)
                    
            post_frames = []
            for ts, f in buffer_snapshot:
                if timestamp_end < ts <= window_end:
                    out_f = jpeg_decode(f) if isinstance(f, (bytes, bytearray)) else f.copy()
                    if target_shape and out_f.shape[:2] != target_shape:
                        out_f = cv2.resize(out_f, (target_shape[1], target_shape[0]))
                    draw_timestamp_overlay(out_f)
                    # mic-pin overlay — resize first, draw second
                    self._draw_mic_pins(out_f, camera_id, mic_pin.mic_id)
                    post_frames.append(out_f)

            # Apply mic-pin overlay to the event frames that arrived pre-assembled
            for ev_f in frames:
                self._draw_mic_pins(ev_f, camera_id, mic_pin.mic_id)

            frames = pre_frames + frames + post_frames
        else:
            window_start = timestamp_start
            window_end = timestamp_end

        # Extract audio segment matching EXTENDED frame timestamp range
        audio_segments = []
        # Need to ensure threading safety if audio buffer is updated concurrently
        # Assuming audio buffer contains (timestamp, chunk_data)
        # C-3: acquire per-mic lock if available for atomic snapshot
        audio_lock = self._audio_buffer_locks.get(mic_id)
        with audio_lock if audio_lock else contextlib.nullcontext():
            buffer_snapshot = list(audio_buffer)
        for ts, data in buffer_snapshot:
            if window_start <= ts <= window_end:
                audio_segments.append(data)
                
        if not audio_segments:
            logger.info(f"No audio found in timestamp range {window_start}-{window_end} for mic {mic_id}. Saving video-only alert.")
            save_video_only()
            return
            
        audio_clip = np.concatenate(audio_segments)
        timestamp = time.time()
        output_path = os.path.join(self.output_dir, f"{alert_type}_{camera_id}_{timestamp:.1f}.mp4")
        
        # Mux in background
        self._mux_executor.submit(
            self._mux_and_save,
            frames, audio_clip, output_path, None,
            {"camera_id": camera_id, "mic_id": mic_id, "alert_type": alert_type, "has_audio": True}
        )

    def on_audio_alert(
        self,
        audio_clip: np.ndarray,
        mic_id: str,
        timestamp_start: float,
        timestamp_end: float,
        keywords: list[str],
        sample_rate: int = None
    ):
        camera_ids = self.layout.cameras_for_mic(mic_id)

        if not camera_ids:
            logger.info(
                f"Mic {mic_id} triggered alert but is not mapped to any camera — suppressed."
            )
            return

        for camera_id in camera_ids:
            self._produce_audio_alert_video(
                audio_clip=audio_clip,
                mic_id=mic_id,
                camera_id=camera_id,
                timestamp_start=timestamp_start,
                timestamp_end=timestamp_end,
                sample_rate=sample_rate,
            )

    def _produce_audio_alert_video(
        self,
        audio_clip: np.ndarray,
        mic_id: str,
        camera_id: str,
        timestamp_start: float,
        timestamp_end: float,
        sample_rate: int = None
    ):
        # Buffer identity debug logging requested by user
        audio_buffer = self.audio_buffers.get(mic_id)
        if audio_buffer is not None:
            logger.info(f"[DEBUG] _produce_audio_alert_video - audio_buffer id: {id(audio_buffer)}, len: {len(audio_buffer)}")

        video_buffer = self.video_buffers.get(camera_id)
        if not video_buffer:
            logger.info(f"No video buffer found for camera {camera_id}. Skipping this camera for mic {mic_id}.")
            return
            
        # Expand window for audio alerts
        window_start = timestamp_start - AUDIO_ALERT_PAD_BEFORE_S
        window_end = timestamp_end + AUDIO_ALERT_PAD_AFTER_S
        
        # Submit the waiting and extraction process to a background thread
        # This prevents blocking the fast audio pipeline while waiting for the slow video pipeline
        self._wait_executor.submit(
            self._wait_and_extract_audio_alert,
            audio_clip, mic_id, camera_id, window_start, window_end, sample_rate
        )
        
    def _wait_and_extract_audio_alert(
        self,
        audio_clip: np.ndarray,
        mic_id: str,
        camera_id: str,
        window_start: float,
        window_end: float,
        sample_rate: int = None
    ):
        video_buffer = self.video_buffers.get(camera_id)
        if not video_buffer:
            return
            
        # 1. Wait for video buffer to catch up indefinitely
        while True:
            if len(video_buffer) > 0:
                lock = self._video_buffer_locks.get(camera_id)
                with lock if lock else contextlib.nullcontext():
                    newest_ts = video_buffer[-1][0]
                if newest_ts >= window_end:
                    break  # Video has caught up!
            time.sleep(0.5)
            
        # 2. Extract video frames
        lock = self._video_buffer_locks.get(camera_id)
        with lock if lock else contextlib.nullcontext():
            buffer_snapshot = list(video_buffer)
            
        if not buffer_snapshot:
            return
            
        oldest_ts = buffer_snapshot[0][0]
        newest_ts = buffer_snapshot[-1][0]
        
        # Clamp to buffer bounds in case of timeout or buffer rotation
        clamped_window_start = max(window_start, oldest_ts)
        clamped_window_end = min(window_end, newest_ts)
        
        frames = []
        for ts, frame in buffer_snapshot:
            if clamped_window_start <= ts <= clamped_window_end:
                # Decode JPEG bytes if stored in compressed form.
                raw = jpeg_decode(frame) if isinstance(frame, (bytes, bytearray)) else frame
                frames.append(raw.copy())
                
        if not frames:
            logger.warning(
                f"No video frames found for audio alert window "
                f"[{clamped_window_start:.1f}, {clamped_window_end:.1f}] in camera {camera_id}. "
                f"Buffer oldest={oldest_ts:.1f}, newest={newest_ts:.1f}. "
                f"Possible cause: Whisper latency exceeded video buffer depth."
            )
            return

        # 3. Extract extended audio segment
        audio_segments = []
        audio_buffer = self.audio_buffers.get(mic_id)
        if audio_buffer:
            audio_lock = self._audio_buffer_locks.get(mic_id)
            with audio_lock if audio_lock else contextlib.nullcontext():
                for ts, data in list(audio_buffer):
                    if clamped_window_start <= ts <= clamped_window_end:
                        audio_segments.append(data)
                    
        final_audio_clip = np.concatenate(audio_segments) if audio_segments else audio_clip

        # 4. Annotate frames
        registry = self.video_registries.get(camera_id)
        nearby_students = []
        
        if registry and frames:
            h, w = frames[0].shape[:2]
            for state in registry.get_all():
                nearest_pin = self.layout.nearest_mic_for_point(state.center, camera_id, (w, h))
                if nearest_pin and nearest_pin.mic_id == mic_id:
                    nearby_students.append(state)

        annotated_frames = []
        for frame in frames:
            ann_frame = frame.copy()
            # Draw nearby students
            for student in nearby_students:
                x1, y1, x2, y2 = student.bbox
                cv2.rectangle(ann_frame, (x1, y1), (x2, y2), (0, 255, 255), 2)
            draw_timestamp_overlay(ann_frame)
            # mic-pin overlay: source mic = red, all others = green
            self._draw_mic_pins(ann_frame, camera_id, source_mic_id=mic_id)
            annotated_frames.append(ann_frame)
            
        timestamp = time.time()
        output_path = os.path.join(self.output_dir, f"audio_alert_{mic_id}_{camera_id}_{timestamp:.1f}.mp4")
        
        # 5. Mux in background
        self._mux_executor.submit(
            self._mux_and_save,
            annotated_frames, final_audio_clip, output_path, sample_rate,
            {"camera_id": camera_id, "mic_id": mic_id, "alert_type": "audio", "has_audio": True}
        )

    def _save_video_only(self, frames: list[np.ndarray], output_path: str):
        if not frames:
            return
        
        h, w = frames[0].shape[:2]
        frames = [cv2.resize(f, (w, h)) if f.shape[:2] != (h, w) else f for f in frames]
        
        fourcc = cv2.VideoWriter_fourcc(*'mp4v')
        out = cv2.VideoWriter(output_path, fourcc, self.video_fps, (w, h))
        for frame in frames:
            out.write(frame)
        out.release()
        logger.info(f"Saved video-only alert: {output_path}")

    def _emit_output(self, output_path: str, metadata: dict | None = None) -> None:
        if self._on_output is None:
            return
        try:
            self._on_output(output_path, metadata or {})
        except Exception as exc:
            logger.error("Composer output callback failed for %s: %s", output_path, exc)

    def _mux_and_save(self, frames: list[np.ndarray], audio: np.ndarray, output_path: str, sample_rate: int = None, metadata: dict | None = None):
        if not frames:
            return

        try:
            # 1. Write frames to temp MP4
            h, w = frames[0].shape[:2]
            frames = [cv2.resize(f, (w, h)) if f.shape[:2] != (h, w) else f for f in frames]

            # EC-6: Use TemporaryDirectory so the OS cleans up even if SIGKILL hits.
            # tempfile.TemporaryDirectory() guarantees deletion on __exit__, including
            # on exception — no separate finally block needed.
            with tempfile.TemporaryDirectory(prefix="thaqib_mux_") as tmpdir:
                temp_video = os.path.join(tmpdir, "video.mp4")
                temp_audio = os.path.join(tmpdir, "audio.wav")

                fourcc = cv2.VideoWriter_fourcc(*'mp4v')
                out = cv2.VideoWriter(temp_video, fourcc, self.video_fps, (w, h))
                for frame in frames:
                    out.write(frame)
                out.release()

                # 2. Write audio to temp WAV
                audio_int16 = (np.clip(audio, -1.0, 1.0) * 32767).astype(np.int16)
                rate = sample_rate if sample_rate else self.audio_sample_rate
                wavfile.write(temp_audio, rate, audio_int16)

                # 3. Run ffmpeg
                cmd = [
                    "ffmpeg", "-y",
                    "-i", temp_video,
                    "-i", temp_audio,
                    "-c:v", "copy",
                    "-c:a", "aac",
                    "-af", "apad",
                    "-shortest",
                    output_path
                ]

                # Run and capture stderr for debugging
                result = subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
                if result.returncode != 0:
                    stderr_text = result.stderr.decode("utf-8", errors="replace").strip()
                    raise RuntimeError(f"ffmpeg exited {result.returncode}:\n{stderr_text}")
                logger.info(f"Successfully created AV alert: {output_path}")
                self._emit_output(output_path, metadata)

        except Exception as e:
            logger.error(f"Error creating AV alert {output_path}: {e}")
