# Pipeline ↔ Dashboard Integration Plan (v3 — Final)

## Problem Summary

| # | Issue | Severity |
|---|-------|----------|
| 1 | `stream.py` annotations reference **non-existent attributes** — crashes silently | 🔴 Breaking |
| 2 | `on_alert` callback references `state.looking_at_neighbor_id` — **alerts never register** | 🔴 Breaking |
| 3 | Alert modal shows **static JPEG**, but pipeline saves **`.avi` video clips** | 🟡 Major |
| 4 | All cameras point to **same `/feed` endpoint** — identical streams | 🟡 Major |
| 5 | Dashboard layout is **horizontally flipped** vs Figma (RTL issues) | 🟠 Bug |
| 6 | No real-time alert notifications on camera cards, no keystroke actions in modal | 🟠 Feature |

## Video Source Paths

- **Front angle**: `C:\Users\shady\Videos\0417.mp4`
- **Back angle**: `C:\Users\shady\Downloads\20260414_132048.mp4`

---

## Proposed Changes

### Phase 1: Fix Broken `stream.py` (Pipeline ↔ Stream Bridge)

#### [MODIFY] [stream.py](file:///f:/University/Graduation%20project_Smart%20Cheating%20System/Thaqib---Smart-Cheating-Detection-System/src/thaqib/api/routes/stream.py)

**1. Replace `_draw_annotations` with `VideoVisualizer`**

The current `_draw_annotations()` references dead attributes. Replace with:

```python
from thaqib.video.visualizer import VideoVisualizer
# Each PipelineInstance gets its own visualizer
annotated = visualizer.draw(pipeline_frame, registry=pipeline_frame.registry)
```

This is the exact same call `demo_video.py` uses — web stream = OpenCV window output.

**2. Fix `on_alert` metadata tracking**

The pipeline's `CheatingEvaluator` already saves `.avi` videos to `alerts/`. The `on_alert` callback only needs to **record metadata** so the dashboard can list and play them. Fix the broken attribute references:

```python
def on_alert(state):
    alert_data = {
        "id": str(uuid.uuid4()),
        "track_id": state.track_id,
        "event_type": "استخدام هاتف" if getattr(state, 'is_using_phone', False) else "نسخ من الجار",
        "severity": "high",
        "timestamp": datetime.now().isoformat(),
        "camera_id": camera_id,
        "location": f"الطالب رقم {state.track_id}",
    }
```

**3. Add video file serving endpoint**

```
GET /api/stream/alerts/video/{filename}  →  FileResponse(.avi/.mp4)
```

**4. Enhance alert list with video file discovery**

`GET /api/stream/alerts` scans `alerts/` directory for video files matching each alert's track_id, attaching `video_file` to the response.

---

### Phase 2: Multi-Camera Pipeline Manager

#### [MODIFY] [stream.py](file:///f:/University/Graduation%20project_Smart%20Cheating%20System/Thaqib---Smart-Cheating-Detection-System/src/thaqib/api/routes/stream.py)

Replace all globals with a `PipelineManager` class:

```python
class PipelineInstance:
    thread: Thread
    pipeline: VideoPipeline          # Direct reference to control it
    visualizer: VideoVisualizer      # Per-camera visualizer state  
    latest_frame: bytes | None
    frame_lock: Lock
    stats: dict
    is_running: bool
    source: str
    camera_id: str

class PipelineManager:
    _instances: dict[str, PipelineInstance] = {}
    _alerts: list[dict] = []         # Shared across all cameras
    _exam_active: bool = True        # Default True for demo (see note below)
```

**Endpoints:**

| Endpoint | Purpose |
|----------|---------|
| `GET /api/stream/start/{camera_id}?source=...` | Start a specific camera pipeline |
| `GET /api/stream/stop/{camera_id}` | Stop a specific camera |
| `GET /api/stream/feed/{camera_id}` | MJPEG stream for a specific camera |
| `GET /api/stream/status/{camera_id}` | Stats for a specific camera |
| `POST /api/stream/exam/start` | Set `_exam_active = True`, start hall cameras |
| `POST /api/stream/exam/stop` | Set `_exam_active = False`, stop all pipelines |
| `GET /api/stream/cameras` | List cameras from DB with pipeline status |
| `POST /api/stream/{camera_id}/action` | Execute visualizer action (see Phase 4b) |

**`_exam_active` variable:**
- Defaults to `True` for the referee (admin) dashboard — cameras auto-start
- When you later build the **invigilator dashboard**, you'll:
  - Default this to `False` for invigilator sessions
  - Wire the invigilator's "بدء الاختبار" button to `POST /exam/start`
  - Also need to implement **invigilator credentials/auth** (not yet in the system)

> [!NOTE]
> **Future TODO for invigilator dashboard**: The current auth system only has `admin`, `invigilator`, and `referee` roles. Invigilator login credentials are not yet configurable from the admin UI. This should be addressed when building the invigilator dashboard.

Old `/feed` and `/start` endpoints remain as aliases for backward compat.

---

### Phase 3: Seed Demo Data

#### [NEW] [seed_demo.py](file:///f:/University/Graduation%20project_Smart%20Cheating%20System/Thaqib---Smart-Cheating-Detection-System/scripts/seed_demo.py)

| Hall | Cameras | Mics | Status |
|------|---------|------|--------|
| **قاعة 101** | كاميرا 1 - أمامية (`0417.mp4`), كاميرا 2 - خلفية (`20260414_132048.mp4`) | ميكروفون 1, ميكروفون 2 | `ready` |
| **قاعة 102** | كاميرا 1 - أمامية (placeholder), كاميرا 2 - خلفية (placeholder) | ميكروفون 1, ميكروفون 2 | `not_ready` |
| **قاعة 103** | كاميرا 1 - أمامية (placeholder), كاميرا 2 - خلفية (placeholder) | ميكروفون 1, ميكروفون 2 | `not_ready` |

Each camera gets a unique `identifier` (e.g., `hall101_cam_front`) used as `camera_id`.

---

### Phase 4: Frontend Dashboard Overhaul

#### [MODIFY] [DashboardPage.tsx](file:///f:/University/Graduation%20project_Smart%20Cheating%20System/Thaqib---Smart-Cheating-Detection-System/frontend/src/pages/DashboardPage.tsx)

**4a. Fix RTL layout (horizontal flip vs Figma)**

Audit and fix CSS `flex-direction`, alignment, and positioning to match the Figma's RTL layout — logo right, user area left, etc.

**4b. Dynamic hall/camera rendering**

Replace hardcoded halls with data from `GET /api/stream/cameras`. For `ready` halls, cameras auto-start (since `_exam_active = True`). For `not_ready` halls, cameras show "الكاميرا غير متصلة" placeholder.

**4c. Real-time alert on camera cards (5 seconds)**

When a new alert arrives:
1. Camera card border **blinks red** (`camera-feed-alert` class — already in CSS)
2. Stats bar at bottom **transforms into alert bar**: shows cheating type + "عرض الحالة" button
3. After **5 seconds**, the alert bar fades back to normal stats
4. Clicking "عرض الحالة" opens `CameraModal` in alert mode (video playback)
5. Alert permanently added to "أخر الحالات" tab

*(No separate toast notification — the alert bar on the camera card is the notification itself.)*

**4d. Remove auto pipeline start on mount**

Replace with a status check: if `_exam_active` is `True`, start camera feeds immediately. Otherwise wait for the "Start Exam" trigger (future invigilator dashboard feature).

---

#### [MODIFY] [CameraModal.tsx](file:///f:/University/Graduation%20project_Smart%20Cheating%20System/Thaqib---Smart-Cheating-Detection-System/frontend/src/components/CameraModal.tsx)

**4e. Alert video playback**

Replace `<img>` in `AlertView` with `<video>` player:

```tsx
{alert.video_file ? (
    <video src={`${API_BASE}/alerts/video/${alert.video_file}`}
           controls autoPlay className="modal-video-player" />
) : (
    <img src={`${API_BASE}/alerts/snapshot/${alert.snapshot_file}`}
         className="modal-video-img" />
)}
```

**4f. Camera view: ALL action buttons** ⭐

When user clicks a camera feed on the main page, the modal opens with the enlarged live feed + action buttons. These replicate **every** feature from `demo_video.py` + the visualizer toggles:

| Button | Maps to | Function | API Action |
|--------|---------|----------|------------|
| 👁️ تحديد الكل | `s` | Select all visible students for monitoring | `select_all` |
| ❌ إلغاء التحديد | `c` | Clear all selections | `clear_selection` |
| 🔗 عرض الجيران | `t` | Toggle neighbor graph overlay (lines between students) | `toggle_neighbors` |
| 📊 لوحة التحكم | `p` | Toggle control panel overlay (stats panel on video) | `toggle_panel` |
| 📱 إظهار الهواتف | — | Toggle phone detection bounding boxes | `toggle_phones` |
| 📄 إظهار الأوراق | — | Toggle paper/book detection bounding boxes + paper lines | `toggle_papers` |

The `toggle_phones` and `toggle_papers` map to the visualizer's `show_phone` and `show_paper` flags (which are `True` by default but have no keyboard shortcut in demo_video.py — we're exposing them as UI buttons).

Each button calls:
```
POST /api/stream/{camera_id}/action  { "action": "select_all" | "clear_selection" | ... }
```

The **main dashboard page only shows clean camera streams** — all controls are inside the modal.

**4g. Accept `cameraId` prop**

`CameraModal` receives the camera ID so it fetches from `/feed/{camera_id}`.

---

### Phase 5: PTT Invigilator Connection

#### [MODIFY] [DashboardPage.tsx](file:///f:/University/Graduation%20project_Smart%20Cheating%20System/Thaqib---Smart-Cheating-Detection-System/frontend/src/pages/DashboardPage.tsx)

The "الاتصال بالمراقب" button:
- Opens a **calling overlay** with a pulsing phone icon
- Connects to `ws://localhost:8000/api/ptt/ws/control_room_{hallId}`
- Sends `{"type": "start_speak", "target_id": "invigilator_{hallId}"}`
- For demo: shows visual calling state → "المراقب غير متصل حالياً" (since no mobile app yet)

---

### Phase 6: CSS Polish

#### [MODIFY] [index.css](file:///f:/University/Graduation%20project_Smart%20Cheating%20System/Thaqib---Smart-Cheating-Detection-System/frontend/src/index.css)

New styles:
- `.camera-alert-bar` — red gradient bar replacing stats during active alert (5s)
- `.camera-alert-bar-btn` — "عرض الحالة" inline button
- `.modal-video-player` — styled `<video>` element
- `.modal-action-buttons` — grid of 6 action buttons in camera modal
- `.modal-action-btn` — individual action button with icon
- `.modal-action-btn.active` — highlighted state for toggles
- `.ptt-overlay` — calling indicator overlay
- RTL layout fixes for navbar/subheader alignment

---

## Execution Order

```
Phase 1 → Phase 2 → Phase 3 → Phase 6 → Phase 4 → Phase 5
(backend)  (backend)  (seed)    (CSS)     (React)    (PTT)
```

## Verification Plan

### Automated Tests
1. `GET /api/stream/cameras` → returns 3 halls with 2 cameras + 2 mics each
2. `GET /api/stream/feed/hall101_cam_front` → returns MJPEG frames
3. `GET /api/stream/feed/hall101_cam_back` → returns different MJPEG frames
4. Wait for cheating → `GET /api/stream/alerts` includes `video_file` field
5. `GET /api/stream/alerts/video/{file}` → serves the `.avi` file
6. `POST /api/stream/hall101_cam_front/action {"action":"toggle_neighbors"}` → 200 OK

### Manual Verification (Browser)
1. Login → Dashboard loads with 3 halls from DB
2. Hall 101 cameras auto-start (both front + back feeds visible)
3. Hall 102/103 cameras show "الكاميرا غير متصلة" (offline)
4. Click camera feed → modal opens with 6 action buttons
5. Click "عرض الجيران" → neighbor graph appears on enlarged feed
6. Wait for cheating → camera card blinks red, alert bar appears for 5s
7. Click "عرض الحالة" → modal with **video playback**
8. Switch to "أخر الحالات" tab → alert listed permanently
9. Click "الاتصال بالمراقب" → calling indicator → "not connected" message
