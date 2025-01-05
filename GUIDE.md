# VisionDrop User Guide

## Program Purpose
VisionDrop is an interactive computer vision application that allows users to manipulate virtual objects using hand gestures. Think of it as a "virtual drag and drop" interface where you can move objects between defined zones using natural hand movements.

## Key Features
- Hand tracking in real-time
- Object detection (default: yellow objects)
- Virtual drop zones
- Visual feedback for interactions

## Setup Instructions

1. Environment Setup
```bash
# Create a virtual environment
python -m venv venv

# Activate virtual environment
# Windows:
venv\Scripts\activate
# Linux/Mac:
source venv/bin/activate

# Install requirements
pip install -r requirements.txt
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
python vision_drag_drop.py
```

2. You will see:
- Your webcam feed
- Blue rectangles (drop zones)
- Hand tracking skeleton
- Yellow object detection boxes
- Quit instructions at the bottom

### Interaction Examples

1. **Hand Detection**
   - Hold your hand up to the camera
   - You'll see a hand skeleton overlay
   - A red dot marks the hand center

2. **Object Detection**
   - Hold a yellow object in view
   - Green boxes will appear around yellow objects
   - Try using sticky notes or tennis balls

3. **Drop Zone Interaction**
   - Move your hand into a blue rectangle
   - The hand center dot turns green when in zone
   - Practice moving between zones

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
Edit `config.py` to change detection colors:
```python
# Example: Change yellow to red detection
self.lower_bound = np.array([0, 100, 100])  # Red in HSV
self.upper_bound = np.array([10, 255, 255])
```

### Adjusting Drop Zones
Edit `config.py` to modify zones:
```python
DROP_ZONES = [
    (100, 100, 300, 300),  # Zone 1: (x1, y1, x2, y2)
    (400, 100, 600, 300)   # Zone 2
]
```

## Advanced Configuration

### Performance Tuning
```python
# In config.py
ENABLE_GPU = True
PROCESSING_SCALE = 0.5  # Reduce for better performance
TRACKING_PRECISION = 0.8  # Adjust tracking sensitivity
```

### Custom Detection Profiles
```python
# In config.py
DETECTION_PROFILES = {
    'high_precision': {
        'confidence': 0.9,
        'min_tracking_confidence': 0.9
    },
    'performance': {
        'confidence': 0.7,
        'min_tracking_confidence': 0.7
    }
}
```

## Troubleshooting

1. **No Camera Feed**
   - Check CAMERA_INDEX in config.py
   - Try different indices (0, 1, 2)
   - Verify webcam connection

2. **Poor Object Detection**
   - Improve lighting
   - Use brighter yellow objects
   - Adjust HSV values in ObjectDetector

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
