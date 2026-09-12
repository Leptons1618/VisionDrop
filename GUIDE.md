# VisionDrop User Guide

## Program Purpose
VisionDrop is an interactive computer vision application that allows users to manipulate virtual objects using hand gestures. Think of it as a "virtual drag and drop" interface where you can move objects between defined zones using natural hand movements.

## Key Features
- Hand tracking in real-time
- Object detection and tracking (YOLO11 + ByteTrack; HSV color fallback)
- Pinch to grab, move, and release objects (debounced, filtered cursor)
- Virtual drop zones
- Visual feedback for interactions

## Setup Instructions

1. Environment Setup
```bash
# Create a virtual environment (use Python 3.10-3.12)
uv venv --python 3.12 .venv

# Activate virtual environment
# Windows:
.venv\Scripts\activate
# Linux/Mac:
source .venv/bin/activate

# Install the package
pip install -e ".[dev]"
```

2. Hardware Requirements
- Webcam
- Well-lit environment
- Yellow objects for detection (e.g., sticky notes, tennis balls)

## System Requirements

### Minimum Requirements
- CPU: Intel Core i5 or AMD Ryzen 5
- RAM: 8GB
- OS: Windows 10, macOS 10.14+, Linux
- Storage: 500MB free space
- Camera: 720p webcam

### Recommended Requirements
- CPU: Intel Core i7 or AMD Ryzen 7
- RAM: 16GB
- GPU: NVIDIA GTX 1660 or better
- Camera: 1080p webcam
- Storage: 1GB free space

## Usage Examples

### Basic Usage
1. Run the program:
```bash
python -m visiondrop
```

2. You will see:
- Your webcam feed
- Blue rectangles (drop zones)
- Hand tracking skeleton
- Detected objects with class, track ID, and confidence
- A green line linking your pinch point to the object you are reaching for
- FPS counter; latency percentiles with `--debug`

### Interaction Examples

1. **Hand Detection**
   - Hold your hand up to the camera
   - You'll see a hand skeleton overlay
   - A red dot marks the pinch point between thumb and index finger

2. **Object Detection**
   - Hold an everyday object in view (cup, bottle, phone, ...)
   - Boxes appear with class, track ID, and confidence
   - Move your pinch point near an object to link to it (green line)

3. **Grab & Drop**
   - Pinch thumb and index together over an object to grab it (yellow HELD box)
   - The object follows your hand; brief occlusion does not drop it
   - Open your hand to release

4. **Drop Zone Interaction**
   - Move your hand into a blue rectangle
   - The pinch point turns green when in zone
   - Release over a zone to score; the HUD shows score and misses
   - The onboarding hint fades away after your first successful drop

## Common Use Cases

1. **Educational Demo**
   ```plaintext
   Drop Zone 1        Drop Zone 2
   [Learning A]  -->  [Learning B]
   Move objects between zones to sort or categorize
   ```

2. **Interactive Game**
   ```plaintext
   Drop Zone 1        Drop Zone 2
   [Basket A]    -->  [Basket B]
   Score points by moving objects to correct zones
   ```

## Customization

### Modifying Colors
Edit `src/visiondrop/config.py` to change display colors:
```python
DEFAULT_COLORS = {
    "red": (0, 0, 255),
    "green": (0, 255, 0),
    ...
}
```

### Adjusting Drop Zones
Edit `src/visiondrop/config.py` to modify zones:
```python
DEFAULT_DROP_ZONES = (
    DropZone(100, 100, 420, 420, label="A"),
    DropZone(500, 100, 820, 420, label="B"),
)
```

## Advanced Configuration

### Session Logging
```bash
python -m visiondrop --log logs/session.jsonl
python -m visiondrop --condition dwell --log logs/session_dwell.jsonl
python scripts/analyze_session.py logs/session.jsonl   # metrics + plot
```

### Performance Tuning
```python
# In src/visiondrop/config.py
AppConfig(frame_width=1280, frame_height=720)   # Lower to 640x480 for speed

# In src/visiondrop/config.py
HandTrackingConfig(num_hands=1, min_detection_confidence=0.6)
```

### Custom Detection Profiles
```python
# In src/visiondrop/config.py
HandTrackingConfig(
    num_hands=2,
    min_detection_confidence=0.9,       # high precision profile
    min_hand_presence_confidence=0.9,
    min_tracking_confidence=0.9,
)
```

## Troubleshooting

1. **No Camera Feed**
   - Pass the camera index with `--source` (0, 1, 2, ...)
   - Try a video file instead: `--source clip.mp4`
   - Verify webcam connection

2. **Poor Object Detection**
   - Improve lighting
   - Restrict classes: `--classes cup,bottle`
   - For the color fallback, use brighter objects or adjust HSV values in `src/visiondrop/config.py`

3. **Hand Tracking Issues**
   - Keep hands in camera view
   - Ensure good lighting
   - Adjust confidence values in config.py

## Tips for Best Results

1. **Lighting**
   - Use consistent, bright lighting
   - Avoid backlighting
   - Minimize shadows

2. **Camera Setup**
   - Position camera at chest/head height
   - Keep 2-3 feet distance
   - Use stable mounting

3. **Performance**
   - Close other camera applications
   - Use dedicated GPU if available
   - Run in a clean environment
