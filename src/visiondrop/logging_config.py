"""Logging setup for VisionDrop."""

from __future__ import annotations

import logging
import os
from datetime import datetime


def setup_logging(level: int = logging.INFO, log_dir: str = "logs") -> str:
    """Configure console and file logging. Returns the log file path."""
    os.makedirs(log_dir, exist_ok=True)
    log_filename = os.path.join(log_dir, f"visiondrop_{datetime.now():%Y%m%d_%H%M%S}.log")

    logging.basicConfig(
        level=level,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        handlers=[
            logging.FileHandler(log_filename),
            logging.StreamHandler(),
        ],
    )

    for noisy in ("absl", "mediapipe", "tensorflow"):
        logging.getLogger(noisy).setLevel(logging.ERROR)

    return log_filename
