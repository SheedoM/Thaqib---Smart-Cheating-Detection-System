import logging
import os
import subprocess
import time
import uuid
from dataclasses import dataclass, field
from typing import Optional
import numpy as np

logger = logging.getLogger(__name__)


@dataclass
class ArchiveRef:
    """Metadata record binding an archive file to its wall-clock recording start."""
    path: str
    wall_start_time: Optional[float] = None  # None = unknown; correction skipped with warning


class AVAlertComposer:
    def __init__(
        self,
        audio_archives: dict[str, str | ArchiveRef] | None = None,
        video_archives: dict[str, str | ArchiveRef] | None = None,
        layout=None,
        output_dir: str = "alerts"
    ):
        """
        Composer that relies on ArchiveRef (wall-clock synchronized) for cross-modal extraction.
        Accepts dicts with either string paths or ArchiveRef objects.
        """
        self.audio_archives: dict[str, ArchiveRef] = {}
        if audio_archives:
            for k, v in audio_archives.items():
                self.audio_archives[k] = v if isinstance(v, ArchiveRef) else ArchiveRef(path=str(v), wall_start_time=None)

        self.video_archives: dict[str, ArchiveRef] = {}
        if video_archives:
            for k, v in video_archives.items():
                self.video_archives[k] = v if isinstance(v, ArchiveRef) else ArchiveRef(path=str(v), wall_start_time=None)

        self.layout = layout
        self.output_dir = output_dir
        os.makedirs(self.output_dir, exist_ok=True)
        
    def stop(self):
        pass

    def shutdown(self, wait: bool = True):
        pass

    def register_archive_start(
        self,
        device_id: str | None = None,
        wall_start_time: float | None = None,
        is_video: bool = True,
        source_type: str | None = None,
        source_id: str | None = None,
        path: str | None = None,
    ):
        """Registers the wall-clock start time of an archive."""
        if source_type is not None:
            dev_id = source_id or device_id or ""
            p = path or ""
            if source_type.lower() == "video":
                existing = self.video_archives.get(dev_id)
                self.video_archives[dev_id] = ArchiveRef(path=p or (existing.path if existing else ""), wall_start_time=wall_start_time)
            else:
                existing = self.audio_archives.get(dev_id)
                self.audio_archives[dev_id] = ArchiveRef(path=p or (existing.path if existing else ""), wall_start_time=wall_start_time)
        else:
            dev_id = device_id or source_id or ""
            p = path or ""
            if is_video:
                existing = self.video_archives.get(dev_id)
                self.video_archives[dev_id] = ArchiveRef(path=p or (existing.path if existing else ""), wall_start_time=wall_start_time)
            else:
                existing = self.audio_archives.get(dev_id)
                self.audio_archives[dev_id] = ArchiveRef(path=p or (existing.path if existing else ""), wall_start_time=wall_start_time)

    def update_video_archive(self, camera_id: str, archive_path: str):
        existing = self.video_archives.get(camera_id)
        wall_start = existing.wall_start_time if existing else None
        self.video_archives[camera_id] = ArchiveRef(path=archive_path, wall_start_time=wall_start)

    def update_audio_archive(self, mic_id: str, archive_path: str):
        existing = self.audio_archives.get(mic_id)
        wall_start = existing.wall_start_time if existing else None
        self.audio_archives[mic_id] = ArchiveRef(path=archive_path, wall_start_time=wall_start)

    def update_video_archive_timed(self, camera_id: str, archive_path: str, wall_start_time: float | None = None):
        existing = self.video_archives.get(camera_id)
        wall_start = wall_start_time if wall_start_time is not None else (existing.wall_start_time if existing else time.time())
        self.video_archives[camera_id] = ArchiveRef(path=archive_path, wall_start_time=wall_start)

    def update_audio_archive_timed(self, mic_id: str, archive_path: str, wall_start_time: float | None = None):
        existing = self.audio_archives.get(mic_id)
        wall_start = wall_start_time if wall_start_time is not None else (existing.wall_start_time if existing else time.time())
        self.audio_archives[mic_id] = ArchiveRef(path=archive_path, wall_start_time=wall_start)

    def _get_seek_offset(self, archive_ref: ArchiveRef, target_wall_time: float) -> float:
        """Convert a wall-clock event time to a stream-relative seek offset."""
        if archive_ref.wall_start_time is None:
            return 0.0  # caller logs the warning before using this
        return max(0.0, target_wall_time - archive_ref.wall_start_time)

    def _cross_modal_offsets(
        self,
        source_start: float,
        source_end: float,
        source_ref: Optional[ArchiveRef],
        target_ref: ArchiveRef,
        source_label: str,
        target_label: str,
    ) -> tuple[float, float] | None:
        """
        Convert [source_start, source_end] stream offsets (relative to source archive)
        into stream offsets relative to target archive, via wall-clock EventWallTime.

        Returns (t_start, t_end) in target stream coordinates, or None if the target
        archive has zero temporal overlap with the event window (e.g. target archive
        started recording after the event concluded). Clamping negative offsets to 0
        is strictly forbidden as it fabricates false evidence from future media.
        """
        if source_ref is None or source_ref.wall_start_time is None:
            logger.warning(
                "Cross-modal alignment: wall_start_time for %s archive is unknown "
                "— seek correction skipped. Evidence may be temporally misaligned.",
                source_label,
            )
            return source_start, source_end
        if target_ref.wall_start_time is None:
            logger.warning(
                "Cross-modal alignment: wall_start_time for %s archive is unknown "
                "— seek correction skipped. Evidence may be temporally misaligned.",
                target_label,
            )
            return source_start, source_end

        event_start_wall = source_ref.wall_start_time + source_start
        event_end_wall   = source_ref.wall_start_time + source_end

        # Invariant check: Did the event conclude before the target archive began recording?
        if event_end_wall <= target_ref.wall_start_time:
            logger.warning(
                "Cross-modal alignment: %s archive started at %.3fs, after event ended at %.3fs "
                "(zero temporal overlap). Target evidence does not exist for this moment.",
                target_label, target_ref.wall_start_time, event_end_wall,
            )
            return None

        # Partial or full overlap:
        if event_start_wall < target_ref.wall_start_time:
            logger.warning(
                "Cross-modal alignment: event started at %.3fs before %s archive began at %.3fs. "
                "Target evidence covers partial window.",
                event_start_wall, target_label, target_ref.wall_start_time,
            )
            t_start = 0.0
        else:
            t_start = event_start_wall - target_ref.wall_start_time

        t_end = event_end_wall - target_ref.wall_start_time
        if t_end <= t_start:
            return None

        logger.debug(
            "Cross-modal %s→%s: source=[%.3f,%.3f] wall=[%.3f,%.3f] target=[%.3f,%.3f]",
            source_label, target_label,
            source_start, source_end,
            event_start_wall, event_end_wall,
            t_start, t_end,
        )
        return t_start, t_end

    def compose_video_alert(
        self, 
        camera_id: str, 
        mic_id: str | None, 
        start_sec: float, 
        end_sec: float,
        alert_type: str,
        subject_point: tuple[int, int] | None = None
    ) -> str | None:
        v_ref = self.video_archives.get(camera_id)
        if not v_ref or not os.path.exists(v_ref.path):
            return None
            
        timestamp = time.time()
        uid = uuid.uuid4().hex[:8]
        filename = f"{alert_type}_{camera_id}_{timestamp:.1f}_{uid}.mp4"
        output_path = os.path.join(self.output_dir, f"combined_AV_{filename}")
        
        a_ref = self.audio_archives.get(mic_id) if mic_id else None
        has_audio = a_ref and os.path.exists(a_ref.path)
        
        if has_audio and a_ref:
            # Check cross-modal offsets to ensure audio covers the event window
            offsets = self._cross_modal_offsets(
                source_start=start_sec,
                source_end=end_sec,
                source_ref=v_ref,
                target_ref=a_ref,
                source_label=f"video:{camera_id}",
                target_label=f"audio:{mic_id}",
            )
            
            if offsets is None:
                # Audio archive started after event — fallback to video-only alert
                logger.info(
                    "Audio archive has no temporal overlap with video event for %s. Generating video-only alert.",
                    camera_id,
                )
                video_only_path = os.path.join(
                    self.output_dir, f"{alert_type}_{camera_id}_{timestamp:.1f}_{uid}.mp4"
                )
                success = self._extract_and_annotate_video(
                    v_ref.path, video_only_path, camera_id, mic_id, start_sec, end_sec, subject_point
                )
                return video_only_path if success else None

            a_start, a_end = offsets
            annotated_video_path = os.path.join(self.output_dir, f"temp_vid_alert_{filename}")
            try:
                has_video = self._extract_and_annotate_video(
                    v_ref.path, annotated_video_path, camera_id, mic_id, start_sec, end_sec, subject_point
                )
                if not has_video:
                    logger.warning(
                        "No frames extracted from video archive for %s at %.3fs.",
                        camera_id, start_sec,
                    )
                    return None

                self._merge_with_ffmpeg(
                    annotated_video_path, a_ref.path, output_path,
                    audio_start=a_start, audio_end=a_end,
                )
                logger.info("AV Composer merged audio into video alert: %s", output_path)
                return output_path
            except Exception as e:
                logger.error("Error composing AV alert for %s: %s", camera_id, e)
                return None
            finally:
                if os.path.exists(annotated_video_path):
                    try:
                        os.remove(annotated_video_path)
                    except OSError:
                        pass
        else:
            video_only_path = os.path.join(
                self.output_dir, f"{alert_type}_{camera_id}_{timestamp:.1f}_{uid}.mp4"
            )
            success = self._extract_and_annotate_video(
                v_ref.path, video_only_path, camera_id, mic_id, start_sec, end_sec, subject_point
            )
            if success:
                logger.info("AV Composer generated video-only alert: %s", video_only_path)
                return video_only_path
            return None

    def compose_audio_alert(
        self,
        alert_wav_path: str,
        mic_id: str,
        camera_ids: list[str],
        start_sec: float,
        end_sec: float
    ) -> list[str]:
        """
        Called by AudioPipeline when an audio alert (.wav) is ready.
        start_sec / end_sec are stream-relative offsets into the AUDIO archive.
        The video archive is sought at the wall-time-corrected equivalent offset.
        """
        if not camera_ids:
            logger.info(
                "Mic %s triggered alert but is not mapped to any camera — suppressed.",
                mic_id,
            )
            return []

        a_ref = self.audio_archives.get(mic_id)  # may be None if mic unknown
        filename = os.path.basename(alert_wav_path).replace(".wav", "")
        generated_paths = []

        for camera_id in camera_ids:
            v_ref = self.video_archives.get(camera_id)
            if not v_ref or not os.path.exists(v_ref.path):
                logger.warning(
                    "Video archive not found for camera %s. Skipping combined alert.",
                    camera_id,
                )
                continue

            # R1: cross-modal offset correction via wall-clock event time
            offsets = self._cross_modal_offsets(
                source_start=start_sec,
                source_end=end_sec,
                source_ref=a_ref,
                target_ref=v_ref,
                source_label=f"audio:{mic_id}",
                target_label=f"video:{camera_id}",
            )
            if offsets is None:
                logger.warning(
                    "Video archive for camera %s has zero temporal overlap with audio alert on %s. Skipping.",
                    camera_id, mic_id,
                )
                continue

            v_start, v_end = offsets

            uid = uuid.uuid4().hex[:8]
            output_path = os.path.join(
                self.output_dir, f"combined_AV_{camera_id}_{filename}_{uid}.mp4"
            )
            annotated_video_path = os.path.join(
                self.output_dir, f"temp_video_{camera_id}_{filename}_{uid}.mp4"
            )

            try:
                has_video = self._extract_and_annotate_video(
                    v_ref.path, annotated_video_path, camera_id, mic_id, v_start, v_end
                )
                if not has_video:
                    logger.warning(
                        "No frames extracted from video archive for %s at %.3fs. "
                        "Audio alert happened after video ended?",
                        camera_id, v_start,
                    )
                    continue

                self._merge_with_ffmpeg(annotated_video_path, alert_wav_path, output_path)
                logger.info(
                    "AV Composer extracted video for audio alert: %s", output_path
                )
                generated_paths.append(output_path)
            except Exception as e:
                logger.error(
                    "Error composing audio alert for camera %s: %s", camera_id, e
                )
            finally:
                if os.path.exists(annotated_video_path):
                    try:
                        os.remove(annotated_video_path)
                    except OSError:
                        pass

        return generated_paths

    def _extract_and_annotate_video(
        self,
        video_archive: str,
        output_path: str,
        camera_id: str,
        mic_id: Optional[str],
        start_sec: float,
        end_sec: float,
        subject_point: Optional[tuple] = None,
    ) -> bool:
        from thaqib.video.timestamps import draw_timestamp_overlay
        import cv2

        cap = cv2.VideoCapture(video_archive)
        if not cap.isOpened():
            logger.error("Failed to open video archive: %s", video_archive)
            return False

        fps = cap.get(cv2.CAP_PROP_FPS)
        if fps <= 0 or fps != fps:  # handles NaN
            fps = 30.0
        width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        if width <= 0 or height <= 0:
            logger.error("Invalid video archive dimensions: %dx%d", width, height)
            cap.release()
            return False

        start_sec = max(0.0, float(start_sec))
        end_sec = max(start_sec + 0.1, float(end_sec))
        start_frame = int(round(start_sec * fps))
        target_frames = max(1, int(round((end_sec - start_sec) * fps)))

        # Dual-mode seek: POS_MSEC primary, POS_FRAMES fallback
        cap.set(cv2.CAP_PROP_POS_MSEC, start_sec * 1000.0)
        curr_frame = cap.get(cv2.CAP_PROP_POS_FRAMES)
        if curr_frame < 0 or abs(curr_frame - start_frame) > fps:
            cap.set(cv2.CAP_PROP_POS_FRAMES, start_frame)

        fourcc = cv2.VideoWriter_fourcc(*'mp4v')
        out = cv2.VideoWriter(output_path, fourcc, fps, (width, height))
        if not out.isOpened():
            logger.error("Failed to create VideoWriter for output: %s", output_path)
            cap.release()
            return False

        frames_written = 0
        read_attempts = 0
        max_attempts = target_frames * 3 + 30
        while frames_written < target_frames and read_attempts < max_attempts:
            read_attempts += 1
            ret, frame = cap.read()
            if not ret:
                break
            self._draw_mic_pins(frame, camera_id, mic_id)
            if subject_point:
                px = max(0, min(subject_point[0], width - 1))
                py = max(0, min(subject_point[1], height - 1))
                cv2.circle(frame, (px, py), 10, (0, 255, 255), -1, cv2.LINE_AA)
                cv2.circle(frame, (px, py), 10, (0, 0, 0), 2, cv2.LINE_AA)
            current_sec = start_sec + (frames_written / fps)
            draw_timestamp_overlay(frame, ts=time.time(), archive_offset_sec=current_sec)
            out.write(frame)
            frames_written += 1

        out.release()
        cap.release()
        return frames_written > 0

    def _draw_mic_pins(self, frame, camera_id, source_mic_id):
        import cv2
        if not self.layout: return
        pins = self.layout.get_pins_for_camera(camera_id)
        h, w = frame.shape[:2]
        for pin in pins:
            px, py = int(pin.norm_pos[0] * w), int(pin.norm_pos[1] * h)
            color = (0, 0, 255) if pin.mic_id == source_mic_id else (0, 255, 0)
            cv2.circle(frame, (px, py), 9, color, -1)

    def _merge_with_ffmpeg(
        self, 
        video_input: str, 
        audio_input: str, 
        output_path: str,
        audio_start: float | None = None,
        audio_end: float | None = None
    ):
        """Runs FFmpeg to combine video and audio inputs into output_path."""
        cmd = ["ffmpeg", "-y", "-nostdin"]
        cmd.extend(["-i", video_input])
        if audio_start is not None and audio_end is not None:
            cmd.extend(["-ss", f"{audio_start:.3f}", "-to", f"{audio_end:.3f}"])
        elif audio_start is not None:
            cmd.extend(["-ss", f"{audio_start:.3f}"])
        cmd.extend([
            "-i", audio_input,
            "-map", "0:v:0",
            "-map", "1:a:0",
            "-c:v", "copy",
            "-c:a", "aac",
            "-shortest",
            output_path
        ])
        result = subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, stdin=subprocess.DEVNULL)
        if result.returncode != 0:
            err = result.stderr.decode("utf-8", errors="replace")
            raise RuntimeError(f"FFmpeg error ({result.returncode}): {err}")

