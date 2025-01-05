import cv2
import numpy as np
import mediapipe as mp
import logging
from config import *
from logging_config import setup_logging
from collections import deque

class SquareDragger:
    def __init__(self):
        self.mp_hands = mp.solutions.hands
        self.hands = self.mp_hands.Hands(
            min_detection_confidence=0.7,
            max_num_hands=1
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

    def is_pinching(self, hand_landmarks):
        """Check if index and middle fingers are pinching"""
        if not hand_landmarks:
            return False
            
        index_tip = hand_landmarks.landmark[8]
        middle_tip = hand_landmarks.landmark[12]
        
        # Calculate distance between finger tips
        distance = np.sqrt(
            (index_tip.x - middle_tip.x)**2 + 
            (index_tip.y - middle_tip.y)**2
        )
        
        return distance < 0.03  # Threshold for pinch detection

    def get_pinch_position(self, hand_landmarks, frame_shape):
        """Get the midpoint between index and middle finger"""
        if not hand_landmarks:
            return None
            
        index_tip = hand_landmarks.landmark[8]
        middle_tip = hand_landmarks.landmark[12]
        
        x = int((index_tip.x + middle_tip.x) * frame_shape[1] / 2)
        y = int((index_tip.y + middle_tip.y) * frame_shape[0] / 2)
        
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

    while cap.isOpened():
        ret, frame = cap.read()
        if not ret:
            break

        frame = cv2.flip(frame, 1)
        rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        results = dragger.hands.process(rgb_frame)

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
