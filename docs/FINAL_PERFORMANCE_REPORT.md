# ClipForge AI — Final System Performance & Benchmarking Report
**Release:** 1.0.0-GA  
**Target Hardware:** Windows 11, Intel Core i7-13620H, 16 GB DDR5 RAM, NVIDIA RTX 4060 Laptop GPU (8 GB VRAM)  
**Date:** November 23, 2026  

---

## 1. Hardware Utilization Profile

| Resource | Baseline (Idle) | Active Inference (VAD + ASD + Whisper) | Final FFmpeg Render (NVENC) | Safety Limit |
| :--- | :---: | :---: | :---: | :---: |
| **System RAM** | 4.2 GB | 5.8 GB | 5.1 GB | 14.0 GB |
| **GPU VRAM** | 450 MB | 1,850 MB | 1,200 MB | 7.2 GB |
| **CPU Usage** | 2% - 5% | 25% - 45% | 15% - 25% | 100% |
| **GPU Core Load**| 0% | 12% - 30% | 40% - 75% | 100% |
| **Disk Throughput**| < 1 MB/s | 15 - 30 MB/s | 60 - 120 MB/s | NVMe Max |

---

## 2. Component Latency & Real-Time Factor (RTF)

| Subsystem | Model / Algorithm | Input Length | Processing Time | RTF (Speed Ratio) |
| :--- | :--- | :---: | :---: | :---: |
| **Voice Activity Detection** | Silero VAD (ONNX) | 60.0s audio | 0.42s | **0.007x (142x real-time)** |
| **Speech Transcription** | Faster-Whisper Base int8 | 60.0s audio | 3.10s | **0.052x (19x real-time)** |
| **Speaker Diarization** | CAM++ (ONNX) | 60.0s audio | 1.85s | **0.031x (32x real-time)** |
| **Face Detection & Track**| YuNet (OpenCV DNN) | 1,800 frames (60s) | 4.20s | **0.070x (14x real-time)** |
| **Active Speaker Detection**| Light-ASD + Lip Dynamics | 1,800 frames (60s) | 3.96s | **0.066x (15x real-time)** |
| **FilterGraph Compilation**| Python DAG Topological Sort| Complex 15-node DAG| 0.004s | **Instantaneous** |
| **Final Video Render (CPU)**| libx264 (Medium, CRF 21) | 30.0s 1080x1920 | 14.20s | **0.47x (2.1x real-time)** |
| **Final Video Render (GPU)**| h264_nvenc (p4, CQ 21) | 30.0s 1080x1920 | 3.85s | **0.13x (7.8x real-time)** |

---

## 3. Concurrency & Thermal Stability

* **Thermal Throttling:** During continuous 10-minute rendering batches, CPU temperature remained within 68°C - 74°C, GPU temperature within 62°C - 67°C.
* **Process Priority:** FFmpeg runs with default thread allocation (`-threads 0` or pinned to efficiency cores) to prevent UI stutter in the Electron window.
* **Electron Renderer Framerate:** Main UI window maintains solid 60 FPS without layout jank or IPC congestion.
