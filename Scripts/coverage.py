#!/usr/bin/env python3
"""Line-coverage gate for VisionDropCore (SRS MNT-2).

The engine is the module whose behaviour the product depends on and the one
module that can be exercised completely without a camera, a display or a
permission — so it is the one worth gating.

    swift test --enable-code-coverage
    python3 Scripts/coverage.py [--minimum 85] [--module VisionDropCore]
"""

import argparse
import collections
import json
import pathlib
import subprocess
import sys


def codecov_path() -> pathlib.Path:
    output = subprocess.run(
        ["swift", "test", "--enable-code-coverage", "--show-codecov-path"],
        capture_output=True, text=True, check=True,
    )
    return pathlib.Path(output.stdout.strip())


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--minimum", type=float, default=85.0)
    parser.add_argument("--module", default="VisionDropCore")
    args = parser.parse_args()

    report = json.loads(codecov_path().read_text())
    needle = f"/Sources/{args.module}/"
    files = collections.defaultdict(lambda: [0, 0])

    for export in report["data"]:
        for entry in export["files"]:
            if needle not in entry["filename"]:
                continue
            lines = entry["summary"]["lines"]
            name = entry["filename"].split("/Sources/", 1)[1]
            files[name][0] += lines["covered"]
            files[name][1] += lines["count"]

    if not files:
        print(f"no coverage data for {args.module}", file=sys.stderr)
        return 1

    for name, (covered, total) in sorted(files.items(), key=lambda kv: kv[1][0] / max(kv[1][1], 1)):
        print(f"  {100 * covered / max(total, 1):5.1f}%  {covered:4d}/{total:<4d}  {name}")

    covered = sum(value[0] for value in files.values())
    total = sum(value[1] for value in files.values())
    percent = 100 * covered / max(total, 1)
    print(f"\n{args.module}: {percent:.1f}% ({covered}/{total} lines), gate {args.minimum:.0f}%")

    if percent < args.minimum:
        print(f"FAIL: coverage {percent:.1f}% is below the {args.minimum:.0f}% gate", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
