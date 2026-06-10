"""
Standalone demo for the Thaqib Audio Cheating Detection System.

Processes audio from files or live microphones, displays a real-time
terminal dashboard, and saves evidence when cheating keywords are detected.

Usage (file mode):
    python scripts/demo_audio.py --files mic1.mp3 mic2.m4a

Usage (live mode):
    python scripts/demo_audio.py --devices 1 3

Usage (list available audio devices):
    python scripts/demo_audio.py --list-devices
"""

import argparse
import logging
import os
import sys
import time
from datetime import datetime

# Add src to path for development
sys.path.insert(0, str(__file__).replace("\\", "/").rsplit("/", 2)[0] + "/src")


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


cv2 = None  # Lazy loaded in main()
import numpy as np
import threading
from queue import Queue, Empty

# ── Terminal & GUI Dashboard ──────────────────────────────────────────

class AudioDashboard:
    """Real-time GUI and Terminal display for audio pipeline status."""

    def __init__(self, num_mics: int):
        self._num_mics = num_mics
        self._energy_profile = [0.0] * num_mics
        self._last_classification = "WAITING"
        self._active_mics: list[int] = []
        self._chunks_processed = 0
        self._alerts: list[dict] = []
        self._start_time = time.time()
        self._last_transcript = ""
        
        self._lock = threading.Lock()
        
        self._listen_mic_id = None
        self._playback_queue = Queue()
        self._is_playing = False
        self._playback_thread = None
        self._button_rects = [] # (mic_id, x, y, w, h)
        self.pipeline = None
        self.current_mic_page = 0
        self.alert_scroll_offset = 0
        self._last_alert_time_per_mic = {}

    def _playback_worker(self):
        import sounddevice as sd
        try:
            with sd.OutputStream(samplerate=16000, channels=1, dtype='float32') as stream:
                while self._is_playing:
                    try:
                        audio = self._playback_queue.get(timeout=0.1)
                        if audio is None:
                            break
                        stream.write(audio)
                    except Empty:
                        continue
        except Exception as e:
            logger.error(f"Playback error: {e}")

    def toggle_listen(self, mic_id: int):
        with self._lock:
            if self._listen_mic_id == mic_id:
                # Turn off
                self._listen_mic_id = None
                while not self._playback_queue.empty():
                    try: self._playback_queue.get_nowait()
                    except Empty: break
            else:
                # Turn on
                self._listen_mic_id = mic_id
                # Ensure thread is running
                if not self._is_playing:
                    self._is_playing = True
                    self._playback_thread = threading.Thread(target=self._playback_worker, daemon=True)
                    self._playback_thread.start()

    def handle_click(self, event, x, y, flags, param):
        if event == cv2.EVENT_LBUTTONDOWN:
            for mic_id, bx, by, bw, bh in self._button_rects:
                if bx <= x <= bx + bw and by <= y <= by + bh:
                    self.toggle_listen(mic_id)
                    break

    def stop(self):
        self._is_playing = False
        if self._playback_thread is not None:
            self._playback_thread.join(timeout=1.0)

    def update(self, chunk, classification) -> None:
        """Called on every processed chunk (from background thread)."""
        with self._lock:
            self._chunks_processed += 1
            self._energy_profile = classification.energy_profile.tolist()

            if classification.is_silent:
                self._last_classification = "SILENT"
                self._active_mics = []
            elif classification.is_global:
                self._last_classification = "GLOBAL"
                self._active_mics = []
            elif classification.is_local:
                self._last_classification = "LOCAL"
                self._active_mics = classification.active_mics

            if self._listen_mic_id is not None and self._listen_mic_id < len(chunk.mic_data):
                if self._playback_queue.qsize() < 10:
                    self._playback_queue.put(chunk.mic_data[self._listen_mic_id].copy())

        # Terminal Log (Continuous, no clearing)
        active = f"(Mics: {[m for m in self._active_mics]})" if self._active_mics else ""
        energies = ", ".join(f"{e:.3f}" for e in self._energy_profile)
        print(f"[Chunk {self._chunks_processed:04d}] {self._last_classification:7s} {active:12s} | Energies: [{energies}]")

    def on_alert(self, alert) -> None:
        """Called when a cheating alert is triggered (from background thread)."""
        time_str = time.strftime("%H:%M:%S")
        with self._lock:
            self._alerts.append({
                "time": time_str,
                "mic": alert.mic_id,
                "keywords": alert.matched_keywords,
                "transcript": alert.transcript,
            })
            self._last_transcript = alert.transcript
            self._last_alert_time_per_mic[alert.mic_id] = time.time()
            
        # Terminal Log
        try:
            print(f"\n{'='*60}")
            print(f"🚨 AUDIO ALERT [{time_str}] - Mic {alert.mic_id}")
            print(f"🚨 Keywords: {alert.matched_keywords}")
            print(f"🚨 Transcript: {alert.transcript}")
            print(f"{'='*60}\n")
        except UnicodeEncodeError:
            print(f"\n{'='*60}")
            print(f"[ALERT] AUDIO ALERT [{time_str}] - Mic {alert.mic_id}")
            print(f"[ALERT] Keywords: {alert.matched_keywords}")
            print(f"[ALERT] Transcript: {alert.transcript}")
            print(f"{'='*60}\n")

    def scroll_alerts(self, direction: int) -> None:
        """Scroll the alert list offset: -1 for up, 1 for down."""
        with self._lock:
            self.alert_scroll_offset += direction

    def change_mic_page(self, direction: int) -> None:
        """Change mic page: -1 for left, 1 for right."""
        with self._lock:
            total_pages = max(1, (self._num_mics + 5) // 6)
            self.current_mic_page = max(0, min(total_pages - 1, self.current_mic_page + direction))

    def render_gui(self) -> np.ndarray:
        """Render the OpenCV GUI canvas."""
        with self._lock:
            # Create a dark canvas — widened to 1100px to give all header elements room
            h, w = 600, 1100
            frame = np.zeros((h, w, 3), dtype=np.uint8)

            # ── Header Bar ───────────────────────────────────────────────────────────
            # Two-tone gradient bar: slightly lighter at right edge for depth
            cv2.rectangle(frame, (0, 0), (w, 62), (30, 30, 30), -1)
            cv2.rectangle(frame, (0, 60), (w, 62), (70, 70, 70), -1)  # bottom separator line

            # Shared font & baseline Y for all header items
            _hfont  = cv2.FONT_HERSHEY_SIMPLEX
            _hY     = 40
            _margin = 18  # px gap between adjacent elements

            # ── [1] LEFT: Window title — fixed anchor X=15 ───────────────────────────
            title_txt   = "THAQIB AUDIO MONITOR"
            title_scale = 0.68
            cv2.putText(frame, title_txt, (15, _hY), _hfont, title_scale, (255, 255, 255), 2)
            (title_w, _), _ = cv2.getTextSize(title_txt, _hfont, title_scale, 2)

            # ── [2] After title: Session elapsed time ────────────────────────────────
            elapsed    = int(time.time() - self._start_time)
            elapsed_txt = f"Time: {elapsed // 60:02d}:{elapsed % 60:02d}"
            elapsed_x  = 15 + title_w + _margin
            cv2.putText(frame, elapsed_txt, (elapsed_x, _hY), _hfont, 0.48, (180, 180, 180), 1)
            (elapsed_w, _), _ = cv2.getTextSize(elapsed_txt, _hfont, 0.48, 1)

            # ── [3] After elapsed: Live real-time wall clock (Cyan) ──────────────────
            clock_txt = f"Clock: {datetime.now().strftime('%H:%M:%S')}"
            clock_x   = elapsed_x + elapsed_w + _margin
            cv2.putText(frame, clock_txt, (clock_x, _hY), _hfont, 0.48, (0, 220, 220), 1)
            (clock_w, _), _ = cv2.getTextSize(clock_txt, _hfont, 0.48, 1)

            # ── [4] After clock: Mic-page & alert counters ───────────────────────────
            total_mics  = self._num_mics
            total_pages = max(1, (total_mics + 5) // 6)
            page_txt    = (f"Mics: {total_mics} "
                           f"(Page {self.current_mic_page + 1}/{total_pages}) "
                           f"| Alerts: {len(self._alerts)}")
            page_x = clock_x + clock_w + _margin
            cv2.putText(frame, page_txt, (page_x, _hY), _hfont, 0.48, (200, 200, 200), 1)
            (page_w, _), _ = cv2.getTextSize(page_txt, _hfont, 0.48, 1)

            # ── [5] FAR-RIGHT: Health badge — right-aligned, anchored from edge ──────
            health_text  = "HEALTH: OK"
            health_color = (0, 220, 0)
            if hasattr(self, "pipeline") and self.pipeline is not None:
                h_state  = self.pipeline._health_state
                beam_sz  = self.pipeline._keyword_detector._beam_size
                if h_state == "CRITICAL":
                    health_text  = f"HEALTH: CRIT (b={beam_sz})"
                    health_color = (0, 60, 255)
                else:
                    health_text  = f"HEALTH: OK (b={beam_sz})"
                    health_color = (0, 220, 0)
            (health_w, health_h), _ = cv2.getTextSize(health_text, _hfont, 0.5, 2)
            health_x = w - health_w - 12  # 12px right-edge margin
            # Draw a subtle pill background behind the badge for contrast
            badge_bg_color = (20, 60, 20) if "OK" in health_text else (60, 10, 10)
            cv2.rectangle(frame,
                          (health_x - 6, _hY - health_h - 4),
                          (health_x + health_w + 6, _hY + 6),
                          badge_bg_color, -1)
            cv2.putText(frame, health_text, (health_x, _hY), _hfont, 0.5, health_color, 2)

            # Left Column (Microphones)
            bar_y = 100
            max_e = max(self._energy_profile) if self._energy_profile else 1.0
            max_e = max(max_e, 0.001)
            
            self._button_rects.clear()

            # Determine which mics to render based on page and alert priority bubble-up
            all_mics = list(range(self._num_mics))
            now = time.time()
            alert_mics = [m for m in all_mics if now - self._last_alert_time_per_mic.get(m, 0.0) < 5.0]
            
            start_idx = self.current_mic_page * 6
            end_idx = min(self._num_mics, start_idx + 6)
            page_mics = all_mics[start_idx:end_idx]
            
            mics_to_render = []
            for am in alert_mics:
                if am not in mics_to_render:
                    mics_to_render.append(am)
            for pm in page_mics:
                if pm not in mics_to_render:
                    mics_to_render.append(pm)
            mics_to_render = mics_to_render[:6]

            for i in mics_to_render:
                energy = self._energy_profile[i] if i < len(self._energy_profile) else 0.0
                is_local_active = (i in self._active_mics)
                is_in_alert = (now - self._last_alert_time_per_mic.get(i, 0.0) < 5.0)

                # Bar background
                cv2.rectangle(frame, (130, bar_y), (360, bar_y + 25), (50, 50, 50), -1)
                
                # Bar fill
                norm = min(1.0, energy / max_e) if max_e > 0.01 else 0.0
                fill_w = int(norm * 230)
                
                if is_in_alert:
                    color = (0, 0, 255) # Red alert
                elif is_local_active:
                    color = (0, 165, 255) # Orange local active
                else:
                    color = (0, 255, 0) # Green default
                
                if fill_w > 0:
                    cv2.rectangle(frame, (130, bar_y), (130 + fill_w, bar_y + 25), color, -1)
                
                # Dynamic Threshold Tick Marks
                threshold_val = 0.05
                if hasattr(self, "pipeline") and self.pipeline is not None:
                    threshold_val = self.pipeline._keyword_detector.get_vad_threshold(i)
                tick_x = 130 + int(threshold_val * 230)
                tick_x = max(130, min(360, tick_x))
                cv2.line(frame, (tick_x, bar_y), (tick_x, bar_y + 25), (0, 255, 255), 2)
                cv2.putText(frame, f"T={threshold_val:.2f}", (tick_x - 18, bar_y + 37),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.32, (0, 255, 255), 1)

                # Transient Suppression Alert
                transient_active = False
                if hasattr(self, "pipeline") and self.pipeline is not None:
                    last_time = self.pipeline._preprocessor._transient_detected_times.get(i, 0.0)
                    if time.time() - last_time < 1.5:
                        transient_active = True
                
                if transient_active:
                    cv2.putText(frame, "[TRANSIENT FILTERED]", (130, bar_y - 4),
                                cv2.FONT_HERSHEY_SIMPLEX, 0.4, (0, 0, 255), 1)
                elif is_in_alert:
                    cv2.putText(frame, "[ALERT FLASHING]", (130, bar_y - 4),
                                cv2.FONT_HERSHEY_SIMPLEX, 0.4, (0, 0, 255), 1)

                # Listen button
                btn_w, btn_h = 60, 25
                btn_x = 370
                btn_y = bar_y
                
                is_listening = (self._listen_mic_id == i)
                btn_color = (0, 0, 200) if is_listening else (100, 100, 100)
                cv2.rectangle(frame, (btn_x, btn_y), (btn_x + btn_w, btn_y + btn_h), btn_color, -1)
                
                text = "STOP" if is_listening else "LISTEN"
                cv2.putText(frame, text, (btn_x + 5, btn_y + 18), 
                            cv2.FONT_HERSHEY_SIMPLEX, 0.4, (255, 255, 255), 1)
                
                self._button_rects.append((i, btn_x, btn_y, btn_w, btn_h))
                
                # Enhanced Microphone Labels
                label = f"mic{i}"
                if hasattr(self, "pipeline") and self.pipeline is not None:
                    label = self.pipeline._mic_registry.get(i, f"mic{i}")
                label_display = label.capitalize()
                if label_display == "Front":
                    label_display = "Front Row"
                elif label_display == "Back":
                    label_display = "Back Row"
                mic_text = f"Mic {i} ({label_display})"

                cv2.putText(frame, mic_text, (10, bar_y + 18), 
                            cv2.FONT_HERSHEY_SIMPLEX, 0.45, (255, 255, 255), 1)
                cv2.putText(frame, f"{energy:.3f}", (140, bar_y + 18), 
                            cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 0) if fill_w > 40 else (255, 255, 255), 1)
                
                bar_y += 65

            # Classification Status (Left Column bottom)
            status_y = 510
            cv2.putText(frame, "STATUS:", (15, status_y), cv2.FONT_HERSHEY_SIMPLEX, 0.65, (200, 200, 200), 2)
            
            cls_color = (255, 255, 255)
            if self._last_classification == "LOCAL":
                cls_color = (0, 165, 255)
            elif self._last_classification == "GLOBAL":
                cls_color = (255, 200, 0)
                
            active_str = f"(Mics: {[m for m in self._active_mics]})" if self._active_mics else ""
            cv2.putText(frame, f"{self._last_classification} {active_str}", (110, status_y), 
                        cv2.FONT_HERSHEY_SIMPLEX, 0.65, cls_color, 2)

            # Vertical Divider
            cv2.line(frame, (445, 75), (445, 585), (80, 80, 80), 1)

            # Right Column: Alerts Ticker
            ticker_x = 460
            cv2.rectangle(frame, (ticker_x, 75), (w - 10, 105), (40, 40, 40), -1)
            cv2.putText(frame, f"ALERTS TICKER ({len(self._alerts)})", (ticker_x + 10, 95), 
                        cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2)

            all_alerts = list(reversed(self._alerts))
            max_offset = max(0, len(all_alerts) - 4)
            self.alert_scroll_offset = max(0, min(max_offset, self.alert_scroll_offset))
            
            visible_alerts = all_alerts[self.alert_scroll_offset : self.alert_scroll_offset + 4]
            
            if self.alert_scroll_offset > 0:
                cv2.putText(frame, "▲ More Alerts (UP Key)", (ticker_x + 50, 120),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.45, (0, 255, 255), 1)
            
            ay = 140
            for alert in visible_alerts:
                # Card Background
                cv2.rectangle(frame, (ticker_x + 5, ay - 12), (w - 15, ay + 42), (25, 25, 25), -1)
                # Card Border
                cv2.rectangle(frame, (ticker_x + 5, ay - 12), (w - 15, ay + 42), (60, 60, 60), 1)
                
                txt = f"[{alert['time']}] Mic {alert['mic']}"
                cv2.putText(frame, txt, (ticker_x + 15, ay + 8), cv2.FONT_HERSHEY_SIMPLEX, 0.42, (255, 255, 255), 1)
                
                kw_txt = f"Kws: {alert['keywords']}"
                cv2.putText(frame, kw_txt, (ticker_x + 15, ay + 22), cv2.FONT_HERSHEY_SIMPLEX, 0.4, (0, 0, 255), 1)
                
                trans_txt = f"\"{alert['transcript'][:35]}...\"" if len(alert['transcript']) > 35 else f"\"{alert['transcript']}\""
                cv2.putText(frame, trans_txt, (ticker_x + 15, ay + 36), cv2.FONT_HERSHEY_SIMPLEX, 0.38, (180, 180, 180), 1)
                
                ay += 65

            if self.alert_scroll_offset + 4 < len(all_alerts):
                cv2.putText(frame, "▼ Older Alerts (DOWN Key)", (ticker_x + 50, ay + 10),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.45, (0, 255, 255), 1)

            return frame


# ── Main ──────────────────────────────────────────────────────────────

def list_audio_devices():
    """Print available audio devices."""
    try:
        import sounddevice as sd
        print("\nAvailable Audio Devices:")
        print("=" * 60)
        devices = sd.query_devices()
        for i, dev in enumerate(devices):
            inputs = dev["max_input_channels"]
            if inputs > 0:
                print(f"  [{i}] {dev['name']} ({inputs} input channels)")
        print("=" * 60)
    except ImportError:
        print("sounddevice not installed. Install with: pip install sounddevice")


def main():
    # Load settings FIRST so argparse defaults reflect the .env configuration.
    # CLI flags still override everything — settings are just the defaults.
    from thaqib.config import get_settings
    s = get_settings()

    parser = argparse.ArgumentParser(
        description="Thaqib Audio Cheating Detection Demo",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument(
        "--files",
        nargs="+",
        help="Audio file paths (one per mic). Example: --files mic1.mp3 mic2.m4a",
    )
    parser.add_argument(
        "--devices",
        nargs="+",
        type=int,
        help="Live mic device IDs. Example: --devices 1 3",
    )
    parser.add_argument(
        "--multi-channel",
        type=int,
        default=None,
        help="Multi-channel audio interface device ID",
    )
    parser.add_argument(
        "--channels",
        type=int,
        default=2,
        help="Number of channels for multi-channel device",
    )
    parser.add_argument(
        "--list-devices",
        action="store_true",
        help="List available audio input devices and exit",
    )
    parser.add_argument(
        "--sample-rate",
        type=int,
        default=s.audio_sample_rate,
        help="Sample rate in Hz [env: AUDIO_SAMPLE_RATE]",
    )
    parser.add_argument(
        "--chunk-ms",
        type=int,
        default=s.audio_chunk_ms,
        help="Analysis window in milliseconds [env: AUDIO_CHUNK_MS]",
    )
    parser.add_argument(
        "--whisper-model",
        type=str,
        default=s.audio_whisper_model,
        choices=["tiny", "base", "small", "medium"],
        help="Whisper model size [env: AUDIO_WHISPER_MODEL]",
    )
    parser.add_argument(
        "--language",
        type=str,
        default=s.audio_language,
        help="Expected language code [env: AUDIO_LANGUAGE]",
    )
    parser.add_argument(
        "--keywords",
        type=str,
        default=s.audio_keywords_file,
        help="Path to keywords JSON file [env: AUDIO_KEYWORDS_FILE]",
    )
    parser.add_argument(
        "--real-time",
        action="store_true",
        help="Simulate real-time playback for file mode",
    )
    parser.add_argument(
        "--cross-correlation",
        action="store_true",
        default=s.audio_cross_correlation,
        help="Enable cross-correlation validation [env: AUDIO_CROSS_CORRELATION]",
    )
    parser.add_argument(
        "--no-strict",
        action="store_true",
        default=False,
        help="Disable strict mode: only keyword matches trigger alerts "
             "[env: AUDIO_STRICT_MODE=false]",
    )
    parser.add_argument(
        "--sim-mics",
        type=int,
        default=0,
        help="Run in simulation mode with N mics",
    )

    args = parser.parse_args()

    if args.list_devices:
        list_audio_devices()
        return

    # Dynamically import cv2 for GUI dashboard
    global cv2
    try:
        import cv2 as _cv2
        cv2 = _cv2
    except ImportError:
        print("\nError: opencv-python (cv2) is required to run the GUI demo. Please install it.")
        sys.exit(1)

    # Resolve strict mode: --no-strict CLI flag overrides the .env setting
    strict_mode = s.audio_strict_mode and not args.no_strict

    # Create audio source
    if args.files:
        from thaqib.audio.source import FileAudioSource

        source = FileAudioSource(
            file_paths=args.files,
            sample_rate=args.sample_rate,
            chunk_ms=args.chunk_ms,
            real_time=args.real_time,
        )
        print(f"\nFile mode: {len(args.files)} mic files")
        for f in args.files:
            print(f"  - {f}")

    elif args.devices:
        from thaqib.audio.source import LiveAudioSource

        source = LiveAudioSource(
            device_ids=args.devices,
            sample_rate=args.sample_rate,
            chunk_ms=args.chunk_ms,
        )
        print(f"\nLive mode: devices {args.devices}")

    elif args.multi_channel is not None:
        from thaqib.audio.source import LiveAudioSource

        source = LiveAudioSource(
            multi_channel_device=args.multi_channel,
            channels=args.channels,
            sample_rate=args.sample_rate,
            chunk_ms=args.chunk_ms,
        )
        print(f"\nMulti-channel mode: device {args.multi_channel}, {args.channels} channels")

    elif args.sim_mics > 0:
        source = type('DummySource', (), {
            'num_mics': args.sim_mics,
            'sample_rate': args.sample_rate,
            'duration_ms': args.chunk_ms,
            'start': lambda: None,
            'stop': lambda: None,
            'get_chunk': lambda: None
        })()
        print(f"\nSimulation Mode: {args.sim_mics} microphones")

    else:
        parser.error("Specify --files, --devices, --multi-channel, --sim-mics, or --list-devices")
        return

    # ── Step 1: Print session info ────────────────────────────────────────────
    print("\n" + "=" * 80)
    print("  THAQIB AUDIO — SESSION STARTING")
    print("=" * 80)
    print("  [ ACTIVE CONFIGURATION ]")
    
    # Dump all audio-related settings from .env
    settings_dict = s.model_dump()
    audio_settings = {k: v for k, v in settings_dict.items() if k.startswith("audio_")}
    
    # Apply CLI overrides
    audio_settings["audio_whisper_model"] = args.whisper_model
    audio_settings["audio_language"] = args.language
    audio_settings["audio_keywords_file"] = args.keywords
    audio_settings["audio_chunk_ms"] = args.chunk_ms
    audio_settings["audio_sample_rate"] = args.sample_rate
    audio_settings["audio_cross_correlation"] = args.cross_correlation
    audio_settings["audio_strict_mode"] = strict_mode
    
    # Print formatted settings
    max_key_len = max(len(k) for k in audio_settings.keys())
    for k, v in sorted(audio_settings.items()):
        print(f"  {k:<{max_key_len}} : {v}")
    
    print("=" * 80)

    # ── Step 2: Create dashboard and pipeline (no models loaded yet) ─────────
    dashboard = AudioDashboard(num_mics=source.num_mics)

    if args.sim_mics > 0:
        class MockDetector:
            def __init__(self):
                self._beam_size = 3
            def get_vad_threshold(self, mic_id):
                return 0.15 + 0.05 * np.sin(time.time() * 0.5 + mic_id)

        class MockPreprocessor:
            def __init__(self):
                self._transient_detected_times = {}

        class MockPipeline:
            def __init__(self, num_mics):
                self._health_state = "NORMAL"
                self._keyword_detector = MockDetector()
                self._preprocessor = MockPreprocessor()
                self._mic_registry = {i: f"Zone {chr(65 + i // 4)}{i % 4 + 1}" for i in range(num_mics)}
                self._is_running = True
                self.alerts = []
                self.stats = {
                    "chunks_processed": 0,
                    "silent_chunks": 0,
                    "global_chunks": 0,
                    "local_chunks": 0,
                    "speech_detected": 0,
                    "alerts_triggered": 0,
                    "dropped_chunks": 0,
                    "two_pass_rescored": 0,
                }
            def start(self):
                self._is_running = True
            def stop(self):
                self._is_running = False

        pipeline = MockPipeline(args.sim_mics)
        dashboard.pipeline = pipeline

        # Start simulated background stream worker
        def sim_worker():
            import random
            active_alert_mic = -1
            alert_start_time = 0
            
            while pipeline._is_running:
                time.sleep(0.25)
                
                # Fluctuate health state
                cycle = int(time.time() // 15) % 2
                if cycle == 1:
                    pipeline._health_state = "CRITICAL"
                    pipeline._keyword_detector._beam_size = 1
                else:
                    pipeline._health_state = "NORMAL"
                    pipeline._keyword_detector._beam_size = 3

                # Check alert state timeout
                if active_alert_mic != -1 and time.time() - alert_start_time > 5.0:
                    active_alert_mic = -1
                    
                # Randomly trigger new alerts
                if active_alert_mic == -1 and random.random() < 0.05:
                    active_alert_mic = random.randint(0, args.sim_mics - 1)
                    alert_start_time = time.time()
                    alert = type('Alert', (), {
                        'mic_id': active_alert_mic,
                        'matched_keywords': [random.choice(['*HUMAN_SPEECH_DETECTED*', 'help me', 'question 3', 'cheat'])],
                        'transcript': f"Simulated whisper caught on zone {active_alert_mic}",
                        'sample_rate': 16000,
                        'confidence': random.uniform(0.6, 0.95)
                    })
                    dashboard.on_alert(alert)
                    
                # Randomly trigger transient suppression
                if random.random() < 0.05:
                    m = random.randint(0, args.sim_mics - 1)
                    pipeline._preprocessor._transient_detected_times[m] = time.time()
                    
                # Generate simulated energy profile
                energies = []
                for m in range(args.sim_mics):
                    base = 0.005 + 0.015 * np.abs(np.sin(time.time() * 0.8 + m))
                    if m == active_alert_mic:
                        base += random.uniform(0.15, 0.35)
                    energies.append(base)
                    
                class DummyClassification:
                    def __init__(self, engs, alert_m):
                        self.energy_profile = np.array(engs)
                        self.is_silent = False
                        self.is_global = False
                        self.is_local = True
                        self.active_mics = [alert_m] if alert_m != -1 else []
                
                class DummyChunk:
                    def __init__(self, num_m):
                        self.mic_data = np.zeros((num_m, 4000))
                        self.sample_rate = 16000
                        self.duration_ms = 250
                        
                dashboard.update(DummyChunk(args.sim_mics), DummyClassification(energies, active_alert_mic))
                pipeline.stats["chunks_processed"] += 1
                
        threading.Thread(target=sim_worker, daemon=True).start()

    else:
        from thaqib.audio.pipeline import AudioPipeline

        pipeline = AudioPipeline(
            source=source,
            whisper_model=args.whisper_model,
            language=args.language,
            keywords_file=args.keywords,
            use_cross_correlation=args.cross_correlation,
            strict_mode=strict_mode,
            on_chunk=dashboard.update,
            on_alert=dashboard.on_alert,
        )
        dashboard.pipeline = pipeline

        # ── Step 3: Eagerly load all AI models BEFORE starting the pipeline ───────
        print("\n  [1/3] Loading Silero VAD model...", end="", flush=True)
        t_start = time.time()
        pipeline._keyword_detector._ensure_vad_loaded()
        print(f" done ({time.time()-t_start:.1f}s)")

        if not pipeline._vad_only:
            print(f"  [2/3] Loading Whisper '{args.whisper_model}' model...", end="", flush=True)
            t_w = time.time()
            pipeline._keyword_detector._ensure_whisper_loaded()
            print(f" done ({time.time()-t_w:.1f}s)")
        else:
            print("  [2/3] VAD-only mode active — skipping Whisper model load.")

        print(f"  [3/3] Starting audio pipeline...", end="", flush=True)

        # ── Step 4: Start pipeline (models already in memory — zero cold start) ───
        pipeline.start()
        print(" ready!\n")

    window_name = "Thaqib Audio Monitor"
    cv2.namedWindow(window_name)
    cv2.setMouseCallback(window_name, dashboard.handle_click)

    try:
        # Main GUI Loop
        while pipeline._is_running:
            frame = dashboard.render_gui()
            cv2.imshow(window_name, frame)
            
            # Press Q or ESC to quit
            raw_key = cv2.waitKey(30)
            if raw_key != -1:
                key_code = raw_key & 0xFF
                if key_code == ord('q') or key_code == 27:
                    print("\nQuitting...")
                    pipeline.stop()
                    break
                
                # Check arrow keys
                is_up = (raw_key == 2490368 or raw_key == 65362 or (raw_key > 255 and key_code == 82))
                is_down = (raw_key == 2621440 or raw_key == 65364 or (raw_key > 255 and key_code == 84))
                is_left = (raw_key == 2424832 or raw_key == 65361 or (raw_key > 255 and key_code == 81))
                is_right = (raw_key == 2555904 or raw_key == 65363 or (raw_key > 255 and key_code == 83))
                
                if is_up:
                    dashboard.scroll_alerts(-1)
                elif is_down:
                    dashboard.scroll_alerts(1)
                elif is_left:
                    dashboard.change_mic_page(-1)
                elif is_right:
                    dashboard.change_mic_page(1)
                    
            # If window is closed by clicking X
            if cv2.getWindowProperty(window_name, cv2.WND_PROP_VISIBLE) < 1:
                print("\nWindow closed. Quitting...")
                pipeline.stop()
                break
                
    except KeyboardInterrupt:
        pipeline.stop()

    dashboard.stop()
    cv2.destroyAllWindows()
    alerts = pipeline.alerts

    # Final summary
    stats = pipeline.stats
    print("\n" + "=" * 60)
    print("  THAQIB AUDIO — SESSION COMPLETE")
    print("=" * 60)
    print(f"  Chunks processed:  {stats['chunks_processed']}")
    print(f"  Silent chunks:     {stats['silent_chunks']}")
    print(f"  Global chunks:     {stats['global_chunks']}")
    print(f"  Local chunks:      {stats['local_chunks']}")
    print(f"  Two-pass rescored: {stats.get('two_pass_rescored', 0)}  <- GLOBAL->LOCAL (noise-masked whispers recovered)")
    print(f"  Dropped chunks:    {stats.get('dropped_chunks', 0)}")
    print(f"  Speech detected:   {stats['speech_detected']}")
    print(f"  Alerts triggered:  {stats['alerts_triggered']}")
    print("-" * 60)

    if alerts:
        print(f"\n  CHEATING ALERTS ({len(alerts)}):")
        for i, alert in enumerate(alerts, 1):
            print(f"\n  Alert #{i}:")
            print(f"    Mic:       {alert.mic_id}")
            print(f"    Keywords:  {alert.matched_keywords}")
            print(f"    Transcript: \"{alert.transcript[:80]}\"")
            print(f"    Confidence: {alert.confidence:.3f}")
    else:
        print("\n  No cheating detected.")

    print("\n" + "=" * 60)


if __name__ == "__main__":
    main()
