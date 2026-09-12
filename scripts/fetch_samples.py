"""Download small sample media for tests and manual checks into samples/.

Usage: python scripts/fetch_samples.py
"""

from __future__ import annotations

import urllib.request
from pathlib import Path

SAMPLES = {
    "woman_hands.jpg": "https://storage.googleapis.com/mediapipe-assets/woman_hands.jpg",
    "thumb_up.jpg": "https://storage.googleapis.com/mediapipe-assets/thumb_up.jpg",
    "bus.jpg": "https://ultralytics.com/images/bus.jpg",
}


def main() -> None:
    directory = Path(__file__).resolve().parent.parent / "samples"
    directory.mkdir(exist_ok=True)
    for name, url in SAMPLES.items():
        path = directory / name
        if path.exists():
            print(f"have      {path}")
            continue
        print(f"download  {url}")
        urllib.request.urlretrieve(url, path)
    print(f"samples in {directory}")


if __name__ == "__main__":
    main()
