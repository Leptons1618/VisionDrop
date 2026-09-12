"""The 1€ filter (Casiez et al., CHI 2012): speed-adaptive smoothing.

Smooths hand jitter when slow, reduces lag when fast. Parameters follow the
paper's tuning procedure: set beta=0 and pick min_cutoff, then raise beta until
lag during fast motion is acceptable. These are calibration knobs — tune per
camera and frame rate.
"""

from __future__ import annotations

import math
import time

Point = tuple[float, float]


class OneEuroFilter:
    def __init__(self, min_cutoff: float = 1.0, beta: float = 0.007, d_cutoff: float = 1.0):
        self.min_cutoff = min_cutoff
        self.beta = beta
        self.d_cutoff = d_cutoff
        self._x: float | None = None
        self._dx = 0.0
        self._t_prev: float | None = None

    @staticmethod
    def _alpha(cutoff: float, dt: float) -> float:
        tau = 1.0 / (2.0 * math.pi * cutoff)
        return 1.0 / (1.0 + tau / dt)

    def reset(self) -> None:
        self._x = None
        self._dx = 0.0
        self._t_prev = None

    def filter(self, value: float, timestamp: float | None = None) -> float:
        timestamp = time.perf_counter() if timestamp is None else timestamp
        if self._x is None or self._t_prev is None:
            self._x = value
            self._t_prev = timestamp
            return value

        dt = timestamp - self._t_prev
        if dt <= 0.0:
            return self._x

        dx = (value - self._x) / dt
        alpha_d = self._alpha(self.d_cutoff, dt)
        self._dx = alpha_d * dx + (1.0 - alpha_d) * self._dx

        cutoff = self.min_cutoff + self.beta * abs(self._dx)
        alpha = self._alpha(cutoff, dt)
        self._x = alpha * value + (1.0 - alpha) * self._x
        self._t_prev = timestamp
        return self._x


class PointFilter:
    """Applies the 1€ filter to both axes of a 2D point."""

    def __init__(self, min_cutoff: float = 1.0, beta: float = 0.007):
        self._x = OneEuroFilter(min_cutoff, beta)
        self._y = OneEuroFilter(min_cutoff, beta)

    def reset(self) -> None:
        self._x.reset()
        self._y.reset()

    def filter(self, point: Point, timestamp: float | None = None) -> Point:
        x, y = point
        return self._x.filter(float(x), timestamp), self._y.filter(float(y), timestamp)
