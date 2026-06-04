# Audio Cheating Detection — Technical Documentation

> Part of the **Thaqib Smart Cheating Detection System**

## Overview

The audio subsystem provides **real-time, multi-microphone speech detection** for exam environments. It identifies cheating by detecting localized speech (whispers heard by only one microphone) vs. global sounds (heard by all microphones), then runs speech-to-text to extract keywords.

```
Microphones (any count)
    │
    ▼
┌─────────────────────────────────────────────────────────────┐
│                      AudioPipeline                          │
│                                                             │
│  ┌──────────────┐  ┌────────────────┐  ┌─────────────────┐ │
│  │ Preprocessor │  │  Discriminator │  │ KeywordDetector  │ │
│  │  HPF + NR    │  │  Global/Local  │  │ VAD → Whisper →  │ │
│  │  + Gain      │  │  Classifier    │  │ Keywords         │ │
│  └──────┬───────┘  └───────┬────────┘  └────────┬────────┘ │
│         │                  │                     │          │
│         ▼                  ▼                     ▼          │
│  ┌──────────────────────────────────────────────────────┐   │
│  │               Evidence Recorder                      │   │
│  │  Alerts (WAV + JSON)  |  Episodes (WAV + JSON)       │   │
│  └──────────────────────────────────────────────────────┘   │
│                                                             │
│  ┌──────────────────────────────────────────────────────┐   │
│  │            Session Recorder (full exam)              │   │
│  └──────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────┘
```

---

## Quick Start

```bash
# File mode — process pre-recorded audio (2 mics)
python scripts/demo_audio.py --files mic1.mp3 mic2.m4a --real-time

# Live mode — capture from USB microphones
python scripts/demo_audio.py --devices 1 3

# Live mode — multi-channel audio interface
python scripts/demo_audio.py --multi-channel 5 --channels 4

# List available audio devices
python scripts/demo_audio.py --list-devices
```

---

## Processing Pipeline

### 1. Audio Source (`source.py`)

Provides a unified interface for audio input:

| Source | Class | Use Case |
|--------|-------|----------|
| Pre-recorded files | `FileAudioSource` | Testing, development, re-analysis |
| USB microphones | `LiveAudioSource` | Production — one device per mic |
| Multi-channel interface | `LiveAudioSource` | Production — single device, N channels |

Both produce identical `AudioChunk` objects (shape: `n_mics × n_samples`).

### 2. Audio Preprocessor (`preprocessor.py`)

Three adaptive stages clean each audio chunk **before** VAD and Whisper:

| Stage | What it does | Settings |
|-------|-------------|----------|
| **High-pass filter** | Removes sub-bass rumble (HVAC, AC, desk vibrations). 4th-order Butterworth. | `AUDIO_HPF_CUTOFF=100` |
| **Noise reduction** | Spectral subtraction using a learned room noise profile. Profile builds automatically from GLOBAL/SILENT chunks. | `AUDIO_NOISE_REDUCTION=true` |
| **Adaptive gain** | Normalizes RMS amplitude so VAD/Whisper receive consistent signal level regardless of mic sensitivity. | `AUDIO_ADAPTIVE_GAIN=true` |

### 3. Global/Local Discriminator (`discriminator.py`)

Classifies each chunk as **SILENT**, **GLOBAL**, or **LOCAL** based on energy distribution across microphones.

**2-mic mode** (most common):
1. Compute RMS energy per mic
2. Learn baseline energy ratio during calibration window (first 30 non-silent chunks)
3. Compute normalized ratio = `raw_ratio / baseline_ratio`
4. If `normalized_ratio >= 2.0x` → **LOCAL** (possible cheating)

**N-mic mode**:
- Normalize energy relative to loudest mic
- If ≥ 60% of mics heard the sound → **GLOBAL**

**Periodic recalibration** adapts to changing room acoustics every 5 minutes.

### 4. Keyword Detector (`keyword_detector.py`)

Two-stage speech analysis on LOCAL chunks only:

| Stage | Engine | Purpose |
|-------|--------|---------|
| **VAD** | Silero VAD | Confirms the local sound is human speech (not a chair scraping, cough, etc.) |
| **STT + Match** | OpenAI Whisper | Transcribes speech → matches against `keywords.json` |

**Detection modes**:
- **STRICT** (`AUDIO_STRICT_MODE=true`): ANY detected speech = violation (silent exam)
- **KEYWORD** (`AUDIO_STRICT_MODE=false`): Only speech matching keywords.json is flagged

**Adaptive VAD threshold**: The system calibrates the VAD threshold to the room's noise floor automatically (`threshold = noise_floor_mean + 2σ`).

### 5. Threading Architecture

```
Main Loop (AudioPipeline thread)
   │
   ├── Reads chunks from AudioSource
   ├── Classifies: SILENT / GLOBAL / LOCAL
   ├── Feeds noise samples to Preprocessor
   ├── Streams audio to SessionRecorder
   └── Enqueues LOCAL chunks to inference queue
            │
            ▼
   VAD Worker Thread
   │  Runs Silero VAD on LOCAL chunks (fast: ~5ms)
   │  Accumulates speech buffers
   └── Pushes ready buffers to Whisper queue
            │
            ▼
   Whisper Worker Thread
      Runs Whisper STT + keyword matching (slow: ~0.5–4s)
      Creates AudioAlert objects
      Saves evidence (WAV + JSON)
```

This three-thread design ensures Whisper's latency never blocks real-time chunk processing.

---

## Evidence Output

### Per-Alert Evidence (`audio alerts/`)

Each cheating detection saves two files:

```
audio_alert_SYS10-30-00_OFFSET00h05m30s_front.wav   ← audio clip (pre + event + post)
audio_alert_SYS10-30-00_OFFSET00h05m30s_front.json  ← metadata
```

**JSON metadata includes**: timestamp, mic label, transcript, matched keywords, Whisper confidence, discriminator forensics (baseline ratio, raw ratio, normalized ratio), SHA-256 hash of the WAV file.

### Sustained Episode Evidence (`audio alerts/`)

When cheating is sustained for ≥ `AUDIO_EPISODE_MIN_SEC` seconds:

```
episode_front_2026-05-10_10-30-00.wav   ← full episode audio (first to last alert)
episode_front_2026-05-10_10-30-00.json  ← metadata (duration, all keywords, all transcripts)
```

**Episode lifecycle**:
```
t=0s   First alert           → Episode OPENED
t=3s   Sustained ≥ MIN_SEC   → Episode CONFIRMED
t=8s   No alerts for 5s      → Episode CLOSED → full WAV + JSON saved
```

If cheating lasts < `AUDIO_EPISODE_MIN_SEC`, the episode is discarded as noise.

### Session Recording (`sessions/`)

Records **all** incoming audio for the entire exam:

```
sessions/
  session_2026-05-10_10-30-00/
    session_mic0.wav              ← full exam audio from mic 0
    session_mic1.wav              ← full exam audio from mic 1
    session_manifest.json         ← metadata (duration, file sizes)
```

Enables post-exam forensic review and offline re-analysis with different thresholds.

---

## Microphone Registry

Supports **any number of microphones** with **any label format** (IPs, names, seat numbers, UUIDs).

### Configuration (`.env`)

```env
# Format 1 — comma list (index = order)
AUDIO_MIC_NAMES=192.168.1.10,192.168.1.11,192.168.1.12

# Format 2 — JSON array
AUDIO_MIC_NAMES=["192.168.1.10","192.168.1.11"]

# Format 3 — JSON dict (explicit mapping, non-sequential IDs)
AUDIO_MIC_NAMES={"0":"192.168.1.10","5":"door_cam","99":"hall"}

# Leave empty → default labels: mic0, mic1, mic2, ...
AUDIO_MIC_NAMES=
```

### Filename Sanitization

Labels containing special characters (dots, colons, brackets) are automatically sanitized for filenames while preserving the original label in logs and JSON:

| Label | Filename | JSON `mic_name` |
|-------|----------|-----------------|
| `192.168.1.10` | `..._192_168_1_10.wav` | `"192.168.1.10"` |
| `[2001:db8::1]` | `..._2001_db8__1.wav` | `"[2001:db8::1]"` |
| `front cam #2` | `..._front_cam_2.wav` | `"front cam #2"` |
| `front` | `..._front.wav` | `"front"` |

---

## Configuration Reference

All settings are loaded from `.env` (environment variables). CLI flags override `.env` values.

### Core

| Variable | Default | Description |
|----------|---------|-------------|
| `AUDIO_WHISPER_MODEL` | `tiny` | Whisper model size (`tiny`, `base`, `small`, `medium`) |
| `AUDIO_LANGUAGE` | `ar` | BCP-47 language code for Whisper |
| `AUDIO_KEYWORDS_FILE` | `keywords.json` | Cheating keywords JSON file |
| `AUDIO_STRICT_MODE` | `true` | `true` = any speech is cheating; `false` = keywords only |
| `AUDIO_OUTPUT_DIR` | `audio alerts` | Evidence output directory |

### Signal Processing

| Variable | Default | Description |
|----------|---------|-------------|
| `AUDIO_SAMPLE_RATE` | `16000` | Sample rate (Hz). Must be 16000 for Silero + Whisper. |
| `AUDIO_CHUNK_MS` | `500` | Analysis window (ms) |
| `AUDIO_SILENCE_THRESHOLD` | `0.01` | RMS below this = silence |
| `AUDIO_HPF_CUTOFF` | `100` | High-pass filter cutoff (Hz). 0 = disabled. |
| `AUDIO_NOISE_REDUCTION` | `true` | Enable spectral noise reduction |
| `AUDIO_NOISE_REDUCTION_STRENGTH` | `0.75` | Noise reduction aggressiveness (0.0–1.0) |
| `AUDIO_ADAPTIVE_GAIN` | `true` | Normalize RMS before VAD/Whisper |

### Discriminator

| Variable | Default | Description |
|----------|---------|-------------|
| `AUDIO_GLOBAL_RATIO` | `0.3` | Energy fraction to count as "heard" (N-mic mode) |
| `AUDIO_GLOBAL_FRACTION` | `0.6` | Fraction of mics for GLOBAL classification |
| `AUDIO_CALIBRATION_CHUNKS` | `30` | Non-silent chunks for baseline learning (0 = disable) |
| `AUDIO_LOCAL_RATIO_MULTIPLIER` | `2.0` | Normalized ratio threshold for LOCAL |
| `AUDIO_RECALIBRATION_INTERVAL_SEC` | `300` | Seconds between periodic recalibrations |

### VAD & Whisper

| Variable | Default | Description |
|----------|---------|-------------|
| `AUDIO_VAD_THRESHOLD` | `0.5` | Initial VAD threshold (overridden by adaptive) |
| `AUDIO_ADAPTIVE_VAD` | `true` | Auto-calibrate VAD threshold to room noise |
| `AUDIO_VAD_CALIBRATION_CHUNKS` | `50` | Chunks per adaptive calibration cycle |
| `AUDIO_SPEECH_BUFFER_SEC` | `2.5` | Seconds of speech to accumulate before Whisper |
| `AUDIO_SPEECH_GAP_MAX` | `2` | Non-speech chunks before buffer reset |
| `AUDIO_WHISPER_BEAM_SIZE` | `1` | Whisper beam size (1 = greedy, 5 = accurate) |
| `AUDIO_DEVICE` | `auto` | Compute device: `auto`, `cuda`, `cpu` |
| `AUDIO_COMPUTE_TYPE` | `auto` | Precision: `auto`, `float16`, `int8`, etc. |

### Evidence

| Variable | Default | Description |
|----------|---------|-------------|
| `AUDIO_CLIP_SEC_BEFORE` | `2.0` | Seconds of audio before alert in clip |
| `AUDIO_CLIP_SEC_AFTER` | `2.0` | Seconds of audio after alert in clip |
| `AUDIO_HISTORY_CHUNKS` | `20` | Rolling history depth for pre-event buffer |
| `AUDIO_INFERENCE_QUEUE_SIZE` | `10` | Max LOCAL chunks queued for inference |
| `AUDIO_CROSS_CORRELATION` | `false` | Extra validation for LOCAL classification |
| `AUDIO_SESSION_RECORDING` | `true` | Record full session audio |
| `AUDIO_SESSIONS_DIR` | `sessions` | Session recording output directory |
| `AUDIO_EPISODE_RECORDING` | `true` | Track sustained cheating episodes |
| `AUDIO_EPISODE_MIN_SEC` | `3.0` | Min duration to confirm episode |
| `AUDIO_EPISODE_GRACE_SEC` | `5.0` | Wait time before closing episode |
| `AUDIO_MIC_NAMES` | `""` | Mic labels (see Microphone Registry above) |

---

## Module Reference

```
src/thaqib/audio/
├── __init__.py          # Package exports: AudioChunk, AudioAlert, AudioPipeline
├── models.py            # Data classes: AudioChunk, SoundClassification, AudioAlert, CheatEpisode
├── pipeline.py          # Main orchestrator + EpisodeTracker
├── source.py            # FileAudioSource, LiveAudioSource
├── discriminator.py     # GlobalLocalDiscriminator (2-mic and N-mic modes)
├── keyword_detector.py  # KeywordDetector (Silero VAD + Whisper + fuzzy matching)
├── preprocessor.py      # AudioPreprocessor (HPF + noise reduction + gain)
├── evidence.py          # AudioEvidenceRecorder (WAV + JSON + SHA-256)
└── session_recorder.py  # SessionAudioRecorder (full-session WAV streaming)
```

---

## Dependencies

| Package | Purpose | Required? |
|---------|---------|-----------|
| `numpy` | Audio array processing | ✅ Required |
| `torch` | Silero VAD runtime | ✅ Required |
| `whisper` or `faster-whisper` | Speech-to-text | ✅ Required (either) |
| `pydub` + `ffmpeg` | Audio file loading (MP3, M4A) | ✅ Required for file mode |
| `sounddevice` | Live microphone capture | ✅ Required for live mode |
| `opencv-python` | GUI dashboard in demo | ✅ Required for demo |
| `scipy` | High-pass filter (Butterworth) | Optional (graceful fallback) |
| `noisereduce` | Spectral noise reduction | Optional (graceful fallback) |
| `librosa` | Audio loading fallback | Optional (uses pydub first) |
