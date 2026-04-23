from ultralytics import YOLO
import sys

def inspect(model_path):
    print(f"\n--- Inspecting {model_path} ---")
    try:
        model = YOLO(model_path)
        print("Classes:", model.names)
    except Exception as e:
        print("Error:", e)

inspect('models/best.pt')
inspect('models/thaqib_best.pt')
