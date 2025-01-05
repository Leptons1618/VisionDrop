import mediapipe as mp
import cv2

class HandTracker:
    def __init__(self, detection_confidence=0.5, tracking_confidence=0.5):
        self.mp_hands = mp.solutions.hands
        self.mp_drawing = mp.solutions.drawing_utils
        self.hands = self.mp_hands.Hands(
            min_detection_confidence=detection_confidence,
            min_tracking_confidence=tracking_confidence
        )

    def find_hands(self, frame, draw=True):
        frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        results = self.hands.process(frame_rgb)
        
        if results.multi_hand_landmarks and draw:
            for hand_landmarks in results.multi_hand_landmarks:
                self.mp_drawing.draw_landmarks(
                    frame,
                    hand_landmarks,
                    self.mp_hands.HAND_CONNECTIONS
                )
        
        return frame, results.multi_hand_landmarks

    def get_hand_center(self, hand_landmarks, frame_shape):
        if hand_landmarks:
            center_x = int(hand_landmarks.landmark[9].x * frame_shape[1])
            center_y = int(hand_landmarks.landmark[9].y * frame_shape[0])
            return (center_x, center_y)
        return None
