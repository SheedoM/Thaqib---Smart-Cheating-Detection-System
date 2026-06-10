import cv2
from ultralytics import YOLO

def debug_yolo():
    image_path = 'testing file/video/photo_2026-06-10_12-13-02.jpg'
    model_path = 'models/phonem.pt'
    
    print("Loading model...")
    model = YOLO(model_path)
    
    print("Reading image...")
    img = cv2.imread(image_path)
    
    print("Running YOLO inference with verbose=True...")
    results = model(img, conf=0.01, verbose=True, imgsz=640)
    
    print("Detections:")
    for result in results:
        boxes = result.boxes
        if boxes is None or len(boxes) == 0:
            print("No bounding boxes detected.")
            continue
        for i in range(len(boxes)):
            box = boxes[i]
            xyxy = box.xyxy[0].cpu().numpy().tolist()
            conf = float(box.conf[0])
            cls_id = int(box.cls[0])
            label = result.names[cls_id]
            print(f"Index {i}: bbox={xyxy}, conf={conf:.4f}, cls_id={cls_id}, label={label}")

if __name__ == '__main__':
    debug_yolo()
