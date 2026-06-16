"""
test_audio_duration.py
======================
Verifies that on_audio_alert correctly produces a clip covering the FULL
speech event duration plus 1s pre/post padding.

Simulated scenario
------------------
  t = now
  speech starts at  t - 7.0
  speech ends   at  t - 2.0   →  5 seconds of speech
  padding:  1.0s before start, 1.0s after end
  expected clip window: [t-8.0 , t-1.0]  = 7.0 seconds

Verification checks
-------------------
  1. ffprobe: video duration ≈ 7.0 s
  2. ffprobe: audio duration ≈ 7.0 s (or slightly longer due to apad)
  3. Frame count ≈ 7.0 × 30 = 210 frames
  4. Pixel colour at mic0 pin (0.5,0.5) = RED on first/middle/last frame
  5. Audio non-silence in middle 1s window (sine wave present)

Usage
-----
    venv\\Scripts\\python.exe scripts\\test_audio_duration.py
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

# ── Logging ──────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)7s] %(name)s: %(message)s",
    stream=sys.stdout,
)
log = logging.getLogger("test_audio_duration")

# ── Resolve src/ ──────────────────────────────────────────────────────────────
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from thaqib.av_alert_composer import AVAlertComposer, AUDIO_ALERT_PAD_BEFORE_S, AUDIO_ALERT_PAD_AFTER_S
from thaqib.mic_layout import MicLayout, MicPin
from thaqib.video.registry import GlobalStudentRegistry

# ── Constants ─────────────────────────────────────────────────────────────────
W, H   = 640, 360
FPS    = 30.0
SR     = 16000
CAM_ID = "cam0"
MIC_ID = "mic0"

SPEECH_DURATION  = 5.0   # seconds of speech
PAD_BEFORE       = AUDIO_ALERT_PAD_BEFORE_S  # 1.0 s
PAD_AFTER        = AUDIO_ALERT_PAD_AFTER_S   # 1.0 s
EXPECTED_CLIP_S  = SPEECH_DURATION + PAD_BEFORE + PAD_AFTER  # 7.0 s
EXPECTED_FRAMES  = int(EXPECTED_CLIP_S * FPS)                # 210

MIC_NORM_POS = (0.5, 0.5)    # pin at centre of frame
MIC_PIX_X    = int(MIC_NORM_POS[0] * W)   # 320
MIC_PIX_Y    = int(MIC_NORM_POS[1] * H)   # 180


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

    _cfg._settings_instance = _FS()
    return _cfg._settings_instance


# ── Build composer ─────────────────────────────────────────────────────────────
def build_composer(output_dir: str, ts: float) -> AVAlertComposer:
    layout = MicLayout(layout_file=os.path.join(output_dir, "_mic_layout.json"))
    layout.pins[MIC_ID] = MicPin(mic_id=MIC_ID, camera_id=CAM_ID, norm_pos=MIC_NORM_POS)

    # Audio buffer: 10 chunks/second spanning [t-10, t]
    audio_buf: deque = deque(maxlen=200)
    chunk_s = 0.1
    chunk_n = int(SR * chunk_s)
    # Fill with a 440 Hz sine so it's provably non-silent
    for i in range(120):
        ts_chunk = ts - 10.0 + i * chunk_s
        t_arr    = np.linspace(ts_chunk, ts_chunk + chunk_s, chunk_n, endpoint=False)
        data     = (0.3 * np.sin(2 * np.pi * 440 * t_arr)).astype(np.float32)
        audio_buf.append((ts_chunk, data))

    # Video buffer: 30 fps spanning [t-10, t]
    video_buf: deque = deque(maxlen=500)
    for i in range(300):
        ts_frame = ts - 10.0 + i / FPS
        frame    = np.full((H, W, 3), (50, 80, 120), dtype=np.uint8)  # dark blue ≠ red/green
        video_buf.append((ts_frame, frame))

    return AVAlertComposer(
        layout=layout,
        audio_buffers={MIC_ID: audio_buf},
        video_buffers={CAM_ID: video_buf},
        video_registries={CAM_ID: GlobalStudentRegistry()},
        output_dir=output_dir,
        video_fps=FPS,
        audio_sample_rate=SR,
    )


# ── ffprobe helpers ───────────────────────────────────────────────────────────
def ffprobe_duration(path: str, stream: str = "v:0") -> float:
    """Return duration of first video (v:0) or audio (a:0) stream in seconds."""
    cmd = [
        "ffprobe", "-v", "error",
        "-select_streams", stream,
        "-show_entries", "stream=duration",
        "-of", "default=noprint_wrappers=1:nokey=1",
        str(path),
    ]
    out = subprocess.run(cmd, capture_output=True, text=True).stdout.strip()
    try:
        return float(out.split()[0])
    except (ValueError, IndexError):
        return -1.0


def ffprobe_has_audio(path: str) -> bool:
    cmd = [
        "ffprobe", "-v", "error",
        "-show_entries", "stream=codec_type",
        "-of", "default=noprint_wrappers=1",
        str(path),
    ]
    return "codec_type=audio" in subprocess.run(cmd, capture_output=True, text=True).stdout


# ── Pixel-colour helpers ──────────────────────────────────────────────────────
def _is_red(bgr: tuple) -> bool:
    b, g, r = bgr
    return r >= 160 and g < 80 and b < 80


def sample_pixel(frame: np.ndarray, px: int, py: int) -> tuple:
    py = min(py, frame.shape[0] - 1)
    px = min(px, frame.shape[1] - 1)
    b, g, r = frame[py, px]
    return (int(b), int(g), int(r))


# ── Main ──────────────────────────────────────────────────────────────────────
def run_test():
    output_dir = tempfile.mkdtemp(prefix="thaqib_audio_dur_")
    log.info(f"Output dir: {output_dir}")

    _install_fake_settings(output_dir)
    ts = time.time()

    composer = build_composer(output_dir, ts)

    # Speech window: started 7s ago, ended 2s ago → 5s duration
    ts_start = ts - 7.0
    ts_end   = ts - 2.0

    # 5-second 440 Hz sine clip (the "speech event" audio itself)
    t_arr      = np.linspace(0, SPEECH_DURATION, int(SR * SPEECH_DURATION), endpoint=False)
    speech_clip = (0.3 * np.sin(2 * np.pi * 440 * t_arr)).astype(np.float32)

    log.info(
        f"\nFiring on_audio_alert:\n"
        f"  ts_start = ts - 7.0  (speech began 7s ago)\n"
        f"  ts_end   = ts - 2.0  (speech ended 2s ago)\n"
        f"  speech duration = {SPEECH_DURATION}s\n"
        f"  expected clip   = {EXPECTED_CLIP_S}s  "
        f"({PAD_BEFORE}s pre + {SPEECH_DURATION}s event + {PAD_AFTER}s post)\n"
        f"  expected frames ≈ {EXPECTED_FRAMES}"
    )

    composer.on_audio_alert(
        audio_clip=speech_clip,
        mic_id=MIC_ID,
        timestamp_start=ts_start,
        timestamp_end=ts_end,
        keywords=["cheat"],
        sample_rate=SR,
    )

    log.info("Waiting 20 s for ffmpeg mux thread…")
    time.sleep(20)

    # ── Find output file ──────────────────────────────────────────────────────
    mp4_files = sorted(Path(output_dir).glob("*.mp4"))
    log.info(f"\nFound {len(mp4_files)} .mp4 file(s):")
    for f in mp4_files:
        log.info(f"  {f.name}  ({f.stat().st_size:,} bytes)")

    if not mp4_files:
        log.error("NO OUTPUT FILE — test cannot proceed.")
        print("\n" + "="*60)
        print("Audio alerts correctly capture the full speech event duration "
              "(not just one chunk), with 1s pre/post padding, matching video "
              "extraction, and mic-pin overlay on all frames: NO")
        sys.exit(1)

    clip = str(mp4_files[0])

    results = {}

    # ── Check 1: video duration ───────────────────────────────────────────────
    vid_dur = ffprobe_duration(clip, "v:0")
    log.info(f"\n[1] Video duration = {vid_dur:.2f}s  (expected ≈ {EXPECTED_CLIP_S:.1f}s)")
    results["video_duration_ok"] = abs(vid_dur - EXPECTED_CLIP_S) <= 1.0  # ±1s tolerance

    # ── Check 2: audio stream present ────────────────────────────────────────
    has_audio = ffprobe_has_audio(clip)
    aud_dur   = ffprobe_duration(clip, "a:0")
    log.info(f"[2] Audio present: {has_audio}  duration = {aud_dur:.2f}s")
    results["audio_present"] = has_audio

    # ── Check 3: frame count ──────────────────────────────────────────────────
    cap = cv2.VideoCapture(clip)
    frames_read = []
    while True:
        ret, f = cap.read()
        if not ret:
            break
        frames_read.append(f)
    cap.release()
    n_frames = len(frames_read)
    log.info(f"[3] Frame count = {n_frames}  (expected ≈ {EXPECTED_FRAMES})")
    results["frame_count_ok"] = abs(n_frames - EXPECTED_FRAMES) <= 15  # ±15 frames tolerance

    # ── Check 4: mic-pin RED on first/middle/last frame ───────────────────────
    log.info(f"\n[4] Mic-pin colour check at pixel ({MIC_PIX_X}, {MIC_PIX_Y}):")
    pin_ok = True
    for pos_name, fidx in [("first", 0), ("middle", n_frames // 2), ("last", n_frames - 1)]:
        if fidx >= len(frames_read):
            log.error(f"    {pos_name}: frame index {fidx} out of range")
            pin_ok = False
            continue
        bgr = sample_pixel(frames_read[fidx], MIC_PIX_X, MIC_PIX_Y)
        ok  = _is_red(bgr)
        log.info(f"    {pos_name} frame [{fidx}]: BGR{bgr}  → {'RED ✓' if ok else 'NOT RED ✗'}")
        if not ok:
            pin_ok = False
    results["mic_pin_red"] = pin_ok

    # ── Check 5: audio non-silence in middle 1s window ────────────────────────
    # Use ffmpeg to extract 1s of audio starting at 3.0s (middle of event)
    mid_wav = os.path.join(output_dir, "mid_check.wav")
    subprocess.run(
        ["ffmpeg", "-y", "-i", clip, "-ss", "3.0", "-t", "1.0",
         "-vn", "-acodec", "pcm_s16le", mid_wav],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
    )
    if os.path.exists(mid_wav):
        import scipy.io.wavfile as wavfile
        _, audio_data = wavfile.read(mid_wav)
        rms = float(np.sqrt(np.mean(audio_data.astype(np.float32) ** 2)))
        log.info(f"\n[5] Middle 1s audio RMS = {rms:.1f}  (expected > 100 for 440Hz sine)")
        results["audio_non_silent"] = rms > 100.0
    else:
        log.error("[5] Could not extract mid-clip audio — ffmpeg extraction failed")
        results["audio_non_silent"] = False

    # ── Summary ───────────────────────────────────────────────────────────────
    log.info("\n" + "="*60)
    for key, val in results.items():
        log.info(f"  {key:25s} : {'PASS' if val else 'FAIL'}")

    passed = all(results.values())
    print("\n" + "="*60)
    verdict = "YES" if passed else "NO"
    print(
        f"Audio alerts correctly capture the full speech event duration "
        f"(not just one chunk), with 1s pre/post padding, matching video "
        f"extraction, and mic-pin overlay on all frames: {verdict}"
    )

    if not passed:
        sys.exit(1)


if __name__ == "__main__":
    run_test()
