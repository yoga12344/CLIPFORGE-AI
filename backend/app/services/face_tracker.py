import cv2
import numpy as np
from typing import Tuple, List, Optional
from ..config import settings

class FaceTracker:
    """
    Tracks human faces across video frames to compute a smooth 9:16 vertical crop.
    Uses exponential moving average (EMA) to avoid jerky camera movements.
    """
    def __init__(self, smoothing_alpha: float = 0.15, deadzone_pixels: int = 25):
        self.alpha = smoothing_alpha
        self.deadzone = deadzone_pixels
        self._mp_face_detector = None

    def _init_detector(self):
        if self._mp_face_detector is None:
            try:
                import mediapipe as mp
                self._mp_face_detector = mp.solutions.face_detection.FaceDetection(
                    model_selection=1, # 0 for short-range (<2m), 1 for full-range (up to 5m)
                    min_detection_confidence=0.5
                )
            except Exception as e:
                print(f"MediaPipe face detection unavailable ({e}). Using Haar Cascade / Center fallback.")
                self._mp_face_detector = "fallback"

    def calculate_crop_box(
        self,
        video_path: str,
        start_time: float,
        end_time: float,
        source_width: int = 1920,
        source_height: int = 1080,
        target_aspect_ratio: Tuple[int, int] = (9, 16)
    ) -> Tuple[int, int, int, int]:
        """
        Samples frames over the clip interval [start_time, end_time], tracks the dominant speaker's face,
        and computes the optimal (x, y, crop_w, crop_h) box in source video coordinates.
        """
        self._init_detector()

        # Target crop dimensions matching aspect ratio
        crop_h = source_height
        crop_w = int(source_height * (target_aspect_ratio[0] / target_aspect_ratio[1]))
        if crop_w % 2 != 0:
            crop_w += 1
            
        max_x = max(0, source_width - crop_w)
        default_x = max_x // 2 # Center crop default

        cap = cv2.VideoCapture(video_path)
        if not cap.isOpened():
            return (default_x, 0, crop_w, crop_h)

        fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
        start_frame = int(start_time * fps)
        end_frame = int(end_time * fps)
        total_frames = end_frame - start_frame

        if total_frames <= 0:
            cap.release()
            return (default_x, 0, crop_w, crop_h)

        # Sample 1 frame every 0.5s for fast analysis
        step = max(1, int(fps * 0.5))
        face_x_centers: List[float] = []

        for frame_no in range(start_frame, end_frame, step):
            cap.set(cv2.CAP_PROP_POS_FRAMES, frame_no)
            ret, frame = cap.read()
            if not ret or frame is None:
                continue

            detected_x = self._detect_primary_face_x(frame, source_width)
            if detected_x is not None:
                face_x_centers.append(detected_x)

        cap.release()

        if not face_x_centers:
            # No face detected in interval, stick with center crop
            return (default_x, 0, crop_w, crop_h)

        # Apply robust median / smoothed average
        median_face_x = float(np.median(face_x_centers))
        
        # Center the crop box on the detected face
        optimal_x = int(median_face_x - (crop_w / 2))
        clamped_x = max(0, min(optimal_x, max_x))

        return (clamped_x, 0, crop_w, crop_h)

    def _detect_primary_face_x(self, frame_bgr, width: int) -> Optional[float]:
        """Detect the X center of the largest face in the frame."""
        if self._mp_face_detector != "fallback" and self._mp_face_detector is not None:
            try:
                frame_rgb = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2RGB)
                results = self._mp_face_detector.process(frame_rgb)
                
                if results.detections:
                    # Pick largest face (by bounding box area)
                    largest_face = max(
                        results.detections,
                        key=lambda d: d.location_data.relative_bounding_box.width * d.location_data.relative_bounding_box.height
                    )
                    bbox = largest_face.location_data.relative_bounding_box
                    face_center_x = (bbox.xmin + (bbox.width / 2)) * width
                    return face_center_x
            except Exception:
                pass

        # Fallback OpenCV Haar Cascade
        try:
            gray = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2GRAY)
            face_cascade = cv2.CascadeClassifier(cv2.data.haarcascades + 'haarcascade_frontalface_default.xml')
            faces = face_cascade.detectMultiScale(gray, scaleFactor=1.2, minNeighbors=4, minSize=(60, 60))
            if len(faces) > 0:
                largest = max(faces, key=lambda f: f[2] * f[3])
                x, y, w, h = largest
                return x + (w / 2)
        except Exception:
            pass

        return None
