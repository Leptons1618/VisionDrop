# VisionDrop

A computer vision-based drag and drop interface using hand tracking and object detection.

## Features

- Real-time hand tracking using MediaPipe
- Object detection using color-based tracking
- Virtual drop zones with visual feedback
- Interactive gesture-based interface

## Prerequisites

- Python 3.8+
- Webcam
- Sufficient lighting for hand and object detection

## Installation

1.Clone the repository:

```bash
git clone https://github.com/yourusername/VisionDrop.git
cd VisionDrop
```plaintext

2.Install dependencies:

```bash
pip install -r requirements.txt
```plaintext

## Usage

Run the main application:

```bash
python vision_drag_drop.py
```

### Controls

- Use your hands naturally in front of the camera
- Move objects to the highlighted drop zones
- Press 'q' to quit the application

## Configuration

You can modify the following settings in `config.py`:

- Camera settings (resolution, camera index)
- Hand detection sensitivity
- Drop zone positions
- Color definitions

## Project Structure

```
VisionDrop/
├── vision_drag_drop.py  # Main application
├── hand_tracker.py      # Hand tracking module
├── object_detector.py   # Object detection module
├── config.py           # Configuration settings
├── requirements.txt    # Project dependencies
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

- MediaPipe for hand tracking
- OpenCV for computer vision capabilities
