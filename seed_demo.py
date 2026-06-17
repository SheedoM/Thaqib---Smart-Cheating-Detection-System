"""
Demo seed for the Thaqib monitoring dashboard.

Two modes (choose via command-line argument):
  python seed_demo.py college     — single-college institution  (default)
  python seed_demo.py university  — university with three colleges

Optional simulator URL:
  python seed_demo.py college --simulator-base-url http://192.168.1.10:8000

Each mode is fully self-contained: wipes ALL existing data (institutions,
users, halls, devices, exams, alerts) and rebuilds from scratch.
No setup wizard required.

Credentials
  Admin password : Admin12345!
  Invigilator pw : Demo12345!
"""

from __future__ import annotations

import argparse
import logging
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path

from src.thaqib.db.database import SessionLocal
from src.thaqib.db.models.events import Alert, DetectionEvent, GroupEvent
from src.thaqib.db.models.exams import Assignment, ExamAdminAssignment, ExamSession
from src.thaqib.db.models.infrastructure import Device, Hall, Institution
from src.thaqib.db.models.users import RefreshToken, User
from src.thaqib.core.security import get_password_hash

logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger(__name__)

ROOT = Path(__file__).resolve().parent
VIDEO_DIR = ROOT / "simulator" / "test_videos"

ADMIN_PASSWORD = "Admin12345!"
INVIG_PASSWORD = "Demo12345!"

CAM_VIDEO = {
    "front": VIDEO_DIR / "cam1.mp4",
    "back":  VIDEO_DIR / "cam2.mp4",
    "side":  VIDEO_DIR / "cam1.mp4",
}
CAM_LABEL = {
    "front": "الكاميرا الأمامية",
    "back":  "الكاميرا الخلفية",
    "side":  "الكاميرا الجانبية",
}
SIMULATOR_BASE_URL = os.environ.get("SIMULATOR_BASE_URL", "http://localhost:8000").rstrip("/")

# ─── College blueprints ────────────────────────────────────────────────────────
#
# Each blueprint fully describes one college's halls, staff, and exam schedule.
# hall["demo_video"] = True  →  cameras and microphones get simulator stream URLs.
#
# Schedule row: (exam_name, exam_type, day_offset, start_hour, duration_h,
#                hall_name, student_count, invigilator_username)

CS_BLUEPRINT = {
    "name":          "كلية الحاسوب والمعلومات",
    "code":          "CIS",
    "contact_email": "info@cis.demo",
    "halls": [
        {"name": "قاعة 101", "capacity": 120, "demo_video": True},
        {"name": "قاعة 102", "capacity": 100, "demo_video": False},
        {"name": "قاعة 103", "capacity": 80,  "demo_video": False},
    ],
    "invigilators": [
        ("invigilator", "المراقب الرئيسي", "invigilator@cis.demo"),
        ("a.mahmoud",   "أحمد محمود",      "a.mahmoud@cis.demo"),
        ("f.ali",       "فاطمة علي",       "f.ali@cis.demo"),
    ],
    "schedule": [
        ("اختبار نهائي — مقدمة في علوم الحاسب",  "final",   0,   9, 3, "قاعة 101", 96, "invigilator"),
        ("اختبار منتصف الفصل — قواعد البيانات",   "midterm", 2,  10, 2, "قاعة 101", 88, "invigilator"),
        ("اختبار نهائي — الرياضيات المتقطعة",     "final",   5,   9, 3, "قاعة 101", 72, "invigilator"),
        ("اختبار منتصف الفصل — هياكل البيانات",   "midterm", 0,  14, 2, "قاعة 102", 78, "a.mahmoud"),
        ("اختبار نهائي — البرمجة الكائنية",       "final",   3,   9, 3, "قاعة 102", 90, "a.mahmoud"),
        ("اختبار منتصف الفصل — الشبكات",         "midterm", 6,  11, 2, "قاعة 102", 65, "a.mahmoud"),
        ("اختبار نهائي — الجبر الخطي",           "final",   0,  16, 3, "قاعة 103", 64, "f.ali"),
        ("اختبار منتصف الفصل — أمن المعلومات",   "midterm", 4,  10, 2, "قاعة 103", 55, "f.ali"),
        ("اختبار نهائي — الذكاء الاصطناعي",      "final",   7,   9, 3, "قاعة 103", 80, "f.ali"),
    ],
}

ENG_BLUEPRINT = {
    "name":          "كلية الهندسة",
    "code":          "ENG",
    "contact_email": "info@eng.demo",
    "halls": [
        {"name": "قاعة 201", "capacity": 130, "demo_video": False},
        {"name": "قاعة 202", "capacity": 110, "demo_video": False},
        {"name": "قاعة 203", "capacity": 90,  "demo_video": False},
    ],
    "invigilators": [
        ("m.hassan",  "محمد حسن",     "m.hassan@eng.demo"),
        ("s.ibrahim", "سارة إبراهيم", "s.ibrahim@eng.demo"),
        ("k.omar",    "خالد عمر",     "k.omar@eng.demo"),
    ],
    "schedule": [
        ("اختبار نهائي — الديناميكا الحرارية",      "final",   0,  10, 3, "قاعة 201", 85, "m.hassan"),
        ("اختبار منتصف الفصل — الدوائر الكهربائية", "midterm", 3,   9, 2, "قاعة 201", 70, "m.hassan"),
        ("اختبار نهائي — الميكانيكا التطبيقية",     "final",   6,   9, 3, "قاعة 201", 60, "m.hassan"),
        ("اختبار منتصف الفصل — الرياضيات الهندسية", "midterm", 0,  15, 2, "قاعة 202", 95, "s.ibrahim"),
        ("اختبار نهائي — الإلكترونيات",             "final",   4,  10, 3, "قاعة 202", 80, "s.ibrahim"),
        ("اختبار منتصف الفصل — تصميم الأنظمة",      "midterm", 7,  11, 2, "قاعة 202", 55, "s.ibrahim"),
        ("اختبار نهائي — هندسة البرمجيات",          "final",   0,  13, 3, "قاعة 203", 75, "k.omar"),
        ("اختبار منتصف الفصل — إدارة المشاريع",     "midterm", 5,  10, 2, "قاعة 203", 65, "k.omar"),
        ("اختبار نهائي — أنظمة التحكم",             "final",   8,   9, 3, "قاعة 203", 50, "k.omar"),
    ],
}

BUS_BLUEPRINT = {
    "name":          "كلية إدارة الأعمال",
    "code":          "BUS",
    "contact_email": "info@bus.demo",
    "halls": [
        {"name": "قاعة 301", "capacity": 150, "demo_video": False},
        {"name": "قاعة 302", "capacity": 120, "demo_video": False},
        {"name": "قاعة 303", "capacity": 100, "demo_video": False},
    ],
    "invigilators": [
        ("n.youssef", "نور يوسف",   "n.youssef@bus.demo"),
        ("r.kamal",   "رانيا كمال", "r.kamal@bus.demo"),
        ("t.saad",    "طارق سعد",   "t.saad@bus.demo"),
    ],
    "schedule": [
        ("اختبار نهائي — مبادئ التسويق",            "final",   0,  11, 3, "قاعة 301", 110, "n.youssef"),
        ("اختبار منتصف الفصل — الاقتصاد الجزئي",    "midterm", 2,   9, 2, "قاعة 301",  95, "n.youssef"),
        ("اختبار نهائي — إدارة الموارد البشرية",     "final",   5,  10, 3, "قاعة 301",  88, "n.youssef"),
        ("اختبار منتصف الفصل — المحاسبة المالية",    "midterm", 0,  14, 2, "قاعة 302", 100, "r.kamal"),
        ("اختبار نهائي — استراتيجيات الأعمال",       "final",   4,   9, 3, "قاعة 302",  75, "r.kamal"),
        ("اختبار منتصف الفصل — التجارة الإلكترونية", "midterm", 7,  11, 2, "قاعة 302",  60, "r.kamal"),
        ("اختبار نهائي — الاقتصاد الكلي",            "final",   0,  15, 3, "قاعة 303",  85, "t.saad"),
        ("اختبار منتصف الفصل — إدارة المشاريع",      "midterm", 3,  10, 2, "قاعة 303",  70, "t.saad"),
        ("اختبار نهائي — الريادة والابتكار",          "final",   6,   9, 3, "قاعة 303",  65, "t.saad"),
    ],
}


# ─── Helpers ──────────────────────────────────────────────────────────────────

def _simulator_hall_prefix(hall_name: str) -> str:
    digits = "".join(ch for ch in hall_name if ch.isdigit())
    return f"hall{digits}" if digits else hall_name.replace(" ", "").lower()


def _default_mic_placements(camera_ids: list[str]) -> list[dict]:
    return [
        {"camera_id": camera_id, "norm_pos": [0.5, 0.5]}
        for camera_id in camera_ids
    ]


def _simulator_camera_url(camera_id: str) -> str:
    return f"{SIMULATOR_BASE_URL}/camera/{camera_id}/feed"


def _simulator_mic_url(mic_id: str) -> str:
    return f"{SIMULATOR_BASE_URL}/mic/{mic_id}/feed"


def _wipe_all(db) -> None:
    """Delete everything in FK-safe order."""
    db.query(Alert).delete(synchronize_session=False)
    db.query(DetectionEvent).delete(synchronize_session=False)
    db.query(GroupEvent).delete(synchronize_session=False)
    db.query(Assignment).delete(synchronize_session=False)
    for s in db.query(ExamSession).all():
        db.delete(s)  # ORM removes exam_session_halls junction rows
    db.flush()
    db.query(Device).delete(synchronize_session=False)
    db.query(Hall).delete(synchronize_session=False)
    db.query(RefreshToken).delete(synchronize_session=False)
    db.query(User).delete(synchronize_session=False)
    db.query(Institution).filter(Institution.parent_id.isnot(None)).delete(synchronize_session=False)
    db.query(Institution).delete(synchronize_session=False)
    db.flush()
    logger.info("Wiped all existing data")


def _create_hall(db, institution_id, spec: dict) -> Hall:
    hall = Hall(
        institution_id=institution_id,
        name=spec["name"],
        capacity=spec["capacity"],
        status="ready",
    )
    db.add(hall)
    db.flush()

    use_simulator_streams = spec.get("demo_video", False)
    hall_prefix = _simulator_hall_prefix(spec["name"])
    camera_ids: list[str] = []
    for key in ("front", "back", "side"):
        camera_id = f"{hall_prefix}_cam_{key}"
        camera_ids.append(camera_id)
        cam = Device(
            hall_id=hall.id,
            type="camera",
            identifier=camera_id,
            stream_url=_simulator_camera_url(camera_id) if use_simulator_streams else None,
            position={"label": CAM_LABEL[key]},
            status="online" if use_simulator_streams else "offline",
        )
        db.add(cam)

    mic_id = f"{hall_prefix}_mic_front"
    db.add(Device(
        hall_id=hall.id,
        type="microphone",
        identifier=mic_id,
        stream_url=_simulator_mic_url(mic_id) if use_simulator_streams else None,
        position={"label": "الميكروفون الرئيسي", "placements": _default_mic_placements(camera_ids)},
        status="online" if use_simulator_streams else "offline",
    ))
    
    if hall_prefix == "hall101":
        for idx, label in enumerate(["الميكروفون الثاني", "الميكروفون الثالث"], start=2):
            extra_mic_id = f"{hall_prefix}_mic_{idx}"
            db.add(Device(
                hall_id=hall.id,
                type="microphone",
                identifier=extra_mic_id,
                stream_url=_simulator_mic_url(extra_mic_id) if use_simulator_streams else None,
                position={"label": label, "placements": _default_mic_placements(camera_ids)},
                status="online" if use_simulator_streams else "offline",
            ))
            
        # Add RF Scanners to demonstrate RF detection UI
        for idx, label in enumerate(["مستشعر الترددات 1", "مستشعر الترددات 2"], start=1):
            scanner_id = f"{hall_prefix}_rf_{idx}"
            db.add(Device(
                hall_id=hall.id,
                type="rf_scanner",
                identifier=scanner_id,
                stream_url=None,
                position={"label": label},
                status="online" if use_simulator_streams else "offline",
            ))
            
    db.flush()

    if use_simulator_streams and not (VIDEO_DIR / "cam1.mp4").exists():
        logger.warning("Demo videos not found in %s — simulator feeds will use fallbacks", VIDEO_DIR)

    return hall


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
    now = datetime.now(timezone.utc)

    admin = User(
        institution_id=institution_id,
        username=admin_username,
        password_hash=get_password_hash(ADMIN_PASSWORD),
        full_name=blueprint.get("admin_fullname", admin_username),
        email=f"{admin_username}@admin.demo",
        role=admin_role,
        status="active",
    )
    db.add(admin)
    db.flush()

    halls: dict[str, Hall] = {}
    for hall_spec in blueprint["halls"]:
        halls[hall_spec["name"]] = _create_hall(db, institution_id, hall_spec)

    invigilators: dict[str, User] = {}
    for username, full_name, email in blueprint["invigilators"]:
        user = User(
            institution_id=institution_id,
            username=username,
            password_hash=get_password_hash(INVIG_PASSWORD),
            full_name=full_name,
            email=email,
            role="invigilator",
            status="active",
        )
        db.add(user)
        db.flush()
        invigilators[username] = user

    for (exam_name, exam_type, day_offset, start_hour,
         duration_h, hall_name, students, invig_username) in blueprint["schedule"]:

        hall = halls.get(hall_name)
        invig = invigilators.get(invig_username)
        if hall is None or invig is None:
            logger.warning("Skipping '%s' — hall or invigilator not found", exam_name)
            continue

        start = (now + timedelta(days=day_offset)).replace(
            hour=start_hour, minute=0, second=0, microsecond=0,
        )
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

        if admin_role == "admin":
            db.add(ExamAdminAssignment(
                exam_session_id=session.id,
                admin_id=admin.id,
                assignment_role="lead",
                assigned_by=assigned_by_id or admin.id,
            ))

        db.add(Assignment(
            exam_session_id=session.id,
            invigilator_id=invig.id,
            hall_id=hall.id,
            role="primary",
        ))
        db.flush()

        logger.info("    %-55s → %s (%s)", exam_name, hall_name, invig_username)


# ─── Entry points ─────────────────────────────────────────────────────────────

def seed_college(db) -> None:
    logger.info("\n── Mode: Single College ─────────────────────────────────────────")

    inst = Institution(
        name=CS_BLUEPRINT["name"],
        code=CS_BLUEPRINT["code"],
        type="college",
        contact_email=CS_BLUEPRINT["contact_email"],
    )
    db.add(inst)
    db.flush()
    logger.info("Institution: %s  [college]", inst.name)

    _seed_college_data(
        db,
        CS_BLUEPRINT,
        inst.id,
        admin_username="admin",
        admin_role="super_admin",
    )
    db.commit()

    logger.info("\n✅ College seed complete — 3 invigilators, 9 exam sessions.")
    logger.info("   admin        → %s  (password: %s)", inst.name, ADMIN_PASSWORD)
    logger.info("   invigilator  → CS Final today at 09:00 in Hall 101")
    logger.info("   a.mahmoud    → DSA Midterm today at 14:00 in Hall 102")
    logger.info("   f.ali        → Linear Algebra Final today at 16:00 in Hall 103")
    logger.info("   Invigilator password: %s", INVIG_PASSWORD)


def seed_university(db) -> None:
    logger.info("\n── Mode: University ─────────────────────────────────────────────")

    univ = Institution(
        name="جامعة النور",
        code="ALNOUR",
        type="university",
        contact_email="info@alnour.demo",
    )
    db.add(univ)
    db.flush()

    university_admin = User(
        institution_id=univ.id,
        username="admin",
        password_hash=get_password_hash(ADMIN_PASSWORD),
        full_name="مدير الجامعة",
        email="admin@alnour.demo",
        role="super_admin",
        status="active",
    )
    db.add(university_admin)
    db.flush()
    logger.info("University: %s — super_admin: admin", univ.name)

    college_configs = [
        (CS_BLUEPRINT,  "admin_cs",  "مشرف كلية الحاسوب"),
        (ENG_BLUEPRINT, "admin_eng", "مشرف كلية الهندسة"),
        (BUS_BLUEPRINT, "admin_bus", "مشرف كلية الأعمال"),
    ]
    for blueprint, admin_username, admin_fullname in college_configs:
        blueprint = {**blueprint, "admin_fullname": admin_fullname}
        college = Institution(
            name=blueprint["name"],
            code=blueprint["code"],
            type="college",
            parent_id=univ.id,
            contact_email=blueprint["contact_email"],
        )
        db.add(college)
        db.flush()
        logger.info("\n  College: %s  (admin: %s)", college.name, admin_username)
        _seed_college_data(
            db,
            blueprint,
            college.id,
            admin_username=admin_username,
            admin_role="admin",
            assigned_by_id=university_admin.id,
        )

    db.commit()

    logger.info("\n✅ University seed complete — 3 colleges, 27 exam sessions.")
    logger.info("   University super-admin : admin          (password: %s)", ADMIN_PASSWORD)
    logger.info("   CIS college admin      : admin_cs       (password: %s)", ADMIN_PASSWORD)
    logger.info("   ENG college admin      : admin_eng      (password: %s)", ADMIN_PASSWORD)
    logger.info("   BUS college admin      : admin_bus      (password: %s)", ADMIN_PASSWORD)
    logger.info("   All invigilator accounts use password   : %s", INVIG_PASSWORD)
    logger.info("   CIS  — invigilator / a.mahmoud / f.ali")
    logger.info("   ENG  — m.hassan / s.ibrahim / k.omar")
    logger.info("   BUS  — n.youssef / r.kamal / t.saad")


# ─── CLI ──────────────────────────────────────────────────────────────────────

def main() -> None:
    global SIMULATOR_BASE_URL

    parser = argparse.ArgumentParser(description="Seed demo data for Thaqib.")
    parser.add_argument(
        "mode",
        nargs="?",
        choices=["college", "university"],
        default="college",
        help="Seed a standalone college (default) or a university with 3 colleges.",
    )
    parser.add_argument(
        "--simulator-base-url",
        default=os.environ.get("SIMULATOR_BASE_URL", SIMULATOR_BASE_URL),
        help="Base URL for simulator camera/mic feeds (default: http://localhost:8000).",
    )
    args = parser.parse_args()

    SIMULATOR_BASE_URL = args.simulator_base_url.rstrip("/")

    db = SessionLocal()
    try:
        _wipe_all(db)
        if args.mode == "university":
            seed_university(db)
        else:
            seed_college(db)
    except Exception as exc:
        db.rollback()
        logger.exception("Seed failed: %s", exc)
    finally:
        db.close()


if __name__ == "__main__":
    main()
