import mss
import base64
import io
import threading
from PIL import Image

try:
    import cv2
    OPENCV_AVAILABLE = True
except ImportError:
    OPENCV_AVAILABLE = False


class ScreenCapture:
    """Captures the screen and/or webcam, returning base64-encoded PNG images."""

    def __init__(self):
        self._sct = None
        self._sct_lock = threading.Lock()
        self._cam = None
        self._cam_lock = threading.Lock()

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _get_sct(self):
        """Lazy-init mss instance per-thread to avoid cross-thread issues."""
        if self._sct is None:
            self._sct = mss.mss()
        return self._sct

    def _encode_pil(self, img: Image.Image, max_size: int = 900) -> str:
        """Resize and base64-encode a PIL image."""
        img.thumbnail((max_size, max_size), Image.LANCZOS)
        buf = io.BytesIO()
        img.save(buf, format="PNG")
        return base64.b64encode(buf.getvalue()).decode("utf-8")

    # ------------------------------------------------------------------
    # Screen capture
    # ------------------------------------------------------------------

    def capture_as_base64(self, monitor_index: int = 1) -> str:
        """Capture the full screen (or a specific monitor) as base64 PNG."""
        sct = self._get_sct()
        monitor = sct.monitors[monitor_index] if monitor_index < len(sct.monitors) else sct.monitors[1]
        raw = sct.grab(monitor)
        img = Image.frombytes("RGB", raw.size, raw.bgra, "raw", "BGRX")
        return self._encode_pil(img)

    def capture_region_as_base64(self, x: int, y: int, width: int, height: int) -> str:
        """Capture a rectangular region of the screen as base64 PNG."""
        sct = self._get_sct()
        region = {"top": y, "left": x, "width": width, "height": height}
        raw = sct.grab(region)
        img = Image.frombytes("RGB", raw.size, raw.bgra, "raw", "BGRX")
        return self._encode_pil(img)

    def get_monitor_count(self) -> int:
        """Return the number of monitors detected (excluding the 'all' virtual monitor at index 0)."""
        sct = self._get_sct()
        return max(0, len(sct.monitors) - 1)

    # ------------------------------------------------------------------
    # Webcam capture
    # ------------------------------------------------------------------

    def open_camera(self, camera_index: int = 0) -> bool:
        """Open the webcam.  Returns True on success."""
        if not OPENCV_AVAILABLE:
            print("OpenCV (cv2) is not installed — webcam support unavailable.")
            return False
        with self._cam_lock:
            if self._cam is not None and self._cam.isOpened():
                return True
            cam = cv2.VideoCapture(camera_index, cv2.CAP_DSHOW)
            if not cam.isOpened():
                cam = cv2.VideoCapture(camera_index)
            if cam.isOpened():
                cam.set(cv2.CAP_PROP_FRAME_WIDTH, 1280)
                cam.set(cv2.CAP_PROP_FRAME_HEIGHT, 720)
                self._cam = cam
                return True
            return False

    def release_camera(self):
        """Release the webcam resource."""
        with self._cam_lock:
            if self._cam is not None:
                self._cam.release()
                self._cam = None

    def is_camera_open(self) -> bool:
        with self._cam_lock:
            return self._cam is not None and self._cam.isOpened()

    def capture_camera_frame_as_base64(self) -> str | None:
        """Capture a single webcam frame and return it as base64 PNG.
        Returns None if the camera is not available."""
        if not OPENCV_AVAILABLE:
            return None
        with self._cam_lock:
            if self._cam is None or not self._cam.isOpened():
                return None
            ret, frame = self._cam.read()
            if not ret:
                return None
            # Convert BGR → RGB
            frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        img = Image.fromarray(frame_rgb)
        return self._encode_pil(img, max_size=800)

    def capture_camera_frame_as_qimage(self):
        """Capture a webcam frame and return a (height, width, 3) RGB numpy array.
        Returns None if unavailable.  Used by the live preview widget."""
        if not OPENCV_AVAILABLE:
            return None
        with self._cam_lock:
            if self._cam is None or not self._cam.isOpened():
                return None
            ret, frame = self._cam.read()
            if not ret:
                return None
            return cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
