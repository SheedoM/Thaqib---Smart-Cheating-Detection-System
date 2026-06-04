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

# Add src to path for development
sys.path.insert(0, str(__file__).replace("\\", "/").rsplit("/", 2)[0] + "/src")


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


import cv2
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
            
        # Terminal Log
        print(f"\n{'='*60}")
        print(f"🚨 AUDIO ALERT [{time_str}] - Mic {alert.mic_id}")
        print(f"🚨 Keywords: {alert.matched_keywords}")
        print(f"🚨 Transcript: {alert.transcript}")
        print(f"{'='*60}\n")

    def render_gui(self) -> np.ndarray:
        """Render the OpenCV GUI canvas."""
        with self._lock:
            # Create a dark canvas
            h, w = 600, 800
            frame = np.zeros((h, w, 3), dtype=np.uint8)
            
            # Header
            cv2.rectangle(frame, (0, 0), (w, 60), (40, 40, 40), -1)
            cv2.putText(frame, f"THAQIB AUDIO MONITOR", (20, 40),
                        cv2.FONT_HERSHEY_SIMPLEX, 1.0, (255, 255, 255), 2)
            
            elapsed = int(time.time() - self._start_time)
            cv2.putText(frame, f"Time: {elapsed//60:02d}:{elapsed%60:02d} | Chunks: {self._chunks_processed}",
                        (w - 350, 40), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (200, 200, 200), 2)

            # Energy Bars
            bar_y = 100
            max_e = max(self._energy_profile) if self._energy_profile else 1.0
            max_e = max(max_e, 0.001)
            
            self._button_rects.clear()

            for i, energy in enumerate(self._energy_profile):
                # Bar background
                cv2.rectangle(frame, (150, bar_y), (w - 150, bar_y + 30), (50, 50, 50), -1)
                
                # Bar fill
                norm = min(1.0, energy / max_e) if max_e > 0.01 else 0.0
                fill_w = int(norm * (w - 300))
                
                color = (0, 255, 0) # Green default
                if i in self._active_mics:
                    color = (0, 165, 255) # Orange if active local
                
                if fill_w > 0:
                    cv2.rectangle(frame, (150, bar_y), (150 + fill_w, bar_y + 30), color, -1)
                
                # Listen button
                btn_w, btn_h = 80, 30
                btn_x = w - 120
                btn_y = bar_y
                
                is_listening = (self._listen_mic_id == i)
                btn_color = (0, 0, 200) if is_listening else (100, 100, 100)
                cv2.rectangle(frame, (btn_x, btn_y), (btn_x + btn_w, btn_y + btn_h), btn_color, -1)
                
                text = "STOP" if is_listening else "LISTEN"
                cv2.putText(frame, text, (btn_x + 10, btn_y + 22), 
                            cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2)
                
                self._button_rects.append((i, btn_x, btn_y, btn_w, btn_h))
                
                # Text
                cv2.putText(frame, f"Mic {i}", (20, bar_y + 22), 
                            cv2.FONT_HERSHEY_SIMPLEX, 0.8, (255, 255, 255), 2)
                cv2.putText(frame, f"{energy:.3f}", (160, bar_y + 22), 
                            cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 0, 0) if fill_w > 40 else (255, 255, 255), 2)
                
                bar_y += 50

            # Classification Status
            status_y = bar_y + 40
            cv2.putText(frame, "STATUS:", (20, status_y), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (200, 200, 200), 2)
            
            cls_color = (255, 255, 255)
            if self._last_classification == "LOCAL":
                cls_color = (0, 165, 255) # Orange
            elif self._last_classification == "GLOBAL":
                cls_color = (255, 200, 0) # Cyan-ish
                
            active_str = f"(Mics: {[m for m in self._active_mics]})" if self._active_mics else ""
            cv2.putText(frame, f"{self._last_classification} {active_str}", (150, status_y), 
                        cv2.FONT_HERSHEY_SIMPLEX, 0.8, cls_color, 2)

            # Alerts Section
            alerts_y = status_y + 60
            cv2.rectangle(frame, (0, alerts_y - 30), (w, alerts_y), (40, 40, 40), -1)
            cv2.putText(frame, f"RECENT ALERTS ({len(self._alerts)})", (20, alerts_y - 8), 
                        cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)
            
            ay = alerts_y + 30
            for alert in self._alerts[-4:]: # Show last 4 alerts
                txt = f"[{alert['time']}] Mic {alert['mic']}: {alert['keywords']}"
                cv2.putText(frame, txt, (20, ay), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 0, 255), 2)
                ay += 30
                trans_txt = f"\"{alert['transcript'][:80]}\""
                cv2.putText(frame, trans_txt, (40, ay), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (200, 200, 200), 1)
                ay += 35

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

    args = parser.parse_args()

    if args.list_devices:
        list_audio_devices()
        return

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

    else:
        parser.error("Specify --files, --devices, --multi-channel, or --list-devices")
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
    from thaqib.audio.pipeline import AudioPipeline

    dashboard = AudioDashboard(num_mics=source.num_mics)

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

    # ── Step 3: Eagerly load all AI models BEFORE starting the pipeline ───────
    print("\n  [1/3] Loading Silero VAD model...", end="", flush=True)
    t_start = time.time()
    pipeline._keyword_detector._ensure_vad_loaded()
    print(f" done ({time.time()-t_start:.1f}s)")

    print(f"  [2/3] Loading Whisper '{args.whisper_model}' model...", end="", flush=True)
    t_w = time.time()
    pipeline._keyword_detector._ensure_whisper_loaded()
    print(f" done ({time.time()-t_w:.1f}s)")

    print(f"  [3/3] Starting audio pipeline...", end="", flush=True)

    # ── Step 4: Start pipeline (models already in memory — zero cold start) ───
    # load_models() inside start() returns instantly since both models are
    # already loaded — _ensure_*_loaded() is a no-op when model != None.
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
            key = cv2.waitKey(30) & 0xFF
            if key == ord('q') or key == 27:
                print("\nQuitting...")
                pipeline.stop()
                break
                
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
