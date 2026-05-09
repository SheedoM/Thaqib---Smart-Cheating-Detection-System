import os
import numpy as np
import sounddevice as sd
import queue
import uuid
from config import *

audio_queue = queue.Queue()

def audio_callback(indata, frames, time, status):
    audio_queue.put(indata.copy())

def frame_to_bytes(frame):
    return (frame * 32767).astype(np.int16).tobytes()

def bandpass_filter(x):
    return x  # ممكن تزود فلتر لاحقًا

def save_sample(audio, label):
    folder = os.path.join(DATA_DIR, label)
    os.makedirs(folder, exist_ok=True)

    filename = os.path.join(folder, f"{uuid.uuid4()}.npy")
    np.save(filename, audio)

def load_data():
    X, y = [], []

    for label in ["cheating", "non_cheating"]:
        folder = os.path.join(DATA_DIR, label)

        if not os.path.exists(folder):
            continue

        for file in os.listdir(folder):
            data = np.load(os.path.join(folder, file))
            X.append(data)
            y.append(label)

    return X, y
