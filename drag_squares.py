from tensorflow_config import configure_tensorflow
configure_tensorflow()  # Must be called before other imports

import cv2
import numpy as np
import mediapipe as mp
import logging
from config import *
from logging_config import setup_logging
from collections import deque
import os

# Suppress TensorFlow warnings
os.environ['TF_CPP_MIN_LOG_LEVEL'] = '3'
os.environ['TF_ENABLE_ONEDNN_OPTS'] = '0'

class SquareDragger:
    def __init__(self):
        self.mp_hands = mp.solutions.hands
        self.hands = self.mp_hands.Hands(
            min_detection_confidence=0.7,
            max_num_hands=1,
            model_complexity=0  # Use lighter model for better performance
        )
        
        # Initialize squares with random positions
        self.squares = []
        self.square_size = 50
        self.alpha = 0.4  # Transparency
        
        # Create squares with different colors
        colors = [(255,0,0), (0,255,0), (0,0,255), (255,255,0), (0,255,255)]
        for i in range(5):
            x = 100 + i * 100
            y = 100
            self.squares.append({
                'pos': [x, y],
                'color': colors[i],
                'dragging': False
            })
        
        # Initialize trail system
        self.trail_length = 20  # Number of points in trail
        self.trail_points = deque(maxlen=self.trail_length)
        self.trail_alpha = 0.6  # Starting opacity
        self.trail_fade = 0.95  # Fade factor per point
        
        self.logger = logging.getLogger(__name__)
        self.logger.info("SquareDragger initialized with trail system")
        
        # Add pinch detection parameters
        self.pinch_threshold = 0.04  # Increased threshold for more reliable detection
        self.smoothing_factor = 0.5  # For smooth pinch detection
        self.last_pinch_state = False
        self.pinch_cooldown = 0
        self.cooldown_frames = 5  # Frames to wait before allowing new pinch

    def is_pinching(self, hand_landmarks):
        """Improved pinch detection with smoothing and additional fingers check"""
        if not hand_landmarks:
            return False

        if self.pinch_cooldown > 0:
            self.pinch_cooldown -= 1
            return self.last_pinch_state

        # Get all relevant finger landmarks
        index_tip = hand_landmarks.landmark[8]
        index_pip = hand_landmarks.landmark[6]  # Index finger PIP joint
        middle_tip = hand_landmarks.landmark[12]
        middle_pip = hand_landmarks.landmark[10]  # Middle finger PIP joint
        thumb_tip = hand_landmarks.landmark[4]

        # Calculate distances
        pinch_distance = np.sqrt(
            (index_tip.x - thumb_tip.x)**2 + 
            (index_tip.y - thumb_tip.y)**2
        )

        # Check if fingers are extended (using PIP joints)
        index_extended = index_tip.y < index_pip.y
        middle_extended = middle_tip.y < middle_pip.y

        # Determine pinch state with multiple conditions
        current_pinch = (pinch_distance < self.pinch_threshold and 
                        index_extended and middle_extended)

        # Apply smoothing
        smoothed_pinch = (current_pinch or 
                         (self.last_pinch_state and pinch_distance < self.pinch_threshold * 1.2))

        # Update state
        if smoothed_pinch != self.last_pinch_state:
            self.pinch_cooldown = self.cooldown_frames
        self.last_pinch_state = smoothed_pinch

        return smoothed_pinch

    def get_pinch_position(self, hand_landmarks, frame_shape):
        """Improved pinch position calculation"""
        if not hand_landmarks:
            return None

        # Use thumb and index finger midpoint for better accuracy
        thumb_tip = hand_landmarks.landmark[4]
        index_tip = hand_landmarks.landmark[8]

        x = int((thumb_tip.x + index_tip.x) * frame_shape[1] / 2)
        y = int((thumb_tip.y + index_tip.y) * frame_shape[0] / 2)
        
        return [x, y]

    def point_in_square(self, point, square):
        """Check if point is inside square"""
        x, y = point
        sx, sy = square['pos']
        return (sx <= x <= sx + self.square_size and 
                sy <= y <= sy + self.square_size)

    def draw_squares(self, frame):
        """Draw all squares on frame"""
        overlay = frame.copy()
        
        for square in self.squares:
            x, y = square['pos']
            color = square['color']
            cv2.rectangle(overlay, (x, y), 
                         (x + self.square_size, y + self.square_size),
                         color, -1)
        
        # Apply transparency
        cv2.addWeighted(overlay, self.alpha, frame, 1 - self.alpha, 0, frame)
        
        return frame

    def draw_trail(self, frame):
        """Draw the trailing effect with fade"""
        overlay = frame.copy()
        
        if len(self.trail_points) > 1:
            alpha = self.trail_alpha
            for i in range(len(self.trail_points) - 1):
                start_point = tuple(map(int, self.trail_points[i]))
                end_point = tuple(map(int, self.trail_points[i + 1]))
                
                cv2.line(overlay, start_point, end_point, 
                        (0, 255, 255), 2)  # Yellow trail
                alpha *= self.trail_fade
            
            cv2.addWeighted(overlay, alpha, frame, 1 - alpha, 0, frame)
        
        return frame

def main():
    setup_logging()
    logger = logging.getLogger(__name__)
    logger.info("Starting Square Dragger application")

    cap = cv2.VideoCapture(CAMERA_INDEX)
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, FRAME_WIDTH)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, FRAME_HEIGHT)

    dragger = SquareDragger()

    # Add performance optimizations
    cv2.setNumThreads(4)  # Optimize OpenCV threading
    
    while cap.isOpened():
        ret, frame = cap.read()
        if not ret:
            break

        # Process frame at half resolution for better performance
        frame = cv2.resize(frame, None, fx=0.5, fy=0.5)
        frame = cv2.flip(frame, 1)

        # Convert to RGB only once
        rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        rgb_frame.flags.writeable = False  # Optimization for MediaPipe
        results = dragger.hands.process(rgb_frame)
        rgb_frame.flags.writeable = True

        # Scale frame back to original size
        frame = cv2.resize(frame, (FRAME_WIDTH, FRAME_HEIGHT))

        # Draw squares first
        frame = dragger.draw_squares(frame)

        if results.multi_hand_landmarks:
            hand_landmarks = results.multi_hand_landmarks[0]  # Get first hand
            pinch_pos = dragger.get_pinch_position(hand_landmarks, frame.shape)
            is_pinching = dragger.is_pinching(hand_landmarks)

            # Update trail
            if pinch_pos:
                dragger.trail_points.append(pinch_pos)
                
                # Draw trail before the current position
                frame = dragger.draw_trail(frame)
                
                # Draw current pinch position
                cv2.circle(frame, tuple(pinch_pos), 5, (0, 255, 0), -1)

            # Handle dragging
            for square in dragger.squares:
                if is_pinching:
                    if (not square['dragging'] and 
                        dragger.point_in_square(pinch_pos, square)):
                        square['dragging'] = True
                        logger.debug(f"Started dragging square at {square['pos']}")
                    
                    if square['dragging']:
                        square['pos'] = [
                            pinch_pos[0] - dragger.square_size//2,
                            pinch_pos[1] - dragger.square_size//2
                        ]
                else:
                    if square['dragging']:
                        logger.debug(f"Released square at {square['pos']}")
                    square['dragging'] = False
        else:
            # Clear trail when hand is not detected
            dragger.trail_points.clear()

        # Display instructions
        cv2.putText(frame, "Pinch to drag squares", (10, 30),
                    cv2.FONT_HERSHEY_SIMPLEX, 1, (255, 255, 255), 2)

        cv2.imshow('Square Dragger', frame)

        if cv2.waitKey(1) & 0xFF == ord('q'):
            break

    cap.release()
    cv2.destroyAllWindows()

if __name__ == "__main__":
    main()
