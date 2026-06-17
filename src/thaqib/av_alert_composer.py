import logging
import os
import subprocess
import time

logger = logging.getLogger(__name__)


class AVAlertComposer:
    def __init__(
        self,
        audio_archives: dict[str, str],  # mic_id -> path to audio archive
        video_archives: dict[str, str],  # camera_id -> path to video archive
        layout=None,
        output_dir: str = "alerts",
    ):
        """
        Composer that relies purely on post-extraction from archives.
        No memory buffers, no circular queues.
        """
        self.audio_archives = audio_archives
        self.video_archives = video_archives
        self.layout = layout
        self.output_dir = output_dir
        os.makedirs(self.output_dir, exist_ok=True)

    def stop(self):
        # Kept for compatibility with run.py
        pass

    def shutdown(self, wait: bool = True):
        # Kept for compatibility with run.py
        pass

    def compose_video_alert(
        self,
        camera_id: str,
        mic_id: str,
        start_sec: float,
        end_sec: float,
        alert_type: str,
        subject_point: tuple[int, int],
    ):
        """
        Called by VideoPipeline when a video alert is ready.
        Extracts video from the Video Archive, annotates it (mic pins + student center),
        extracts audio from the Audio Archive, and merges them.
        """
        video_archive = self.video_archives.get(camera_id)

        if not video_archive or not os.path.exists(video_archive):
            logger.warning(
                f"Video archive not found for camera {camera_id}. Cannot compose video alert."
            )
            return

        timestamp = time.time()
        filename = f"{alert_type}_{camera_id}_{timestamp:.1f}.mp4"
        output_path = os.path.join(self.output_dir, f"combined_AV_{filename}")

        has_audio = False
        audio_archive = None
        if mic_id:
            audio_archive = self.audio_archives.get(mic_id)
            if audio_archive and os.path.exists(audio_archive):
                has_audio = True
            else:
                logger.warning(
                    f"Audio archive not found for mic {mic_id}. Generating video-only alert."
                )
        else:
            logger.info(f"No mic mapped. Generating video-only alert for {camera_id}.")

        if has_audio:
            annotated_video_path = os.path.join(self.output_dir, f"temp_vid_alert_{filename}")

            # 1. Extract from video archive and draw annotations
            has_video = self._extract_and_annotate_video(
                video_archive=video_archive,
                output_path=annotated_video_path,
                camera_id=camera_id,
                mic_id=mic_id,
                start_sec=start_sec,
                end_sec=end_sec,
                subject_point=subject_point,
            )

            if not has_video:
                logger.warning(
                    f"No frames extracted from video archive for {camera_id} at {start_sec}s. "
                    "Audio alert after video EOF?"
                )
                if os.path.exists(annotated_video_path):
                    os.remove(annotated_video_path)
                return

            # 2. Extract audio from audio archive and merge
            self._merge_with_ffmpeg(
                video_input=annotated_video_path,
                audio_input=audio_archive,
                audio_start=start_sec,
                audio_end=end_sec,
                output_path=output_path,
            )

            if os.path.exists(annotated_video_path):
                os.remove(annotated_video_path)

            logger.info(f"AV Composer successfully merged audio into video alert: {output_path}")
        else:
            # Generate video-only alert
            video_only_path = os.path.join(
                self.output_dir, f"{alert_type}_{camera_id}_{timestamp:.1f}.mp4"
            )
            self._extract_and_annotate_video(
                video_archive=video_archive,
                output_path=video_only_path,
                camera_id=camera_id,
                mic_id=mic_id,
                start_sec=start_sec,
                end_sec=end_sec,
                subject_point=subject_point,
            )
            logger.info(f"AV Composer generated video-only alert: {video_only_path}")

    def compose_audio_alert(
        self,
        alert_wav_path: str,
        mic_id: str,
        camera_ids: list[str],
        start_sec: float,
        end_sec: float,
    ):
        """
        Called by AudioPipeline when an audio alert (.wav) is ready.
        Extracts the matching video from the Video Archive and merges them.
        """
        if not camera_ids:
            logger.info(f"Mic {mic_id} triggered alert but is not mapped to any camera - suppressed.")
            return

        filename = os.path.basename(alert_wav_path).replace(".wav", "")

        for camera_id in camera_ids:
            video_archive = self.video_archives.get(camera_id)
            if not video_archive or not os.path.exists(video_archive):
                logger.warning(f"Video archive not found for camera {camera_id}. Skipping combined alert.")
                continue

            output_path = os.path.join(self.output_dir, f"combined_AV_{camera_id}_{filename}.mp4")

            # Since we need to draw mic pins, we extract and annotate using OpenCV
            annotated_video_path = os.path.join(
                self.output_dir, f"temp_video_{camera_id}_{filename}.mp4"
            )
            has_video = self._extract_and_annotate_video(
                video_archive, annotated_video_path, camera_id, mic_id, start_sec, end_sec
            )

            if not has_video:
                logger.warning(
                    f"No frames extracted from video archive for {camera_id} at {start_sec}s. "
                    "Audio alert happened after video ended?"
                )
                if os.path.exists(annotated_video_path):
                    os.remove(annotated_video_path)
                continue

            # We extract video from the archive, and use the already-cut audio alert
            self._merge_with_ffmpeg(
                video_input=annotated_video_path,
                audio_input=alert_wav_path,
                output_path=output_path,
            )

            if os.path.exists(annotated_video_path):
                os.remove(annotated_video_path)

            logger.info(f"AV Composer successfully extracted video for audio alert: {output_path}")

    def _extract_and_annotate_video(
        self,
        video_archive: str,
        output_path: str,
        camera_id: str,
        mic_id: str,
        start_sec: float,
        end_sec: float,
        subject_point: tuple[int, int] = None,
    ) -> bool:
        import cv2

        cap = cv2.VideoCapture(video_archive)
        if not cap.isOpened():
            logger.error(f"Failed to open video archive: {video_archive}")
            return False

        fps = cap.get(cv2.CAP_PROP_FPS)
        if fps <= 0:
            fps = 30.0

        width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))

        # Seek to start
        cap.set(cv2.CAP_PROP_POS_MSEC, start_sec * 1000.0)

        fourcc = cv2.VideoWriter_fourcc(*"mp4v")
        out = cv2.VideoWriter(output_path, fourcc, fps, (width, height))

        frames_written = 0
        while True:
            current_sec = cap.get(cv2.CAP_PROP_POS_MSEC) / 1000.0
            if current_sec > end_sec:
                break

            ret, frame = cap.read()
            if not ret:
                break

            # Draw mic pins
            self._draw_mic_pins(frame, camera_id, mic_id)

            # Draw subject point if provided
            if subject_point:
                px, py = subject_point
                # Ensure the point is within frame bounds (if resolution changed)
                px = max(0, min(px, width - 1))
                py = max(0, min(py, height - 1))
                # Draw a prominent yellow dot with a black border
                cv2.circle(frame, (px, py), 10, (0, 255, 255), -1, cv2.LINE_AA)
                cv2.circle(frame, (px, py), 10, (0, 0, 0), 2, cv2.LINE_AA)

            out.write(frame)
            frames_written += 1

        out.release()
        cap.release()
        return frames_written > 0

    def _draw_mic_pins(self, frame, camera_id: str, source_mic_id: str | None) -> None:
        import cv2

        if not self.layout:
            return
        pins = self.layout.get_pins_for_camera(camera_id)
        if not pins:
            return
        h, w = frame.shape[:2]
        for pin in pins:
            px = int(pin.norm_pos[0] * w)
            py = int(pin.norm_pos[1] * h)
            color = (0, 0, 255) if pin.mic_id == source_mic_id else (0, 255, 0)
            cv2.circle(frame, (px, py), 9, color, -1, cv2.LINE_AA)
            cv2.circle(frame, (px, py), 9, (255, 255, 255), 1, cv2.LINE_AA)
            cv2.putText(
                frame,
                pin.mic_id,
                (px + 12, py + 5),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.45,
                color,
                1,
                cv2.LINE_AA,
            )

    def _merge_with_ffmpeg(
        self,
        video_input: str,
        audio_input: str,
        output_path: str,
        video_start: float = None,
        video_end: float = None,
        audio_start: float = None,
        audio_end: float = None,
    ):
        """Runs FFmpeg to combine inputs, applying cutting to whichever needs it."""
        cmd = ["ffmpeg", "-y"]

        # Add video input (with or without seeking)
        if video_start is not None and video_end is not None:
            cmd.extend(["-ss", str(video_start), "-to", str(video_end)])
        cmd.extend(["-i", video_input])

        # Add audio input (with or without seeking)
        if audio_start is not None and audio_end is not None:
            cmd.extend(["-ss", str(audio_start), "-to", str(audio_end)])
        cmd.extend(["-i", audio_input])

        # Merge streams
        cmd.extend(
            [
                "-map",
                "0:v:0",
                "-map",
                "1:a:0",
                "-c:v",
                "copy",
                "-c:a",
                "aac",
                "-shortest",
                output_path,
            ]
        )

        result = subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
        if result.returncode != 0:
            stderr_text = result.stderr.decode("utf-8", errors="replace").strip()
            raise RuntimeError(f"ffmpeg exited {result.returncode}:\n{stderr_text}")
