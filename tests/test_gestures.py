"""Tests for the gesture detector state machine."""

from __future__ import annotations

from typing import Callable, Optional

import pytest

from gamerscroll.gestures import Gesture, GestureDetector, Timer


class FakeClock:
    """Deterministic monotonic clock for gesture timing tests."""

    def __init__(self, start: float = 0.0) -> None:
        self._now = start

    def __call__(self) -> float:
        return self._now

    def advance(self, seconds: float) -> None:
        self._now += seconds


class FakeTimer:
    """Timer that records its due time and fires only when told."""

    def __init__(self, due_at: float, callback: Callable[[], None]) -> None:
        self.due_at = due_at
        self.callback = callback
        self.cancelled = False

    def start(self) -> None:
        pass

    def cancel(self) -> None:
        self.cancelled = True


class FakeTimerFactory:
    """Collects scheduled timers and fires those whose due time has passed."""

    def __init__(self, clock: FakeClock) -> None:
        self._clock = clock
        self.timers: list[FakeTimer] = []

    def __call__(self, delay: float, callback: Callable[[], None]) -> Timer:
        timer = FakeTimer(self._clock() + delay, callback)
        self.timers.append(timer)
        return timer

    def fire_due(self) -> None:
        now = self._clock()
        for timer in self.timers:
            if not timer.cancelled and now >= timer.due_at:
                timer.callback()


def make_detector(
    clock: FakeClock,
    hold_threshold_ms: float = 500.0,
    double_click_window_ms: float = 300.0,
    debounce_ms: float = 150.0,
) -> tuple[GestureDetector, FakeTimerFactory, list[Gesture]]:
    captured: list[Gesture] = []
    timers = FakeTimerFactory(clock)

    def on_gesture(gesture: Gesture) -> None:
        captured.append(gesture)

    detector = GestureDetector(
        on_short_press=lambda: on_gesture(Gesture.SHORT_PRESS),
        on_double_press=lambda: on_gesture(Gesture.DOUBLE_PRESS),
        on_long_hold=lambda: on_gesture(Gesture.LONG_HOLD),
        hold_threshold_ms=hold_threshold_ms,
        double_click_window_ms=double_click_window_ms,
        debounce_ms=debounce_ms,
        time_fn=clock,
        timer_factory=timers,
    )
    return detector, timers, captured


def test_short_press_is_recognized() -> None:
    clock = FakeClock()
    detector, timers, captured = make_detector(clock)

    detector.press()
    clock.advance(0.1)  # 100 ms
    detector.release()
    clock.advance(0.4)  # past double-click window
    timers.fire_due()

    assert captured == [Gesture.SHORT_PRESS]


def test_double_press_is_recognized() -> None:
    clock = FakeClock()
    detector, timers, captured = make_detector(clock)

    detector.press()
    clock.advance(0.05)
    detector.release()
    clock.advance(0.1)  # second press within 300 ms window
    detector.press()
    clock.advance(0.05)
    detector.release()

    assert captured == [Gesture.DOUBLE_PRESS]


def test_long_hold_fires_at_threshold() -> None:
    clock = FakeClock()
    detector, timers, captured = make_detector(clock)

    detector.press()
    assert captured == []  # not yet
    clock.advance(0.5)  # exactly at threshold
    timers.fire_due()
    assert captured == [Gesture.LONG_HOLD]

    detector.release()
    clock.advance(1.0)
    timers.fire_due()
    assert captured == [Gesture.LONG_HOLD]  # no extra gesture on release


def test_long_hold_does_not_fire_short_after_release() -> None:
    clock = FakeClock()
    detector, timers, captured = make_detector(clock)

    detector.press()
    clock.advance(0.6)
    timers.fire_due()
    detector.release()
    clock.advance(1.0)
    timers.fire_due()

    assert captured == [Gesture.LONG_HOLD]


def test_short_press_after_long_hold_is_debounced() -> None:
    clock = FakeClock()
    detector, timers, captured = make_detector(clock, debounce_ms=150.0)

    detector.press()
    clock.advance(0.5)
    timers.fire_due()
    detector.release()
    clock.advance(0.05)  # 50 ms after release, still inside debounce
    detector.press()
    detector.release()
    clock.advance(1.0)
    timers.fire_due()

    assert captured == [Gesture.LONG_HOLD]


def test_presses_during_debounce_are_ignored() -> None:
    clock = FakeClock()
    detector, timers, captured = make_detector(clock, debounce_ms=150.0)

    detector.press()
    clock.advance(0.05)
    detector.release()
    clock.advance(0.3)
    timers.fire_due()
    # short press recognized here
    assert captured == [Gesture.SHORT_PRESS]

    detector.press()
    clock.advance(0.05)
    detector.release()
    clock.advance(0.05)  # 50 ms after short press, inside debounce
    timers.fire_due()
    clock.advance(1.0)
    timers.fire_due()

    assert captured == [Gesture.SHORT_PRESS]


def test_release_without_press_is_ignored() -> None:
    clock = FakeClock()
    detector, timers, captured = make_detector(clock)

    detector.release()
    clock.advance(1.0)
    timers.fire_due()

    assert captured == []


def test_double_click_window_expires_alone() -> None:
    clock = FakeClock()
    detector, timers, captured = make_detector(clock)

    detector.press()
    clock.advance(0.05)
    detector.release()
    clock.advance(0.35)  # past double-click window
    timers.fire_due()

    assert captured == [Gesture.SHORT_PRESS]


def test_second_release_after_window_is_two_short_presses() -> None:
    clock = FakeClock()
    detector, timers, captured = make_detector(clock, debounce_ms=0.0)

    detector.press()
    clock.advance(0.05)
    detector.release()
    clock.advance(0.35)  # first short press fires
    timers.fire_due()
    detector.press()
    clock.advance(0.05)
    detector.release()
    clock.advance(0.35)
    timers.fire_due()

    assert captured == [Gesture.SHORT_PRESS, Gesture.SHORT_PRESS]


def test_press_after_long_hold_release_resets() -> None:
    clock = FakeClock()
    detector, timers, captured = make_detector(clock, debounce_ms=0.0)

    detector.press()
    clock.advance(0.5)
    timers.fire_due()
    detector.release()
    clock.advance(0.5)
    timers.fire_due()
    detector.press()
    clock.advance(0.05)
    detector.release()
    clock.advance(0.35)
    timers.fire_due()

    assert captured == [Gesture.LONG_HOLD, Gesture.SHORT_PRESS]


def test_disabled_detector_ignores_all_input() -> None:
    clock = FakeClock()
    detector, timers, captured = make_detector(clock)

    detector.set_enabled(False)
    detector.press()
    clock.advance(1.0)
    timers.fire_due()
    detector.release()

    assert captured == []


def test_reenabled_detector_works_normally() -> None:
    clock = FakeClock()
    detector, timers, captured = make_detector(clock)

    detector.set_enabled(False)
    detector.set_enabled(True)
    detector.press()
    clock.advance(0.05)
    detector.release()
    clock.advance(0.35)
    timers.fire_due()

    assert captured == [Gesture.SHORT_PRESS]


def test_stop_cancels_pending_timers() -> None:
    clock = FakeClock()
    detector, timers, captured = make_detector(clock)

    detector.press()
    detector.stop()
    clock.advance(1.0)
    timers.fire_due()
    detector.release()

    assert captured == []


def test_default_timing_values_are_sensible() -> None:
    detector = GestureDetector(
        on_short_press=lambda: None,
        on_double_press=lambda: None,
        on_long_hold=lambda: None,
    )

    assert detector.hold_threshold_ms == 500.0
    assert detector.double_click_window_ms == 300.0
    assert detector.debounce_ms == 150.0


def test_long_hold_emitted_even_if_release_races_timer() -> None:
    clock = FakeClock()
    detector, timers, captured = make_detector(clock)

    detector.press()
    clock.advance(0.6)
    # Timer has not been fired manually; release happens after threshold.
    detector.release()
    timers.fire_due()

    assert captured == [Gesture.LONG_HOLD]


def test_double_press_second_hold_becomes_long_hold() -> None:
    clock = FakeClock()
    detector, timers, captured = make_detector(clock)

    detector.press()
    clock.advance(0.05)
    detector.release()
    clock.advance(0.1)
    detector.press()
    clock.advance(0.6)
    detector.release()
    timers.fire_due()

    assert captured == [Gesture.LONG_HOLD]
