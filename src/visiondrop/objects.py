"""Object detection backends.

Two interchangeable detectors share the ``detect_objects`` /
``draw_detections`` interface:

- :class:`YoloDetector` (default): YOLO11 with ByteTrack tracking. Track IDs
  persist through short occlusions according to the tracker buffer (30 frames
  by default, i.e. ~1 s at 30 FPS), which is what keeps a held object
  associated while the hand passes over it.
- :class:`ColorObjectDetector`: the HSV fallback from the original prototype.
"""

from __future__ import annotations

import logging
from pathlib import Path
from time import perf_counter

import cv2
import numpy as np

from visiondrop.config import ColorDetectionConfig, YoloConfig
from visiondrop.models import default_model_dir

logger = logging.getLogger(__name__)

Detection = dict
COCO_TRACKER = "bytetrack.yaml"


class ColorObjectDetector:
    """Detect blobs by HSV color range. Used as a fallback and for demos."""

    def __init__(self, config: ColorDetectionConfig | None = None):
        self.logger = logging.getLogger(__name__)
        self.config = config or ColorDetectionConfig()

    def preprocess_frame(self, frame: np.ndarray) -> np.ndarray:
        blurred = cv2.GaussianBlur(frame, self.config.blur_kernel, 0)
        return cv2.cvtColor(blurred, cv2.COLOR_BGR2HSV)

    def detect_objects(self, frame: np.ndarray) -> list[Detection]:
        start_time = perf_counter()
        hsv = self.preprocess_frame(frame)
        detections: list[Detection] = []

        try:
            for color_range in self.config.color_ranges:
                mask = cv2.inRange(hsv, color_range["lower"], color_range["upper"])
                contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

                for contour in contours:
                    area = cv2.contourArea(contour)
                    if area > self.config.min_area:
                        x, y, w, h = cv2.boundingRect(contour)
                        detections.append(
                            {
                                "type": color_range["name"],
                                "bbox": (x, y, w, h),
                                "area": area,
                                "center": (x + w // 2, y + h // 2),
                                "track_id": None,
                            }
                        )
        except Exception:
            self.logger.exception("Object detection failed")
            return []

        self.logger.debug(
            "Detection time: %.3fs, Objects found: %d", perf_counter() - start_time, len(detections)
        )
        return detections


def parse_yolo_results(names: dict[int, str], results, allowed_ids=None) -> list[Detection]:
    """Convert Ultralytics results into VisionDrop detection dicts."""
    detections: list[Detection] = []
    for result in results:
        boxes = getattr(result, "boxes", None)
        if boxes is None:
            continue
        for box in boxes:
            class_id = int(box.cls.item())
            if allowed_ids is not None and class_id not in allowed_ids:
                continue
            x1, y1, x2, y2 = (int(v) for v in box.xyxy[0].tolist())
            track_id = None
            if getattr(box, "id", None) is not None:
                track_id = int(box.id.item())
            detections.append(
                {
                    "type": names.get(class_id, str(class_id)),
                    "bbox": (x1, y1, x2 - x1, y2 - y1),
                    "center": ((x1 + x2) // 2, (y1 + y2) // 2),
                    "confidence": float(box.conf.item()),
                    "track_id": track_id,
                }
            )
    return detections


class YoloDetector:
    """YOLO11 object detection with ByteTrack multi-object tracking."""

    def __init__(self, config: YoloConfig | None = None, model_dir: str | Path | None = None):
        try:
            from ultralytics import YOLO
        except ImportError as exc:  # pragma: no cover - depends on environment
            raise ImportError(
                "The YOLO detector requires the 'ultralytics' package "
                "(pip install ultralytics). Use --detector color for the fallback."
            ) from exc

        self.logger = logging.getLogger(__name__)
        self.config = config or YoloConfig()

        weights = Path(self.config.model)
        if not weights.is_absolute():
            directory = Path(model_dir).expanduser() if model_dir else default_model_dir()
            directory.mkdir(parents=True, exist_ok=True)
            weights = directory / weights
        self._model = YOLO(str(weights))

        self._allowed_ids = None
        if self.config.classes:
            names_to_ids = {name: i for i, name in self._model.names.items()}
            missing = [name for name in self.config.classes if name not in names_to_ids]
            if missing:
                self.logger.warning("Ignoring unknown classes: %s", ", ".join(missing))
            self._allowed_ids = {names_to_ids[name] for name in self.config.classes if name in names_to_ids}
        self.logger.info(
            "YoloDetector ready (%s, classes=%s)",
            Path(self.config.model).name,
            self.config.classes or "all",
        )

    def detect_objects(self, frame: np.ndarray) -> list[Detection]:
        start_time = perf_counter()
        kwargs = {
            "conf": self.config.confidence,
            "iou": self.config.iou,
            "imgsz": self.config.image_size,
            "device": self.config.device,
            "verbose": False,
        }
        if self.config.track:
            results = self._model.track(frame, persist=True, tracker=COCO_TRACKER, **kwargs)
        else:
            results = self._model.predict(frame, **kwargs)

        detections = parse_yolo_results(self._model.names, results, self._allowed_ids)
        self.logger.debug(
            "Detection time: %.3fs, Objects found: %d", perf_counter() - start_time, len(detections)
        )
        return detections


def draw_detections(frame, detections, color_map=None):
    """Draw one box per detection, labelled with class, track id, and confidence."""
    if color_map is None:
        color_map = {"yellow": (0, 255, 255), "red": (0, 0, 255)}

    for detection in detections:
        color = color_map.get(detection["type"], (0, 255, 0))
        x, y, w, h = detection["bbox"]
        cv2.rectangle(frame, (x, y), (x + w, y + h), color, 2)

        label = str(detection["type"])
        if detection.get("track_id") is not None:
            label += f" #{detection['track_id']}"
        if detection.get("confidence") is not None:
            label += f" {detection['confidence']:.2f}"

        cv2.putText(frame, label, (x, max(y - 10, 18)), cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, 2)

    return frame


def create_object_detector(
    kind: str = "yolo",
    yolo_config: YoloConfig | None = None,
    color_config: ColorDetectionConfig | None = None,
    model_dir: str | Path | None = None,
):
    """Build a detector by name. Raises ValueError for unknown kinds."""
    if kind == "color":
        return ColorObjectDetector(color_config)
    if kind == "yolo":
        return YoloDetector(yolo_config, model_dir=model_dir)
    raise ValueError(f"Unknown detector '{kind}'. Use 'yolo' or 'color'.")
