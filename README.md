# VisionDrop

A computer vision-based drag and drop interface using hand tracking and object detection.

## Features

- Real-time hand tracking using MediaPipe
- Object detection using TensorFlow
- Virtual drop zones for object placement
- Interactive visual feedback

## Prerequisites

- Python 3.8 or higher
- Webcam or camera device
- GPU recommended for better performance

## Installation

1. Clone the repository:

```bash
git clone https://github.com/yourusername/VisionDrop.git
cd VisionDrop
```

1. Install dependencies:

```bash
pip install -r requirements.txt
```

## Usage

Run the main script:

```bash
python vision_drag_drop.py
```

- Press 'q' to quit the application
- Use your hand to interact with detected objects
- Green boxes indicate objects in drop zones
- Red boxes indicate objects outside drop zones
- Blue rectangles show valid drop zones

## Configuration

The application includes configurable drop zones and detection parameters in the main script. Modify the following variables to adjust behavior:

- `drop_zone`: List of drop zone coordinates
- `min_detection_confidence`: Adjust hand detection sensitivity
- `min_tracking_confidence`: Adjust hand tracking reliability

## License

[Your chosen license]

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.
