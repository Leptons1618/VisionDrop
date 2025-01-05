# VisionDrop

A computer vision-based drag and drop interface using hand tracking and object detection. This interactive application allows users to manipulate virtual objects using hand gestures in real-time.

## Features

- Real-time hand tracking using MediaPipe
- Object detection using color-based tracking (default: yellow objects)
- Virtual drop zones with visual feedback
- Interactive gesture-based interface
- Logging system for debugging and monitoring
- Customizable detection zones and colors

## System Requirements

- Operating System: Windows 10/11, macOS 10.14+, or Linux
- CPU: Intel Core i5/AMD Ryzen 5 or better
- RAM: 8GB minimum, 16GB recommended
- GPU: Optional but recommended for better performance
- Storage: 500MB free space
- Display: 1280x720 minimum resolution

## Prerequisites

- Python 3.8+
- Webcam
- Well-lit environment
- Yellow objects for detection (e.g., sticky notes, tennis balls)
- CUDA-compatible GPU (optional, for improved performance)
- Minimum 2GB free RAM for processing

## Installation

1. Clone the repository:
```bash
git clone https://github.com/yourusername/VisionDrop.git
cd VisionDrop
```

2. Create and activate virtual environment:
```bash
# Create virtual environment
python -m venv venv

# Activate (Windows)
venv\Scripts\activate
# Activate (Linux/Mac)
source venv/bin/activate
```

3. Install dependencies:
```bash
pip install -r requirements.txt
```

## Usage

### Quick Start
1. Run the application:
```bash
python vision_drag_drop.py
```

2. Interface Elements:
- Webcam feed with hand tracking overlay
- Blue rectangles indicating drop zones
- Green boxes around detected yellow objects
- Hand center marked with a red dot
- Quit instructions at the bottom

### Interaction Guide

1. **Hand Tracking**
   - Hold your hand up to the camera
   - Watch the hand skeleton overlay appear
   - Notice the red dot marking your hand's center

2. **Object Detection**
   - Present yellow objects to the camera
   - Observe green boxes around detected objects
   - Try different yellow items (sticky notes, tennis balls)

3. **Drop Zone Interaction**
   - Move your hand into the blue rectangles
   - Watch the hand center dot turn green in zones
   - Practice moving between different zones

## Configuration

### Camera Settings
Edit `config.py` to adjust camera parameters:
```python
CAMERA_INDEX = 0  # Try 1 or 2 if camera not found
FRAME_WIDTH = 640
FRAME_HEIGHT = 480
```

### Detection Settings
Modify color detection in `object_detector.py`:
```python
# Example: Change to detect red objects
self.lower_bound = np.array([0, 100, 100])   # Red in HSV
self.upper_bound = np.array([10, 255, 255])
```

### Drop Zones
Customize zones in `config.py`:
```python
DROP_ZONES = [
    (100, 100, 300, 300),  # Zone 1: (x1, y1, x2, y2)
    (400, 100, 600, 300)   # Zone 2
]
```

## Troubleshooting

### Common Issues
1. **No Camera Feed**
   - Verify CAMERA_INDEX in config.py
   - Check webcam connection
   - Try different USB ports

2. **Poor Detection**
   - Ensure proper lighting
   - Use brighter yellow objects
   - Adjust HSV values in ObjectDetector

3. **Hand Tracking Issues**
   - Maintain hands in camera view
   - Improve lighting conditions
   - Fine-tune confidence values

### Advanced Troubleshooting

1. **Performance Issues**
   - Check CPU/RAM usage in Task Manager
   - Enable GPU acceleration in config.py
   - Reduce frame resolution if needed

2. **Installation Problems**
   - Update pip: `python -m pip install --upgrade pip`
   - Install Visual C++ Redistributable (Windows)
   - Check Python version compatibility

3. **Runtime Errors**
   - Clear cache: `pip cache purge`
   - Reinstall dependencies
   - Check system logs

### Best Practices
1. **Environment Setup**
   - Use consistent, bright lighting
   - Avoid backlighting
   - Minimize background movement

2. **Camera Positioning**
   - Mount at chest/head height
   - Maintain 2-3 feet distance
   - Use stable surface

3. **Performance Tips**
   - Close other camera applications
   - Use dedicated GPU if available
   - Keep background simple

## Project Structure
```
VisionDrop/
├── vision_drag_drop.py  # Main application
├── hand_tracker.py      # Hand tracking module
├── object_detector.py   # Object detection module
├── config.py           # Configuration settings
├── logging_config.py   # Logging setup
├── requirements.txt    # Dependencies
└── README.md          # Documentation
```

## Contributing

1. Fork the repository
2. Create your feature branch (`git checkout -b feature/AmazingFeature`)
3. Commit your changes (`git commit -m 'Add some AmazingFeature'`)
4. Push to the branch (`git push origin feature/AmazingFeature`)
5. Open a Pull Request

## License

This project is licensed under the MIT License - see the LICENSE file for details.

## Acknowledgments

- MediaPipe for hand tracking capabilities
- OpenCV for computer vision functionality
- Contributors and maintainers
