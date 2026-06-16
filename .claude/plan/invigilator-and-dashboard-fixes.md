# Implementation Plan: Dashboard / Invigilator UX Fixes + Role Clarifications + Seed Actor Roles

> Planning only. No production code modified here. External Codex/Gemini wrappers
> were unavailable in this environment, so context was gathered with built-in tools.

This plan answers 5 conceptual questions and fixes 7 concrete issues raised in one batch.

---

## Part 0 — Conceptual answers (no code; included so the plan is self-contained)

### Actors of the system (from `src/thaqib/db/models/users.py:6-10` + `core/scoping.py`)
There are exactly **3 roles**, plus the institution hierarchy (university → college, depth capped at 2):

| Role | Who | Scope | Where they live in the UI |
|------|-----|-------|---------------------------|
| `super_admin` | The top owner created by the setup wizard. For a **university** install this is the university administrator; for a **college/standalone** install it's that institution's owner. Seed data should create exactly **one** `super_admin` per seeded institution tree. | Own institution **+ all child colleges** (`accessible_institution_ids`). | `UniversityDashboardPage` if `is_multi_college`, else `DashboardPage` (super-admin nav). |
| `admin` | A control-room operator scoped to specific exams via `ExamAdminAssignment`. Seeded college accounts like `admin_cs`, `admin_eng`, and `admin_bus` must be `admin`, not `super_admin`. | Only exams they are assigned to. | `DashboardPage` (admin nav, can operate cameras/PTT). |
| `invigilator` | Physical hall staff. Assigned to halls via `Assignment.invigilator_id`. | Only their assigned halls/sessions. | `InvigilatorLayout` → `SchedulePage` / `HallMonitoringPage`. |

### "Did I become a super_admin?" → **Yes.**
`setup.py:install_system` always creates the first user with `role="super_admin"` (`setup.py:84-92`), regardless of institution type. So after setup + sign-in you are the university super_admin. The single college you added has **no admin account** yet — the setup wizard only creates colleges, not their admins (`setup.py:96-108`).

### "Should seed data create several super_admins?" → **No.**
The seed data must mirror the three-actor model:
- `super_admin`: exactly one institutional owner for the seed run.
- `admin`: college/control-room operators such as `admin_cs`, `admin_eng`, and `admin_bus`.
- `invigilator`: physical hall staff assigned through `Assignment.invigilator_id`.

In `university` seed mode, `admin` at the university root remains the only `super_admin`. Every college admin account must be `role="admin"`. In `college` seed mode, the standalone `admin` account can remain the single `super_admin` because it is the only institutional owner in that seed tree.

### "Why do I see *Damietta University* listed under *Colleges*?" → **Bug.**
`GET /api/overview/colleges` filters `Institution.id.in_(scope)` where `scope = {university_id} ∪ {college_ids}` (`overview.py:99-103`, `scoping.py:21-31`). The university's **own** id is in scope, so the root institution is rendered as a college card. Fix in Part 1.

### "Where is the Exams page?" → **Bug.**
`SUPER_ADMIN_NAV_ITEMS` (`DashboardPage.tsx:90-95`) contains `home / halls / supervisors / settings` — **no `exams`**. `ExamsTab` only renders when `activeNav === 'exams'` (`DashboardPage.tsx:614`), and `exams` exists only in `ADMIN_NAV_ITEMS`. Since you log in as super_admin, the tab is hidden. Fix in Part 4.

---

## Task Type
- [x] Frontend (LoginPage, DashboardPage nav, HallMonitoringPage redesign)
- [x] Backend (overview colleges scoping, camera offline serialization)
- [x] Data/seed (single super_admin invariant, college admins as admins, camera status, hall 101 third camera offline)

---

## Part 1 — Backend: stop listing the university as a college

**File:** `src/thaqib/api/routes/overview.py:90-154` (`list_colleges`)

Return the **children** for a university, and the **self** card only for a single-tenant install.

```python
@router.get("/colleges")
def list_colleges(db, scope, current_user):
    multi = is_multi_college(db, current_user.institution_id)
    if multi:
        # university → only direct children (colleges), exclude the root itself
        institutions = (
            db.query(Institution)
            .filter(Institution.parent_id == current_user.institution_id)
            .all()
        )
    else:
        # single-tenant college/standalone → the one card (own institution)
        institutions = (
            db.query(Institution)
            .filter(Institution.id == current_user.institution_id)
            .all()
        )
    # ... unchanged per-institution KPI aggregation ...
```

**Also review** `get_summary.active_colleges` (`overview.py:65-81`): it counts distinct `institution_id` of active exams within scope. Since exams are always created under colleges (never the university root), this is already correct, but add a defensive `!= current_user.institution_id` filter for clarity.

**Tests:** extend `tests/test_overview.py` — for a university with N colleges, `/colleges` returns exactly N cards and none has `id == university_id`. For a standalone college, returns 1 card (itself).

---

## Part 2 — Data/seed: one super_admin, college accounts are admin

**Files:**
- `seed_demo.py:12-18` — import `ExamAdminAssignment`.
- `seed_demo.py:200-273` — change `_seed_college_data` so the caller controls the seeded admin role and exam-admin assignment behavior.
- `seed_demo.py:275-350` — call the helper with the correct role for college vs university seed modes.
- `tests/test_seed_demo.py` (or a new seed-focused test file) — cover the seed actor invariant.

### Required seed invariant
Seed data must create only one `super_admin` for the whole seeded institution tree:
- `college` mode: `admin` is the one standalone institution owner and remains `super_admin`.
- `university` mode: root `admin` at the university is the only `super_admin`.
- `admin_cs`, `admin_eng`, and `admin_bus` are `admin` actors, not `super_admin`.
- All invigilator accounts remain `invigilator`.

### Implementation detail
Currently `_seed_college_data` hardcodes the college admin as `role="super_admin"` (`seed_demo.py:204-212`), so university mode creates four super-admins: the root `admin` plus one per college. Change the helper to accept an explicit role:

```python
from src.thaqib.db.models.exams import Assignment, ExamAdminAssignment, ExamSession

def _seed_college_data(
    db,
    blueprint: dict,
    institution_id,
    admin_username: str,
    *,
    admin_role: str = "admin",
    assigned_by_id=None,
) -> None:
    """Create admin, invigilators, halls, and exam sessions for one college."""
    # ...
    admin = User(
        institution_id=institution_id,
        username=admin_username,
        password_hash=get_password_hash(ADMIN_PASSWORD),
        full_name=blueprint.get("admin_fullname", admin_username),
        email=f"{admin_username}@admin.demo",
        role=admin_role,
        status="active",
    )
```

Call it like this:

```python
# Single-college seed: one owner for the standalone institution.
_seed_college_data(
    db,
    CS_BLUEPRINT,
    inst.id,
    admin_username="admin",
    admin_role="super_admin",
)

# University seed: root admin is already the sole super_admin; college accounts are admins.
_seed_college_data(
    db,
    blueprint,
    college.id,
    admin_username=admin_username,
    admin_role="admin",
    assigned_by_id=university_admin.id,
)
```

Because `admin` users only see exams through `ExamAdminAssignment`, also attach each seeded college admin to the sessions created for their college. Prefer `created_by=admin.id` for seeded exams (the admin created the exam, the invigilator monitors the hall), and add an admin assignment only when the seeded admin role is `admin`:

```python
session = ExamSession(
    institution_id=institution_id,
    exam_name=exam_name,
    exam_type=exam_type,
    scheduled_start=start,
    scheduled_end=start + timedelta(hours=duration_h),
    status="scheduled",
    student_count=students,
    configuration={"sensitivity": "high"},
    created_by=admin.id,
)
session.halls.append(hall)
db.add(session)
db.flush()

if admin.role == "admin":
    db.add(ExamAdminAssignment(
        exam_session_id=session.id,
        admin_id=admin.id,
        assignment_role="lead",
        assigned_by=assigned_by_id or admin.id,
    ))
```

Keep the existing `Assignment(...)` row for the invigilator unchanged.

**Tests:** add a seed-aware test that runs `seed_university(db_session)` and asserts:
- exactly one user has `role == "super_admin"`, and its username is `admin`;
- `admin_cs`, `admin_eng`, and `admin_bus` all have `role == "admin"`;
- invigilator accounts still have `role == "invigilator"`;
- each seeded college admin has `ExamAdminAssignment` rows for that college's seeded exams, so `/api/sessions` will not be empty when logging in as `admin_cs`.

---

## Part 3 — Backend + seed: cameras with no stream URL are "offline"

### 3a. Serialization (single source of truth)
**File:** `src/thaqib/api/routes/stream.py:229-242` (`_serialize_camera`)

Derive status from whether a source is configured, instead of echoing the raw DB value:

```python
def _serialize_camera(device, hall, runtime):
    source = (device.stream_url or "").strip()
    is_running = runtime is not None and runtime.stats.get("is_running", False)
    if not source:
        status = "offline"
    elif is_running:
        status = "online"
    else:
        status = device.status or "offline"
    return { ... "status": status, "active": is_running,
             "feed_path": f"/api/stream/feed/{device.id}" if source else None,
             "source_configured": bool(source), ... }
```

Readiness already reports "failed / stream URL not configured" (`exams.py:38-48`) — no change needed there. The frontend `CamerasTab` (`DashboardPage.tsx:842-879`) already shows "الكاميرا غير متصلة" when `!feed_path`, so this mainly makes the `status` field truthful for any consumer.

### 3b. Seed: status follows stream_url + hall 101 third camera offline
**File:** `seed_demo.py:162-197` (`_create_hall`)

Currently all 3 cams (`front/back/side`) of a `demo_video` hall get a stream URL and `status="online"`. Change so:
- A camera's `status` is `"online"` only when it has a stream URL, else `"offline"`.
- The **third** camera (`"side"`) of demo-video halls (Hall 101) is intentionally offline.

```python
OFFLINE_KEYS = {"side"}  # third camera is intentionally offline in the demo
for key in ("front", "back", "side"):
    video = CAM_VIDEO[key]
    has_source = use_video and video.exists() and key not in OFFLINE_KEYS
    cam = Device(
        hall_id=hall.id, type="camera",
        identifier=f"{spec['name']}-cam-{key}",
        stream_url=str(video) if has_source else None,
        position={"label": CAM_LABEL[key]},
        status="online" if has_source else "offline",
    )
```

Result: Hall 101 → front + back stream (online), side = offline. This **also** reduces Hall 101's invigilator grid from 3 → 2 configured feeds (clean 2-up grid), complementing Part 6.

**Tests:** `tests/test_infrastructure.py` / seed-aware test — a camera with `stream_url=None` serializes with `status == "offline"` and `feed_path is None`.

---

## Part 4 — Frontend: expose the Exams tab to super_admin

**File:** `frontend/src/pages/DashboardPage.tsx:90-95`

Add `exams` to the super-admin nav (placed after `home`):

```ts
const SUPER_ADMIN_NAV_ITEMS = [
  { label: 'الرئيسية',   key: 'home',        active: true },
  { label: 'الإمتحانات', key: 'exams',       active: false },
  { label: 'القاعات',    key: 'halls',       active: false },
  { label: 'المشرفين',   key: 'supervisors', active: false },
  { label: 'الإعدادات',  key: 'settings',    active: false },
];
```

`ExamsTab` already renders for `activeNav === 'exams'` (`DashboardPage.tsx:614-615`) — no other wiring needed. Verify `ExamsTab` API calls authorize for super_admin (it uses `_require_exam_observer`, which short-circuits for super_admin at `exams.py:166-168`).

---

## Part 5 — Frontend: show/hide password toggle on login

**File:** `frontend/src/pages/LoginPage.tsx:80-89`

Wrap the password input, add an eye toggle (lucide `Eye`/`EyeOff`, already a dependency).

```tsx
const [showPassword, setShowPassword] = useState(false);
// ...
<div className="relative w-full">
  <input
    type={showPassword ? 'text' : 'password'}
    name="password"
    placeholder="كلمة المرور"
    value={formData.password}
    onChange={handleInputChange}
    className="thaqib-input pl-11"   /* room for the icon (LTR side in RTL layout) */
    required
  />
  <button
    type="button"
    onClick={() => setShowPassword(v => !v)}
    className="absolute inset-y-0 left-3 flex items-center text-gray-400 hover:text-gray-600"
    aria-label={showPassword ? 'إخفاء كلمة المرور' : 'إظهار كلمة المرور'}
    tabIndex={-1}
  >
    {showPassword ? <EyeOff size={18} /> : <Eye size={18} />}
  </button>
</div>
```

Note `dir="rtl"`: place the icon on the visual left (`left-3`) and pad with `pl-11`. Update `frontend/src/test/SetupWizard.test.tsx` only if it asserts on the login DOM (it likely doesn't).

---

## Part 6 — Frontend: invigilator monitoring UI parity with admin dashboard

Goal: reuse the admin look-and-feel, kill the empty "4th black box", and stop the PTT button from covering the video.

**File:** `frontend/src/pages/invigilator/HallMonitoringPage.tsx`

### 6a. Fix the grid (root cause of the "4th black box")
`HallMonitoringPage.tsx:258-263` hardcodes `grid-cols-2` for >1 feed. With 3 feeds that yields a 2×2 grid with one empty (black) cell. Use a column count derived from the feed count:

```tsx
const cols =
  configuredFeeds.length <= 1 ? 'grid-cols-1' :
  configuredFeeds.length === 2 ? 'grid-cols-2' :
  configuredFeeds.length === 3 ? 'grid-cols-3' :
  'grid-cols-2';           // 4+ → 2 columns
<div className={`grid gap-1 p-1 ${cols}`}> ... </div>
```

(With Part 3b, Hall 101 drops to 2 feeds, but this fix is required generally.)

### 6b. Move PTT out of the video overlay
Currently the talk button is `absolute bottom-4` over the feed (`HallMonitoringPage.tsx:308-327`). Remove that floating button and instead render a **dedicated control bar** under the video (or in the top breadcrumb), mirroring `HallVoiceControl` from the admin dashboard (`DashboardPage.tsx:130-212`): a status pill + a "تحدث مع القاعة" press-and-hold button that is **not** layered over the stream. Keep the connecting/error banners but render them in the info panel, not floating over the feed.

### 6c. Tabs to match the admin dashboard
Restructure the page body into two tabs like `DashboardPage` (`activeTab: 'cameras' | 'cases'`):
- **المراقبة (cameras):** the live grid (6a) + voice control bar (6b).
- **الحالات (cases/alerts):** the existing alerts list/`AlertReviewModal` block (`HallMonitoringPage.tsx:441-486`, `583-687`) moved under this tab.

### 6d. Extract a shared feed-grid component — **CONFIRMED IN SCOPE** (user chose "Full parity + shared component")
Extract the camera-tile rendering into a shared component `frontend/src/components/CameraFeedGrid.tsx` consumed by **both** `DashboardPage.CamerasTab` ([DashboardPage.tsx:837-911](frontend/src/pages/DashboardPage.tsx:837)) and the invigilator page, so styling stays identical. The component owns: the dynamic column count (6a), per-tile status dot / placeholder / "offline" states, click-to-enlarge, and the live `<img>` MJPEG source. Admin passes camera stats + alert overlays; invigilator passes feeds + enlarge handler. This is the canonical "reuse the same UI" deliverable.

---

## Part 7 — Diagnose the invigilator blank page (needs runtime reproduction)

Static review of the invigilator path shows no obvious crash:
- `App.tsx:131-139` routes `invigilator` → `InvigilatorLayout` → index `SchedulePage`.
- `SchedulePage` fetches `/api/sessions/my`; backend returns a JSON array (`exams.py:170-196`). On non-OK it sets an error string (not blank).

Because it can't be reproduced from source alone, this needs the running app:

1. **Reproduce** with the seeded invigilator (`invigilator` / `Demo12345!`) and open the browser **console + network** tab.
2. Most likely candidates to confirm/fix:
   - An **uncaught render error** (no React error boundary exists in `App.tsx` → a throw paints a white screen). → Add a top-level error boundary so failures render a message instead of blank.
   - `/api/sessions/my` returning a non-array (e.g. an error object) → `.filter` throws. Guard: `setAssignments(Array.isArray(data) ? data : [])` in `SchedulePage.tsx:27`.
   - A stale/blank route (URL not under `/invigilator`) — confirm the `Navigate` fallback fires.
3. Add the error boundary regardless (cheap insurance for every role), then fix the specific cause found in step 1.

> This item is intentionally diagnostic-first rather than a blind code change, since the root cause isn't determinable from static reading.

---

## Key Files

| File | Operation | What |
|------|-----------|------|
| `src/thaqib/api/routes/overview.py:90-154` | Modify | `list_colleges` returns children (university) / self (single-tenant), never the root as a college |
| `src/thaqib/api/routes/stream.py:229-242` | Modify | `_serialize_camera` → `status="offline"` when no `stream_url` |
| `seed_demo.py:200-350` | Modify | one seeded `super_admin`; `admin_cs`/`admin_eng`/`admin_bus` use `role="admin"` and receive exam assignments |
| `seed_demo.py:162-197` | Modify | camera status follows `stream_url`; Hall 101 "side" cam offline |
| `frontend/src/pages/DashboardPage.tsx:90-95` | Modify | add `exams` to `SUPER_ADMIN_NAV_ITEMS` |
| `frontend/src/pages/LoginPage.tsx:80-89` | Modify | password show/hide toggle |
| `frontend/src/pages/invigilator/HallMonitoringPage.tsx:258-327, 441-486` | Modify | dynamic grid cols, PTT out of overlay, tabbed layout |
| `frontend/src/components/CameraFeedGrid.tsx` | Create (opt.) | shared feed grid for admin + invigilator |
| `frontend/src/App.tsx` | Modify | add top-level error boundary (Part 7) |
| `tests/test_seed_demo.py` | Modify | cover seeded actor roles and college admin exam assignments |
| `tests/test_overview.py`, `tests/test_infrastructure.py` | Modify | cover Parts 1 & 3 |

## Risks & Mitigation
| Risk | Mitigation |
|------|------------|
| Changing `list_colleges` breaks single-tenant card | Branch on `is_multi_college`; keep self-card path; add both test cases |
| Changing college seed accounts to `admin` makes their dashboard empty | Create `ExamAdminAssignment` rows for every seeded exam created for that college admin |
| Marking cams offline hides a genuinely-online camera that simply lacks a URL in DB | "Offline" is correct by the stated rule (no stream URL ⇒ offline); production cams must have a URL |
| Invigilator UI refactor regresses the voice/PTT flow | Keep `useHallVoice` wiring intact; only relocate the button + reflow grid; test press-and-hold on touch + mouse |
| Blank-page fix without repro | Add error boundary first (safe), then confirm exact cause via console before further edits |
| Seed reshuffles demo expectations | Re-run `python seed_demo.py university`, verify exactly one `super_admin`, `admin_cs` can see CIS exams, and Hall 101 shows 2 live + 1 offline cam |

## Suggested order
1. Part 2 (seed actor roles + exam admin assignments) →
2. Part 3b + Part 4 + Part 5 (small, high-value, low-risk) →
3. Part 1 + Part 3a (backend scoping/serialization + tests) →
4. Part 7 error boundary, then reproduce blank page →
5. Part 6 invigilator UI redesign (largest; do last).

### SESSION_ID (for /ccg:execute)
- CODEX_SESSION: n/a (external model wrapper not installed in this environment)
- GEMINI_SESSION: n/a
