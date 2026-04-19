"""
Write demo_db.json and sync it into the DB for the monitoring dashboard.

Edit the paths in `demo_db.json` if you want to change the demo sources without
hardcoding them in Python. Run from repo root:
    .\\venv\\Scripts\\python scripts\\seed_demo.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.thaqib.db.database import SessionLocal, engine
from src.thaqib.db.models import Base
from src.thaqib.db.models.infrastructure import Device, Hall, Institution

OUT = ROOT / "demo_db.json"

DATA = {
    "institution": {
        "name": "Demo Monitoring Institution",
        "code": "DEMO",
        "contact_email": "demo-monitoring@example.com",
    },
    "halls": [
        {
            "id": "hall_101",
            "name": "قاعة 101",
            "building": "Main",
            "floor": "1",
            "capacity": 120,
            "status": "ready",
            "mics": ["ميكروفون 1", "ميكروفون 2"],
            "cameras": [
                {
                    "id": "hall101_cam_front",
                    "name": "كاميرا 1 - أمامية",
                    "source": r"C:\Users\shady\Downloads\IMG_5123.MOV",
                },
                {
                    "id": "hall101_cam_back",
                    "name": "كاميرا 2 - خلفية",
                    "source": r"C:\Users\shady\Downloads\20260414_132048.mp4",
                },
            ],
        },
        {
            "id": "hall_102",
            "name": "قاعة 102",
            "building": "Main",
            "floor": "1",
            "capacity": 120,
            "status": "not_ready",
            "mics": ["ميكروفون 1", "ميكروفون 2"],
            "cameras": [
                {"id": "hall102_cam_front", "name": "كاميرا 1 - أمامية", "source": ""},
                {"id": "hall102_cam_back", "name": "كاميرا 2 - خلفية", "source": ""},
            ],
        },
        {
            "id": "hall_103",
            "name": "قاعة 103",
            "building": "Main",
            "floor": "2",
            "capacity": 120,
            "status": "not_ready",
            "mics": ["ميكروفون 1", "ميكروفون 2"],
            "cameras": [
                {"id": "hall103_cam_front", "name": "كاميرا 1 - أمامية", "source": ""},
                {"id": "hall103_cam_back", "name": "كاميرا 2 - خلفية", "source": ""},
            ],
        },
        {
            "id": "hall_104",
            "name": "قاعة 104",
            "building": "Main",
            "floor": "2",
            "capacity": 120,
            "status": "not_ready",
            "mics": ["ميكروفون 1", "ميكروفون 2"],
            "cameras": [
                {"id": "hall104_cam_front", "name": "كاميرا 1 - أمامية", "source": ""},
                {"id": "hall104_cam_back", "name": "كاميرا 2 - خلفية", "source": ""},
            ],
        },
    ],
}


def write_json() -> None:
    OUT.write_text(json.dumps(DATA, ensure_ascii=False, indent=2), encoding="utf-8")


def ensure_institution(db) -> Institution:
    seed_info = DATA["institution"]
    institution = db.query(Institution).filter(Institution.code == seed_info["code"]).first()
    if institution is None:
        institution = db.query(Institution).order_by(Institution.created_at.asc()).first()

    if institution is None:
        institution = Institution(
            name=seed_info["name"],
            code=seed_info["code"],
            contact_email=seed_info["contact_email"],
        )
        db.add(institution)
        db.commit()
        db.refresh(institution)
    return institution


def upsert_hall(db, institution: Institution, hall_data: dict) -> Hall:
    hall = (
        db.query(Hall)
        .filter(Hall.institution_id == institution.id, Hall.name == hall_data["name"])
        .first()
    )
    if hall is None:
        hall = Hall(
            institution_id=institution.id,
            name=hall_data["name"],
            building=hall_data.get("building"),
            floor=hall_data.get("floor"),
            capacity=hall_data.get("capacity", 120),
            layout_map={"seed_id": hall_data["id"]},
            status=hall_data.get("status", "not_ready"),
        )
        db.add(hall)
        db.commit()
        db.refresh(hall)
    else:
        hall.building = hall_data.get("building")
        hall.floor = hall_data.get("floor")
        hall.capacity = hall_data.get("capacity", hall.capacity)
        hall.layout_map = {"seed_id": hall_data["id"]}
        hall.status = hall_data.get("status", hall.status)
        db.add(hall)
        db.commit()
        db.refresh(hall)
    return hall


def upsert_device(
    db,
    hall: Hall,
    *,
    identifier: str,
    device_type: str,
    label: str,
    stream_url: str,
    slot: int,
    status: str,
) -> None:
    device = (
        db.query(Device)
        .filter(Device.hall_id == hall.id, Device.identifier == identifier)
        .first()
    )
    position = {
        "label": label,
        "slot": slot,
        "device_type": device_type,
    }
    if device is None:
        device = Device(
            hall_id=hall.id,
            type=device_type,
            identifier=identifier,
            ip_address=None,
            stream_url=stream_url,
            position=position,
            coverage_area={},
            status=status,
        )
    else:
        device.type = device_type
        device.stream_url = stream_url
        device.position = position
        device.coverage_area = device.coverage_area or {}
        device.status = status
    db.add(device)
    db.commit()


def sync_to_db() -> None:
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        institution = ensure_institution(db)
        for hall_index, hall_data in enumerate(DATA["halls"], start=1):
            hall = upsert_hall(db, institution, hall_data)
            hall_is_ready = hall_data.get("status") == "ready"
            for camera_index, camera in enumerate(hall_data.get("cameras", []), start=1):
                source = (camera.get("source") or "").strip()
                upsert_device(
                    db,
                    hall,
                    identifier=camera["id"],
                    device_type="camera",
                    label=camera["name"],
                    stream_url=source,
                    slot=camera_index,
                    status="online" if hall_is_ready and source else "offline",
                )
            for mic_index, mic_name in enumerate(hall_data.get("mics", []), start=1):
                upsert_device(
                    db,
                    hall,
                    identifier=f"{hall_data['id']}_mic_{mic_index}",
                    device_type="microphone",
                    label=mic_name,
                    stream_url="",
                    slot=hall_index * 10 + mic_index,
                    status="offline",
                )
    finally:
        db.close()


def main() -> None:
    write_json()
    sync_to_db()
    print(f"Wrote {OUT}")
    print("Synced demo halls/devices into the database.")


if __name__ == "__main__":
    main()
