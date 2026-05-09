"""
╔══════════════════════════════════════════════════════════════╗
║        نظام كشف الغش الصوتي في لجان الامتحانات              ║
║        Exam Cheat Detection System  —  Pro Edition           ║
║                                                              ║
║  الاستخدام:                                                  ║
║    python cheat_detector.py collect   ← جمع سامبلز           ║
║    python cheat_detector.py train     ← تدريب الموديل        ║
║    python cheat_detector.py run       ← تشغيل الكشف          ║
║    python cheat_detector.py report    ← تقرير الجلسة         ║
║    python cheat_detector.py load_dir  ← تحميل ملفات wav      ║
╚══════════════════════════════════════════════════════════════╝
"""

import sys
import os
import json
import time
import queue
import logging
import hashlib
import threading
import argparse
from pathlib import Path
from datetime import datetime
from dataclasses import dataclass, field, asdict
from typing import Optional

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


# ══════════════════════════════════════════════════════════════
#  CONFIG  —  كل الإعدادات في مكان واحد
# ══════════════════════════════════════════════════════════════
@dataclass
class Config:
    # ── صوت ──────────────────────────────────────────────────
    samplerate:      int   = 16000
    frame_duration:  float = 0.03        # ثانية لكل frame
    channels:        int   = 1
    silence_limit:   float = 1.0         # ثواني صمت لإنهاء الجملة
    calib_time:      float = 3.0         # ثواني معايرة
    min_duration:    float = 0.3         # أقل مدة للتسجيل

    # ── حساسية (1 = حساس جداً … 10 = صارم جداً) ──────────────
    sensitivity:     int   = 5

    # ── ملفات ─────────────────────────────────────────────────
    data_dir:        str   = "training_data"
    model_path:      str   = "cheat_model.pkl"
    scaler_path:     str   = "cheat_scaler.pkl"   # محتفظ به للتوافق (مدمج في pipeline)
    log_dir:         str   = "logs"
    detections_dir:  str   = "detections"
    report_dir:      str   = "reports"

    # ── تصنيفات ───────────────────────────────────────────────
    cheat_label:     int   = 1

    # ── features ──────────────────────────────────────────────
    n_mfcc:          int   = 13
    bandpass_low:    int   = 80
    bandpass_high:   int   = 4000

    # ── حساب تلقائي ───────────────────────────────────────────
    @property
    def frame_size(self) -> int:
        return int(self.samplerate * self.frame_duration)

    @property
    def noise_multiplier(self) -> float:
        s = max(1, min(10, self.sensitivity))
        return 1.5 + (s - 1) * 0.5          # 1.5 → 6.0

    @property
    def min_confidence(self) -> float:
        s = max(1, min(10, self.sensitivity))
        return 0.50 + (s - 1) * 0.04        # 0.50 → 0.86

    @property
    def cheat_min_secs(self) -> float:
        s = max(1, min(10, self.sensitivity))
        return 0.3 + (s - 1) * 0.1          # 0.3 → 1.2

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
CFG.sensitivity = 8  # ← زوّد من 5 لـ 8 أو 9


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
#  DETECTION EVENT  —  بيانات كل حدث صوتي
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


_BP_B, _BP_A = _butter_bandpass()   # حساب مرة واحدة بس


def bandpass_filter(data: np.ndarray) -> np.ndarray:
    return lfilter(_BP_B, _BP_A, data)


def frame_to_bytes(frame: np.ndarray) -> bytes:
    return (frame * 32767).astype(np.int16).tobytes()


def _calibrate_noise(vad_obj) -> float:
    """قياس ضوضاء القاعة وإرجاع threshold مناسب."""
    samples = []
    with sd.InputStream(
        callback=_audio_callback,
        channels=CFG.channels,
        samplerate=CFG.samplerate,
        blocksize=CFG.frame_size,
    ):
        start = time.time()
        while time.time() - start < CFG.calib_time:
            frame = _audio_queue.get()
            samples.append(float(np.mean(frame ** 2)))

    base = float(np.mean(samples))
    threshold = base * CFG.noise_multiplier
    logger.info(
        f"Calibration done | base={base:.7f} | "
        f"multiplier=×{CFG.noise_multiplier:.1f} | threshold={threshold:.7f}"
    )
    return threshold


# ══════════════════════════════════════════════════════════════
#  FEATURE EXTRACTION
# ══════════════════════════════════════════════════════════════
def extract_features(audio: np.ndarray, sr: int = None) -> Optional[np.ndarray]:
    """
    يستخرج feature vector من مقطع صوتي.
    المجموعات:
        - Energy (2)
        - ZCR    (2)
        - Spectral: centroid, bandwidth, rolloff, contrast, flatness (5)
        - MFCCs + delta MFCCs  (n_mfcc × 2 = 26 بالافتراضي)
        - Pitch: voiced_ratio, pitch_mean, pitch_std (3)
        - Tempo  (1)
    المجموع الافتراضي: 39 feature
    """
    sr = sr or CFG.samplerate
    if len(audio) < 512:
        return None

    feats = []

    # ── Energy ──────────────────────────────────────────────
    rms = np.sqrt(np.mean(audio ** 2))
    feats += [float(rms), float(np.std(audio ** 2))]

    # ── ZCR ─────────────────────────────────────────────────
    zcr = librosa.feature.zero_crossing_rate(audio)
    feats += [float(np.mean(zcr)), float(np.std(zcr))]

    # ── Spectral ─────────────────────────────────────────────
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

    # ── MFCCs + Delta ────────────────────────────────────────
    mfccs = librosa.feature.mfcc(y=audio, sr=sr, n_mfcc=CFG.n_mfcc)
    delta = librosa.feature.delta(mfccs)
    feats += [float(np.mean(mfccs[i])) for i in range(CFG.n_mfcc)]
    feats += [float(np.mean(delta[i]))  for i in range(CFG.n_mfcc)]

    # ── Pitch ────────────────────────────────────────────────
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

    # ── Tempo ────────────────────────────────────────────────
    try:
        tempo, _ = librosa.beat.beat_track(y=audio, sr=sr)
        feats.append(float(np.atleast_1d(tempo)[0]))
    except Exception:
        feats.append(0.0)

    return np.array(feats, dtype=np.float32)


# ══════════════════════════════════════════════════════════════
#  SAMPLE HELPERS
# ══════════════════════════════════════════════════════════════
def _save_sample(audio_data: np.ndarray, label: str) -> str:
    folder = Path(CFG.data_dir) / label
    folder.mkdir(parents=True, exist_ok=True)
    uid  = hashlib.md5(audio_data.tobytes()).hexdigest()[:8]
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
    """جمع وتصنيف سامبلز صوتية يدوياً."""
    Path(CFG.data_dir).mkdir(parents=True, exist_ok=True)
    vad = webrtcvad.Vad(2)

    print("\n" + "═" * 60)
    print("  📥  جمع السامبلز — Data Collection")
    print("═" * 60)
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
                            print("  اختر التصنيف:")
                            print("    [c] Cheating 🚨")
                            print("    [n] Non-Cheating ✅")
                            print("    [s] استماع")
                            print("    [x] تخطي")

                            label = _get_label_input(audio_data)

                            if label in ("cheating", "non_cheating"):
                                path = _save_sample(audio_data, label)
                                icon = "🚨" if label == "cheating" else "✅"
                                print(f"  {icon} تم الحفظ → {path}\n")
                            else:
                                print("  ⏭  تم التخطي\n")

                # حماية الذاكرة
                if len(speech_buffer) > CFG.samplerate * 30:
                    speech_buffer = speech_buffer[-CFG.samplerate * 5:]

        except KeyboardInterrupt:
            print("\n")
            _print_sample_stats()


# ══════════════════════════════════════════════════════════════
#  LOAD_DIR — تحميل ملفات WAV من فولدر مباشرة
# ══════════════════════════════════════════════════════════════
def load_from_directory():
    """
    تحميل ملفات WAV من فولدرات cheating/ و non_cheating/
    وإضافتها مباشرة لـ training_data دون تسجيل صوتي.
    """
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

        copied = 0
        for wav_path in files:
            try:
                audio, sr = librosa.load(str(wav_path), sr=CFG.samplerate, mono=True)
                saved = _save_sample(audio, label)
                copied += 1
            except Exception as e:
                logger.warning(f"Skipped {wav_path}: {e}")

        print(f"  ✅ تم نسخ {copied} ملف إلى training_data/{label}/")

    print()
    _print_sample_stats()


# ══════════════════════════════════════════════════════════════
#  PHASE 2 — تدريب الموديل
# ══════════════════════════════════════════════════════════════
def train_model():
    """تدريب أفضل موديل ممكن على السامبلز المجمّعة."""
    print("\n" + "═" * 60)
    print("  🧠  التدريب — Model Training")
    print("═" * 60)

    _print_sample_stats()

    X, y = [], []
    label_map = {"non_cheating": 0, "cheating": 1}

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
            except Exception as e:
                logger.warning(f"Skipped {wav}: {e}")

    if len(X) < 10:
        print("\n❌ سامبلز غير كافية (10 على الأقل لكل كلاس).")
        return

    X = np.array(X)
    y = np.array(y)

    print(f"\n  Total samples    : {len(X)}")
    print(f"  Feature vector   : {X.shape[1]} features")
    print(f"  Cheating samples : {int(np.sum(y == 1))}")
    print(f"  Non-cheat samples: {int(np.sum(y == 0))}")

    # ── Candidate Models ──────────────────────────────────────
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

    # ── Cross-Validation ──────────────────────────────────────
    scaler = StandardScaler()
    X_scaled = scaler.fit_transform(X)
    cv = StratifiedKFold(n_splits=5, shuffle=True, random_state=42)

    best_name  = ""
    best_score = 0.0
    best_model = None

    print("\n  ── Cross-Validation Results ──")
    for name, model in candidates.items():
        scores = cross_val_score(model, X_scaled, y, cv=cv, scoring="f1_weighted", n_jobs=-1)
        print(f"  {name:<20s} F1 = {scores.mean():.3f} ± {scores.std():.3f}")
        if scores.mean() > best_score:
            best_score = scores.mean()
            best_model = model
            best_name  = name

    print(f"\n  ✅ أفضل موديل: {best_name}  (F1={best_score:.3f})")

    # ── Final Train / Test ────────────────────────────────────
    X_train, X_test, y_train, y_test = train_test_split(
        X_scaled, y, test_size=0.2, random_state=42, stratify=y
    )
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

    # ── Save Pipeline (model + scaler bundled) ─────────────────
    pipeline = Pipeline([
        ("scaler", scaler),
        ("model",  best_model),
    ])
    # حفظ الـ pipeline ونسخة منفصلة للـ scaler للتوافق مع النسخة القديمة
    joblib.dump(pipeline,           CFG.model_path)
    joblib.dump(scaler,             CFG.scaler_path)

    meta = {
        "model_name":    best_name,
        "f1_score":      best_score,
        "feature_count": X.shape[1],
        "n_mfcc":        CFG.n_mfcc,
        "trained_at":    datetime.now().isoformat(),
        "samples":       {"cheating": int(np.sum(y==1)), "non_cheating": int(np.sum(y==0))},
    }
    with open("model_meta.json", "w", encoding="utf-8") as f:
        json.dump(meta, f, ensure_ascii=False, indent=2)

    print(f"\n  💾 Model saved  → {CFG.model_path}")
    print(f"  💾 Meta saved   → model_meta.json")


# ══════════════════════════════════════════════════════════════
#  PHASE 3 — الكشف الفعلي
# ══════════════════════════════════════════════════════════════
def run_detection():
    """الكشف الفعلي اللحظي في القاعة."""
    print("\n" + "═" * 60)
    print("  🎯  الكشف الفعلي — Live Detection")
    print("═" * 60)

    # ── تحميل الموديل ─────────────────────────────────────────
    if not Path(CFG.model_path).exists():
        print(f"❌ الموديل غير موجود! شغّل: python cheat_detector.py train")
        return

    pipeline = joblib.load(CFG.model_path)

    # قراءة metadata
    meta = {}
    if Path("model_meta.json").exists():
        with open("model_meta.json", encoding="utf-8") as f:
            meta = json.load(f)

    print(f"  ✅ Loaded: {meta.get('model_name','?')}  F1={meta.get('f1_score',0):.3f}")
    print(f"\n  ⚙️  Sensitivity     : {CFG.sensitivity}/10")
    print(f"  ⚙️  Noise multiplier : ×{CFG.noise_multiplier:.1f}")
    print(f"  ⚙️  Min confidence   : {CFG.min_confidence*100:.0f}%")
    print(f"  ⚙️  Min cheat dur.   : {CFG.cheat_min_secs:.1f}s")

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
    events: list[DetectionEvent] = []

    def _classify(audio_data: np.ndarray) -> tuple[int, float]:
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
                            label_str = "Cheating 🚨"   if pred == 1 else "Non-Cheating ✅"

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

                            # ── طباعة الحدث ──────────────────────────
                            flag = " ⚠️ CHEAT" if is_cheat else ""
                            print(
                                f"  [{ts}] #{event_id:04d} | {label_str:<20s} | "
                                f"Conf: {confidence*100:5.1f}% | "
                                f"Dur: {speech_time:.2f}s{flag}"
                            )

                            logger.info(
                                f"Event#{event_id} | {label_str} | "
                                f"conf={confidence:.3f} | dur={speech_time:.2f}s | "
                                f"cheat={is_cheat}"
                            )

                            # ── تنبيه غش ─────────────────────────────
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
                                    f"🚨 CHEAT #{cheat_count} | {label_str} | "
                                    f"conf={confidence:.3f} | dur={speech_time:.2f}s | "
                                    f"file={fname}"
                                )

                            events.append(evt)

                # حماية الذاكرة
                if len(speech_buffer) > CFG.samplerate * 30:
                    speech_buffer = speech_buffer[-CFG.samplerate * 5:]

        except KeyboardInterrupt:
            pass

    # ── ملخص الجلسة ──────────────────────────────────────────
    print(f"\n\n  ══ ملخص الجلسة ══")
    print(f"  إجمالي الأحداث : {event_id}")
    print(f"  حالات غش       : {cheat_count}")
    print(f"  سجل الجلسة     : {_log_file}")

    # حفظ تقرير JSON للجلسة
    _save_session_report(events)


# ══════════════════════════════════════════════════════════════
#  REPORT — تقرير الجلسة
# ══════════════════════════════════════════════════════════════
def _save_session_report(events: list):
    Path(CFG.report_dir).mkdir(parents=True, exist_ok=True)
    fname = os.path.join(
        CFG.report_dir,
        f"report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    )
    data = {
        "generated_at":  datetime.now().isoformat(),
        "total_events":  len(events),
        "cheat_events":  sum(1 for e in events if e.is_cheat),
        "sensitivity":   CFG.sensitivity,
        "events":        [asdict(e) for e in events],
    }
    with open(fname, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    print(f"  📄 تقرير الجلسة → {fname}")


def show_report():
    """طباعة آخر تقرير جلسة بشكل مقروء."""
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
                + (f" | 📁 {e['audio_file']}" if e.get('audio_file') else "")
            )
    print()


# ══════════════════════════════════════════════════════════════
#  ENTRY POINT
# ══════════════════════════════════════════════════════════════
HELP = """
╔══════════════════════════════════════════════════════════════╗
║        نظام كشف الغش الصوتي  —  Pro Edition                 ║
╠══════════════════════════════════════════════════════════════╣
║                                                              ║
║  الأوامر:                                                    ║
║    collect    جمع سامبلز صوتية وتصنيفها يدوياً             ║
║    load_dir   تحميل ملفات WAV من cheating/ و non_cheating/  ║
║    train      تدريب الموديل على السامبلز                    ║
║    run        تشغيل الكشف الفعلي في القاعة                  ║
║    report     عرض آخر تقرير جلسة                            ║
║                                                              ║
║  الترتيب الصحيح:                                             ║
║    1) collect أو load_dir  (30+ سامبل لكل كلاس)             ║
║    2) train                                                  ║
║    3) run                                                    ║
║                                                              ║
║  ضبط الحساسية:                                               ║
║    عدّل SENSITIVITY في config.json (1–10)                    ║
║    أو غيّر CFG.sensitivity في السكريبت                      ║
║    1–3  → حساس جداً   (لجان هادية)                          ║
║    4–6  → متوازن ✅   (الافتراضي)                           ║
║    7–10 → صارم جداً   (بيئات ضوضائية)                       ║
╚══════════════════════════════════════════════════════════════╝
"""

if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Exam Cheat Detection System",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=HELP,
    )
    parser.add_argument(
        "command",
        nargs="?",
        choices=["collect", "load_dir", "train", "run", "report"],
        help="الأمر المطلوب تنفيذه",
    )
    parser.add_argument(
        "--sensitivity", "-s",
        type=int,
        choices=range(1, 11),
        metavar="1-10",
        help="حساسية الكشف (1=حساس جداً … 10=صارم جداً)",
    )

    args = parser.parse_args()

    if args.sensitivity:
        CFG.sensitivity = args.sensitivity
        # إعادة حساب الباندباس بعد تغيير الـ config
        _BP_B, _BP_A = _butter_bandpass()

    if not args.command:
        print(HELP)
    elif args.command == "collect":
        collect_samples()
    elif args.command == "load_dir":
        load_from_directory()
    elif args.command == "train":
        train_model()
    elif args.command == "run":
        run_detection()
    elif args.command == "report":
        show_report()
