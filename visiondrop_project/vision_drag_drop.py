from tensorflow_config import configure_tensorflow
configure_tensorflow()  # Must be called before other imports

import os
# Suppress TensorFlow logging messages
os.environ['TF_CPP_MIN_LOG_LEVEL'] = '2'
os.environ['TF_ENABLE_ONEDNN_OPTS'] = '0'

import cv2
import logging
import signal
import sys
from hand_tracker import HandTracker
from object_detector import ObjectDetector
from config import *
from logging_config import setup_logging

def is_in_drop_zone(point, zones):
    x, y = point
    for zone in zones:
        zx1, zy1, zx2, zy2 = zone
        if zx1 < x < zx2 and zy1 < y < zy2:
            return True
    return False

def signal_handler(sig, frame):
    logger = logging.getLogger(__name__)
    logger.info("Ctrl+C detected. Shutting down gracefully...")
    cv2.destroyAllWindows()
    sys.exit(0)

def main():
    # Setup logging
    setup_logging()
    logger = logging.getLogger(__name__)
    logger.info("Starting VisionDrop application")

    # Setup signal handler for Ctrl+C
    signal.signal(signal.SIGINT, signal_handler)

    # Initialize components
    cap = cv2.VideoCapture(CAMERA_INDEX)
    if not cap.isOpened():
        logger.error("Failed to open camera")
        return
    
    logger.info(f"Camera initialized with resolution: {FRAME_WIDTH}x{FRAME_HEIGHT}")
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, FRAME_WIDTH)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, FRAME_HEIGHT)
    
    hand_tracker = HandTracker(
        detection_confidence=HAND_DETECTION_CONFIDENCE,
        tracking_confidence=HAND_TRACKING_CONFIDENCE
    )
    object_detector = ObjectDetector()
    logger.info("Components initialized successfully")

    # Display quit instructions
    logger.info("Press 'q' or Ctrl+C to quit the application")

    while cap.isOpened():
        ret, frame = cap.read()
        if not ret:
            break

        # Flip frame horizontally for natural interaction
        frame = cv2.flip(frame, 1)

        # Detect hands
        frame, hand_landmarks = hand_tracker.find_hands(frame)

        # Detect objects
        detections = object_detector.detect_objects(frame)
        
        # Process hands and objects
        if hand_landmarks:
            for landmarks in hand_landmarks:
                hand_center = hand_tracker.get_hand_center(landmarks, frame.shape)
                if hand_center:
                    # Draw hand center
                    cv2.circle(frame, hand_center, 5, COLORS['red'], -1)
                    
                    # Check if hand is in drop zone
                    if is_in_drop_zone(hand_center, DROP_ZONES):
                        cv2.circle(frame, hand_center, 10, COLORS['green'], 2)

        # Draw drop zones
        for zone in DROP_ZONES:
            cv2.rectangle(frame, (zone[0], zone[1]), (zone[2], zone[3]), COLORS['blue'], 2)

        # Draw object detections
        frame = object_detector.draw_detections(frame, detections)

        # Add quit message to frame
        quit_text = "Press 'q' or Ctrl+C to quit"
        cv2.putText(frame, quit_text, (10, frame.shape[0] - 10),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.5, COLORS['red'], 1)

        # Display the frame
        cv2.imshow('VisionDrop', frame)

        if cv2.waitKey(1) & 0xFF == ord('q'):
            logger.info("Quit command ('q') detected. Shutting down...")
            break

    logger.info("Application shutting down")
    cap.release()
    cv2.destroyAllWindows()

if __name__ == "__main__":
    main()
