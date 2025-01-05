# Camera settings
CAMERA_INDEX = 0
FRAME_WIDTH = 800
FRAME_HEIGHT = 600

# Hand detection settings
HAND_DETECTION_CONFIDENCE = 0.5
HAND_TRACKING_CONFIDENCE = 0.5

# Drop zone settings
DROP_ZONES = [
    (100, 100, 300, 300),  # Zone 1: (x1, y1, x2, y2)
    (400, 100, 600, 300)   # Zone 2: (x1, y1, x2, y2)
]

# Colors (BGR format)
COLORS = {
    'red': (0, 0, 255),
    'green': (0, 255, 0),
    'blue': (255, 0, 0)
}
