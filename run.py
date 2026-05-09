import numpy as np
import joblib
import sounddevice as sd
import webrtcvad

from utils import *
from config import *

model = joblib.load(MODEL_PATH)
vad = webrtcvad.Vad(2)

def extract_features(signal):
    return [
        np.mean(signal),
        np.std(signal),
        np.max(signal),
        np.min(signal)
    ]

print("🎧 Running real-time detection...")

with sd.InputStream(
    samplerate=SAMPLERATE,
    channels=CHANNELS,
    blocksize=FRAME_SIZE,
    callback=audio_callback
):

    buffer = []

    while True:
        frame = audio_queue.get().flatten()
        frame = bandpass_filter(frame)

        buffer.append(frame)

        if len(buffer) > 30:
            signal = np.concatenate(buffer[-30:])

            features = extract_features(signal)
            pred = model.predict([features])[0]

            print("🚨 CHEATING" if pred == "cheating" else "✅ SAFE")
