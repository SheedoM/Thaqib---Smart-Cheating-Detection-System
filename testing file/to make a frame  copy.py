import cv2, os

# ← حط اسم الفيديو هنا
video_path = '/home/_0xlol/Desktop/shalan/ved/IMG_5123.MOV'

os.makedirs('frames', exist_ok=True)

cap = cv2.VideoCapture(video_path)
fps = cap.get(cv2.CAP_PROP_FPS)
interval = int(fps * 5)  # صورة كل 5 ثواني

count = 0
saved = 0

while True:
    ret, frame = cap.read()
    if not ret:
        break
    if count % interval == 0:
        cv2.imwrite(f'/home/_0xlol/Desktop/frames/v2/frame_{saved}.jpg', frame)
        saved += 1
    count += 1

cap.release()
print(f"✅ اتحفظ {saved} صورة في مجلد frames!")