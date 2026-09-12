# VisionDrop

A computer vision-based drag and drop interface using hand tracking and object detection. This interactive application allows users to manipulate virtual objects using hand gestures in real-time.

## Features

- Real-time hand tracking using MediaPipe Tasks (21 landmarks, gesture labels)
- Object detection and multi-object tracking using YOLO11 + ByteTrack
- HSV color detection fallback for objects the model does not know
- Hand-object association: objects within the pinch radius are linked to the hand
- Pinch grab / drag / release with debounce, hysteresis, and 1€-filtered cursor
- Holds survive brief occlusion and cancel cleanly if the hand disappears
- Virtual drop zones with score/miss counters
- Audio cues, expanding drop flashes, and a pulsing onboarding hint
- JSONL session logging and an offline analysis script (`scripts/analyze_session.py`)
- Interactive gesture-based interface
- Logging system and latency HUD (`--debug`)
- Customizable detection zones, classes, and colors

## System Requirements

- Operating System: Windows 10/11, macOS 10.14+, or Linux
- CPU: Intel Core i5/AMD Ryzen 5 or better
- RAM: 8GB minimum, 16GB recommended
- GPU: Optional but recommended for better performance
- Storage: 500MB free space
- Display: 1280x720 minimum resolution

## Prerequisites

- Python 3.10–3.12 (MediaPipe does not ship wheels for Python 3.13+ in all environments)
- Webcam
- Well-lit environment
- Everyday objects for detection (cup, bottle, phone, ...) or yellow objects with `--detector color`
- NVIDIA GPU recommended for real-time YOLO inference (CPU works with `--imgsz 480`)
- Minimum 2GB free RAM for processing

## Installation

1. Clone the repository:
```bash
git clone https://github.com/yourusername/VisionDrop.git
cd VisionDrop
```

2. Create and activate a virtual environment (Python 3.10–3.12):
```bash
# With uv (recommended)
uv venv --python 3.12 .venv

# Or with the standard library
python3.12 -m venv .venv

# Activate (Windows)
.venv\Scripts\activate
# Activate (Linux/Mac)
source .venv/bin/activate
```

3. Install the package:
```bash
pip install -e ".[dev]"
```

## Usage

### Quick Start
1. Run the application:
```bash
python -m visiondrop
# or, after install:
visiondrop
```

On first run the MediaPipe model bundle and YOLO weights are downloaded and
cached in `~/.cache/visiondrop/models` (override with `--model-dir` or the
`VISIONDROP_MODEL_DIR` environment variable).

2. Interface Elements:
- Webcam feed with hand tracking overlay
- Blue rectangles indicating drop zones
- Boxes around detected objects labelled with class, track ID, and confidence
- Green line linking the pinch point to the associated object
- Pinch point (thumb tip + index tip midpoint) marked with a red dot
- FPS counter, plus latency percentiles with `--debug`

### Interaction Guide

1. **Hand Tracking**
   - Hold your hand up to the camera
   - Watch the hand skeleton overlay appear
   - Notice the red dot marking the pinch point between thumb and index finger

2. **Object Detection**
   - Present everyday objects (cup, bottle, cell phone, book, ...)
   - Observe boxes with class, track ID, and confidence
   - Restrict classes to reduce noise: `python -m visiondrop --classes cup,bottle,cell phone`
   - For yellow blobs instead: `python -m visiondrop --detector color`

3. **Grab & Drop**
   - Pinch thumb and index together over an object to grab it (yellow HELD box)
   - Move your hand and the object follows, even if briefly occluded
   - Open your hand to drop it

4. **Drop Zone Interaction**
   - Move your hand into the blue rectangles
   - Watch the pinch point turn green in zones
   - Release over a zone to score (chime); a miss gets a low tone
   - The HUD tracks score and misses; the hint disappears after your first score

## Configuration

### Camera Settings
Pass the camera index or a video file at the command line:
```bash
python -m visiondrop --source 1
python -m visiondrop --source clip.mp4
```
Frame size and hand-tracking confidences live in `src/visiondrop/config.py`
(`AppConfig`, `HandTrackingConfig`).

### Detection Settings
YOLO defaults live in `src/visiondrop/config.py` (`YoloConfig`): model,
confidence, inference size, device, and class allowlist. The CLI exposes the
common ones:

```bash
python -m visiondrop --classes cup,bottle --imgsz 480 --debug
```

To tune the HSV fallback, edit `ColorDetectionConfig` in the same file:
```python
ColorDetectionConfig(color_ranges=[{
    "name": "red",
    "lower": np.array([0, 100, 100]),   # Red in HSV
    "upper": np.array([10, 255, 255]),
}])
```

### Drop Zones
Customize zones in `src/visiondrop/config.py`:
```python
DEFAULT_DROP_ZONES = (
    DropZone(100, 100, 420, 420, label="A"),
    DropZone(500, 100, 820, 420, label="B"),
)
```

## Troubleshooting

### Common Issues
1. **No Camera Feed**
   - Verify the `--source` argument (try 1 or 2 for other cameras)
   - Check webcam connection
   - Try different USB ports

2. **Poor Detection**
   - Ensure proper lighting
   - Restrict the class allowlist (`--classes cup,bottle`) to reduce noise
   - For yellow blobs use the color fallback (`--detector color`) and adjust HSV values in `ColorDetectionConfig`

3. **Hand Tracking Issues**
   - Maintain hands in camera view
   - Improve lighting conditions
   - Fine-tune confidence values

### Advanced Troubleshooting

1. **Performance Issues**
   - Check the latency HUD: `python -m visiondrop --debug`
   - Lower detector inference size: `--imgsz 480`
   - Reduce frame resolution with `--width`/`--height`
   - YOLO uses the GPU automatically when PyTorch sees one; otherwise it runs on CPU

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
├── src/visiondrop/
│   ├── app.py             # Main loop, CLI entry point
│   ├── hands.py           # MediaPipe Tasks hand tracking + gesture labels
│   ├── objects.py         # YOLO11 detector, ByteTrack, HSV fallback
│   ├── association.py     # Hand-to-object linking
│   ├── filters.py         # 1€ filter for cursor/object smoothing
│   ├── interaction.py     # Grab/drag/drop state machine
│   ├── feedback.py        # Audio tones, drop flashes, onboarding hint
│   ├── session.py         # JSONL session recorder
│   ├── analysis.py        # Session metrics and latency plot
│   ├── config.py          # AppConfig, thresholds, drop zones, colors
│   ├── models.py          # Model weight download/cache
│   └── logging_config.py  # Logging setup
├── scripts/
│   ├── fetch_samples.py   # Download sample media into samples/
│   └── analyze_session.py # Print metrics and plot for a JSONL session
├── tests/                 # pytest suite (unit + sample integration)
├── docs/CASE_STUDY.md     # Project plan and research write-up
├── pyproject.toml         # Package metadata and dependencies
└── requirements.txt       # Direct dependencies (pip fallback)
```

## Development
```bash
pip install -e ".[dev]"
python scripts/fetch_samples.py   # real test media into samples/ (gitignored)
python -m pytest                  # unit tests plus sample integration checks
```

## Evaluation
```bash
# Record a session (works with a camera or a video file)
python -m visiondrop --log logs/session.jsonl

# Grab conditions: pinch (default) or dwell (hover 0.5 s to grab/drop)
python -m visiondrop --condition dwell --log logs/session.jsonl

# Metrics table + latency/event plot
python scripts/analyze_session.py logs/session.jsonl
```
Replaying the same video file reproduces the same timestamps and interaction
metrics; latency numbers describe the machine that recorded the session.
The full study procedure is in [docs/STUDY_PROTOCOL.md](docs/STUDY_PROTOCOL.md).

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
