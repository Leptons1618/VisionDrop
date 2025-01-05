import cv2
import numpy as np

class ObjectDetector:
    def __init__(self):
        # Initialize basic color detection
        self.lower_bound = np.array([20, 100, 100])  # HSV color range for detection
        self.upper_bound = np.array([30, 255, 255])  # Example: yellow color

    def detect_objects(self, frame):
        # Convert to HSV color space
        hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
        
        # Create a mask for color detection
        mask = cv2.inRange(hsv, self.lower_bound, self.upper_bound)
        
        # Find contours
        contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        
        detections = []
        for contour in contours:
            if cv2.contourArea(contour) > 500:  # Minimum area threshold
                x, y, w, h = cv2.boundingRect(contour)
                detections.append((x, y, w, h))
        
        return detections

    def draw_detections(self, frame, detections, color=(0, 255, 0)):
        for x, y, w, h in detections:
            cv2.rectangle(frame, (x, y), (x + w, y + h), color, 2)
        return frame
