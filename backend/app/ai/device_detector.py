import logging
from typing import Dict, List, Optional, Tuple
from pydantic import BaseModel

logger = logging.getLogger("clipforge.ai.device")

class InferenceDeviceStatus(BaseModel):
    ctranslate2_version: str = "Unknown"
    faster_whisper_version: str = "Unknown"
    cuda_available: bool = False
    cuda_device_count: int = 0
    cuda_device_name: Optional[str] = None
    cuda_functional: bool = False
    cpu_supported_compute_types: List[str] = []
    cuda_supported_compute_types: List[str] = []
    recommended_device: str = "cpu"
    recommended_compute_type: str = "int8"
    diagnostic_message: Optional[str] = None

_cached_device_status: Optional[InferenceDeviceStatus] = None

class DeviceDetector:
    @classmethod
    def detect(cls, force_refresh: bool = False) -> InferenceDeviceStatus:
        global _cached_device_status
        if _cached_device_status is not None and not force_refresh:
            return _cached_device_status

        status = InferenceDeviceStatus()

        try:
            import ctranslate2
            import faster_whisper
            status.ctranslate2_version = ctranslate2.__version__
            status.faster_whisper_version = faster_whisper.__version__

            # 1. Query CPU compute types
            try:
                status.cpu_supported_compute_types = sorted(list(ctranslate2.get_supported_compute_types("cpu")))
            except Exception as e:
                logger.warning(f"Error querying CPU compute types: {e}")
                status.cpu_supported_compute_types = ["int8", "float32"]

            # 2. Query CUDA device count
            try:
                status.cuda_device_count = ctranslate2.get_cuda_device_count()
                status.cuda_available = status.cuda_device_count > 0
            except Exception as e:
                logger.warning(f"Error querying CUDA device count: {e}")
                status.cuda_available = False

            # 3. Test real CUDA allocation & cuBLAS availability if devices present
            if status.cuda_available:
                try:
                    status.cuda_supported_compute_types = sorted(list(ctranslate2.get_supported_compute_types("cuda")))
                    
                    # Check cuBLAS library presence (required for CTranslate2 GPU execution)
                    import ctypes
                    has_cublas = False
                    for dll in ["cublas64_12.dll", "cublas64_11.dll"]:
                        try:
                            ctypes.cdll.LoadLibrary(dll)
                            has_cublas = True
                            break
                        except Exception:
                            pass

                    if not has_cublas:
                        status.cuda_functional = False
                        status.recommended_device = "cpu"
                        status.recommended_compute_type = "int8"
                        status.diagnostic_message = (
                            "NVIDIA GPU detected, but required CUDA cuBLAS library (cublas64_12.dll) "
                            "is not installed on the system. Automatic fallback to high-performance CPU int8 active."
                        )
                        logger.info(status.diagnostic_message)
                    else:
                        # Active test allocation
                        import numpy as np
                        test_arr = np.array([1.0, 2.0, 3.0], dtype=np.float32)
                        view = ctranslate2.StorageView.from_array(test_arr)
                        cuda_view = view.to_device(ctranslate2.Device.cuda)
                        if str(cuda_view.device).lower() == "cuda":
                            status.cuda_functional = True
                            status.recommended_device = "cuda"
                            status.recommended_compute_type = "float16" if "float16" in status.cuda_supported_compute_types else "int8_float16"
                            status.diagnostic_message = "CUDA acceleration verified functional with CTranslate2."
                except Exception as cuda_err:
                    status.cuda_functional = False
                    status.recommended_device = "cpu"
                    status.recommended_compute_type = "int8"
                    status.diagnostic_message = f"CUDA present but test allocation failed: {cuda_err}. Falling back to CPU int8."
                    logger.warning(status.diagnostic_message)
            else:
                status.recommended_device = "cpu"
                status.recommended_compute_type = "int8"
                status.diagnostic_message = "No CUDA devices detected by CTranslate2 runtime. CPU inference active."

        except ImportError as imp_err:
            status.diagnostic_message = f"faster-whisper or ctranslate2 not installed: {imp_err}"
            logger.error(status.diagnostic_message)

        _cached_device_status = status
        return status

    @classmethod
    def resolve_device_and_compute_type(
        cls,
        requested_device: str = "auto",
        requested_compute_type: Optional[str] = None
    ) -> Tuple[str, str, bool, Optional[str]]:
        """
        Resolve target device and compute type with verified fallback.
        Returns: (device, compute_type, is_fallback, diagnostic_message)
        """
        status = cls.detect()
        req_dev = requested_device.lower() if requested_device else "auto"

        # Case 1: Explicit CPU requested
        if req_dev == "cpu":
            comp = requested_compute_type or "int8"
            if comp not in status.cpu_supported_compute_types:
                comp = "int8"
            return "cpu", comp, False, None

        # Case 2: Auto or CUDA requested
        if req_dev in ("auto", "cuda"):
            if status.cuda_functional:
                comp = requested_compute_type or status.recommended_compute_type
                if comp not in status.cuda_supported_compute_types:
                    comp = "float16" if "float16" in status.cuda_supported_compute_types else "int8"
                return "cuda", comp, False, None
            else:
                # Fallback to CPU
                is_fallback = req_dev == "cuda"
                msg = status.diagnostic_message or "CUDA requested but not functional; fell back to CPU int8."
                return "cpu", "int8", is_fallback, msg

        return "cpu", "int8", False, None
