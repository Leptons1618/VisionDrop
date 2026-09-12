import numpy as np

from visiondrop.feedback import SOUNDS, Feedback, tone_samples, tone_sequence


def test_tone_samples_length_and_fades():
    wave = tone_samples(440.0, 0.1, sample_rate=8000)
    assert len(wave) == 800
    assert wave[0] == 0.0
    assert abs(wave[-1]) < 1e-3
    assert np.max(np.abs(wave)) <= 0.4 + 1e-6


def test_tone_frequency():
    wave = tone_samples(1000.0, 0.05, sample_rate=8000, amplitude=1.0)
    zero_crossings = int(np.sum(np.diff(np.signbit(wave))))
    assert abs(zero_crossings - 2 * 1000 * 0.05) <= 2


def test_tone_sequence_concatenates():
    wave = tone_sequence([(440.0, 0.05), (880.0, 0.1)], sample_rate=8000)
    assert len(wave) == 400 + 800


def test_sound_presets_exist():
    assert set(SOUNDS) == {"grab", "success", "miss"}


def test_feedback_audio_disabled_is_silent():
    feedback = Feedback(audio=False)
    assert feedback.audio_available is False
    feedback.play("success")  # must not raise


def test_onboarding_visible_until_first_drop():
    feedback = Feedback(audio=False)
    frame = np.zeros((200, 800, 3), dtype=np.uint8)

    feedback.draw_onboarding(frame, now=0.0)
    assert frame.sum() > 0

    feedback.mark_onboarded()
    frame[:] = 0
    feedback.draw_onboarding(frame, now=0.1)
    assert frame.sum() == 0


def test_flashes_expire():
    feedback = Feedback(audio=False)
    frame = np.zeros((100, 100, 3), dtype=np.uint8)
    feedback.flash((50, 50), (0, 255, 0), now=0.0)

    feedback.draw_flashes(frame, now=0.1)
    assert frame.sum() > 0

    frame[:] = 0
    feedback.draw_flashes(frame, now=1.0)
    assert frame.sum() == 0
