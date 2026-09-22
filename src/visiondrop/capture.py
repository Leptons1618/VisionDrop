"""Background camera capture with latest-frame handoff.

The reader thread blocks on ``cap.read()`` and publishes the newest frame; the
consumer always takes the latest and never processes a backlog, which keeps
end-to-end latency bounded.
"""

from __future__ import annotations

import threading
import time

import numpy as np

from . import config as _config


class CameraCapture:
    def __init__(
        self,
        index: int | None = None,
        width: int | None = None,
        height: int | None = None,
        mirror: bool = True,
        config: _config.EngineConfig | None = None,
    ) -> None:
        cfg = config or _config.DEFAULT_CONFIG
        self.index = cfg.camera_index if index is None else index
        self.width = cfg.frame_width if width is None else width
        self.height = cfg.frame_height if height is None else height
        self.mirror = mirror

        self._cap = None
        self._thread: threading.Thread | None = None
        self._lock = threading.Lock()
        self._frame: np.ndarray | None = None
        self._timestamp = 0.0
        self._running = False
        self.actual_size: tuple[int, int] | None = None

    def open(self) -> bool:
        import cv2

        self._cap = cv2.VideoCapture(self.index)
        if not self._cap.isOpened():
            return False
        self._cap.set(cv2.CAP_PROP_FRAME_WIDTH, self.width)
        self._cap.set(cv2.CAP_PROP_FRAME_HEIGHT, self.height)
        ok, frame = self._cap.read()
        if not ok or frame is None:
            return False
        self.actual_size = (frame.shape[1], frame.shape[0])
        self._frame = self._flip(frame)
        self._timestamp = time.monotonic()
        return True

    def _flip(self, frame: np.ndarray) -> np.ndarray:
        if not self.mirror:
            return frame
        import cv2

        return cv2.flip(frame, 1)

    def _loop(self) -> None:
        assert self._cap is not None
        while self._running:
            ok, frame = self._cap.read()
            if not ok or frame is None:
                time.sleep(0.005)
                continue
            with self._lock:
                self._frame = self._flip(frame)
                self._timestamp = time.monotonic()

    def start(self) -> None:
        if self._running:
            return
        self._running = True
        self._thread = threading.Thread(target=self._loop, name="visiondrop-camera", daemon=True)
        self._thread.start()

    def read(self) -> tuple[np.ndarray | None, float]:
        with self._lock:
            return self._frame, self._timestamp

    def stop(self) -> None:
        self._running = False
        if self._thread is not None:
            self._thread.join(timeout=1.0)
            self._thread = None
        if self._cap is not None:
            self._cap.release()
            self._cap = None

    def __enter__(self) -> "CameraCapture":
        if not self.open():
            raise RuntimeError(f"Unable to open camera index {self.index}")
        self.start()
        return self

    def __exit__(self, *exc: object) -> None:
        self.stop()
