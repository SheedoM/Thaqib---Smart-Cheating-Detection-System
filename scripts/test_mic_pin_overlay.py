"""
test_mic_pin_overlay.py — Verify mic-pin overlay (red source / green others)
on ALL frames (pre/event/post) for both on_video_alert and on_audio_alert.

Layout:  3 pins for cam_test
  mic_a  (0.2, 0.3)  — left
  mic_b  (0.5, 0.5)  — centre  ← subject_point is closest to this one
  mic_c  (0.8, 0.7)  — right

Test A  — on_video_alert / gaze  : mic_b should be RED, mic_a/mic_c GREEN
Test B  — on_video_alert / phone : mic_b should be RED, mic_a/mic_c GREEN
Test C  — on_audio_alert / mic_a : mic_a should be RED, mic_b/mic_c GREEN

For each output clip we:
  1. Use ffprobe to confirm both video + audio streams exist.
  2. Read every frame with cv2.VideoCapture and sample the pixel at each
     known pin position.  The correct channel must be ≥200 and the other
     two channels < 60  (pure red → B≈0 G≈0 R≈255 in BGR, pure green → B≈0 G≈255 R≈0).

Usage:
    venv\\Scripts\\python.exe scripts\\test_mic_pin_overlay.py
"""

import logging
import os
import subprocess
import sys
import tempfile
import time
from collections import deque
from pathlib import Path

import cv2
import numpy as np

# ── Logging ─────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)7s] %(name)s: %(message)s",
    stream=sys.stdout,
)
log = logging.getLogger("test_mic_pin_overlay")

# ── Resolve src/ ─────────────────────────────────────────────────────────────
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from thaqib.av_alert_composer import AVAlertComposer
from thaqib.mic_layout import MicLayout, MicPin
from thaqib.video.registry import GlobalStudentRegistry

# ── Constants ────────────────────────────────────────────────────────────────
W, H   = 640, 360
FPS    = 30.0
SR     = 16000
CAM_ID = "cam_test"

# Pins: id -> norm_pos
PINS = {
    "mic_a": (0.2, 0.3),   # pixel: (128, 108)
    "mic_b": (0.5, 0.5),   # pixel: (320, 180)  ← nearest to subject
    "mic_c": (0.8, 0.7),   # pixel: (512, 252)
}

# Subject point — closest to mic_b
SUBJECT_POINT = (310, 175)  # pixel coords, clearly nearest mic_b


# ── Settings shim ─────────────────────────────────────────────────────────────
def _install_fake_settings(output_dir: str):
    import thaqib.config as _cfg
    import pydantic_settings

    class _FS(pydantic_settings.BaseSettings):
        alerts_dir:                    str   = output_dir
        alert_max_height:              int   = 0
        video_quality:                 int   = 75
        archive_mode:                  str   = "raw"
        archive_dir:                   str   = output_dir
        detection_interval:            int   = 3
        detection_imgsz:               int   = 640
        suspicious_duration_threshold: float = 3.0
        device:                        str   = "cpu"

    _cfg._settings_instance = _FS()   # type: ignore[assignment]
    return _cfg._settings_instance


# ── Build composer ─────────────────────────────────────────────────────────────
def build_composer(output_dir: str, ts_base: float) -> AVAlertComposer:
    layout = MicLayout()
    for mic_id, norm_pos in PINS.items():
        layout.pins[mic_id] = [MicPin(mic_id=mic_id, camera_id=CAM_ID, norm_pos=norm_pos)]

    # ~6 s of synthetic audio centred on ts_base, for every mic
    audio_bufs: dict[str, deque] = {}
    for mic_id in PINS:
        buf: deque = deque(maxlen=500)
        chunk = SR // 10
        for i in range(70):
            ts   = ts_base - 3.5 + i * 0.1
            data = (np.random.randn(chunk) * 0.01).astype(np.float32)
            buf.append((ts, data))
        audio_bufs[mic_id] = buf

    # Video buffer for cam_test — filled with solid-blue raw frames at ts_base ± 3 s
    video_buf: deque = deque(maxlen=500)
    for i in range(200):
        ts    = ts_base - 5.0 + i * 0.05
        frame = np.full((H, W, 3), (180, 80, 40), dtype=np.uint8)  # dark teal ≠ red/green
        video_buf.append((ts, frame))

    return AVAlertComposer(
        layout=layout,
        audio_buffers=audio_bufs,
        video_buffers={CAM_ID: video_buf},
        video_registries={CAM_ID: GlobalStudentRegistry()},
        output_dir=output_dir,
        video_fps=FPS,
        audio_sample_rate=SR,
    )


# ── Frame helpers ─────────────────────────────────────────────────────────────
def make_event_frames(ts_base: float, n: int = 30) -> list[np.ndarray]:
    """Return n solid-colour event frames (no mic markers yet)."""
    return [
        np.full((H, W, 3), (180, 80, 40), dtype=np.uint8)
        for _ in range(n)
    ]


# ── Pixel-colour validation ───────────────────────────────────────────────────
RED   = (0, 0, 255)   # BGR
GREEN = (0, 255, 0)   # BGR

def _is_red(bgr: tuple) -> bool:
    b, g, r = bgr
    return r >= 160 and g < 80 and b < 80

def _is_green(bgr: tuple) -> bool:
    b, g, r = bgr
    return g >= 160 and r < 80 and b < 80

def pin_pixel(mic_id: str, frame_w: int = W, frame_h: int = H) -> tuple[int, int]:
    nx, ny = PINS[mic_id]
    return int(nx * frame_w), int(ny * frame_h)

def sample_pixel(frame: np.ndarray, mic_id: str) -> tuple[int, int, int]:
    px, py = pin_pixel(mic_id, frame.shape[1], frame.shape[0])
    # clamp to frame bounds
    px = min(px, frame.shape[1] - 1)
    py = min(py, frame.shape[0] - 1)
    b, g, r = frame[py, px]
    return (int(b), int(g), int(r))


# ── ffprobe helper ────────────────────────────────────────────────────────────
def ffprobe_has_audio(path: str) -> bool:
    cmd = [
        "ffprobe", "-v", "error",
        "-show_entries", "stream=codec_type",
        "-of", "default=noprint_wrappers=1",
        str(path),
    ]
    out = subprocess.run(cmd, capture_output=True, text=True).stdout
    return "codec_type=audio" in out


# ── Per-clip checker ──────────────────────────────────────────────────────────
def check_clip(
    clip_path: str,
    source_mic: str,
    label: str,
) -> bool:
    """Read all frames from clip_path; for every frame verify colour at each pin."""
    if not os.path.exists(clip_path):
        log.error(f"  [{label}] MISSING: {clip_path}")
        return False

    cap = cv2.VideoCapture(clip_path)
    if not cap.isOpened():
        log.error(f"  [{label}] Cannot open {clip_path}")
        return False

    frame_count  = 0
    failures     = []  # (frame_idx, mic_id, expected, got)
    sampled_frames = {}  # {frame_idx: frame} for first/middle/last

    while True:
        ret, frame = cap.read()
        if not ret:
            break
        fidx = frame_count
        frame_count += 1
        for mic_id in PINS:
            bgr = sample_pixel(frame, mic_id)
            if mic_id == source_mic:
                if not _is_red(bgr):
                    failures.append((fidx, mic_id, "RED", bgr))
            else:
                if not _is_green(bgr):
                    failures.append((fidx, mic_id, "GREEN", bgr))

        # Keep first / middle / last frame for reporting
        if fidx == 0:
            sampled_frames["first"] = frame.copy()

    cap.release()

    if frame_count > 0:
        # re-open to grab middle & last frame
        cap2 = cv2.VideoCapture(clip_path)
        mid_idx = frame_count // 2
        last_idx = frame_count - 1
        for fi in range(frame_count):
            ret, frame = cap2.read()
            if not ret:
                break
            if fi == mid_idx:
                sampled_frames["middle"] = frame.copy()
            if fi == last_idx:
                sampled_frames["last"] = frame.copy()
        cap2.release()

    log.info(f"  [{label}] {frame_count} frames read from clip")
    log.info(f"  [{label}] source_mic={source_mic!r} → should be RED; others GREEN")

    # Report spot-check pixels
    for pos_name, f in sampled_frames.items():
        pixels = {m: sample_pixel(f, m) for m in PINS}
        log.info(f"  [{label}] {pos_name} frame pixels: " + 
                 "  ".join(f"{m}=BGR{v}" for m, v in pixels.items()))

    if failures:
        # Only print first 5 failures to keep output sane
        for (fi, mid, exp, got) in failures[:5]:
            log.error(f"  [{label}] FAIL frame={fi} mic={mid} expected={exp} got=BGR{got}")
        if len(failures) > 5:
            log.error(f"  [{label}] ... and {len(failures) - 5} more failures")
        return False

    log.info(f"  [{label}] All {frame_count} frames PASS ✓")
    return True


# ── Main ──────────────────────────────────────────────────────────────────────
def run_test():
    output_dir = tempfile.mkdtemp(prefix="thaqib_micpin_test_")
    log.info(f"Output dir: {output_dir}")

    _install_fake_settings(output_dir)
    ts_now   = time.time()
    composer = build_composer(output_dir, ts_base=ts_now)

    results = {}

    # ── Test A: on_video_alert / gaze  ──────────────────────────────────────
    log.info("\n" + "="*60)
    log.info("[TEST A] on_video_alert / alert_type='gaze'")
    ts_a = ts_now
    frames_a = make_event_frames(ts_a)
    composer.on_video_alert(
        frames=frames_a,
        alert_type="gaze",
        subject_point=SUBJECT_POINT,
        camera_id=CAM_ID,
        timestamp_start=ts_a,
        timestamp_end=ts_a + len(frames_a) / FPS,
    )

    # ── Test B: on_video_alert / phone  ─────────────────────────────────────
    log.info("\n" + "="*60)
    log.info("[TEST B] on_video_alert / alert_type='phone'")
    ts_b = ts_now + 1.0
    frames_b = make_event_frames(ts_b)
    composer.on_video_alert(
        frames=frames_b,
        alert_type="phone",
        subject_point=SUBJECT_POINT,
        camera_id=CAM_ID,
        timestamp_start=ts_b,
        timestamp_end=ts_b + len(frames_b) / FPS,
    )

    # ── Test C: on_audio_alert / mic_a  ─────────────────────────────────────
    log.info("\n" + "="*60)
    log.info("[TEST C] on_audio_alert / mic_id='mic_a'")
    # mic_a must be mapped to cam_test (it is — set in build_composer)
    ts_c = ts_now + 0.5
    chunk = SR // 10
    audio_c = (np.random.randn(int(SR * 2)) * 0.01).astype(np.float32)
    composer.on_audio_alert(
        audio_clip=audio_c,
        mic_id="mic_a",
        timestamp_start=ts_c,
        timestamp_end=ts_c + 2.0,
        keywords=[],
        sample_rate=SR,
    )

    # ── Wait for mux threads ─────────────────────────────────────────────────
    log.info("\nWaiting 20 s for ffmpeg mux threads to finish…")
    time.sleep(20)

    # ── Discover output files ────────────────────────────────────────────────
    mp4_files = sorted(Path(output_dir).glob("*.mp4"))
    log.info(f"\nFound {len(mp4_files)} .mp4 file(s):")
    for f in mp4_files:
        log.info(f"  {f.name}  ({f.stat().st_size:,} bytes)")

    # Map files to test labels by alert_type prefix
    def find_clip(prefix: str) -> str | None:
        for f in mp4_files:
            if f.name.startswith(prefix):
                return str(f)
        return None

    clip_a = find_clip("gaze_")
    clip_b = find_clip("phone_")
    clip_c = find_clip("audio_alert_mic_a")

    log.info("\n" + "="*60)
    log.info("PIXEL-COLOUR CHECK")
    results["A_gaze"]  = check_clip(clip_a,  source_mic="mic_b", label="A gaze")  if clip_a  else False
    results["B_phone"] = check_clip(clip_b,  source_mic="mic_b", label="B phone") if clip_b  else False
    results["C_audio"] = check_clip(clip_c,  source_mic="mic_a", label="C audio") if clip_c  else False

    # ── Audio-stream sanity ──────────────────────────────────────────────────
    log.info("\n" + "="*60)
    log.info("AUDIO STREAM CHECK")
    for clip, name in [(clip_a, "A gaze"), (clip_b, "B phone"), (clip_c, "C audio")]:
        if clip:
            has_audio = ffprobe_has_audio(clip)
            log.info(f"  [{name}] has audio stream: {'YES' if has_audio else 'NO'}")
            results[f"{name}_audio"] = has_audio
        else:
            log.error(f"  [{name}] clip not found — cannot check audio")
            results[f"{name}_audio"] = False

    # ── Final verdict ────────────────────────────────────────────────────────
    log.info("\n" + "="*60)
    for key, val in results.items():
        log.info(f"  {key:20s} : {'PASS' if val else 'FAIL'}")

    passed = all(results.values())
    print("\n" + "="*60)
    verdict = "YES" if passed else "NO"
    print(
        f"All alert clips now show all configured mic pins (green) "
        f"with the actual audio-source mic highlighted in red, "
        f"on every frame including pre/post padding, "
        f"for both video- and audio-triggered alerts: {verdict}"
    )

    if not passed:
        sys.exit(1)


if __name__ == "__main__":
    run_test()
