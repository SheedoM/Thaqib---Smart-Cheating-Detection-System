import sys
import os
import cv2
import time
import numpy as np

# Add src to path
sys.path.insert(0, os.path.abspath('src'))

from thaqib.config import get_settings

def test_comparison():
    image_path = 'testing file/video/photo_2026-06-10_12-13-02.jpg'
    if not os.path.exists(image_path):
        print(f"Error: Image {image_path} does not exist.")
        return

    frame = cv2.imread(image_path)
    if frame is None:
        print("Error: Failed to read image.")
        return

    # Configuration 1: Dedicated phone model (phonem.pt)
    print("\n=== CONFIG 1: Dedicated Phone Model (models/phonem.pt) ===")
    settings = get_settings()
    settings.phone_model = "models/phonem.pt"
    
    from thaqib.video.detector import HumanDetector
    
    t0 = time.perf_counter()
    detector_dedicated = HumanDetector()
    detector_dedicated.load()
    load_time = time.perf_counter() - t0
    
    t0 = time.perf_counter()
    result_dedicated = detector_dedicated.detect(frame, frame_index=0, timestamp=0.0)
    detect_time = time.perf_counter() - t0
    
    persons_d = [d for d in result_dedicated.detections if d.class_id == HumanDetector.PERSON_CLASS_ID]
    phones_d = [d for d in result_dedicated.detections if d.class_id == HumanDetector.PHONE_CLASS_ID]
    print(f"Load time: {load_time:.2f}s | Detection time: {detect_time:.3f}s")
    print(f"Detected: {len(persons_d)} persons, {len(phones_d)} phones")
    for i, p in enumerate(phones_d):
        print(f"  Phone {i}: bbox={p.bbox}, conf={p.confidence:.4f}")

    # Configuration 2: Shared phone model (yolo11m.pt)
    print("\n=== CONFIG 2: Shared Phone Model (yolo11m.pt) ===")
    # Clear the lru_cache for get_settings to reload, or just force the settings properties
    # Let's clean up and initialize a new detector by overriding the settings
    settings.phone_model = ""
    
    t0 = time.perf_counter()
    detector_shared = HumanDetector()
    detector_shared.load()
    load_time = time.perf_counter() - t0
    
    t0 = time.perf_counter()
    result_shared = detector_shared.detect(frame, frame_index=0, timestamp=0.0)
    detect_time = time.perf_counter() - t0
    
    persons_s = [d for d in result_shared.detections if d.class_id == HumanDetector.PERSON_CLASS_ID]
    phones_s = [d for d in result_shared.detections if d.class_id == HumanDetector.PHONE_CLASS_ID]
    print(f"Load time: {load_time:.2f}s | Detection time: {detect_time:.3f}s")
    print(f"Detected: {len(persons_s)} persons, {len(phones_s)} phones")
    for i, p in enumerate(phones_s):
        print(f"  Phone {i}: bbox={p.bbox}, conf={p.confidence:.4f}")

    # Save annotated image for the shared model pass since it works best
    annotated = frame.copy()
    for d in persons_s:
        x1, y1, x2, y2 = d.bbox
        cv2.rectangle(annotated, (x1, y1), (x2, y2), (0, 255, 0), 2)
        cv2.putText(annotated, f"Person {d.confidence:.2f}", (x1, y1 - 10),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 2)
                    
    for d in phones_s:
        x1, y1, x2, y2 = d.bbox
        cv2.rectangle(annotated, (x1, y1), (x2, y2), (0, 0, 255), 2)
        cv2.putText(annotated, f"Phone {d.confidence:.2f}", (x1, y1 - 10),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 255), 2)
                    
    output_path = 'testing file/video/annotated_photo_shared.jpg'
    cv2.imwrite(output_path, annotated)
    print(f"\nSaved annotated image to {output_path}")

if __name__ == '__main__':
    test_comparison()
