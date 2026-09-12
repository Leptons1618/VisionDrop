"""Download and cache MediaPipe model bundles."""

from __future__ import annotations

import logging
import os
import urllib.request
from pathlib import Path

logger = logging.getLogger(__name__)

MODEL_URLS: dict[str, str] = {
    "gesture_recognizer": (
        "https://storage.googleapis.com/mediapipe-models/gesture_recognizer/"
        "gesture_recognizer/float16/1/gesture_recognizer.task"
    ),
    "hand_landmarker": (
        "https://storage.googleapis.com/mediapipe-models/hand_landmarker/"
        "hand_landmarker/float16/1/hand_landmarker.task"
    ),
}

_ENV_MODEL_DIR = "VISIONDROP_MODEL_DIR"


def default_model_dir() -> Path:
    """Return the cache directory for model bundles.

    Override with the VISIONDROP_MODEL_DIR environment variable.
    """
    override = os.environ.get(_ENV_MODEL_DIR)
    if override:
        return Path(override).expanduser()
    cache_home = os.environ.get("XDG_CACHE_HOME")
    base = Path(cache_home).expanduser() if cache_home else Path.home() / ".cache"
    return base / "visiondrop" / "models"


def ensure_model(name: str, model_dir: str | Path | None = None) -> Path:
    """Return the local path of a model bundle, downloading it on first use."""
    if name not in MODEL_URLS:
        raise KeyError(f"Unknown model '{name}'. Available: {', '.join(sorted(MODEL_URLS))}")

    directory = Path(model_dir).expanduser() if model_dir else default_model_dir()
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / f"{name}.task"
    if path.exists():
        return path

    url = MODEL_URLS[name]
    logger.info("Downloading %s model to %s", name, path)
    partial = path.with_suffix(".task.part")
    urllib.request.urlretrieve(url, partial)
    partial.replace(path)
    return path
