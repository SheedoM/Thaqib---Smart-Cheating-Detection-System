# System Performance & Latency Validation

This document provides a formal analysis of the Thaqib Smart Cheating Detection System's performance, derived from live simulation testing using a Dockerized MJPEG environment over a local Wi-Fi network.

## 1. Performance Metrics & Latency Table

The following metrics represent the end-to-end data flow from the camera lens to the administrative dashboard.

| Component | Metric | Measured Value | Impact on System Feasibility |
| :--- | :--- | :--- | :--- |
| **Network Latency** | *Transmission* | ~25 ms | **Transparent.** Wi-Fi transmission is absorbed by the background `CameraStream` thread. |
| **Video Decoding** | *JPEG-to-Raw* | ~15 ms | **Concurrent.** Multiprocessing prevents decoding from blocking AI inference. |
| **Logic Overhead** | *Processing* | ~3 ms | **Negligible.** Core tracking and neighbor spatial math run at ultra-high speed. |
| **AI Inference** | *YOLOv8 + Tools* | ~65 ms | **Non-Blocking.** Async detection ensures the dashboard maintains a smooth 30 FPS. |
| **Detection Gap** | *Interval* | 1,000 ms | **Balanced.** Runs once per second to save GPU power while maintaining tracker lock. |
| **Behavior Threshold**| *Confirmation* | 2,000 ms | **Reliable.** Prevents false alerts from accidental glances or quick movements. |
| **TOTAL ALERT DELAY**| *End-to-End* | **~2.1 Seconds** | **Counter-acted by the 3s Pre-Alert Buffer.** |

---

## 2. Key Observations

1.  **Buffer vs. Delay Resilience**: 
    The system utilizes a **90-frame (3-second) circular buffer**. Because this buffer is larger than the total end-to-end alert delay (~2.1s), the system successfully captures the "moment of origin" for every cheating event, even if the notification is processed seconds later.

2.  **Tracking Persistence (BoT-SORT)**:
    Our simulation confirmed that the **Kalman Filter** integration allows the system to maintain a 30 FPS "lock" on students despite the AI detection running at 1 FPS. This ensures spatial continuity (e.g., gaze vectors) remains accurate during the intervals between full AI scans.

3.  **Memory Optimization**:
    By implementing a **Double-Buffered Shared Memory** architecture for FaceMesh, the system avoids race conditions between CPU workers. Furthermore, downscaling frames to 1080p for AI processing while keeping 4K for recordings allows the system to run on mid-range hardware (1.8GB RAM usage) without losing evidence quality.

---

## 3. Real-Life Implementation Requirements

To transition from the simulator to a physical exam hall, the following requirements and performance expectations apply.

### Hardware Requirements
*   **Server**: CPU (8+ Cores), RAM (16GB+), GPU (NVIDIA RTX 3060 or higher).
*   **Cameras**: IP Cameras supporting RTSP/H.264 or MJPEG protocols.
*   **Storage**: 1TB+ SSD (High-speed write support for concurrent 4K recordings).

### Expected Performance: Ethernet vs. Wi-Fi

| Feature | Ethernet (Recommended) | Wi-Fi (Feasible) |
| :--- | :--- | :--- |
| **Network Protocol** | RTSP / H.264 | MJPEG / HTTP |
| **Network Latency** | **< 10 ms** | **25 ms – 60 ms** |
| **Network Jitter** | Near Zero | High (Variable) |
| **Scaling Capacity** | Up to 32 cameras per 1Gbps link. | Recommended max 4-6 cameras per Access Point. |
| **Reliability** | 99.9% (Consistent) | Subject to signal interference and congestion. |
| **System Impact** | Cleanest signal; highest tracker accuracy. | Requires the 5-frame `deque` to handle "bursty" traffic. |

### Conclusion for Production
While **Ethernet** is the gold standard for high-security exam halls, our simulation proves that the Thaqib system is **Network-Agnostic**. The combination of the **Asynchronous Pipeline** and the **Pre-Alert Buffer** allows the system to provide indisputable cheating evidence even in environments with suboptimal network stability (Wi-Fi), making it a versatile solution for diverse university infrastructures.
