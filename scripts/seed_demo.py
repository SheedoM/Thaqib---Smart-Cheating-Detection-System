"""
Write demo_db.json and sync it into the DB for the monitoring dashboard.

Seeds demo halls, cameras, and microphones with streaming URLs.
For testing: Uses simulator HTTP streams
For production: Uses RTSP URLs from actual IP cameras

Run from repo root:
    .\\venv\\Scripts\\python scripts\\seed_demo.py

With custom stream host (e.g., for production cameras):
    .\\venv\\Scripts\\python scripts\\seed_demo.py --stream-host=192.168.1.100 --protocol=rtsp
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.thaqib.db.database import SessionLocal, engine
from src.thaqib.db.models import Base
from src.thaqib.db.models.infrastructure import Device, Hall, Institution

OUT = ROOT / "demo_db.json"

# Stream configuration (can be overridden via environment variables or CLI)
STREAM_HOST = os.environ.get("STREAM_HOST", "localhost")
STREAM_HTTP_PORT = int(os.environ.get("STREAM_HTTP_PORT", "8000"))
STREAM_PROTOCOL = os.environ.get("STREAM_PROTOCOL", "http")  # 'http' for simulator, 'rtsp' for production


def get_stream_url(camera_id: str, protocol: str = "http", host: str = "localhost", port: int = 8000) -> str:
    """
    Generate stream URL for a camera.
    
    Args:
        camera_id: The camera identifier (e.g., 'hall101_cam_front')
        protocol: 'http' for simulator testing, 'rtsp' for production cameras
        host: Stream host (simulator IP or camera IP)
        port: Stream port
    
    Returns:
        Stream URL (http://host:port/camera/{id}/feed or rtsp://host:port/live/{id})
    """
    if protocol.lower() == "rtsp":
        return f"rtsp://{host}:{port}/live/{camera_id}"
    return f"http://{host}:{port}/camera/{camera_id}/feed"


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
            "image": "/c4b54a3086bba70544daebd23a684e9ed5ddbe56.jpg",
            "mics": ["ميكروفون 1", "ميكروفون 2"],
            "cameras": [
                {"id": "hall101_cam_front", "name": "كاميرا 1 - أمامية"},
                {"id": "hall101_cam_back", "name": "كاميرا 2 - خلفية"},
                {"id": "hall101_cam_side", "name": "كاميرا 3 - جانبية"},
            ],
        },
        {
            "id": "hall_102",
            "name": "قاعة 102",
            "building": "Main",
            "floor": "1",
            "capacity": 120,
            "status": "not_ready",
            "image": "/c4b54a3086bba70544daebd23a684e9ed5ddbe56.jpg",
            "mics": ["ميكروفون 1", "ميكروفون 2"],
            "cameras": [
                {"id": "hall102_cam_front", "name": "كاميرا 1 - أمامية"},
                {"id": "hall102_cam_back", "name": "كاميرا 2 - خلفية"},
                {"id": "hall102_cam_side", "name": "كاميرا 3 - جانبية"},
            ],
        },
        {
            "id": "hall_103",
            "name": "قاعة 103",
            "building": "Main",
            "floor": "2",
            "capacity": 120,
            "status": "not_ready",
            "image": "/c4b54a3086bba70544daebd23a684e9ed5ddbe56.jpg",
            "mics": ["ميكروفون 1", "ميكروفون 2"],
            "cameras": [
                {"id": "hall103_cam_front", "name": "كاميرا 1 - أمامية"},
                {"id": "hall103_cam_back", "name": "كاميرا 2 - خلفية"},
                {"id": "hall103_cam_side", "name": "كاميرا 3 - جانبية"},
            ],
        },
        {
            "id": "hall_104",
            "name": "قاعة 104",
            "building": "Main",
            "floor": "2",
            "capacity": 120,
            "status": "not_ready",
            "image": "/c4b54a3086bba70544daebd23a684e9ed5ddbe56.jpg",
            "mics": ["ميكروفون 1", "ميكروفون 2"],
            "cameras": [
                {"id": "hall104_cam_front", "name": "كاميرا 1 - أمامية"},
                {"id": "hall104_cam_back", "name": "كاميرا 2 - خلفية"},
                {"id": "hall104_cam_side", "name": "كاميرا 3 - جانبية"},
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
            image=hall_data.get("image"),
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
        hall.image = hall_data.get("image", hall.image)
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


def sync_to_db(protocol: str = "http", host: str = "localhost", port: int = 8000) -> None:
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        institution = ensure_institution(db)
        for hall_index, hall_data in enumerate(DATA["halls"], start=1):
            hall = upsert_hall(db, institution, hall_data)
            hall_is_ready = hall_data.get("status") == "ready"
            for camera_index, camera in enumerate(hall_data.get("cameras", []), start=1):
                # Generate streaming URL for this camera
                stream_url = get_stream_url(camera["id"], protocol, host, port)
                # Camera is online if hall is ready (streaming source is available)
                is_online = hall_is_ready
                upsert_device(
                    db,
                    hall,
                    identifier=camera["id"],
                    device_type="camera",
                    label=camera["name"],
                    stream_url=stream_url,
                    slot=camera_index,
                    status="online" if is_online else "offline",
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
    parser = argparse.ArgumentParser(
        description="Seed demo data into database for Thaqib monitoring system"
    )
    parser.add_argument(
        "--protocol",
        default=os.environ.get("STREAM_PROTOCOL", "http"),
        choices=["http", "rtsp"],
        help="Stream protocol: 'http' for simulator testing, 'rtsp' for production cameras (default: http)",
    )
    parser.add_argument(
        "--stream-host",
        default=os.environ.get("STREAM_HOST", "localhost"),
        help="Stream host address - simulator IP or camera server IP (default: localhost or STREAM_HOST env var)",
    )
    parser.add_argument(
        "--stream-port",
        type=int,
        default=int(os.environ.get("STREAM_HTTP_PORT", "8000")),
        help="Stream port (default: 8000 or STREAM_HTTP_PORT env var)",
    )
    args = parser.parse_args()

    # Update global stream config from CLI args
    global STREAM_HOST, STREAM_HTTP_PORT, STREAM_PROTOCOL
    STREAM_HOST = args.stream_host
    STREAM_HTTP_PORT = args.stream_port
    STREAM_PROTOCOL = args.protocol

    write_json()
    sync_to_db(protocol=args.protocol, host=args.stream_host, port=args.stream_port)
    print(f"Wrote {OUT}")
    print("Synced demo halls/devices into the database.")
    print(f"\nStream Configuration:")
    print(f"  Protocol: {args.protocol.upper()}")
    print(f"  Host: {args.stream_host}:{args.stream_port}")
    if args.protocol == "http":
        print(f"  Example URL: http://{args.stream_host}:{args.stream_port}/camera/hall101_cam_front/feed")
        print(f"\nMake sure the simulator is running:")
        print(f"  docker-compose -f simulator/docker-compose.simulator.yml up")
    else:
        print(f"  Example URL: rtsp://{args.stream_host}:{args.stream_port}/live/hall101_cam_front")


if __name__ == "__main__":
    main()
