"""
================================================
 نظام كشف الغش الصوتي في لجان الامتحانات
 Exam Cheat Detection System — ML Version
================================================

المراحل:
    python cheat_detector_ml.py collect   → جمع سامبلز للتدريب
    python cheat_detector_ml.py train     → تدريب الـ model
    python cheat_detector_ml.py run       → تشغيل الكشف الفعلي
"""

import sys
import os
import json
import time
import queue
import logging
import hashlib
import numpy as np
import sounddevice as sd
import soundfile as sf
import webrtcvad
import librosa
from datetime import datetime
from scipy.signal import butter, lfilter

# ML
from sklearn.ensemble import RandomForestClassifier, GradientBoostingClassifier
from sklearn.preprocessing import StandardScaler
from sklearn.model_selection import train_test_split, cross_val_score
from sklearn.metrics import classification_report, confusion_matrix
import joblib

# ====================================================
# ثوابت وإعدادات
# ====================================================
SAMPLERATE      = 16000
FRAME_DURATION  = 0.03
FRAME_SIZE      = int(SAMPLERATE * FRAME_DURATION)
CHANNELS        = 1
SILENCE_LIMIT   = 1.0       # ثانية صمت لإنهاء الجملة
CALIB_TIME      = 3.0       # ثواني معايرة
MIN_DURATION    = 0.3       # أقل مدة للتسجيل
CHEAT_MIN_SECS  = 0.6       # أقل مدة لتصنيف الغش

# مسارات الملفات
DATA_DIR        = "training_data"
MODEL_PATH      = "cheat_model.pkl"
SCALER_PATH     = "cheat_scaler.pkl"
LABELS_PATH     = "cheat_labels.json"
LOG_DIR         = "logs"

# تصنيفات الصوت
CLASSES = {
    "0": "Speech 🗣️",      # كلام حقيقي = غش محتمل
    "1": "Whisper 🤫",     # همس = غش محتمل
    "2": "Noise 🔇",       # ضوضاء عادية
    "3": "Paper 📄",       # حركة / ورق
    "4": "Cough 😤",       # سعلة / عطسة
}
CHEAT_CLASSES = {"0", "1"}   # الكلاسات اللي تُعتبر غش

# ====================================================
# إعداد الـ Logging
# ====================================================
os.makedirs(LOG_DIR, exist_ok=True)
log_file = os.path.join(LOG_DIR, f"exam_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log")
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
    handlers=[
        logging.FileHandler(log_file, encoding="utf-8"),
        logging.StreamHandler(sys.stdout),
    ]
)
logger = logging.getLogger("CheatDetector")

# ====================================================
# مكونات الصوت المشتركة
# ====================================================
audio_queue = queue.Queue()

def audio_callback(indata, frames, time_info, status):
    if status:
        logger.warning(f"Stream: {status}")
    audio_queue.put(indata.copy())

def butter_bandpass(lowcut=80, highcut=4000, fs=SAMPLERATE, order=4):
    nyq  = 0.5 * fs
    return butter(order, [lowcut / nyq, highcut / nyq], btype='band')

def bandpass_filter(data):
    b, a = butter_bandpass()
    return lfilter(b, a, data)

def frame_to_bytes(frame):
    return (frame * 32767).astype(np.int16).tobytes()

# ====================================================
# استخراج Features
# ====================================================
def extract_features(audio, sr=SAMPLERATE):
    """
    يستخرج vector من 20 feature من مقطع صوتي.
    """
    if len(audio) < 512:
        return None

    features = []

    # --- Energy ---
    energy = float(np.mean(audio ** 2))
    features.append(energy)
    features.append(float(np.std(audio ** 2)))

    # --- ZCR ---
    zcr = librosa.feature.zero_crossing_rate(audio)
    features.append(float(np.mean(zcr)))
    features.append(float(np.std(zcr)))

    # --- Spectral ---
    centroid  = librosa.feature.spectral_centroid(y=audio, sr=sr)
    bandwidth = librosa.feature.spectral_bandwidth(y=audio, sr=sr)
    rolloff   = librosa.feature.spectral_rolloff(y=audio, sr=sr)
    contrast  = librosa.feature.spectral_contrast(y=audio, sr=sr)

    features += [
        float(np.mean(centroid)),
        float(np.mean(bandwidth)),
        float(np.mean(rolloff)),
        float(np.mean(contrast)),
        float(np.std(centroid)),
    ]

    # --- MFCCs (أول 8) ---
    mfccs = librosa.feature.mfcc(y=audio, sr=sr, n_mfcc=8)
    features += [float(np.mean(mfccs[i])) for i in range(8)]

    # --- Pitch ---
    try:
        f0, voiced_flag, _ = librosa.pyin(
            audio,
            fmin=librosa.note_to_hz('C2'),
            fmax=librosa.note_to_hz('C7'),
            sr=sr
        )
        voiced_ratio = float(np.mean(voiced_flag)) if voiced_flag is not None else 0.0
        pitch_mean   = float(np.nanmean(f0)) if (f0 is not None and np.any(voiced_flag)) else 0.0
    except Exception:
        voiced_ratio = 0.0
        pitch_mean   = 0.0

    features += [voiced_ratio, pitch_mean]

    return np.array(features, dtype=np.float32)

# ====================================================
# PHASE 1 — جمع السامبلز
# ====================================================
def collect_samples():
    """
    يسجل سامبلز صوتية ويطلب من المستخدم تصنيفها يدوياً.
    """
    os.makedirs(DATA_DIR, exist_ok=True)
    vad = webrtcvad.Vad(2)

    print("\n" + "="*60)
    print("  مرحلة جمع السامبلز — Data Collection")
    print("="*60)
    print("التصنيفات المتاحة:")
    for k, v in CLASSES.items():
        print(f"  [{k}] {v}")
    print("\nاضغط Ctrl+C للإنهاء في أي وقت.\n")

    # معايرة الضوضاء
    print("🎤 معايرة الضوضاء... ابقَ ساكت لمدة 3 ثواني...")
    noise_thresh = _calibrate_noise(vad)
    print(f"✅ Threshold: {noise_thresh:.6f}\n")

    sample_count = _count_existing_samples()
    print(f"📁 السامبلز الموجودة: {sample_count}")
    print("🎙  ابدأ الكلام / الهمس / تحريك الورق...\n")

    speech_buffer = []
    speech_started = False
    silence_time = 0.0
    speech_time  = 0.0

    with sd.InputStream(callback=audio_callback,
                        channels=CHANNELS,
                        samplerate=SAMPLERATE,
                        blocksize=FRAME_SIZE):
        try:
            while True:
                frame = audio_queue.get().flatten()
                frame = bandpass_filter(frame)
                energy = np.mean(frame ** 2)

                speech_flag = False
                if energy > noise_thresh:
                    try:
                        speech_flag = vad.is_speech(frame_to_bytes(frame), SAMPLERATE)
                    except Exception:
                        pass

                if speech_flag:
                    if not speech_started:
                        speech_started = True
                        speech_buffer  = []
                        speech_time    = 0.0
                        silence_time   = 0.0
                        print("🔴 Recording...")
                    speech_buffer.append(frame)
                    silence_time  = 0.0
                    speech_time  += FRAME_DURATION
                else:
                    if speech_started:
                        silence_time += FRAME_DURATION
                        speech_buffer.append(frame)

                        if silence_time > SILENCE_LIMIT:
                            speech_started = False

                            if speech_time < MIN_DURATION:
                                print("⚡ Too short, ignored.\n")
                                speech_buffer = []
                                continue

                            audio_data = np.concatenate(speech_buffer)
                            speech_buffer = []

                            # اختيار التصنيف
                            print(f"\n⏱️  Duration: {speech_time:.2f}s")
                            print("صنّف هذا الصوت:")
                            for k, v in CLASSES.items():
                                print(f"  [{k}] {v}")
                            print("  [s] تشغيل الصوت مجدداً")
                            print("  [x] تجاهل")

                            label = _get_label_input(audio_data)

                            if label is not None:
                                _save_sample(audio_data, label)
                                print(f"✅ Saved as: {CLASSES[label]}\n")
                            else:
                                print("⏭  Skipped.\n")

                if len(speech_buffer) > SAMPLERATE * 30:
                    speech_buffer = speech_buffer[-SAMPLERATE * 5:]

        except KeyboardInterrupt:
            total = _count_existing_samples()
            print(f"\n\n✅ Collection done. Total samples: {total}")
            _print_sample_stats()

def _calibrate_noise(vad_obj):
    samples = []
    with sd.InputStream(callback=audio_callback,
                        channels=CHANNELS,
                        samplerate=SAMPLERATE,
                        blocksize=FRAME_SIZE):
        start = time.time()
        while time.time() - start < CALIB_TIME:
            frame = audio_queue.get()
            samples.append(np.mean(frame ** 2))
    return np.mean(samples) * 2.0

def _count_existing_samples():
    count = 0
    for label in CLASSES:
        d = os.path.join(DATA_DIR, label)
        if os.path.isdir(d):
            count += len([f for f in os.listdir(d) if f.endswith(".wav")])
    return count

def _print_sample_stats():
    print("\nإحصائيات السامبلز:")
    for k, v in CLASSES.items():
        d = os.path.join(DATA_DIR, k)
        n = len([f for f in os.listdir(d) if f.endswith(".wav")]) if os.path.isdir(d) else 0
        bar = "█" * n
        print(f"  {v:20s} : {n:3d}  {bar}")

def _get_label_input(audio_data):
    while True:
        choice = input("اختيارك: ").strip().lower()
        if choice == "x":
            return None
        if choice == "s":
            sd.play(audio_data, SAMPLERATE)
            sd.wait()
        elif choice in CLASSES:
            return choice
        else:
            print("اختيار غير صحيح، حاول مجدداً.")

def _save_sample(audio_data, label):
    folder = os.path.join(DATA_DIR, label)
    os.makedirs(folder, exist_ok=True)
    uid  = hashlib.md5(audio_data.tobytes()).hexdigest()[:8]
    path = os.path.join(folder, f"{label}_{uid}.wav")
    sf.write(path, audio_data, SAMPLERATE)

# ====================================================
# PHASE 2 — تدريب الـ Model
# ====================================================
def train_model():
    print("\n" + "="*60)
    print("  مرحلة التدريب — Model Training")
    print("="*60)

    X, y = [], []

    # تحميل السامبلز
    for label in CLASSES:
        folder = os.path.join(DATA_DIR, label)
        if not os.path.isdir(folder):
            continue
        files = [f for f in os.listdir(folder) if f.endswith(".wav")]
        print(f"  Loading class {CLASSES[label]}: {len(files)} samples")

        for fname in files:
            path = os.path.join(folder, fname)
            try:
                audio, sr = librosa.load(path, sr=SAMPLERATE, mono=True)
                feats = extract_features(audio, sr)
                if feats is not None:
                    X.append(feats)
                    y.append(int(label))
            except Exception as e:
                logger.warning(f"Skipped {path}: {e}")

    if len(X) < 10:
        print("\n❌ سامبلز غير كافية! اجمع على الأقل 10 سامبلز لكل كلاس.")
        return

    X = np.array(X)
    y = np.array(y)

    print(f"\nTotal samples: {len(X)}")
    print(f"Feature vector size: {X.shape[1]}")

    # تطبيع الـ Features
    scaler = StandardScaler()
    X_scaled = scaler.fit_transform(X)

    # تقسيم Train/Test
    X_train, X_test, y_train, y_test = train_test_split(
        X_scaled, y, test_size=0.2, random_state=42, stratify=y
    )

    # تدريب نموذجين واختيار الأفضل
    models = {
        "RandomForest": RandomForestClassifier(
            n_estimators=200, max_depth=15,
            class_weight="balanced", random_state=42
        ),
        "GradientBoosting": GradientBoostingClassifier(
            n_estimators=150, max_depth=5,
            learning_rate=0.1, random_state=42
        ),
    }

    best_model  = None
    best_score  = 0
    best_name   = ""

    for name, model in models.items():
        cv_scores = cross_val_score(model, X_scaled, y, cv=5, scoring="f1_weighted")
        print(f"\n{name} CV F1: {cv_scores.mean():.3f} ± {cv_scores.std():.3f}")
        if cv_scores.mean() > best_score:
            best_score = cv_scores.mean()
            best_model = model
            best_name  = name

    # تدريب الأفضل على كل البيانات
    print(f"\n✅ Best model: {best_name} (F1={best_score:.3f})")
    best_model.fit(X_train, y_train)

    # تقييم
    y_pred = best_model.predict(X_test)
    label_names = [CLASSES[str(i)] for i in sorted(set(y))]
    print("\n--- Classification Report ---")
    print(classification_report(y_test, y_pred, target_names=label_names))
    print("--- Confusion Matrix ---")
    print(confusion_matrix(y_test, y_pred))

    # حفظ الـ Model
    joblib.dump(best_model, MODEL_PATH)
    joblib.dump(scaler, SCALER_PATH)
    with open(LABELS_PATH, "w", encoding="utf-8") as f:
        json.dump(CLASSES, f, ensure_ascii=False)

    print(f"\n💾 Model saved: {MODEL_PATH}")
    print(f"💾 Scaler saved: {SCALER_PATH}")

# ====================================================
# PHASE 3 — الكشف الفعلي
# ====================================================
def run_detection():
    print("\n" + "="*60)
    print("  نظام الكشف الفعلي — Live Detection")
    print("="*60)

    # تحميل الـ Model
    if not os.path.exists(MODEL_PATH):
        print("❌ Model غير موجود! شغّل: python cheat_detector_ml.py train")
        return

    model  = joblib.load(MODEL_PATH)
    scaler = joblib.load(SCALER_PATH)
    print("✅ Model loaded successfully.")

    vad = webrtcvad.Vad(2)

    # معايرة
    print("\n🎤 معايرة الضوضاء... ابقَ ساكت...")
    noise_thresh = _calibrate_noise(vad)
    print(f"✅ Noise threshold: {noise_thresh:.6f}")
    print("🎙  المراقبة بدأت...\n")

    os.makedirs("detections", exist_ok=True)

    speech_buffer  = []
    speech_started = False
    silence_time   = 0.0
    speech_time    = 0.0
    event_id       = 0
    cheat_count    = 0

    with sd.InputStream(callback=audio_callback,
                        channels=CHANNELS,
                        samplerate=SAMPLERATE,
                        blocksize=FRAME_SIZE):
        try:
            while True:
                frame = audio_queue.get().flatten()
                frame = bandpass_filter(frame)
                energy = np.mean(frame ** 2)

                speech_flag = False
                if energy > noise_thresh:
                    try:
                        speech_flag = vad.is_speech(frame_to_bytes(frame), SAMPLERATE)
                    except Exception:
                        pass

                if speech_flag:
                    if not speech_started:
                        speech_started = True
                        speech_buffer  = []
                        speech_time    = 0.0
                        silence_time   = 0.0
                    speech_buffer.append(frame)
                    silence_time  = 0.0
                    speech_time  += FRAME_DURATION

                else:
                    if speech_started:
                        silence_time += FRAME_DURATION
                        speech_buffer.append(frame)

                        if silence_time > SILENCE_LIMIT:
                            speech_started = False
                            event_id += 1

                            if speech_time < MIN_DURATION:
                                speech_buffer = []
                                continue

                            audio_data = np.concatenate(speech_buffer)
                            speech_buffer = []

                            # استخراج الـ Features والتصنيف
                            feats = extract_features(audio_data)
                            if feats is None:
                                continue

                            feats_scaled = scaler.transform([feats])
                            pred         = model.predict(feats_scaled)[0]
                            proba        = model.predict_proba(feats_scaled)[0]
                            confidence   = float(proba[pred])
                            label_str    = CLASSES[str(pred)]
                            is_cheat     = (str(pred) in CHEAT_CLASSES
                                            and confidence >= 0.65
                                            and speech_time >= CHEAT_MIN_SECS)

                            # طباعة الحدث
                            ts = datetime.now().strftime("%H:%M:%S")
                            print(f"[{ts}] #{event_id:04d} | {label_str} | "
                                  f"Conf: {confidence*100:.0f}% | "
                                  f"Duration: {speech_time:.2f}s"
                                  + (" ⚠️" if is_cheat else ""))

                            # تسجيل
                            logger.info(
                                f"Event#{event_id} | {label_str} | "
                                f"conf={confidence:.2f} | dur={speech_time:.2f}s | "
                                f"cheat={is_cheat}"
                            )

                            # تنبيه غش
                            if is_cheat:
                                cheat_count += 1
                                fname = os.path.join(
                                    "detections",
                                    f"cheat_{cheat_count:04d}_{label_str.split()[0]}.wav"
                                )
                                sf.write(fname, audio_data, SAMPLERATE)

                                print("\n" + "🚨" * 30)
                                print(f"  ⚠️  CHEATING DETECTED!")
                                print(f"  النوع      : {label_str}")
                                print(f"  الثقة      : {confidence*100:.0f}%")
                                print(f"  المدة      : {speech_time:.2f}s")
                                print(f"  الملف      : {fname}")
                                print(f"  إجمالي الغش: {cheat_count}")
                                print("🚨" * 30 + "\n")

                                logger.warning(
                                    f"🚨 CHEAT #{cheat_count} | {label_str} | "
                                    f"conf={confidence:.2f} | file={fname}"
                                )

                if len(speech_buffer) > SAMPLERATE * 30:
                    speech_buffer = speech_buffer[-SAMPLERATE * 5:]

        except KeyboardInterrupt:
            print(f"\n\n✅ Session ended.")
            print(f"📊 Total events: {event_id}")
            print(f"🚨 Cheat alerts: {cheat_count}")
            print(f"📄 Log saved: {log_file}")

# ====================================================
# نقطة الدخول
# ====================================================
def print_help():
    print("""
استخدام:
    python cheat_detector_ml.py collect   ← جمع سامبلز للتدريب
    python cheat_detector_ml.py train     ← تدريب الـ model
    python cheat_detector_ml.py run       ← تشغيل الكشف الفعلي

الترتيب الصحيح:
    1) collect  (اجمع 30+ سامبل لكل نوع صوت)
    2) train    (درّب الـ model على السامبلز)
    3) run      (شغّل الكشف الفعلي في القاعة)
""")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print_help()
    elif sys.argv[1] == "collect":
        collect_samples()
    elif sys.argv[1] == "train":
        train_model()
    elif sys.argv[1] == "run":
        run_detection()
    else:
        print_help()
