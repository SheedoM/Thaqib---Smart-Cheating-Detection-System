"""
================================================
  جمع السامبلز الصوتية — Data Collection Tool
  الخطوة الأولى في مشروع كشف الغش
================================================

شغّله ببساطة:
    python collect_samples.py

هيجمع سامبلز من 5 أنواع:
    [0] كلام عادي   ← غش محتمل
    [1] همس          ← غش محتمل
    [2] ضوضاء عامة  ← مش غش
    [3] حركة / ورق  ← مش غش
    [4] سعلة / عطسة ← مش غش
"""

import os
import time
import queue
import hashlib
import numpy as np
import sounddevice as sd
import soundfile as sf
import webrtcvad
from scipy.signal import butter, lfilter

# ====================================================
# إعدادات
# ====================================================
SAMPLERATE     = 16000
FRAME_DURATION = 0.03
FRAME_SIZE     = int(SAMPLERATE * FRAME_DURATION)
CHANNELS       = 1
SILENCE_LIMIT  = 1.0    # ثانية صمت لإنهاء التسجيل
CALIB_TIME     = 3.0    # ثواني معايرة
MIN_DURATION   = 0.3    # أقل مدة مقبولة للسامبل

DATA_DIR = "training_data"

CLASSES = {
    "0": "كلام عادي   🗣️  ← غش محتمل",
    "1": "همس          🤫  ← غش محتمل",
    "2": "ضوضاء عامة  🔇  ← مش غش",
    "3": "حركة / ورق  📄  ← مش غش",
    "4": "سعلة / عطسة 😤  ← مش غش",
}

TARGETS = {k: 40 for k in CLASSES}   # هدف 40 سامبل لكل كلاس

# ====================================================
# مكونات الصوت
# ====================================================
audio_queue = queue.Queue()

def audio_callback(indata, frames, time_info, status):
    audio_queue.put(indata.copy())

def bandpass_filter(data, lowcut=80, highcut=4000, fs=SAMPLERATE, order=4):
    nyq = 0.5 * fs
    b, a = butter(order, [lowcut / nyq, highcut / nyq], btype='band')
    return lfilter(b, a, data)

def frame_to_bytes(frame):
    return (frame * 32767).astype(np.int16).tobytes()

# ====================================================
# إحصائيات السامبلز الموجودة
# ====================================================
def count_samples():
    counts = {}
    for k in CLASSES:
        folder = os.path.join(DATA_DIR, k)
        if os.path.isdir(folder):
            counts[k] = len([f for f in os.listdir(folder) if f.endswith(".wav")])
        else:
            counts[k] = 0
    return counts

def print_progress():
    counts = count_samples()
    total  = sum(counts.values())
    print("\n📊 التقدم الحالي:")
    print("-" * 50)
    for k, v in CLASSES.items():
        n      = counts[k]
        target = TARGETS[k]
        done   = min(n, target)
        bar    = "█" * done + "░" * (target - done)
        pct    = int(done / target * 100)
        status = "✅" if n >= target else f"{n}/{target}"
        print(f"  [{k}] {bar} {pct:3d}%  {status}")
    print("-" * 50)
    print(f"  إجمالي السامبلز: {total}\n")

# ====================================================
# حفظ السامبل
# ====================================================
def save_sample(audio_data, label):
    folder = os.path.join(DATA_DIR, label)
    os.makedirs(folder, exist_ok=True)
    uid    = hashlib.md5(audio_data.tobytes()).hexdigest()[:8]
    path   = os.path.join(folder, f"{label}_{uid}.wav")
    sf.write(path, audio_data, SAMPLERATE)
    return path

# ====================================================
# معايرة الضوضاء
# ====================================================
def calibrate():
    print("🎤 معايرة الضوضاء... ابقَ ساكت تماماً لمدة 3 ثواني...")
    samples = []

    with sd.InputStream(callback=audio_callback,
                        channels=CHANNELS,
                        samplerate=SAMPLERATE,
                        blocksize=FRAME_SIZE):
        start = time.time()
        while time.time() - start < CALIB_TIME:
            frame = audio_queue.get()
            samples.append(np.mean(frame ** 2))

    threshold = np.mean(samples) * 2.0
    print(f"✅ تم. Threshold = {threshold:.6f}\n")
    return threshold

# ====================================================
# تسجيل سامبل واحد
# ====================================================
def record_one(vad, noise_thresh):
    """
    يستمع للميكروفون ويرجع أول مقطع صوتي مكتمل.
    """
    speech_buffer  = []
    speech_started = False
    silence_time   = 0.0
    speech_time    = 0.0

    with sd.InputStream(callback=audio_callback,
                        channels=CHANNELS,
                        samplerate=SAMPLERATE,
                        blocksize=FRAME_SIZE):
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
                    print("  🔴 Recording...", end="\r")
                speech_buffer.append(frame)
                silence_time  = 0.0
                speech_time  += FRAME_DURATION

            else:
                if speech_started:
                    silence_time += FRAME_DURATION
                    speech_buffer.append(frame)

                    if silence_time > SILENCE_LIMIT:
                        if speech_time < MIN_DURATION:
                            # قصير جداً، استنى تاني
                            speech_started = False
                            speech_buffer  = []
                            speech_time    = 0.0
                            continue

                        return np.concatenate(speech_buffer), speech_time

# ====================================================
# الحلقة الرئيسية
# ====================================================
def main():
    os.makedirs(DATA_DIR, exist_ok=True)

    print("\n" + "="*55)
    print("  🎙  أداة جمع السامبلز — كشف الغش في الامتحانات")
    print("="*55)
    print(__doc__)

    # معايرة
    noise_thresh = calibrate()
    vad = webrtcvad.Vad(2)

    # عرض التقدم الحالي
    print_progress()

    print("💡 نصائح:")
    print("  • سجّل في نفس القاعة اللي هتشتغل فيها")
    print("  • نوّع في طريقة الكلام والهمس")
    print("  • اضغط Ctrl+C في أي وقت للإنهاء\n")

    session_count = 0

    try:
        while True:
            # اختيار الكلاس
            counts = count_samples()
            print("اختار نوع الصوت اللي هتسجله:")
            for k, v in CLASSES.items():
                n = counts[k]
                done_marker = " ✅" if n >= TARGETS[k] else f" ({n}/{TARGETS[k]})"
                print(f"  [{k}] {v}{done_marker}")
            print("  [p] عرض التقدم")
            print("  [q] إنهاء")
            print()

            choice = input("اختيارك: ").strip().lower()

            if choice == "q":
                break
            elif choice == "p":
                print_progress()
                continue
            elif choice not in CLASSES:
                print("❌ اختيار غير صحيح\n")
                continue

            selected_class = choice
            class_name     = CLASSES[choice].split("←")[0].strip()

            # بدء التسجيل
            print(f"\n⏳ جاهز لتسجيل: {class_name}")
            print("   ابدأ الصوت بعد النقطتين ...")
            time.sleep(0.5)

            audio_data, duration = record_one(vad, noise_thresh)

            print(f"  ✅ تم التسجيل — المدة: {duration:.2f}s")

            # تشغيل الصوت للمراجعة
            print("  🔊 تشغيل الصوت للمراجعة...")
            sd.play(audio_data, SAMPLERATE)
            sd.wait()

            # تأكيد الحفظ
            while True:
                confirm = input("  حفظ؟ [y] نعم  [n] تجاهل  [r] إعادة التسجيل: ").strip().lower()

                if confirm == "y":
                    path = save_sample(audio_data, selected_class)
                    session_count += 1
                    counts = count_samples()
                    total_class = counts[selected_class]
                    print(f"  💾 محفوظ! ({total_class} سامبل للنوع ده)\n")
                    break

                elif confirm == "n":
                    print("  ⏭  تم التجاهل\n")
                    break

                elif confirm == "r":
                    print(f"\n⏳ جاهز لتسجيل: {class_name}")
                    print("   ابدأ الصوت بعد النقطتين ...")
                    time.sleep(0.5)
                    audio_data, duration = record_one(vad, noise_thresh)
                    print(f"  ✅ تم التسجيل — المدة: {duration:.2f}s")
                    print("  🔊 تشغيل الصوت للمراجعة...")
                    sd.play(audio_data, SAMPLERATE)
                    sd.wait()

                else:
                    print("  اضغط y أو n أو r")

    except KeyboardInterrupt:
        pass

    # ملخص نهائي
    print("\n" + "="*55)
    print(f"  ✅ انتهت الجلسة — تم تسجيل {session_count} سامبل جديد")
    print("="*55)
    print_progress()

    counts = count_samples()
    ready  = all(counts[k] >= TARGETS[k] for k in CLASSES)

    if ready:
        print("🎉 كل الكلاسات جاهزة! ممكن تشغّل التدريب دلوقتي:")
        print("   python cheat_detector_ml.py train\n")
    else:
        missing = {k: max(0, TARGETS[k] - counts[k]) for k in CLASSES}
        print("📌 لسه محتاج:")
        for k, m in missing.items():
            if m > 0:
                name = CLASSES[k].split("←")[0].strip()
                print(f"   {name}: {m} سامبل")
        print()

if __name__ == "__main__":
    main()


    
