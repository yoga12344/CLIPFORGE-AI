import shutil
import subprocess
import json
import psutil
from typing import Dict, Any, Optional
from ..core.config import settings

class HardwareMonitor:
    @staticmethod
    def get_gpu_info() -> Dict[str, Any]:
        """Inspect real NVIDIA GPU state via nvidia-smi."""
        info = {
            "has_gpu": False,
            "gpu_name": "None (CPU only)",
            "driver_version": "N/A",
            "cuda_version": "N/A",
            "vram_total_mb": 0,
            "vram_used_mb": 0,
            "vram_free_mb": 0,
            "vram_percent": 0.0,
            "temperature_c": None,
            "utilization_gpu_percent": None,
            "nvenc_available": False,
        }

        try:
            # Query nvidia-smi with CSV output for precise metric parsing
            cmd = [
                "nvidia-smi",
                "--query-gpu=name,driver_version,memory.total,memory.used,memory.free,temperature.gpu,utilization.gpu",
                "--format=csv,noheader,nounits"
            ]
            result = subprocess.run(cmd, capture_output=True, text=True, check=True)
            lines = result.stdout.strip().splitlines()
            if lines:
                parts = [p.strip() for p in lines[0].split(',')]
                if len(parts) >= 7:
                    name = parts[0]
                    driver = parts[1]
                    total = float(parts[2])
                    used = float(parts[3])
                    free = float(parts[4])
                    temp = float(parts[5])
                    util = float(parts[6])

                    info["has_gpu"] = True
                    info["gpu_name"] = name
                    info["driver_version"] = driver
                    info["vram_total_mb"] = int(total)
                    info["vram_used_mb"] = int(used)
                    info["vram_free_mb"] = int(free)
                    info["vram_percent"] = round((used / max(total, 1)) * 100, 1)
                    info["temperature_c"] = temp
                    info["utilization_gpu_percent"] = util
        except Exception:
            pass

        # Check NVENC encoder in FFmpeg
        try:
            ffmpeg_bin = settings.get_ffmpeg_binary()
            enc_result = subprocess.run([ffmpeg_bin, "-encoders"], capture_output=True, text=True)
            if "h264_nvenc" in enc_result.stdout:
                info["nvenc_available"] = True
        except Exception:
            pass

        return info

    @staticmethod
    def get_system_metrics() -> Dict[str, Any]:
        """Collect complete, non-mock hardware metrics."""
        # CPU
        cpu_percent = psutil.cpu_percent(interval=None)
        cpu_count_logical = psutil.cpu_count(logical=True)
        cpu_count_physical = psutil.cpu_count(logical=False)

        # RAM
        ram = psutil.virtual_memory()
        ram_info = {
            "total_gb": round(ram.total / (1024 ** 3), 2),
            "used_gb": round(ram.used / (1024 ** 3), 2),
            "free_gb": round(ram.available / (1024 ** 3), 2),
            "percent": ram.percent,
        }

        # Disk Storage
        storage_path = str(settings.DATA_DIR)
        disk = psutil.disk_usage(storage_path)
        disk_info = {
            "path": storage_path,
            "total_gb": round(disk.total / (1024 ** 3), 2),
            "used_gb": round(disk.used / (1024 ** 3), 2),
            "free_gb": round(disk.free / (1024 ** 3), 2),
            "percent": disk.percent,
        }

        # GPU
        gpu_info = HardwareMonitor.get_gpu_info()

        return {
            "cpu": {
                "utilization_percent": cpu_percent,
                "cores_logical": cpu_count_logical,
                "cores_physical": cpu_count_physical,
            },
            "ram": ram_info,
            "disk": disk_info,
            "gpu": gpu_info,
            "ffmpeg": {
                "path": settings.get_ffmpeg_binary(),
                "available": shutil.which("ffmpeg") is not None or settings.get_ffmpeg_binary() != "ffmpeg",
            }
        }
