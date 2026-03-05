import numpy as np
import sounddevice as sd
import soundfile as sf
import webrtcvad
import librosa
import queue
import time
from scipy.signal import butter, lfilter

# ======================
# إعدادات الصوت
# ======================
samplerate = 16000
frame_duration = 0.03
frame_size = int(samplerate * frame_duration)
channels = 1

silence_limit = 1.0
calibration_time = 2.0

vad = webrtcvad.Vad(2)

audio_queue = queue.Queue()

speech_buffer = []
speech_started = False
silence_time = 0
speech_time = 0
sentence_id = 0

# ======================
# فلتر Bandpass للصوت البشري
# ======================
def butter_bandpass(lowcut, highcut, fs, order=4):
    nyq = 0.5 * fs
    low = lowcut / nyq
    high = highcut / nyq
    return butter(order, [low, high], btype='band')

def bandpass_filter(data):
    b, a = butter_bandpass(80, 4000, samplerate)
    return lfilter(b, a, data)

# ======================
# تحويل الفريم للـ VAD
# ======================
def frame_to_bytes(frame):
    return (frame * 32767).astype(np.int16).tobytes()

# ======================
# استخراج Features
# ======================
def extract_features(audio, sr=16000):

    if len(audio) < 512:
        return None

    energy = np.mean(audio**2)
    zcr = np.mean(librosa.feature.zero_crossing_rate(audio))
    centroid = np.mean(librosa.feature.spectral_centroid(y=audio, sr=sr))

    return energy, zcr, centroid

# ======================
# تصنيف نوع الصوت
# ======================
def classify_sound(audio, sr=16000):

    feats = extract_features(audio, sr)
    if feats is None:
        return "Unknown"

    energy, zcr, centroid = feats

    # Whisper
    if energy < 0.0006 and centroid > 2500:
        return "Whisper"

    # Paper / movement
    if zcr > 0.12 and energy < 0.002:
        return "Paper / movement"

    # Normal speech
    if energy >= 0.0006:
        return "Normal speech"

    return "Noise"

# ======================
# Callback التسجيل
# ======================
def audio_callback(indata, frames, time_info, status):
    if status:
        print(status)
    audio_queue.put(indata.copy())

# ======================
# معايرة الضوضاء
# ======================
print("🎤 Calibrating noise...")
noise_samples = []

with sd.InputStream(callback=audio_callback,
                    channels=channels,
                    samplerate=samplerate,
                    blocksize=frame_size):

    start = time.time()
    while time.time() - start < calibration_time:
        frame = audio_queue.get()
        noise_samples.append(np.mean(frame**2))

noise_threshold = np.mean(noise_samples) * 1.5
print(f"✅ Noise threshold: {noise_threshold:.6f}")
print("🎙️ Start speaking...")

# ======================
# التسجيل الفعلي
# ======================
with sd.InputStream(callback=audio_callback,
                    channels=channels,
                    samplerate=samplerate,
                    blocksize=frame_size):

    while True:
        frame = audio_queue.get().flatten()

        # فلترة
        frame = bandpass_filter(frame)

        energy = np.mean(frame**2)

        speech_flag = False
        if energy > noise_threshold:
            speech_flag = vad.is_speech(frame_to_bytes(frame), samplerate)

        # ======================
        # في كلام
        # ======================
        if speech_flag:

            label = classify_sound(frame, samplerate)

            if not speech_started:
                print(f"🟢 {label} started")
                speech_started = True
                speech_buffer = []
                speech_time = 0

            speech_buffer.append(frame)
            silence_time = 0
            speech_time += frame_duration

        # ======================
        # سكوت
        # ======================
        else:
            if speech_started:
                silence_time += frame_duration
                speech_buffer.append(frame)

                if silence_time > silence_limit:
                    speech_started = False
                    sentence_id += 1

                    audio_data = np.concatenate(speech_buffer)
                    filename = f"sentence_{sentence_id}.wav"

                    sf.write(filename, audio_data, samplerate)

                    label = classify_sound(audio_data, samplerate)

                    print(f"💾 Saved: {filename}")
                    print(f"📢 Type: {label}")
                    print(f"⏱️ Duration: {speech_time:.2f}s")
                    print("🎙️ Waiting...")

        # حماية الميموري
        if len(speech_buffer) > samplerate * 30:
            speech_buffer = speech_buffer[-samplerate*5:]
