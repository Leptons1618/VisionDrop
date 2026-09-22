"""Signal filtering for noisy pointer input.

The One Euro filter is the default because it balances jitter and lag: a low
cutoff at low speed removes jitter, while the cutoff rises with speed to avoid
perceptible lag. See Casiez, Roussel & Vogel, CHI 2012 (PLAN.md 3.2).
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field

import numpy as np


def alpha(cutoff: float, dt: float) -> float:
    """Smoothing factor for a first-order low-pass at ``cutoff`` Hz."""
    tau = 1.0 / (2.0 * math.pi * cutoff)
    return 1.0 / (1.0 + tau / dt)


@dataclass
class LowPass:
    """First-order low-pass with an externally supplied smoothing factor."""

    value: float | None = None

    def filter(self, x: float, a: float) -> float:
        if self.value is None:
            self.value = x
        else:
            self.value = a * x + (1.0 - a) * self.value
        return self.value

    def reset(self) -> None:
        self.value = None


@dataclass
class OneEuroFilter:
    """Scalar One Euro filter with timestamp-based (or fixed-rate) updates."""

    min_cutoff: float = 1.0
    beta: float = 0.0
    d_cutoff: float = 1.0
    freq: float = 30.0

    _x: LowPass = field(default_factory=LowPass, init=False, repr=False)
    _dx: LowPass = field(default_factory=LowPass, init=False, repr=False)
    _last_x: float | None = field(default=None, init=False, repr=False)
    _last_t: float | None = field(default=None, init=False, repr=False)

    def reset(self) -> None:
        self._x.reset()
        self._dx.reset()
        self._last_x = None
        self._last_t = None

    def __call__(self, x: float, t: float | None = None) -> float:
        if t is not None and self._last_t is not None:
            dt = max(t - self._last_t, 1e-6)
        else:
            dt = 1.0 / self.freq

        if self._last_x is None:
            dx = 0.0
        else:
            dx = (x - self._last_x) / dt

        dx_hat = self._dx.filter(dx, alpha(self.d_cutoff, dt))
        cutoff = self.min_cutoff + self.beta * abs(dx_hat)
        x_hat = self._x.filter(x, alpha(cutoff, dt))

        self._last_x = x
        if t is not None:
            self._last_t = t
        return x_hat


class OneEuroFilter2D:
    """Two independent One Euro filters for an (x, y) cursor signal."""

    def __init__(
        self,
        min_cutoff: float = 1.4,
        beta: float = 0.007,
        d_cutoff: float = 1.0,
        freq: float = 30.0,
    ) -> None:
        self.x = OneEuroFilter(min_cutoff, beta, d_cutoff, freq)
        self.y = OneEuroFilter(min_cutoff, beta, d_cutoff, freq)

    def reset(self) -> None:
        self.x.reset()
        self.y.reset()

    def __call__(self, point: tuple[float, float], t: float | None = None) -> tuple[float, float]:
        return (self.x(point[0], t), self.y(point[1], t))


class EMASmoother:
    """Exponential moving average, used for scalar signals such as pinch ratio."""

    def __init__(self, factor: float = 0.5) -> None:
        self.factor = factor
        self.value: float | None = None

    def reset(self) -> None:
        self.value = None

    def __call__(self, x: float) -> float:
        if self.value is None:
            self.value = x
        else:
            self.value = self.factor * x + (1.0 - self.factor) * self.value
        return self.value


class VelocityTracker:
    """Smoothed speed (units/second) of a 2D signal over time."""

    def __init__(self, smoothing: float = 0.4) -> None:
        self._last_point: np.ndarray | None = None
        self._last_t: float | None = None
        self.speed = 0.0
        self._smoothing = smoothing

    def reset(self) -> None:
        self._last_point = None
        self._last_t = None
        self.speed = 0.0

    def __call__(self, point: tuple[float, float], t: float) -> float:
        current = np.asarray(point, dtype=float)
        if self._last_point is not None and self._last_t is not None:
            dt = max(t - self._last_t, 1e-6)
            instantaneous = float(np.linalg.norm(current - self._last_point)) / dt
            self.speed = self._smoothing * instantaneous + (1 - self._smoothing) * self.speed
        self._last_point = current
        self._last_t = t
        return self.speed
