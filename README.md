# Thaqib - Smart Cheating Detection System

[![License](https://img.shields.io/badge/License-Apache%202.0-blue.svg)](https://opensource.org/licenses/Apache-2.0)
[![Python](https://img.shields.io/badge/Python-3.10%2B-blue.svg)](https://www.python.org/)
[![Status](https://img.shields.io/badge/Status-Active-success.svg)]()

Thaqib (Arabic: ثاقب, meaning 'piercing' or 'sharp-sighted') is an AI-powered real-time exam monitoring system leveraging Computer Vision (YOLOv8), Object Tracking (BoT-SORT), and Biometric Analysis (MediaPipe & OSNet) to assist invigilators in detecting suspicious behaviors.

## ✨ Key Features

- **Real-time Video Monitoring**: Capture and analyze video streams from IP cameras
- **Human Detection & Tracking**: Identify and track students throughout the exam
- **Head Pose Estimation**: Detect suspicious head movements and orientations
- **Neighbor Modeling**: Identify spatial relationships and risk angles between students
- **Audio Monitoring**: Detect suspicious audio patterns (whispers, talking)
- **Web Dashboard**: Real-time alerts and monitoring interface for invigilators

## 🏗️ Architecture

```
┌─────────────────┐     ┌─────────────────┐     ┌─────────────────┐
│   IP Cameras    │────▶│  Video Pipeline │────▶│                 │
└─────────────────┘     └─────────────────┘     │                 │
                                                │  Detection &    │
┌─────────────────┐     ┌─────────────────┐     │  Alert Engine   │
│   Microphones   │────▶│  Audio Pipeline │────▶│                 │
└─────────────────┘     └─────────────────┘     └────────┬────────┘
                                                         │
                                                         ▼
                                                ┌─────────────────┐
                                                │  Web Dashboard  │
                                                │  (Invigilator)  │
                                                └─────────────────┘
```

## 🚀 Quick Start

### Prerequisites

- Python 3.10 or higher
- Node.js 18+ and npm
- Docker & Docker Compose (for camera simulator)
- GPU recommended for production (NVIDIA with CUDA)

### Installation

```bash
# Clone the repository
git clone https://github.com/SheedoM/Thaqib---Smart-Cheating-Detection-System.git
cd Thaqib---Smart-Cheating-Detection-System

# Create and activate virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install Python dependencies
pip install -e .
pip install -e ".[gpu]"  # For GPU support

# Install frontend dependencies
cd frontend
npm install
cd ..

# Copy environment config
cp .env.example .env
```

### Running the Full System

The system has 3 components: **Camera Simulator**, **Backend**, and **Frontend**.

#### 1. Start the Database

```bash
docker-compose up -d db
```

#### 2. Start the Camera Simulator (for testing with pre-recorded videos)

Place video files in `simulator/test_videos/` (e.g., `cam1.mp4`, `cam2.mp4`), then:

```bash
docker-compose -f simulator/docker-compose.simulator.yml up -d
```

Verify the simulator is running: open `http://localhost:8000/info` in your browser.

#### 3. Seed the Database with Demo Data

```bash
# For simulator (HTTP MJPEG streams)
python scripts/seed_demo.py --protocol=http --stream-host=localhost --stream-port=8000

# For real cameras (RTSP streams)
python scripts/seed_demo.py --protocol=rtsp --stream-host=192.168.1.100 --stream-port=554
```

#### 4. Start the Backend

```bash
uvicorn src.thaqib.main:app --reload --host 0.0.0.0 --port 8001
```

The API will be available at `http://localhost:8001`.

#### 5. Start the Frontend

```bash
cd frontend
npm run dev -- --host
```

Open `http://localhost:5173` in your browser. The Vite dev server proxies `/api` requests to the backend.

### Running the Demo (Standalone Video)

```bash
python scripts/demo_video.py --source <video_path>
```

### Production Workflow (Real IP Cameras)

1. Connect IP cameras to the local network (Wi-Fi or Ethernet)
2. Obtain each camera's RTSP URL from its admin interface (e.g., `rtsp://admin:password@192.168.1.101:554/stream`)
3. Open the Thaqib dashboard → **Hall Management** → create a hall and add cameras with their RTSP stream URLs
4. The backend automatically connects to configured cameras and starts monitoring

## 📁 Project Structure

```text
thaqib/
├── src/thaqib/           # Main source code
│   ├── video/            # Video detection pipeline
│   ├── audio/            # Audio detection pipeline
│   ├── detection/        # Behavioral detection logic
│   ├── server/           # FastAPI backend
│   └── config/           # Configuration management
├── dashboard/            # React web dashboard
├── tests/                # Test suite
├── scripts/              # Utility scripts
└── docs/                 # Documentation
```

## 🔧 Configuration

Copy `.env.example` to `.env` and configure:

```env
# Camera settings
CAMERA_SOURCE=0                    # Webcam index or RTSP URL
DETECTION_INTERVAL=1.0             # Detection frequency (seconds)

# Detection settings
NEIGHBOR_DISTANCE_THRESHOLD=200    # Pixels
RISK_ANGLE_TOLERANCE=15            # Degrees
SUSPICIOUS_DURATION_THRESHOLD=2.0  # Seconds
```

## 📖 Documentation

- [Technical Documentation](docs/technical.md)
- [API Reference](docs/api.md)
- [Deployment Guide](docs/deployment.md)

## 🤝 Contributing

Please read [CONTRIBUTING.md](CONTRIBUTING.md) for details on our code of conduct and the process for submitting pull requests.

## 📄 License

This project is licensed under the Apache License 2.0 - see the [LICENSE](LICENSE) file for details.

## 👥 Team

- Shady Mohamed Faragallah
- Mohamed Elsaied Shalaan
