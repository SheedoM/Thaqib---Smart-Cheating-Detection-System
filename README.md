# Thaqib - Smart Exams Monitoring System

[![License](https://img.shields.io/badge/License-Apache%202.0-blue.svg)](https://opensource.org/licenses/Apache-2.0)
[![Python](https://img.shields.io/badge/Python-3.10%2B-blue.svg)](https://www.python.org/)

**Thaqib** (Arabic: ثاقب, meaning "piercing" or "sharp-sighted") is an AI-powered real-time exam monitoring system that assists invigilators in detecting suspicious behaviors during examinations.

## 🎯 Features

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
- Webcam or IP camera (for testing)
- GPU recommended for production (NVIDIA with CUDA)

### Installation

```bash
# Clone the repository
git clone https://github.com/your-org/thaqib.git
cd thaqib

# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -e .

# For development
pip install -e ".[dev]"

# For GPU support
pip install -e ".[gpu]"
```

### Running the Demo

```bash
# Test video detection with webcam
python -m thaqib.video.demo --source webcam

# Test with video file
python -m thaqib.video.demo --source path/to/video.mp4
```

## 📁 Project Structure

```
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
