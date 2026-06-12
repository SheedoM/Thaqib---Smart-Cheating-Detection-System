import logging
import os
import subprocess
import threading
import time
import uuid
from collections import deque
from typing import Dict

import cv2
import numpy as np
import scipy.io.wavfile as wavfile

from thaqib.mic_layout import MicLayout
from thaqib.video.registry import GlobalStudentRegistry
from thaqib.video.timestamps import draw_timestamp_overlay

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
    ):
        self.layout = layout
        self.audio_buffers = audio_buffers
        self.video_buffers = video_buffers
        self.video_registries = video_registries
        self.output_dir = output_dir
        self.video_fps = video_fps
        self.audio_sample_rate = audio_sample_rate
        
        os.makedirs(self.output_dir, exist_ok=True)

    def on_video_alert(
        self,
        frames: list[np.ndarray],
        alert_type: str,
        subject_point: tuple[int, int],
        camera_id: str,
        timestamp_start: float,
        timestamp_end: float,
    ):
        # Fallback helper to save video only
        def save_video_only():
            timestamp = time.time()
            output_path = os.path.join(self.output_dir, f"{alert_type}_{camera_id}_{timestamp:.1f}.mp4")
            self._save_video_only(frames, output_path)

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
        if not audio_buffer:
            logger.info(f"No audio buffer found for mic {mic_id}. Saving video-only alert.")
            save_video_only()
            return

        # Expand window for video alerts
        window_start = timestamp_start - VIDEO_ALERT_PAD_BEFORE_S
        window_end = timestamp_end + VIDEO_ALERT_PAD_AFTER_S

        video_buffer = self.video_buffers.get(camera_id)
        if video_buffer and len(video_buffer) > 0:
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
                    out_f = f.copy()
                    if target_shape and out_f.shape[:2] != target_shape:
                        out_f = cv2.resize(out_f, (target_shape[1], target_shape[0]))
                    draw_timestamp_overlay(out_f)
                    pre_frames.append(out_f)
                    
            post_frames = []
            for ts, f in buffer_snapshot:
                if timestamp_end < ts <= window_end:
                    out_f = f.copy()
                    if target_shape and out_f.shape[:2] != target_shape:
                        out_f = cv2.resize(out_f, (target_shape[1], target_shape[0]))
                    draw_timestamp_overlay(out_f)
                    post_frames.append(out_f)
                    
            frames = pre_frames + frames + post_frames
        else:
            window_start = timestamp_start
            window_end = timestamp_end

        # Extract audio segment matching EXTENDED frame timestamp range
        audio_segments = []
        # Need to ensure threading safety if audio buffer is updated concurrently
        # Assuming audio buffer contains (timestamp, chunk_data)
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
        threading.Thread(
            target=self._mux_and_save,
            args=(frames, audio_clip, output_path),
            daemon=True,
            name=f"ComposerMux_{timestamp}"
        ).start()

    def on_audio_alert(
        self,
        audio_clip: np.ndarray,
        mic_id: str,
        timestamp_start: float,
        timestamp_end: float,
        keywords: list[str],
        sample_rate: int = None
    ):
        def save_audio_only():
            timestamp = time.time()
            output_path = os.path.join(self.output_dir, f"audio_alert_{mic_id}_{timestamp:.1f}.wav")
            audio_int16 = (np.clip(audio_clip, -1.0, 1.0) * 32767).astype(np.int16)
            rate = sample_rate if sample_rate else self.audio_sample_rate
            wavfile.write(output_path, rate, audio_int16)
            logger.info(f"Saved audio-only alert: {output_path}")

        camera_id = self.layout.camera_for_mic(mic_id)
        if not camera_id:
            logger.info(f"No camera mapped for mic {mic_id}. Saving audio-only alert.")
            save_audio_only()
            return
            
        video_buffer = self.video_buffers.get(camera_id)
        if not video_buffer:
            logger.info(f"No video buffer found for camera {camera_id}. Saving audio-only alert.")
            save_audio_only()
            return
            
        # Expand window for audio alerts
        window_start = timestamp_start - AUDIO_ALERT_PAD_BEFORE_S
        window_end = timestamp_end + AUDIO_ALERT_PAD_AFTER_S
        
        if len(video_buffer) > 0:
            buffer_snapshot = list(video_buffer)
            oldest_ts = buffer_snapshot[0][0]
            newest_ts = buffer_snapshot[-1][0]
            
            # Clamp to buffer bounds
            window_start = max(window_start, oldest_ts)
            window_end = min(window_end, newest_ts)
            
            frames = []
            for ts, frame in buffer_snapshot:
                if window_start <= ts <= window_end:
                    frames.append(frame.copy())
        else:
            frames = []
                
        if not frames:
            logger.info(f"No frames found in extended range {window_start}-{window_end} for camera {camera_id}. Saving audio-only alert.")
            save_audio_only()
            return

        # Extract extended audio segment
        audio_segments = []
        audio_buffer = self.audio_buffers.get(mic_id)
        if audio_buffer:
            for ts, data in list(audio_buffer):
                if window_start <= ts <= window_end:
                    audio_segments.append(data)
                    
        final_audio_clip = np.concatenate(audio_segments) if audio_segments else audio_clip

        registry = self.video_registries.get(camera_id)
        nearby_students = []
        
        # Identify mic pin to draw on frame
        mic_pin = next((p for p in self.layout.get_pins_for_camera(camera_id) if p.mic_id == mic_id), None)
        
        if registry and frames:
            h, w = frames[0].shape[:2]
            for state in registry.get_all():
                nearest_pin = self.layout.nearest_mic_for_point(state.center, camera_id, (w, h))
                if nearest_pin and nearest_pin.mic_id == mic_id:
                    nearby_students.append(state)

        # Annotate frames
        annotated_frames = []
        for frame in frames:
            ann_frame = frame.copy()
            # Draw mic pin
            if mic_pin and frames:
                h, w = frames[0].shape[:2]
                px, py = int(mic_pin.norm_pos[0] * w), int(mic_pin.norm_pos[1] * h)
                cv2.circle(ann_frame, (px, py), 10, (0, 255, 255), -1)
                cv2.putText(
                    ann_frame, mic_id,
                    (px + 12, py + 5),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 255), 1
                )
            
            # Draw nearby students
            for student in nearby_students:
                x1, y1, x2, y2 = student.bbox
                cv2.rectangle(ann_frame, (x1, y1), (x2, y2), (0, 255, 255), 2)
                
            draw_timestamp_overlay(ann_frame)
            annotated_frames.append(ann_frame)
            
        timestamp = time.time()
        output_path = os.path.join(self.output_dir, f"audio_alert_{mic_id}_{timestamp:.1f}.mp4")
        
        # Mux in background
        threading.Thread(
            target=self._mux_and_save,
            args=(annotated_frames, final_audio_clip, output_path, sample_rate),
            daemon=True,
            name=f"ComposerMux_{timestamp}"
        ).start()

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

    def _mux_and_save(self, frames: list[np.ndarray], audio: np.ndarray, output_path: str, sample_rate: int = None):
        if not frames:
            return
            
        _id = uuid.uuid4().hex
        temp_video = f"temp_video_{_id}.mp4"
        temp_audio = f"temp_audio_{_id}.wav"
        
        try:
            # 1. Write frames to temp MP4
            h, w = frames[0].shape[:2]
            frames = [cv2.resize(f, (w, h)) if f.shape[:2] != (h, w) else f for f in frames]
            
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
            
            # Run silently
            subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)
            logger.info(f"Successfully created AV alert: {output_path}")
            
        except Exception as e:
            logger.error(f"Error creating AV alert {output_path}: {e}")
        finally:
            # 4. Delete temp files
            if os.path.exists(temp_video):
                os.remove(temp_video)
            if os.path.exists(temp_audio):
                os.remove(temp_audio)
