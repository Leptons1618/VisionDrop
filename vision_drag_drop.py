import cv2
from hand_tracker import HandTracker
from object_detector import ObjectDetector
from config import *

def is_in_drop_zone(point, zones):
    x, y = point
    for zone in zones:
        zx1, zy1, zx2, zy2 = zone
        if zx1 < x < zx2 and zy1 < y < zy2:
            return True
    return False

def main():
    # Initialize components
    cap = cv2.VideoCapture(CAMERA_INDEX)
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, FRAME_WIDTH)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, FRAME_HEIGHT)
    
    hand_tracker = HandTracker(
        detection_confidence=HAND_DETECTION_CONFIDENCE,
        tracking_confidence=HAND_TRACKING_CONFIDENCE
    )
    object_detector = ObjectDetector()

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

        # Display the frame
        cv2.imshow('VisionDrop', frame)

        if cv2.waitKey(1) & 0xFF == ord('q'):
            break

    cap.release()
    cv2.destroyAllWindows()

if __name__ == "__main__":
    main()
