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
- Webcam or IP camera (for testing)
- GPU recommended for production (NVIDIA with CUDA)

### Installation

```bash
# Clone the repository
git clone https://github.com/SheedoM/Thaqib---Smart-Cheating-Detection-System.git
cd Thaqib---Smart-Cheating-Detection-System

# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -e .
pip install -e ".[gpu]"  # For GPU support
```

### Running the Demo

```bash
python scripts/demo_video.py --source <video_path>
```

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
