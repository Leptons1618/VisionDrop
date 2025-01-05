import cv2
import numpy as np
import logging
from time import time
from dataclasses import dataclass
from typing import List, Tuple, Dict, Optional

@dataclass
class DetectionConfig:
    min_area: float = 500
    color_ranges: List[Dict[str, np.ndarray]] = None
    detection_methods: List[str] = None
    enable_tracking: bool = False
    blur_kernel: Tuple[int, int] = (5, 5)

class ObjectDetector:
    def __init__(self, config: Optional[DetectionConfig] = None):
        self.logger = logging.getLogger(__name__)
        self.logger.info("Initializing Enhanced ObjectDetector")
        
        self.config = config or DetectionConfig()
        self.tracker = cv2.TrackerKCF_create() if self.config.enable_tracking else None
        self.tracking_initialized = False
        
        # Default color ranges if none provided
        if not self.config.color_ranges:
            self.config.color_ranges = [
                {
                    'name': 'yellow',
                    'lower': np.array([20, 100, 100]),
                    'upper': np.array([30, 255, 255])
                },
                {
                    'name': 'black',
                    'lower': np.array([0, 0, 0]),
                    'upper': np.array([180, 255, 30])
                },
            ]

    def preprocess_frame(self, frame):
        blurred = cv2.GaussianBlur(frame, self.config.blur_kernel, 0)
        return cv2.cvtColor(blurred, cv2.COLOR_BGR2HSV)

    def detect_objects(self, frame):
        start_time = time()
        hsv = self.preprocess_frame(frame)
        all_detections = []

        try:
            # Color-based detection
            for color_range in self.config.color_ranges:
                mask = cv2.inRange(hsv, color_range['lower'], color_range['upper'])
                contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
                
                for contour in contours:
                    area = cv2.contourArea(contour)
                    if area > self.config.min_area:
                        x, y, w, h = cv2.boundingRect(contour)
                        all_detections.append({
                            'type': color_range['name'],
                            'bbox': (x, y, w, h),
                            'area': area,
                            'center': (x + w//2, y + h//2)
                        })

            # Object tracking
            if self.config.enable_tracking and all_detections:
                if not self.tracking_initialized:
                    bbox = all_detections[0]['bbox']
                    self.tracker.init(frame, bbox)
                    self.tracking_initialized = True
                else:
                    success, bbox = self.tracker.update(frame)
                    if success:
                        all_detections.append({
                            'type': 'tracked',
                            'bbox': tuple(map(int, bbox)),
                            'confidence': success
                        })

        except Exception as e:
            self.logger.error(f"Detection error: {str(e)}")
            return []

        process_time = time() - start_time
        self.logger.debug(f"Detection time: {process_time:.3f}s, Objects found: {len(all_detections)}")
        return all_detections

    def draw_detections(self, frame, detections, color_map=None):
        if color_map is None:
            color_map = {
                'yellow': (0, 255, 255),
                'red': (0, 0, 255),
                'tracked': (255, 0, 0)
            }

        for detection in detections:
            color = color_map.get(detection['type'], (0, 255, 0))
            x, y, w, h = detection['bbox']
            cv2.rectangle(frame, (x, y), (x + w, y + h), color, 2)
            
            # Draw label
            label = f"{detection['type']}"
            if 'area' in detection:
                label += f" ({detection['area']:.0f}px)"
            cv2.putText(frame, label, (x, y-10), cv2.FONT_HERSHEY_SIMPLEX, 
                       0.5, color, 2)

        return frame
