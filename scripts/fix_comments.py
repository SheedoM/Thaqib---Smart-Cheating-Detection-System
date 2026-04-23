import os
import re

base_dir = "/home/_0xlol/Desktop/shalan"

replacements = {
    "src/thaqib/video/pipeline.py": [
        (
            r"    tracking_result: TrackingResult                     # ⬅️ جبنا ده فوق\n    tools_result: ToolsDetectionResult \| None = None    # ⬅️ ونزلنا ده تحت",
            r"    tracking_result: TrackingResult\n    tools_result: ToolsDetectionResult | None = None"
        ),
        (
            r"# Fix 1: Process pool for face mesh — true CPU parallelism",
            r"# Process pool for face mesh — true CPU parallelism"
        ),
        (
            r"# Double-buffered face mesh jobs: submit on frame N, collect on frame N\+2\.\n\s+# Fix 1: uses multiprocessing\.AsyncResult instead of concurrent\.futures\.Future\.",
            r"# Double-buffered face mesh jobs: submit on frame N, collect on frame N+2."
        ),
        (
            r"# Background archive writer thread \(Fix 2: offload ~1-3ms/frame\)",
            r"# Background archive writer thread (offloads 1-3ms/frame)"
        ),
        (
            r"# Fix 1: Clean up process pool and shared memory",
            r"# Clean up process pool and shared memory"
        ),
        (
            r"\s+# Apply Detection Stability Filter block removed to eliminate tracking artifacts\n",
            r"\n"
        ),
        (
            r"# Collect ALL completed async results from previous cycle \(Fix 1: multiprocessing\)",
            r"# Collect completed async results from previous cycle"
        ),
        (
            r"# Convert plain dict back to FaceMeshResult \(Fix 1\)",
            r"# Convert plain dict back to FaceMeshResult"
        ),
        (
            r"\s+# _process_student_parallel removed \(Fix 1\) — replaced by\n\s+# face_mesh_worker\.extract_in_worker running in child processes\.\n",
            r"\n"
        )
    ],
    "src/thaqib/video/visualizer.py": [
        (
            r'"""\nVideo visualization layer\.\n\nResponsible ONLY for drawing overlays onto frames\.\nDoes NOT perform detection, tracking, registry updates, or neighbor computation\.\n"""',
            r'"""\nVideo visualization layer.\nResponsible ONLY for drawing overlays onto frames.\n"""'
        )
    ],
    "src/thaqib/video/tracker.py": [
        (
            r'"""\nObject tracking using BoT-SORT via boxmot library\.\n\nMaintains persistent identity for detected humans across frames\.\nExtended with per-track bbox smoothing, lost-track memory, and\nID locking\.\n"""',
            r'"""\nObject tracking using BoT-SORT via boxmot library.\nMaintains persistent identity with EMA smoothing and ID locking.\n"""'
        ),
        (
            r"track_buffer=60,\s+# 2s ghost tracks \(was 4s — too long\)",
            r"track_buffer=60,       # 2s ghost tracks"
        )
    ],
    "src/thaqib/video/reid.py": [
        (
            r'"""\nFace-based Re-Identification Module\.\n\nComputes embeddings from Procrustes-normalized 3D face landmarks to maintain\nstudent tracking identity even under challenging conditions \(head rotation up\nto ±45°, partial occlusion, distance variation\)\.\n\nKey improvements over the 7-point baseline:[\s\S]*?tuning\n"""',
            r'"""\nFace-based Re-Identification Module.\nComputes 75-D embeddings from Procrustes-normalized 3D face landmarks.\n"""'
        )
    ],
    "src/thaqib/video/face_mesh.py": [
        (
            r'"""\nFace mesh extraction using MediaPipe Face Landmarker\.\n\nDetects 478 face landmarks in both 2D pixel space and 3D metric space\.\nDoes NOT compute gaze or head pose — only raw mesh geometry\.\n\nUses VIDEO running mode for temporal smoothing \(reduces landmark jitter\nbetween consecutive frames\)\. Each worker thread gets its own landmarker\ninstance via threading\.local\(\) because VIDEO mode is not thread-safe\.\n"""',
            r'"""\nFace mesh extraction using MediaPipe Face Landmarker.\nUses thread-local VIDEO mode for temporal smoothing.\n"""'
        )
    ],
    "src/thaqib/video/face_mesh_worker.py": [
        (
            r'"""\nFace mesh worker for multiprocessing pool \(Fix 1\)\.\n\nEach child process initializes its own FaceLandmarker singleton in IMAGE mode\n\(process-safe, no timestamp tracking needed\)\. Frames are received via shared\nmemory for zero-copy transfer from the main process\.\n\nReturns serializable dicts \(not FaceMeshResult dataclasses\) to avoid pickling\nissues across process boundaries\. The main process converts them back\.\n"""',
            r'"""\nMultiprocessing worker for face mesh extraction using shared memory.\nUses IMAGE mode for process-safe independent frame inference.\n"""'
        )
    ],
    "src/thaqib/video/gaze.py": [
        (
            r'"""\nShared gaze direction computation\.\n\nExtracts a 2D gaze direction vector from a FaceMeshResult using\nMediaPipe\'s head rotation matrix and iris landmark deviations\.\n\nUsed by both pipeline\.py \(cheating evaluation\) and visualizer\.py \(drawing\)\.\n"""',
            r'"""\nShared gaze direction computation.\nExtracts 2D gaze vector using MediaPipe head matrix and iris deviations.\n"""'
        ),
        (
            r"# 3\. Combine in 3D Space \(Coordinate Alignment\)\n\s+# CRITICAL FIX: Invert Eye X-axis to match MediaPipe's 3D Space",
            r"# 3. Combine in 3D Space (Invert Eye X-axis to match MediaPipe 3D Space)"
        )
    ],
    "src/thaqib/video/neighbors.py": [
        (
            r"# Fix 3: Vectorized greedy assignment using argmin — O\(min\(M,N\)\)\n\s+# iterations instead of O\(MN log MN\) sort\.",
            r"# Vectorized greedy assignment using argmin (O(min(M,N)))"
        )
    ],
    "src/thaqib/video/detector.py": [
        (
            r'"""\nHuman detection using YOLOv8\.\n\nProvides periodic detection of human subjects in video frames\.\n"""',
            r'"""\nHuman detection using YOLOv8.\n"""'
        )
    ],
    "src/thaqib/video/cheating_evaluator.py": [
        (
            r'"""\nCheating evaluation module\.\n\nExtracted from pipeline\.py \(P2 Fix 11\) to reduce monolithic complexity\.\nEvaluates gaze-based and phone-based cheating rules synchronously on the\nmain thread to ensure state consistency with the alert recording collector\.\n"""',
            r'"""\nCheating evaluation module.\nEvaluates rules synchronously to ensure state consistency with recording.\n"""'
        )
    ],
    "src/thaqib/video/camera.py": [
        (
            r'"""\nCamera connection handler for IP cameras and webcams\.\n\nProvides a unified interface for capturing frames from various video sources\.\n"""',
            r'"""\nCamera connection handler for IP cameras, webcams, and video files.\n"""'
        )
    ],
    "src/thaqib/video/registry.py": [
        (
            r'"""\nGlobal student spatial registry system\.\n\nStores the spatial state of all tracked students for the current frame\.\n"""',
            r'"""\nGlobal student spatial registry system.\n"""'
        )
    ],
    "scripts/demo_video.py": [
        (
            r'"""\nDemo script for video detection pipeline\.\n\nDemonstrates the full video processing pipeline with webcam or video file\.\nPress \'q\' to quit, \'s\' to select all visible persons, \'t\' to toggle neighbors,\n\'m\' to enter deselect mode \(click a student to remove from monitoring\)\.\n"""',
            r'"""\nDemo script for video detection pipeline.\nSupports webcam/video input and interactive monitoring controls.\n"""'
        )
    ],
    "src/thaqib/config/settings.py": [
        (
            r'"""\nConfiguration management for Thaqib\.\n\nLoads settings from environment variables and \.env file\.\n"""',
            r'"""\nConfiguration management for Thaqib.\n"""'
        )
    ]
}

for rel_path, reps in replacements.items():
    path = os.path.join(base_dir, rel_path)
    if os.path.exists(path):
        with open(path, "r") as f:
            content = f.read()
        
        for old_pattern, new_text in reps:
            content = re.sub(old_pattern, new_text, content)
            
        with open(path, "w") as f:
            f.write(content)
        print(f"Updated {rel_path}")

