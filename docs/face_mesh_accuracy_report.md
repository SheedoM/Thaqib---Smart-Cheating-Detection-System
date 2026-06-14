# Face Mesh Accuracy & Detection Report

You asked how to increase the accuracy of the face mesh drawing to ensure that faces are detected for all students, including those currently being missed.

Based on the analysis of `src/thaqib/video/face_mesh.py`, there are several strict constraints currently configured in the code that are causing some students to be skipped. 

Here are the specific ways to increase accuracy:

### 1. Lower MediaPipe Confidence Thresholds
In `FaceMeshExtractor._get_landmarker()`, the MediaPipe model is configured with extremely strict confidence thresholds:
- `min_face_detection_confidence = 0.80`
- `min_face_presence_confidence = 0.80`
- `min_tracking_confidence = 0.80`

**Recommendation:** Lower these values to `0.50` or `0.60`. A threshold of 0.80 is very high and will reject faces that are slightly blurry, turned sideways, looking down, or far away from the camera.

### 2. Expand the Head Crop Region (Y-Axis)
Currently, the code tries to isolate the head by aggressively cropping the top 40% of the student's body bounding box (`y2 = y1 + int(body_height * 0.40)`).
- **The Issue:** If a student is slumped over their desk, leaning forward, or sitting in an unusual posture, their face might fall *below* the top 40% of their bounding box, meaning their face is physically cut out of the image before the face detector even sees it.
- **Recommendation:** Increase the crop region to the top 50% or 60% of the bounding box (`int(body_height * 0.60)`).

### 3. Remove or Lower the Hard Size Cutoff
There is a hardcoded rule that skips face detection entirely if the cropped head region is smaller than 40x40 pixels:
```python
if crop_w < 40 or crop_h < 40:
    return self._get_cached(track_id, reason="small_crop")
```
- **The Issue:** For students sitting in the back rows of a large exam hall, their head crop might naturally be 30x30 pixels.
- **Recommendation:** Lower this threshold to `20` or remove it entirely to allow the system to attempt detection on smaller, distant faces.

### 4. Increase Bounding Box Padding
After cropping the top 40%, the code applies a 15% padding around the head.
- **The Issue:** MediaPipe performs best when it can see some context around the face (hair, ears, neck). A tight 15% crop might chop off the chin or forehead depending on the YOLO bounding box accuracy.
- **Recommendation:** Increase the padding from `0.15` (15%) to `0.30` (30%).

### Summary
By adjusting these 4 parameters in `src/thaqib/video/face_mesh.py`, the system will stop discarding marginal or distant faces, resulting in meshes being drawn for far more students.
