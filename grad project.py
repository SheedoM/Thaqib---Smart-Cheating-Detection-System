import numpy as np
import sounddevice as sd
import time

# إعدادات
samplerate = 16000
frame_duration = 0.03  # 30 ms
frame_size = int(samplerate * frame_duration)

BASE_THRESHOLD = 0.0005
SPEECH_THRESHOLD = 0.3  # seconds
WINDOW_DURATION = 60  # seconds
EVENT_THRESHOLD = 3  # number of suspicious events

speech_duration = 0
suspicious_events = []
background_energy = []

def audio_callback(indata, frames, time_info, status):
    global speech_duration, suspicious_events, background_energy

    current_time = time.time()

    energy = np.linalg.norm(indata) / frames

    # تحديث متوسط مستوى الضوضاء
    background_energy.append(energy)
    if len(background_energy) > int(5 / frame_duration):
        background_energy.pop(0)
    dynamic_threshold = BASE_THRESHOLD + np.mean(background_energy)

    # تمييز مستوى الصوت
    if energy < dynamic_threshold:
        level = "Silence"
    elif energy < dynamic_threshold * 3:
        level = "Whisper"
    elif energy < dynamic_threshold * 6:
        level = "Normal"
    else:
        level = "Loud"

    # متابعة الكلام المستمر
    if level in ["Whisper", "Normal", "Loud"]:
        speech_duration += frame_duration
    else:
        speech_duration = 0

    # لو الكلام استمر فترة
    if speech_duration >= SPEECH_THRESHOLD:
        print(f"⚠ Suspicious speech detected ({level})")
        suspicious_events.append(current_time)
        speech_duration = 0

    # إزالة الأحداث الأقدم من WINDOW_DURATION
    suspicious_events = [
        t for t in suspicious_events if current_time - t <= WINDOW_DURATION
    ]

    # تكرار الأحداث
    if len(suspicious_events) >= EVENT_THRESHOLD:
        print("🚨 HIGH ALERT: Repeated suspicious speech detected!")
        suspicious_events.clear()


print("🎤 Real-time audio monitoring with dynamic threshold started...")

with sd.InputStream(callback=audio_callback,
                    channels=1,
                    samplerate=samplerate,
                    blocksize=frame_size):
    while True:
        time.sleep(0.1)