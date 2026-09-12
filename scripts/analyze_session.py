"""Print metrics for a JSONL session and render a plot.

Usage: python scripts/analyze_session.py logs/session.jsonl [plot.png]
"""

import sys
from pathlib import Path

from visiondrop.analysis import load_session, render_plot, summarize


def main() -> int:
    if len(sys.argv) < 2:
        print(__doc__)
        return 2

    session = Path(sys.argv[1])
    frames, events = load_session(session)
    summary = summarize(frames, events)
    for key, value in summary.items():
        print(f"{key:20s} {value}")

    plot_path = Path(sys.argv[2]) if len(sys.argv) > 2 else session.with_suffix(".png")
    render_plot(frames, events, plot_path)
    print(f"{'plot':20s} {plot_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
