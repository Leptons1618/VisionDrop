import cv2
import mediapipe as mp
import numpy as np
import tensorflow as tf

# Initialize MediaPipe Hands
mp_hands = mp.solutions.hands
mp_drawing = mp.solutions.drawing_utils

# Load pre-trained object detection model (YOLOv8 or SSD as example)
# Assuming you have a TensorFlow SavedModel for object detection
model = tf.saved_model.load("saved_model")

# Define constants for virtual drop zones
drop_zone = [(100, 100, 300, 300), (400, 100, 600, 300)]  # Example zones

# Function to detect objects using the pre-trained model
def detect_objects(frame):
    input_tensor = tf.convert_to_tensor([frame], dtype=tf.uint8)
    detections = model(input_tensor)
    return detections

# Function to check if an object is within a drop zone
def is_in_drop_zone(object_coords, zones):
    x, y, w, h = object_coords
    for zone in zones:
        zx1, zy1, zx2, zy2 = zone
        if zx1 < x < zx2 and zy1 < y < zy2:
            return zone
    return None

# Initialize Video Capture
cap = cv2.VideoCapture(0)

with mp_hands.Hands(min_detection_confidence=0.5, min_tracking_confidence=0.5) as hands:
    while cap.isOpened():
        ret, frame = cap.read()
        if not ret:
            break

        # Flip the frame for natural interaction
        frame = cv2.flip(frame, 1)
        frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)

        # Process hand detection
        results = hands.process(frame_rgb)

        # Detect objects in the frame
        detections = detect_objects(frame)

        # Draw object bounding boxes and check drop zones
        for detection in detections['detection_boxes']:
            x1, y1, x2, y2 = int(detection[0]), int(detection[1]), int(detection[2]), int(detection[3])
            object_coords = (x1, y1, x2 - x1, y2 - y1)

            zone = is_in_drop_zone(object_coords, drop_zone)
            color = (0, 255, 0) if zone else (0, 0, 255)
            cv2.rectangle(frame, (x1, y1), (x2, y2), color, 2)

        # Draw drop zones
        for zone in drop_zone:
            cv2.rectangle(frame, (zone[0], zone[1]), (zone[2], zone[3]), (255, 0, 0), 2)

        # Draw hand landmarks if detected
        if results.multi_hand_landmarks:
            for hand_landmarks in results.multi_hand_landmarks:
                mp_drawing.draw_landmarks(frame, hand_landmarks, mp_hands.HAND_CONNECTIONS)

        # Display the frame
        cv2.imshow('VisionDrop', frame)

        # Break loop on 'q' key press
        if cv2.waitKey(1) & 0xFF == ord('q'):
            break

# Release resources
cap.release()
cv2.destroyAllWindows()
