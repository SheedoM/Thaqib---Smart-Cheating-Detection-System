"""
╔══════════════════════════════════════════════════════════════╗
║        نظام كشف الغش الصوتي في لجان الامتحانات              ║
║        Exam Cheat Detection System  —  Pro Edition v2        ║
║                                                              ║
║  الاستخدام:                                                  ║
║    python cheat_detector.py collect   ← جمع سامبلز           ║
║    python cheat_detector.py train     ← تدريب الموديل        ║
║    python cheat_detector.py run       ← تشغيل الكشف          ║
║    python cheat_detector.py gui       ← واجهة رسومية         ║
║    python cheat_detector.py report    ← تقرير الجلسة         ║
║    python cheat_detector.py load_dir  ← تحميل ملفات wav      ║
╚══════════════════════════════════════════════════════════════╝

التغييرات في v2:
  ✅  اختيار الميكروفون (--mic / قائمة في GUI)
  ✅  تنبيه صوتي عند الغش  (winsound على Windows / beep عام)
  ✅  تصدير تقرير HTML + CSV
  ✅  SMOTE لمعالجة imbalanced data
  ✅  class_weight في كل الموديلات
  ✅  تحقق من duplicates في load_dir
  ✅  validation تفصيلي على الـ features
  ✅  واجهة رسومية tkinter
"""

import sys
import os
import io
import csv
import json
import time
import queue
import logging
import hashlib
import platform
import threading
import argparse
from pathlib import Path
from datetime import datetime
from dataclasses import dataclass, field, asdict
from typing import Optional, List

import numpy as np
import sounddevice as sd
import soundfile as sf
import webrtcvad
import librosa
from scipy.signal import butter, lfilter

from sklearn.ensemble import RandomForestClassifier, GradientBoostingClassifier
from sklearn.svm import SVC
from sklearn.preprocessing import StandardScaler
from sklearn.model_selection import train_test_split, cross_val_score, StratifiedKFold
from sklearn.metrics import classification_report, confusion_matrix, roc_auc_score
from sklearn.pipeline import Pipeline
import joblib

# SMOTE — اختياري، لو مش مثبّت بيشتغل بدونه
try:
    from imblearn.over_sampling import SMOTE
    HAS_SMOTE = True
except ImportError:
    HAS_SMOTE = False


# ══════════════════════════════════════════════════════════════
#  AUDIO ALERT  —  تنبيه صوتي عند الغش
# ══════════════════════════════════════════════════════════════
def _beep_alert():
    """تشغيل صوت تنبيه — يعمل على Windows وLinux وMac."""
    try:
        if platform.system() == "Windows":
            import winsound
            for _ in range(3):
                winsound.Beep(1000, 300)
                time.sleep(0.1)
        elif platform.system() == "Darwin":
            os.system("afplay /System/Library/Sounds/Ping.aiff 2>/dev/null")
        else:
            # Linux — بيستخدم print('\a') أو paplay
            for _ in range(3):
                print("\a", end="", flush=True)
                time.sleep(0.2)
    except Exception:
        pass  # لو فشل التنبيه مش مشكلة


# ══════════════════════════════════════════════════════════════
#  MIC UTILITIES  —  اختيار الميكروفون
# ══════════════════════════════════════════════════════════════
def list_microphones() -> List[dict]:
    """إرجاع قائمة بكل الميكروفونات المتاحة."""
    devices = sd.query_devices()
    mics = []
    for i, d in enumerate(devices):
        if d["max_input_channels"] > 0:
            mics.append({"index": i, "name": d["name"], "channels": d["max_input_channels"]})
    return mics


def print_microphones():
    mics = list_microphones()
    print("\n🎤 الميكروفونات المتاحة:")
    print("  " + "─" * 50)
    for m in mics:
        default_mark = " ← (الافتراضي)" if m["index"] == sd.default.device[0] else ""
        print(f"  [{m['index']:2d}]  {m['name']}{default_mark}")
    print()
    return mics


# ══════════════════════════════════════════════════════════════
#  CONFIG
# ══════════════════════════════════════════════════════════════
@dataclass
class Config:
    # ── صوت ──────────────────────────────────────────────────
    samplerate:      int   = 16000
    frame_duration:  float = 0.03
    channels:        int   = 1
    silence_limit:   float = 1.0
    calib_time:      float = 3.0
    min_duration:    float = 0.3
    mic_index:       int   = -1          # -1 = default

    # ── حساسية ───────────────────────────────────────────────
    sensitivity:     int   = 5

    # ── ملفات ─────────────────────────────────────────────────
    data_dir:        str   = "training_data"
    model_path:      str   = "cheat_model.pkl"
    scaler_path:     str   = "cheat_scaler.pkl"
    log_dir:         str   = "logs"
    detections_dir:  str   = "detections"
    report_dir:      str   = "reports"

    # ── تصنيفات ───────────────────────────────────────────────
    cheat_label:     int   = 1

    # ── features ──────────────────────────────────────────────
    n_mfcc:          int   = 13
    bandpass_low:    int   = 80
    bandpass_high:   int   = 4000

    # ── تنبيه صوتي ────────────────────────────────────────────
    audio_alert:     bool  = True

    @property
    def frame_size(self) -> int:
        return int(self.samplerate * self.frame_duration)

    @property
    def noise_multiplier(self) -> float:
        s = max(1, min(10, self.sensitivity))
        return 1.5 + (s - 1) * 0.5

    @property
    def min_confidence(self) -> float:
        s = max(1, min(10, self.sensitivity))
        return 0.50 + (s - 1) * 0.04

    @property
    def cheat_min_secs(self) -> float:
        s = max(1, min(10, self.sensitivity))
        return 0.3 + (s - 1) * 0.1

    @property
    def effective_mic(self):
        return None if self.mic_index < 0 else self.mic_index

    def save(self, path: str = "config.json"):
        with open(path, "w", encoding="utf-8") as f:
            json.dump(asdict(self), f, ensure_ascii=False, indent=2)

    @classmethod
    def load(cls, path: str = "config.json") -> "Config":
        if not os.path.exists(path):
            return cls()
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        obj = cls()
        for k, v in data.items():
            if hasattr(obj, k):
                setattr(obj, k, v)
        return obj


CFG = Config.load()


# ══════════════════════════════════════════════════════════════
#  LOGGING
# ══════════════════════════════════════════════════════════════
os.makedirs(CFG.log_dir, exist_ok=True)
_log_file = os.path.join(
    CFG.log_dir,
    f"exam_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"
)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
    handlers=[
        logging.FileHandler(_log_file, encoding="utf-8"),
        logging.StreamHandler(sys.stdout),
    ],
)
logger = logging.getLogger("CheatDetector")


# ══════════════════════════════════════════════════════════════
#  DETECTION EVENT
# ══════════════════════════════════════════════════════════════
@dataclass
class DetectionEvent:
    event_id:   int
    timestamp:  str
    label:      str
    confidence: float
    duration:   float
    is_cheat:   bool
    audio_file: Optional[str] = None


# ══════════════════════════════════════════════════════════════
#  AUDIO UTILITIES
# ══════════════════════════════════════════════════════════════
_audio_queue: queue.Queue = queue.Queue()


def _audio_callback(indata, frames, time_info, status):
    if status:
        logger.warning(f"Stream status: {status}")
    _audio_queue.put(indata.copy())


def _butter_bandpass(lowcut=None, highcut=None, order=4):
    lowcut  = lowcut  or CFG.bandpass_low
    highcut = highcut or CFG.bandpass_high
    nyq = 0.5 * CFG.samplerate
    return butter(order, [lowcut / nyq, highcut / nyq], btype="band")


_BP_B, _BP_A = _butter_bandpass()


def bandpass_filter(data: np.ndarray) -> np.ndarray:
    return lfilter(_BP_B, _BP_A, data)


def frame_to_bytes(frame: np.ndarray) -> bytes:
    return (frame * 32767).astype(np.int16).tobytes()


def _calibrate_noise(vad_obj) -> float:
    samples = []
    with sd.InputStream(
        callback=_audio_callback,
        channels=CFG.channels,
        samplerate=CFG.samplerate,
        blocksize=CFG.frame_size,
        device=CFG.effective_mic,
    ):
        start = time.time()
        while time.time() - start < CFG.calib_time:
            frame = _audio_queue.get()
            samples.append(float(np.mean(frame ** 2)))

    base = float(np.mean(samples))
    threshold = base * CFG.noise_multiplier
    logger.info(
        f"Calibration | base={base:.7f} | ×{CFG.noise_multiplier:.1f} | thresh={threshold:.7f}"
    )
    return threshold


# ══════════════════════════════════════════════════════════════
#  FEATURE EXTRACTION  +  VALIDATION
# ══════════════════════════════════════════════════════════════
def extract_features(audio: np.ndarray, sr: int = None) -> Optional[np.ndarray]:
    """
    Feature vector (39 features):
      Energy(2) + ZCR(2) + Spectral(5) + MFCCs+Delta(26) + Pitch(3) + Tempo(1)
    """
    sr = sr or CFG.samplerate
    if len(audio) < 512:
        return None

    feats = []

    rms = np.sqrt(np.mean(audio ** 2))
    feats += [float(rms), float(np.std(audio ** 2))]

    zcr = librosa.feature.zero_crossing_rate(audio)
    feats += [float(np.mean(zcr)), float(np.std(zcr))]

    centroid  = librosa.feature.spectral_centroid(y=audio, sr=sr)
    bandwidth = librosa.feature.spectral_bandwidth(y=audio, sr=sr)
    rolloff   = librosa.feature.spectral_rolloff(y=audio, sr=sr)
    contrast  = librosa.feature.spectral_contrast(y=audio, sr=sr)
    flatness  = librosa.feature.spectral_flatness(y=audio)

    feats += [
        float(np.mean(centroid)),
        float(np.mean(bandwidth)),
        float(np.mean(rolloff)),
        float(np.mean(contrast)),
        float(np.mean(flatness)),
    ]

    mfccs = librosa.feature.mfcc(y=audio, sr=sr, n_mfcc=CFG.n_mfcc)
    delta = librosa.feature.delta(mfccs)
    feats += [float(np.mean(mfccs[i])) for i in range(CFG.n_mfcc)]
    feats += [float(np.mean(delta[i]))  for i in range(CFG.n_mfcc)]

    try:
        f0, voiced_flag, _ = librosa.pyin(
            audio,
            fmin=librosa.note_to_hz("C2"),
            fmax=librosa.note_to_hz("C7"),
            sr=sr,
        )
        voiced_ratio = float(np.mean(voiced_flag)) if voiced_flag is not None else 0.0
        valid_f0     = f0[voiced_flag] if (f0 is not None and np.any(voiced_flag)) else np.array([0.0])
        pitch_mean   = float(np.mean(valid_f0))
        pitch_std    = float(np.std(valid_f0))
    except Exception:
        voiced_ratio = pitch_mean = pitch_std = 0.0

    feats += [voiced_ratio, pitch_mean, pitch_std]

    try:
        tempo, _ = librosa.beat.beat_track(y=audio, sr=sr)
        feats.append(float(np.atleast_1d(tempo)[0]))
    except Exception:
        feats.append(0.0)

    arr = np.array(feats, dtype=np.float32)

    # ── validation ────────────────────────────────────────────
    if not np.all(np.isfinite(arr)):
        arr = np.nan_to_num(arr, nan=0.0, posinf=0.0, neginf=0.0)

    return arr


def validate_feature_matrix(X: np.ndarray, y: np.ndarray, label_map: dict):
    """طباعة إحصائيات تفصيلية عن الـ features قبل التدريب."""
    print("\n  ── Feature Validation ──")
    print(f"  الشكل  : {X.shape}")
    nan_count = int(np.sum(~np.isfinite(X)))
    print(f"  NaN/Inf: {nan_count}")
    print(f"  Min    : {X.min():.4f}")
    print(f"  Max    : {X.max():.4f}")
    print(f"  Mean   : {X.mean():.4f}")

    for name, val in label_map.items():
        mask = y == val
        print(f"  [{name}] {mask.sum()} سامبل | mean={X[mask].mean():.3f} | std={X[mask].std():.3f}")

    if nan_count > 0:
        print("  ⚠ يوجد قيم غير صالحة — تم تصحيحها تلقائياً")


# ══════════════════════════════════════════════════════════════
#  SAMPLE HELPERS
# ══════════════════════════════════════════════════════════════
def _audio_hash(audio_data: np.ndarray) -> str:
    return hashlib.md5(audio_data.tobytes()).hexdigest()[:8]


def _existing_hashes(label: str) -> set:
    """جمع هاشات الملفات الموجودة لتجنب التكرار."""
    folder = Path(CFG.data_dir) / label
    hashes = set()
    if folder.is_dir():
        for f in folder.glob("*.wav"):
            # الهاش في اسم الملف بعد _ الأخيرة
            parts = f.stem.split("_")
            if len(parts) >= 2:
                hashes.add(parts[-1])
    return hashes


def _save_sample(audio_data: np.ndarray, label: str) -> Optional[str]:
    folder = Path(CFG.data_dir) / label
    folder.mkdir(parents=True, exist_ok=True)

    uid = _audio_hash(audio_data)
    existing = _existing_hashes(label)

    if uid in existing:
        return None  # مكرر

    path = folder / f"{label}_{uid}.wav"
    sf.write(str(path), audio_data, CFG.samplerate)
    return str(path)


def _count_samples() -> dict:
    result = {}
    for label in ("cheating", "non_cheating"):
        d = Path(CFG.data_dir) / label
        result[label] = len(list(d.glob("*.wav"))) if d.is_dir() else 0
    return result


def _print_sample_stats():
    stats = _count_samples()
    print("\n📊 إحصائيات السامبلز:")
    print("  " + "─" * 40)
    for label, icon in (("cheating", "🚨"), ("non_cheating", "✅")):
        n   = stats[label]
        bar = "█" * min(n, 40)
        print(f"  {icon}  {label:<20s} : {n:4d}  {bar}")
    print("  " + "─" * 40)
    total = sum(stats.values())
    print(f"  {'المجموع':<22s} : {total:4d}\n")


def _get_label_input(audio_data: np.ndarray) -> Optional[str]:
    mapping = {"c": "cheating", "n": "non_cheating"}
    while True:
        choice = input("  اختيارك [c/n/s/x]: ").strip().lower()
        if choice == "x":
            return None
        if choice == "s":
            print("  ▶ تشغيل...")
            sd.play(audio_data, CFG.samplerate)
            sd.wait()
        elif choice in mapping:
            return mapping[choice]
        else:
            print("  ⚠ اختيار غير صحيح.")


# ══════════════════════════════════════════════════════════════
#  PHASE 1 — جمع السامبلز
# ══════════════════════════════════════════════════════════════
def collect_samples():
    Path(CFG.data_dir).mkdir(parents=True, exist_ok=True)
    vad = webrtcvad.Vad(2)

    print("\n" + "═" * 60)
    print("  📥  جمع السامبلز — Data Collection")
    print("═" * 60)

    if CFG.effective_mic is not None:
        print(f"  🎤 الميكروفون: [{CFG.mic_index}]")

    print("  [c]  Cheating 🚨   (كلام / همس / تواصل)")
    print("  [n]  Non-Cheating ✅ (ضوضاء / ورق / سعال)")
    print("  [s]  تشغيل المقطع")
    print("  [x]  تخطي")
    print("  Ctrl+C للإنهاء\n")

    print("🎤 معايرة الضوضاء... ابقَ ساكتاً...")
    noise_thresh = _calibrate_noise(vad)
    print(f"✅ Threshold: {noise_thresh:.7f}\n")

    _print_sample_stats()
    print("🎙  ابدأ الآن...\n")

    speech_buffer  = []
    speech_started = False
    silence_time   = 0.0
    speech_time    = 0.0

    with sd.InputStream(
        callback=_audio_callback,
        channels=CFG.channels,
        samplerate=CFG.samplerate,
        blocksize=CFG.frame_size,
        device=CFG.effective_mic,
    ):
        try:
            while True:
                frame  = _audio_queue.get().flatten()
                frame  = bandpass_filter(frame)
                energy = float(np.mean(frame ** 2))

                is_speech = False
                if energy > noise_thresh:
                    try:
                        is_speech = vad.is_speech(frame_to_bytes(frame), CFG.samplerate)
                    except Exception:
                        pass

                if is_speech:
                    if not speech_started:
                        speech_started = True
                        speech_buffer  = []
                        speech_time    = 0.0
                        silence_time   = 0.0
                        print("🔴 Recording...", end="\r")

                    speech_buffer.append(frame)
                    speech_time  += CFG.frame_duration
                    silence_time  = 0.0

                else:
                    if speech_started:
                        speech_buffer.append(frame)
                        silence_time += CFG.frame_duration

                        if silence_time > CFG.silence_limit:
                            speech_started = False

                            if speech_time < CFG.min_duration:
                                print("⚡ قصير جداً — تم تجاهله\n")
                                speech_buffer = []
                                continue

                            audio_data    = np.concatenate(speech_buffer)
                            speech_buffer = []

                            print(f"\n⏱  المدة: {speech_time:.2f}s")
                            label = _get_label_input(audio_data)

                            if label in ("cheating", "non_cheating"):
                                path = _save_sample(audio_data, label)
                                if path is None:
                                    print("  ⚠ سامبل مكرر — تم تجاهله\n")
                                else:
                                    icon = "🚨" if label == "cheating" else "✅"
                                    print(f"  {icon} تم الحفظ → {path}\n")
                            else:
                                print("  ⏭  تم التخطي\n")

                if len(speech_buffer) > CFG.samplerate * 30:
                    speech_buffer = speech_buffer[-CFG.samplerate * 5:]

        except KeyboardInterrupt:
            print("\n")
            _print_sample_stats()


# ══════════════════════════════════════════════════════════════
#  LOAD_DIR
# ══════════════════════════════════════════════════════════════
def load_from_directory():
    print("\n" + "═" * 60)
    print("  📂  تحميل من فولدر — Load from Directory")
    print("═" * 60)

    for label in ("cheating", "non_cheating"):
        src = Path(label)
        if not src.is_dir():
            print(f"  ⚠ فولدر '{label}' غير موجود — تم التخطي")
            continue

        files = list(src.glob("*.wav"))
        print(f"\n  📁 {label}: {len(files)} ملف")

        copied = skipped_dup = skipped_err = 0
        for wav_path in files:
            try:
                audio, sr = librosa.load(str(wav_path), sr=CFG.samplerate, mono=True)
                path = _save_sample(audio, label)
                if path is None:
                    skipped_dup += 1
                else:
                    copied += 1
            except Exception as e:
                logger.warning(f"Skipped {wav_path}: {e}")
                skipped_err += 1

        print(f"  ✅ نسخ: {copied} | مكرر: {skipped_dup} | خطأ: {skipped_err}")

    print()
    _print_sample_stats()


# ══════════════════════════════════════════════════════════════
#  PHASE 2 — تدريب الموديل
# ══════════════════════════════════════════════════════════════
def train_model():
    print("\n" + "═" * 60)
    print("  🧠  التدريب — Model Training")
    print("═" * 60)

    _print_sample_stats()

    X, y = [], []
    label_map = {"non_cheating": 0, "cheating": 1}
    skipped = 0

    for label_name, label_value in label_map.items():
        folder = Path(CFG.data_dir) / label_name
        if not folder.is_dir():
            continue

        files = list(folder.glob("*.wav"))
        print(f"  ⏳ Loading '{label_name}': {len(files)} سامبل...")

        for wav in files:
            try:
                audio, sr = librosa.load(str(wav), sr=CFG.samplerate, mono=True)
                feats = extract_features(audio, sr)
                if feats is not None:
                    X.append(feats)
                    y.append(label_value)
                else:
                    skipped += 1
                    logger.warning(f"Feature extraction returned None: {wav}")
            except Exception as e:
                logger.warning(f"Skipped {wav}: {e}")
                skipped += 1

    if skipped > 0:
        print(f"\n  ⚠ {skipped} سامبل تم تجاهلهم (قصيرة أو تالفة)")

    if len(X) < 10:
        print("\n❌ سامبلز غير كافية (10 على الأقل لكل كلاس).")
        return

    X = np.array(X)
    y = np.array(y)

    # ── Feature Validation ────────────────────────────────────
    validate_feature_matrix(X, y, label_map)

    # ── SMOTE لمعالجة imbalance ───────────────────────────────
    counts = {v: int(np.sum(y == v)) for v in [0, 1]}
    ratio  = min(counts.values()) / max(counts.values()) if max(counts.values()) > 0 else 1.0

    if ratio < 0.7:
        print(f"\n  ⚠ عدم توازن الكلاسات: {counts}")
        if HAS_SMOTE:
            print("  🔄 تطبيق SMOTE لتوازن البيانات...")
            try:
                sm = SMOTE(random_state=42, k_neighbors=min(5, min(counts.values()) - 1))
                X, y = sm.fit_resample(X, y)
                print(f"  ✅ بعد SMOTE: {dict(zip(['non_cheat','cheat'], np.bincount(y)))}")
            except Exception as e:
                print(f"  ⚠ SMOTE فشل ({e}) — سيستمر بدونه")
        else:
            print("  ℹ لتثبيت SMOTE: pip install imbalanced-learn")
            print("  ⚠ سيستمر بـ class_weight فقط")

    print(f"\n  Total samples    : {len(X)}")
    print(f"  Feature vector   : {X.shape[1]} features")
    print(f"  Cheating samples : {int(np.sum(y == 1))}")
    print(f"  Non-cheat samples: {int(np.sum(y == 0))}")

    # ── Candidate Models  (class_weight في الكل) ──────────────
    candidates = {
        "RandomForest": RandomForestClassifier(
            n_estimators=300,
            max_depth=20,
            min_samples_leaf=2,
            class_weight="balanced",
            random_state=42,
            n_jobs=-1,
        ),
        "GradientBoosting": GradientBoostingClassifier(
            n_estimators=200,
            max_depth=5,
            learning_rate=0.08,
            subsample=0.8,
            random_state=42,
            # GradientBoosting لا يدعم class_weight مباشرة
            # SMOTE أو sample_weight يتعامل معاه
        ),
        "SVM": SVC(
            kernel="rbf",
            C=10,
            gamma="scale",
            class_weight="balanced",
            probability=True,
            random_state=42,
        ),
    }

    # حساب sample_weight لـ GradientBoosting
    from sklearn.utils.class_weight import compute_sample_weight
    sample_weights = compute_sample_weight("balanced", y)

    scaler   = StandardScaler()
    X_scaled = scaler.fit_transform(X)
    cv       = StratifiedKFold(n_splits=5, shuffle=True, random_state=42)

    best_name  = ""
    best_score = 0.0
    best_model = None

    print("\n  ── Cross-Validation Results ──")
    for name, model in candidates.items():
        if name == "GradientBoosting":
            # يحتاج fit_params لـ sample_weight في CV
            from sklearn.model_selection import cross_validate
            cv_results = cross_validate(
                model, X_scaled, y, cv=cv,
                scoring="f1_weighted",
                fit_params={"sample_weight": sample_weights},
                n_jobs=-1,
            )
            scores_mean = cv_results["test_score"].mean()
            scores_std  = cv_results["test_score"].std()
        else:
            scores = cross_val_score(model, X_scaled, y, cv=cv, scoring="f1_weighted", n_jobs=-1)
            scores_mean = scores.mean()
            scores_std  = scores.std()

        print(f"  {name:<20s} F1 = {scores_mean:.3f} ± {scores_std:.3f}")
        if scores_mean > best_score:
            best_score = scores_mean
            best_model = model
            best_name  = name

    print(f"\n  ✅ أفضل موديل: {best_name}  (F1={best_score:.3f})")

    if best_score < 0.80:
        print("  ⚠ F1 < 0.80 — يُنصح بجمع سامبلز أكثر وتنوعاً قبل الاستخدام")

    X_train, X_test, y_train, y_test = train_test_split(
        X_scaled, y, test_size=0.2, random_state=42, stratify=y
    )

    if best_name == "GradientBoosting":
        sw_train = compute_sample_weight("balanced", y_train)
        best_model.fit(X_train, y_train, sample_weight=sw_train)
    else:
        best_model.fit(X_train, y_train)

    y_pred  = best_model.predict(X_test)
    y_proba = best_model.predict_proba(X_test)[:, 1]

    print("\n  ── Classification Report ──")
    print(classification_report(y_test, y_pred, target_names=["Non-Cheating", "Cheating"]))

    print("  ── Confusion Matrix ──")
    cm = confusion_matrix(y_test, y_pred)
    print(f"          Pred-0  Pred-1")
    print(f"  True-0:  {cm[0,0]:5d}   {cm[0,1]:5d}   (Non-Cheat)")
    print(f"  True-1:  {cm[1,0]:5d}   {cm[1,1]:5d}   (Cheat)")

    if len(np.unique(y_test)) > 1:
        print(f"\n  ROC-AUC: {roc_auc_score(y_test, y_proba):.3f}")

    pipeline = Pipeline([("scaler", scaler), ("model", best_model)])
    joblib.dump(pipeline, CFG.model_path)
    joblib.dump(scaler,   CFG.scaler_path)

    meta = {
        "model_name":    best_name,
        "f1_score":      best_score,
        "feature_count": X.shape[1],
        "n_mfcc":        CFG.n_mfcc,
        "trained_at":    datetime.now().isoformat(),
        "samples":       {"cheating": int(np.sum(y==1)), "non_cheating": int(np.sum(y==0))},
        "smote_used":    HAS_SMOTE and ratio < 0.7,
    }
    with open("model_meta.json", "w", encoding="utf-8") as f:
        json.dump(meta, f, ensure_ascii=False, indent=2)

    print(f"\n  💾 Model saved  → {CFG.model_path}")
    print(f"  💾 Meta saved   → model_meta.json")


# ══════════════════════════════════════════════════════════════
#  PHASE 3 — الكشف الفعلي
# ══════════════════════════════════════════════════════════════
def run_detection(gui_callback=None):
    """
    الكشف الفعلي.
    gui_callback: دالة تستقبل (DetectionEvent) من الـ GUI — اختيارية.
    """
    print("\n" + "═" * 60)
    print("  🎯  الكشف الفعلي — Live Detection")
    print("═" * 60)

    if not Path(CFG.model_path).exists():
        print(f"❌ الموديل غير موجود! شغّل: python cheat_detector.py train")
        return

    pipeline = joblib.load(CFG.model_path)

    meta = {}
    if Path("model_meta.json").exists():
        with open("model_meta.json", encoding="utf-8") as f:
            meta = json.load(f)

    print(f"  ✅ Loaded: {meta.get('model_name','?')}  F1={meta.get('f1_score',0):.3f}")
    if CFG.effective_mic is not None:
        print(f"  🎤 الميكروفون: [{CFG.mic_index}]")
    print(f"\n  ⚙️  Sensitivity     : {CFG.sensitivity}/10")
    print(f"  ⚙️  Noise multiplier : ×{CFG.noise_multiplier:.1f}")
    print(f"  ⚙️  Min confidence   : {CFG.min_confidence*100:.0f}%")
    print(f"  ⚙️  Min cheat dur.   : {CFG.cheat_min_secs:.1f}s")
    print(f"  🔔 Audio alert      : {'ON' if CFG.audio_alert else 'OFF'}")

    vad = webrtcvad.Vad(2)

    print("\n  🎤 معايرة الضوضاء... ابقَ ساكتاً...")
    noise_thresh = _calibrate_noise(vad)
    print(f"  ✅ Threshold: {noise_thresh:.7f}")
    print("  🎙  المراقبة بدأت...\n")
    print("  " + "─" * 56)

    Path(CFG.detections_dir).mkdir(parents=True, exist_ok=True)

    speech_buffer  = []
    speech_started = False
    silence_time   = 0.0
    speech_time    = 0.0
    event_id       = 0
    cheat_count    = 0
    events: List[DetectionEvent] = []

    def _classify(audio_data: np.ndarray):
        feats = extract_features(audio_data)
        if feats is None:
            return 0, 0.0
        proba = pipeline.predict_proba([feats])[0]
        pred  = int(np.argmax(proba))
        return pred, float(proba[pred])

    with sd.InputStream(
        callback=_audio_callback,
        channels=CFG.channels,
        samplerate=CFG.samplerate,
        blocksize=CFG.frame_size,
        device=CFG.effective_mic,
    ):
        try:
            while True:
                frame  = _audio_queue.get().flatten()
                frame  = bandpass_filter(frame)
                energy = float(np.mean(frame ** 2))

                is_speech = False
                if energy > noise_thresh:
                    try:
                        is_speech = vad.is_speech(frame_to_bytes(frame), CFG.samplerate)
                    except Exception:
                        pass

                if is_speech:
                    if not speech_started:
                        speech_started = True
                        speech_buffer  = []
                        speech_time    = 0.0
                        silence_time   = 0.0

                    speech_buffer.append(frame)
                    speech_time  += CFG.frame_duration
                    silence_time  = 0.0

                else:
                    if speech_started:
                        speech_buffer.append(frame)
                        silence_time += CFG.frame_duration

                        if silence_time > CFG.silence_limit:
                            speech_started = False
                            event_id += 1

                            if speech_time < CFG.min_duration:
                                speech_buffer = []
                                continue

                            audio_data    = np.concatenate(speech_buffer)
                            speech_buffer = []

                            pred, confidence = _classify(audio_data)
                            label_str = "Cheating 🚨" if pred == 1 else "Non-Cheating ✅"

                            is_cheat = (
                                pred == CFG.cheat_label
                                and confidence >= CFG.min_confidence
                                and speech_time >= CFG.cheat_min_secs
                            )

                            ts  = datetime.now().strftime("%H:%M:%S")
                            evt = DetectionEvent(
                                event_id   = event_id,
                                timestamp  = ts,
                                label      = label_str,
                                confidence = confidence,
                                duration   = speech_time,
                                is_cheat   = is_cheat,
                            )

                            flag = " ⚠️ CHEAT" if is_cheat else ""
                            print(
                                f"  [{ts}] #{event_id:04d} | {label_str:<20s} | "
                                f"Conf: {confidence*100:5.1f}% | "
                                f"Dur: {speech_time:.2f}s{flag}"
                            )
                            logger.info(
                                f"Event#{event_id} | {label_str} | "
                                f"conf={confidence:.3f} | dur={speech_time:.2f}s | cheat={is_cheat}"
                            )

                            if is_cheat:
                                cheat_count += 1
                                fname = os.path.join(
                                    CFG.detections_dir,
                                    f"cheat_{cheat_count:04d}_{ts.replace(':','-')}.wav",
                                )
                                sf.write(fname, audio_data, CFG.samplerate)
                                evt.audio_file = fname

                                print("\n  " + "🚨" * 28)
                                print(f"  ⚠️  CHEATING DETECTED  #{cheat_count}")
                                print(f"  الثقة      : {confidence*100:.1f}%")
                                print(f"  المدة      : {speech_time:.2f}s")
                                print(f"  ملف مسجّل  : {fname}")
                                print(f"  إجمالي الغش: {cheat_count}")
                                print("  " + "🚨" * 28 + "\n")

                                logger.warning(
                                    f"🚨 CHEAT #{cheat_count} | conf={confidence:.3f} | file={fname}"
                                )

                                # ── تنبيه صوتي ────────────────────────
                                if CFG.audio_alert:
                                    threading.Thread(target=_beep_alert, daemon=True).start()

                            events.append(evt)
                            if gui_callback:
                                gui_callback(evt)

                if len(speech_buffer) > CFG.samplerate * 30:
                    speech_buffer = speech_buffer[-CFG.samplerate * 5:]

        except KeyboardInterrupt:
            pass

    print(f"\n\n  ══ ملخص الجلسة ══")
    print(f"  إجمالي الأحداث : {event_id}")
    print(f"  حالات غش       : {cheat_count}")
    print(f"  سجل الجلسة     : {_log_file}")

    _save_session_report(events)
    return events


# ══════════════════════════════════════════════════════════════
#  REPORT  —  JSON + CSV + HTML
# ══════════════════════════════════════════════════════════════
def _save_session_report(events: list):
    Path(CFG.report_dir).mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    data = {
        "generated_at":  datetime.now().isoformat(),
        "total_events":  len(events),
        "cheat_events":  sum(1 for e in events if e.is_cheat),
        "sensitivity":   CFG.sensitivity,
        "events":        [asdict(e) for e in events],
    }

    # ── JSON ──────────────────────────────────────────────────
    json_path = os.path.join(CFG.report_dir, f"report_{stamp}.json")
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    # ── CSV ───────────────────────────────────────────────────
    csv_path = os.path.join(CFG.report_dir, f"report_{stamp}.csv")
    with open(csv_path, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.writer(f)
        writer.writerow(["event_id", "timestamp", "label", "confidence_%", "duration_s", "is_cheat", "audio_file"])
        for e in data["events"]:
            writer.writerow([
                e["event_id"],
                e["timestamp"],
                e["label"],
                f"{e['confidence']*100:.1f}",
                f"{e['duration']:.2f}",
                "YES" if e["is_cheat"] else "NO",
                e.get("audio_file", ""),
            ])

    # ── HTML ──────────────────────────────────────────────────
    html_path = os.path.join(CFG.report_dir, f"report_{stamp}.html")
    _write_html_report(data, html_path)

    print(f"  📄 JSON  → {json_path}")
    print(f"  📊 CSV   → {csv_path}")
    print(f"  🌐 HTML  → {html_path}")


def _write_html_report(data: dict, path: str):
    cheats = [e for e in data["events"] if e["is_cheat"]]
    rows   = ""
    for e in data["events"]:
        color = "#ffe5e5" if e["is_cheat"] else "#ffffff"
        flag  = " ⚠️" if e["is_cheat"] else ""
        rows += (
            f'<tr style="background:{color}">'
            f'<td>{e["event_id"]}</td>'
            f'<td>{e["timestamp"]}</td>'
            f'<td>{e["label"]}{flag}</td>'
            f'<td>{e["confidence"]*100:.1f}%</td>'
            f'<td>{e["duration"]:.2f}s</td>'
            f'<td>{"✅ YES" if e["is_cheat"] else "NO"}</td>'
            f'<td><small>{e.get("audio_file","—")}</small></td>'
            f'</tr>\n'
        )

    html = f"""<!DOCTYPE html>
<html lang="ar" dir="rtl">
<head>
<meta charset="UTF-8">
<title>تقرير كشف الغش — {data['generated_at'][:10]}</title>
<style>
  body  {{ font-family: Arial, sans-serif; margin: 30px; background: #f8f9fa; }}
  h1    {{ color: #c0392b; }}
  .box  {{ background: white; border-radius: 8px; padding: 20px;
            box-shadow: 0 2px 6px #0001; margin-bottom: 20px; }}
  .stat {{ display: inline-block; margin: 10px 20px 10px 0;
            font-size: 1.4em; font-weight: bold; }}
  .red  {{ color: #c0392b; }}
  .green{{ color: #27ae60; }}
  table {{ border-collapse: collapse; width: 100%; }}
  th    {{ background: #2c3e50; color: white; padding: 8px 12px; }}
  td    {{ padding: 7px 12px; border-bottom: 1px solid #eee; }}
  tr:hover {{ background: #f0f4ff !important; }}
</style>
</head>
<body>
<h1>🔍 تقرير نظام كشف الغش</h1>
<div class="box">
  <span class="stat">التاريخ: {data['generated_at'][:19]}</span>
  <span class="stat">الحساسية: {data['sensitivity']}/10</span><br>
  <span class="stat">إجمالي الأحداث: <b>{data['total_events']}</b></span>
  <span class="stat red">حالات الغش: <b>{data['cheat_events']}</b></span>
  <span class="stat green">عادي: <b>{data['total_events'] - data['cheat_events']}</b></span>
</div>
<div class="box">
<table>
<tr><th>#</th><th>الوقت</th><th>التصنيف</th><th>الثقة</th><th>المدة</th><th>غش؟</th><th>ملف الصوت</th></tr>
{rows}
</table>
</div>
</body></html>
"""
    with open(path, "w", encoding="utf-8") as f:
        f.write(html)


def show_report():
    reports = sorted(Path(CFG.report_dir).glob("report_*.json")) if Path(CFG.report_dir).is_dir() else []
    if not reports:
        print("❌ لا يوجد تقارير بعد. شغّل run أولاً.")
        return

    latest = reports[-1]
    with open(latest, encoding="utf-8") as f:
        data = json.load(f)

    print("\n" + "═" * 60)
    print(f"  📄  تقرير الجلسة — {latest.name}")
    print("═" * 60)
    print(f"  التاريخ          : {data['generated_at'][:19]}")
    print(f"  إجمالي الأحداث  : {data['total_events']}")
    print(f"  حالات غش        : {data['cheat_events']}")
    print(f"  الحساسية         : {data['sensitivity']}/10")

    cheats = [e for e in data["events"] if e["is_cheat"]]
    if cheats:
        print(f"\n  ── تفاصيل حالات الغش ({len(cheats)}) ──")
        for e in cheats:
            print(
                f"  [{e['timestamp']}] #{e['event_id']:04d} | "
                f"Conf: {e['confidence']*100:.1f}% | "
                f"Dur: {e['duration']:.2f}s"
                + (f" | 📁 {e['audio_file']}" if e.get("audio_file") else "")
            )
    print()


# ══════════════════════════════════════════════════════════════
#  GUI  —  tkinter
# ══════════════════════════════════════════════════════════════
def launch_gui():
    try:
        import tkinter as tk
        from tkinter import ttk, scrolledtext, messagebox
    except ImportError:
        print("❌ tkinter غير متاح في هذا البيئة.")
        return

    root = tk.Tk()
    root.title("🎯 نظام كشف الغش الصوتي  —  v2")
    root.geometry("900x650")
    root.configure(bg="#1e1e2e")
    root.resizable(True, True)

    # ── ألوان ─────────────────────────────────────────────────
    BG      = "#1e1e2e"
    CARD    = "#2a2a3e"
    ACCENT  = "#c0392b"
    GREEN   = "#27ae60"
    TEXT    = "#ececec"
    MUTED   = "#888"
    YELLOW  = "#f39c12"

    # ── متغيرات الحالة ────────────────────────────────────────
    is_running    = tk.BooleanVar(value=False)
    cheat_count   = tk.IntVar(value=0)
    event_count   = tk.IntVar(value=0)
    detect_thread = [None]

    # ══ Header ═══════════════════════════════════════════════
    header = tk.Frame(root, bg=ACCENT, pady=10)
    header.pack(fill="x")
    tk.Label(header, text="🎯  نظام كشف الغش الصوتي", font=("Arial", 16, "bold"),
             bg=ACCENT, fg="white").pack()
    tk.Label(header, text="Exam Cheat Detection System  —  Pro v2",
             font=("Arial", 9), bg=ACCENT, fg="#ffcccc").pack()

    # ══ Main Frame ════════════════════════════════════════════
    main_frame = tk.Frame(root, bg=BG)
    main_frame.pack(fill="both", expand=True, padx=12, pady=8)

    # ── Left Panel ─────────────────────────────────────────────
    left = tk.Frame(main_frame, bg=BG, width=260)
    left.pack(side="left", fill="y", padx=(0, 8))
    left.pack_propagate(False)

    def section(parent, title):
        f = tk.LabelFrame(parent, text=title, bg=CARD, fg=YELLOW,
                          font=("Arial", 9, "bold"), bd=1, relief="groove",
                          padx=8, pady=6)
        f.pack(fill="x", pady=(0, 8))
        return f

    # ─ Mic selector ───────────────────────────────────────────
    mic_frame = section(left, "🎤 الميكروفون")
    mics = list_microphones()
    mic_names = [f"[{m['index']}] {m['name'][:28]}" for m in mics]
    mic_var = tk.StringVar()
    if mic_names:
        default_idx = next((i for i, m in enumerate(mics) if m["index"] == sd.default.device[0]), 0)
        mic_var.set(mic_names[default_idx])
    mic_combo = ttk.Combobox(mic_frame, textvariable=mic_var, values=mic_names,
                              state="readonly", width=28)
    mic_combo.pack()

    def apply_mic(*_):
        sel = mic_var.get()
        if sel:
            idx = int(sel.split("]")[0].replace("[", "").strip())
            CFG.mic_index = idx

    mic_combo.bind("<<ComboboxSelected>>", apply_mic)

    # ─ Sensitivity ────────────────────────────────────────────
    sens_frame = section(left, "⚙️ الحساسية")
    sens_var = tk.IntVar(value=CFG.sensitivity)
    sens_label = tk.Label(sens_frame, text=f"{CFG.sensitivity}/10",
                          bg=CARD, fg=TEXT, font=("Arial", 11, "bold"))
    sens_label.pack()

    def on_sens(val):
        v = int(float(val))
        CFG.sensitivity = v
        sens_label.config(text=f"{v}/10")

    ttk.Scale(sens_frame, from_=1, to=10, orient="horizontal",
              variable=sens_var, command=on_sens).pack(fill="x")

    tk.Label(sens_frame, text="1=حساس جداً   10=صارم جداً",
             bg=CARD, fg=MUTED, font=("Arial", 7)).pack()

    # ─ Audio Alert ────────────────────────────────────────────
    alert_frame = section(left, "🔔 التنبيه الصوتي")
    alert_var = tk.BooleanVar(value=CFG.audio_alert)

    def toggle_alert():
        CFG.audio_alert = alert_var.get()

    tk.Checkbutton(alert_frame, text="تنبيه صوتي عند الغش",
                   variable=alert_var, command=toggle_alert,
                   bg=CARD, fg=TEXT, selectcolor=BG,
                   activebackground=CARD).pack(anchor="w")

    # ─ Stats ──────────────────────────────────────────────────
    stats_frame = section(left, "📊 إحصائيات الجلسة")

    def stat_row(parent, label, var, color):
        f = tk.Frame(parent, bg=CARD)
        f.pack(fill="x", pady=2)
        tk.Label(f, text=label, bg=CARD, fg=MUTED, font=("Arial", 9)).pack(side="left")
        tk.Label(f, textvariable=var, bg=CARD, fg=color,
                 font=("Arial", 11, "bold")).pack(side="right")

    stat_row(stats_frame, "الأحداث الكلية", event_count, TEXT)
    stat_row(stats_frame, "حالات الغش 🚨",  cheat_count, ACCENT)

    # ─ Model info ─────────────────────────────────────────────
    model_frame = section(left, "🧠 الموديل")
    meta = {}
    if Path("model_meta.json").exists():
        with open("model_meta.json", encoding="utf-8") as f:
            meta = json.load(f)
    model_info = (
        f"{meta.get('model_name','غير مدرّب')}  F1={meta.get('f1_score',0):.2f}"
        if meta else "لم يُدرَّب بعد"
    )
    tk.Label(model_frame, text=model_info, bg=CARD, fg=GREEN if meta else ACCENT,
             font=("Arial", 8), wraplength=220).pack()

    # ─ Buttons ────────────────────────────────────────────────
    btn_cfg = {"font": ("Arial", 10, "bold"), "bd": 0, "relief": "flat",
               "cursor": "hand2", "pady": 7}

    def make_btn(parent, text, color, cmd):
        b = tk.Button(parent, text=text, bg=color, fg="white", command=cmd, **btn_cfg)
        b.pack(fill="x", pady=3)
        return b

    btn_frame = tk.Frame(left, bg=BG)
    btn_frame.pack(fill="x", pady=4)

    start_btn = make_btn(btn_frame, "▶  بدء الكشف", GREEN, lambda: start_detection())
    stop_btn  = make_btn(btn_frame, "⏹  إيقاف",     "#555",  lambda: stop_detection())
    stop_btn.config(state="disabled")
    make_btn(btn_frame, "📄 تصدير التقرير", "#2980b9", lambda: export_report())

    # ── Right Panel (log) ──────────────────────────────────────
    right = tk.Frame(main_frame, bg=BG)
    right.pack(side="left", fill="both", expand=True)

    tk.Label(right, text="سجل الأحداث", bg=BG, fg=YELLOW,
             font=("Arial", 10, "bold")).pack(anchor="w")

    log_box = scrolledtext.ScrolledText(
        right, bg="#111122", fg=TEXT, font=("Courier New", 9),
        insertbackground=TEXT, bd=0, relief="flat",
        state="disabled", wrap="word",
    )
    log_box.pack(fill="both", expand=True)

    # ── Status bar ────────────────────────────────────────────
    status_var = tk.StringVar(value="جاهز")
    status_bar = tk.Label(root, textvariable=status_var, bg="#111",
                          fg=MUTED, font=("Arial", 8), anchor="w", padx=8)
    status_bar.pack(fill="x", side="bottom")

    # ── Log helpers ───────────────────────────────────────────
    log_box.tag_config("cheat",    foreground="#ff6b6b")
    log_box.tag_config("normal",   foreground="#74c0fc")
    log_box.tag_config("info",     foreground=MUTED)

    def log(msg, tag="info"):
        log_box.config(state="normal")
        log_box.insert("end", msg + "\n", tag)
        log_box.see("end")
        log_box.config(state="disabled")

    def on_event(evt: DetectionEvent):
        tag = "cheat" if evt.is_cheat else "normal"
        flag = " ⚠️ CHEAT!" if evt.is_cheat else ""
        msg  = (
            f"[{evt.timestamp}] #{evt.event_id:04d} | "
            f"{evt.label} | Conf:{evt.confidence*100:.1f}% | "
            f"Dur:{evt.duration:.2f}s{flag}"
        )
        root.after(0, lambda: log(msg, tag))
        root.after(0, lambda: event_count.set(evt.event_id))
        if evt.is_cheat:
            root.after(0, lambda: cheat_count.set(cheat_count.get() + 1))
            root.after(0, lambda: status_var.set(f"🚨 غش مكتشف! حالة #{cheat_count.get()}"))

    # ── Detection control ─────────────────────────────────────
    stop_flag = [False]

    def start_detection():
        if is_running.get():
            return
        if not Path(CFG.model_path).exists():
            messagebox.showerror("خطأ", "الموديل غير موجود!\nشغّل: python cheat_detector.py train")
            return

        apply_mic()
        is_running.set(True)
        stop_flag[0] = False
        cheat_count.set(0)
        event_count.set(0)
        start_btn.config(state="disabled")
        stop_btn.config(state="normal")
        status_var.set("🎙 جارٍ الكشف...")
        log("─── بدأت جلسة الكشف ───", "info")

        def _run():
            try:
                run_detection(gui_callback=on_event)
            except Exception as e:
                root.after(0, lambda: log(f"❌ خطأ: {e}", "cheat"))
            finally:
                root.after(0, _on_stopped)

        detect_thread[0] = threading.Thread(target=_run, daemon=True)
        detect_thread[0].start()

    def stop_detection():
        # إيقاف بضخ KeyboardInterrupt في Queue
        _audio_queue.put(np.zeros((CFG.frame_size, 1), dtype=np.float32))
        stop_flag[0] = True
        # نقدر نوقفه من خلال إغلاق الـ stream عبر إرسال exception
        # الطريقة الأبسط: وضع flag وترك الـ thread يخرج
        is_running.set(False)
        start_btn.config(state="normal")
        stop_btn.config(state="disabled")
        status_var.set("⏹ تم الإيقاف")
        log("─── توقف الكشف ───", "info")

    def _on_stopped():
        is_running.set(False)
        start_btn.config(state="normal")
        stop_btn.config(state="disabled")
        status_var.set("✅ انتهت الجلسة")
        log("─── انتهت الجلسة ───", "info")

    def export_report():
        reports = sorted(Path(CFG.report_dir).glob("report_*.json")) if Path(CFG.report_dir).is_dir() else []
        if not reports:
            messagebox.showinfo("تقرير", "لا يوجد تقارير بعد.\nشغّل الكشف أولاً.")
            return
        import subprocess
        html = str(reports[-1]).replace(".json", ".html")
        if Path(html).exists():
            try:
                os.startfile(html)
            except Exception:
                subprocess.Popen(["xdg-open", html])
            status_var.set(f"🌐 تم فتح التقرير: {Path(html).name}")
        else:
            messagebox.showinfo("تقرير", f"آخر تقرير JSON:\n{reports[-1]}")

    root.mainloop()


# ══════════════════════════════════════════════════════════════
#  ENTRY POINT
# ══════════════════════════════════════════════════════════════
HELP = """
╔══════════════════════════════════════════════════════════════╗
║        نظام كشف الغش الصوتي  —  Pro Edition v2              ║
╠══════════════════════════════════════════════════════════════╣
║  الأوامر:                                                    ║
║    collect    جمع سامبلز صوتية يدوياً                        ║
║    load_dir   تحميل WAV من cheating/ و non_cheating/         ║
║    train      تدريب الموديل                                  ║
║    run        كشف فعلي في القاعة (Terminal)                  ║
║    gui        واجهة رسومية tkinter                           ║
║    report     عرض آخر تقرير                                  ║
║    mics       قائمة الميكروفونات المتاحة                     ║
║                                                              ║
║  خيارات:                                                     ║
║    --sensitivity 1-10   ضبط الحساسية                        ║
║    --mic INDEX          اختيار الميكروفون برقمه             ║
║    --no-alert           تعطيل التنبيه الصوتي                ║
╚══════════════════════════════════════════════════════════════╝
"""

if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Exam Cheat Detection System v2",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=HELP,
    )
    parser.add_argument(
        "command",
        nargs="?",
        choices=["collect", "load_dir", "train", "run", "gui", "report", "mics"],
        help="الأمر المطلوب",
    )
    parser.add_argument("--sensitivity", "-s", type=int, choices=range(1, 11), metavar="1-10")
    parser.add_argument("--mic",         "-m", type=int, metavar="INDEX", help="رقم الميكروفون")
    parser.add_argument("--no-alert",          action="store_true",       help="تعطيل التنبيه الصوتي")

    args = parser.parse_args()

    if args.sensitivity:
        CFG.sensitivity = args.sensitivity

    if args.mic is not None:
        CFG.mic_index = args.mic

    if args.no_alert:
        CFG.audio_alert = False

    _BP_B, _BP_A = _butter_bandpass()

    if not args.command:
        print(HELP)
    elif args.command == "mics":
        print_microphones()
    elif args.command == "collect":
        collect_samples()
    elif args.command == "load_dir":
        load_from_directory()
    elif args.command == "train":
        train_model()
    elif args.command == "run":
        run_detection()
    elif args.command == "gui":
        launch_gui()
    elif args.command == "report":
        show_report()
