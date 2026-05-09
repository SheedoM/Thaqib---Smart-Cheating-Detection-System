import os
import numpy as np
import sounddevice as sd
import webrtcvad

from config import *
from utils import *

def collect_samples():
    os.makedirs(DATA_DIR, exist_ok=True)

    vad = webrtcvad.Vad(2)

    print("=" * 60)
    print("🎤 Data Collection - 2 Classes")
    print("=" * 60)

    print("  [c] Cheating 🚨")
    print("  [n] Non-Cheating ✅")
    print("  [x] Skip")

    speech_buffer = []
    speech_started = False
    silence_time = 0
    speech_time = 0

    print("\n🎧 Listening...\n")

    with sd.InputStream(
        samplerate=SAMPLERATE,
        channels=CHANNELS,
        blocksize=FRAME_SIZE,
        callback=audio_callback
    ):

        try:
            while True:
                frame = audio_queue.get().flatten()
                frame = bandpass_filter(frame)

                energy = np.mean(frame ** 2)

                speech_flag = False
                if energy > 1e-6:
                    try:
                        speech_flag = vad.is_speech(
                            frame_to_bytes(frame),
                            SAMPLERATE
                        )
                    except:
                        pass

                if speech_flag:
                    if not speech_started:
                        speech_started = True
                        speech_buffer = []
                        speech_time = 0
                        silence_time = 0
                        print("🔴 Recording...")

                    speech_buffer.append(frame)
                    speech_time += 0.03
                    silence_time = 0

                else:
                    if speech_started:
                        speech_buffer.append(frame)
                        silence_time += 0.03

                        if silence_time > SILENCE_LIMIT:
                            speech_started = False

                            if speech_time < MIN_DURATION:
                                speech_buffer = []
                                continue

                            audio = np.concatenate(speech_buffer)
                            speech_buffer = []

                            print("\nLabel:")
                            print("[c] Cheating")
                            print("[n] Non-Cheating")
                            print("[x] Skip")

                            label = input(">>> ").strip().lower()

                            if label == "c":
                                save_sample(audio, "cheating")
                            elif label == "n":
                                save_sample(audio, "non_cheating")
                            else:
                                print("Skipped")

                if len(speech_buffer) > SAMPLERATE * 20:
                    speech_buffer = speech_buffer[-SAMPLERATE * 5:]

        except KeyboardInterrupt:
            print("\n✅ Done collecting samples")
