"""Screen-size lookup on each platform, simulated so it runs anywhere.

Every bad reading must land on the fallback, never on a zero or garbage size
that would collapse the pointer map.
"""

import subprocess
import sys
import types

import pytest

from visiondrop import engine
from visiondrop.engine import FALLBACK_SCREEN_SIZE, parse_xrandr, primary_screen_size

LAPTOP_PLUS_MONITOR = """\
Screen 0: minimum 320 x 200, current 4480 x 1440, maximum 16384 x 16384
eDP-1 connected 1920x1080+2560+0 (normal left inverted right x axis y axis) 309mm x 174mm
   1920x1080     60.00*+
HDMI-1 connected primary 2560x1440+0+0 (normal left inverted right x axis y axis) 597mm x 336mm
   2560x1440     59.95*+
DP-1 disconnected (normal left inverted right x axis y axis)
"""


@pytest.mark.parametrize(
    ("text", "want"),
    [
        (LAPTOP_PLUS_MONITOR, (2560, 1440)),
        ("eDP-1 connected 1366x768+0+0 (normal) 0mm x 0mm\n", (1366, 768)),
        ("XWAYLAND0 connected 3840x2160+0+0 0mm x 0mm\n", (3840, 2160)),
        ("HDMI-1 disconnected (normal)\neDP-1 connected 1280x800+0+0 (normal)\n", (1280, 800)),
        # Connected but switched off: no geometry, so nothing usable.
        ("eDP-1 connected (normal left inverted right x axis y axis)\n", None),
        ("HDMI-1 disconnected (normal)\n", None),
        ("", None),
        ("Can't open display\n", None),
        ("\x00\xff garbage 12x34 not a geometry\n", None),
    ],
)
def test_parse_xrandr(text, want):
    assert parse_xrandr(text) == want


def fake_xrandr(monkeypatch, *, stdout="", error=None):
    def run(argv, **kwargs):
        assert argv[0] == "xrandr" and kwargs.get("timeout"), "must not block on a hung X server"
        if error is not None:
            raise error
        return subprocess.CompletedProcess(argv, 0, stdout=stdout, stderr="")

    monkeypatch.setattr(sys, "platform", "linux")
    monkeypatch.setattr(engine.subprocess, "run", run)


def test_linux_reads_primary_from_xrandr(monkeypatch):
    fake_xrandr(monkeypatch, stdout=LAPTOP_PLUS_MONITOR)
    assert primary_screen_size() == (2560, 1440)


@pytest.mark.parametrize(
    "error",
    [
        FileNotFoundError("xrandr"),  # not installed, e.g. a pure Wayland or headless box
        subprocess.TimeoutExpired("xrandr", 2),
        subprocess.CalledProcessError(1, "xrandr", stderr="Can't open display"),
        PermissionError("xrandr"),
    ],
)
def test_linux_falls_back_when_xrandr_fails(monkeypatch, error):
    fake_xrandr(monkeypatch, error=error)
    assert primary_screen_size() == FALLBACK_SCREEN_SIZE


@pytest.mark.parametrize("stdout", ["", "garbage\n", "HDMI-1 connected primary 0x0+0+0\n"])
def test_linux_falls_back_on_unusable_output(monkeypatch, stdout):
    fake_xrandr(monkeypatch, stdout=stdout)
    assert primary_screen_size() == FALLBACK_SCREEN_SIZE


def fake_quartz(monkeypatch, width, height):
    quartz = types.SimpleNamespace(
        CGMainDisplayID=lambda: 1,
        CGDisplayPixelsWide=lambda _: width,
        CGDisplayPixelsHigh=lambda _: height,
    )
    monkeypatch.setattr(sys, "platform", "darwin")
    monkeypatch.setitem(sys.modules, "Quartz", quartz)


def test_macos_reads_quartz(monkeypatch):
    fake_quartz(monkeypatch, 1512, 982)
    assert primary_screen_size() == (1512, 982)


def test_macos_falls_back_on_zero_display(monkeypatch):
    fake_quartz(monkeypatch, 0, 0)
    assert primary_screen_size() == FALLBACK_SCREEN_SIZE


def test_macos_falls_back_without_pyobjc(monkeypatch):
    monkeypatch.setattr(sys, "platform", "darwin")
    monkeypatch.setitem(sys.modules, "Quartz", None)  # makes `import Quartz` raise ImportError
    assert primary_screen_size() == FALLBACK_SCREEN_SIZE


def fake_user32(monkeypatch, metrics):
    import ctypes

    user32 = types.SimpleNamespace(GetSystemMetrics=lambda index: metrics[index])
    monkeypatch.setattr(sys, "platform", "win32")
    monkeypatch.setattr(ctypes, "windll", types.SimpleNamespace(user32=user32), raising=False)


def test_windows_reads_user32(monkeypatch):
    fake_user32(monkeypatch, {0: 2880, 1: 1800})
    assert primary_screen_size() == (2880, 1800)


def test_windows_falls_back_on_negative_metrics(monkeypatch):
    fake_user32(monkeypatch, {0: -1, 1: 1080})
    assert primary_screen_size() == FALLBACK_SCREEN_SIZE


def test_engine_never_gets_a_degenerate_screen(monkeypatch):
    fake_xrandr(monkeypatch, error=FileNotFoundError("xrandr"))
    from visiondrop import config

    assert engine.Engine(config.DEFAULT_CONFIG).cursor.screen_size == FALLBACK_SCREEN_SIZE
