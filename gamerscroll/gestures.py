"""Single-key gesture detector: short press, double press, long hold."""

from __future__ import annotations

import threading
import time
from enum import Enum, auto
from typing import Callable, Optional, Protocol

from loguru import logger


class Gesture(Enum):
    """Recognized gesture types."""

    SHORT_PRESS = auto()
    DOUBLE_PRESS = auto()
    LONG_HOLD = auto()


class _State(Enum):
    """Internal detector states."""

    IDLE = auto()
    PRESSED = auto()
    AWAITING_DOUBLE_CLICK = auto()
    DOUBLE_PRESSED = auto()
    LONG_HOLD_FIRED = auto()


class Timer(Protocol):
    """Handle returned by a timer factory."""

    def start(self) -> None: ...
    def cancel(self) -> None: ...


class TimerFactory(Protocol):
    """Factory used to schedule future callbacks."""

    def __call__(self, delay: float, callback: Callable[[], None]) -> Timer: ...


class _ThreadTimer:
    """Default timer implementation backed by ``threading.Timer``."""

    def __init__(self, delay: float, callback: Callable[[], None]) -> None:
        self._timer = threading.Timer(delay, callback)
        self._timer.daemon = True

    def start(self) -> None:
        self._timer.start()

    def cancel(self) -> None:
        self._timer.cancel()


def _default_timer_factory(delay: float, callback: Callable[[], None]) -> Timer:
    return _ThreadTimer(delay, callback)


class GestureDetector:
    """Detects gestures from a single phantom key.

    A *short press* is a press-release pair shorter than the hold threshold
    with no follow-up press inside the double-click window. A *double press*
    is a second short press inside that window. A *long hold* fires once when
    the hold threshold is reached while the key is still held.

    The detector is intentionally decoupled from the input source; callers feed
    it :meth:`press` and :meth:`release` events from pynput, Qt, or tests.
    """

    def __init__(
        self,
        on_short_press: Callable[[], None],
        on_double_press: Callable[[], None],
        on_long_hold: Callable[[], None],
        hold_threshold_ms: float = 500.0,
        double_click_window_ms: float = 300.0,
        debounce_ms: float = 150.0,
        time_fn: Optional[Callable[[], float]] = None,
        timer_factory: Optional[TimerFactory] = None,
    ):
        self.on_short_press = on_short_press
        self.on_double_press = on_double_press
        self.on_long_hold = on_long_hold
        self.hold_threshold_ms = max(0.0, hold_threshold_ms)
        self.double_click_window_ms = max(0.0, double_click_window_ms)
        self.debounce_ms = max(0.0, debounce_ms)
        self._time = time_fn or time.monotonic
        self._timer_factory = timer_factory or _default_timer_factory

        self._enabled = True
        self._lock = threading.Lock()
        self._state = _State.IDLE
        self._press_time: float = 0.0
        self._last_gesture_time: float = -1.0
        self._hold_timer: Optional[Timer] = None
        self._double_click_timer: Optional[Timer] = None

    def set_enabled(self, enabled: bool) -> None:
        """Enable or disable gesture recognition."""
        with self._lock:
            self._enabled = enabled
            if not enabled:
                self._clear_timers()
                self._state = _State.IDLE
        logger.debug("Gesture detector enabled={}", enabled)

    def press(self) -> None:
        """Report that the media key was pressed."""
        with self._lock:
            if not self._enabled:
                return

            now = self._time()
            if self._last_gesture_time >= 0.0 and now - self._last_gesture_time < self.debounce_ms / 1000.0:
                logger.debug("Press ignored during debounce")
                return

            if self._state == _State.AWAITING_DOUBLE_CLICK:
                self._cancel_double_click_timer()
                self._state = _State.DOUBLE_PRESSED
                self._press_time = now
                self._schedule_hold_timer(self.hold_threshold_ms / 1000.0)
                return

            self._state = _State.PRESSED
            self._press_time = now
            self._schedule_hold_timer(self.hold_threshold_ms / 1000.0)

    def release(self) -> None:
        """Report that the media key was released."""
        with self._lock:
            if not self._enabled:
                return

            if self._state == _State.PRESSED:
                self._cancel_hold_timer()
                elapsed = self._time() - self._press_time
                if elapsed >= self.hold_threshold_ms / 1000.0:
                    # Release raced the hold timer; emit long hold now.
                    self._state = _State.IDLE
                    self._emit(Gesture.LONG_HOLD)
                    return
                self._state = _State.AWAITING_DOUBLE_CLICK
                self._schedule_double_click_timer(self.double_click_window_ms / 1000.0)
                return

            if self._state == _State.DOUBLE_PRESSED:
                self._cancel_hold_timer()
                elapsed = self._time() - self._press_time
                self._state = _State.IDLE
                if elapsed >= self.hold_threshold_ms / 1000.0:
                    # Second press was held long enough to be a long hold.
                    self._emit(Gesture.LONG_HOLD)
                else:
                    self._emit(Gesture.DOUBLE_PRESS)
                return

            # Released without a tracked press: ignore.
            self._state = _State.IDLE

    def stop(self) -> None:
        """Cancel all pending timers and reset state."""
        with self._lock:
            self._clear_timers()
            self._state = _State.IDLE
        logger.debug("Gesture detector stopped")

    def _schedule_hold_timer(self, delay: float) -> None:
        self._cancel_hold_timer()
        self._hold_timer = self._timer_factory(delay, self._on_hold_timeout)
        self._hold_timer.start()

    def _schedule_double_click_timer(self, delay: float) -> None:
        self._cancel_double_click_timer()
        self._double_click_timer = self._timer_factory(delay, self._on_double_click_timeout)
        self._double_click_timer.start()

    def _cancel_hold_timer(self) -> None:
        if self._hold_timer is not None:
            self._hold_timer.cancel()
            self._hold_timer = None

    def _cancel_double_click_timer(self) -> None:
        if self._double_click_timer is not None:
            self._double_click_timer.cancel()
            self._double_click_timer = None

    def _clear_timers(self) -> None:
        self._cancel_hold_timer()
        self._cancel_double_click_timer()

    def _on_hold_timeout(self) -> None:
        with self._lock:
            if self._state not in (_State.PRESSED, _State.DOUBLE_PRESSED):
                return
            self._state = _State.LONG_HOLD_FIRED
        self._emit(Gesture.LONG_HOLD)

    def _on_double_click_timeout(self) -> None:
        with self._lock:
            if self._state != _State.AWAITING_DOUBLE_CLICK:
                return
            self._state = _State.IDLE
        self._emit(Gesture.SHORT_PRESS)

    def _emit(self, gesture: Gesture) -> None:
        now = self._time()
        self._last_gesture_time = now
        logger.debug("Gesture recognized: {}", gesture.name)
        try:
            if gesture is Gesture.SHORT_PRESS:
                self.on_short_press()
            elif gesture is Gesture.DOUBLE_PRESS:
                self.on_double_press()
            elif gesture is Gesture.LONG_HOLD:
                self.on_long_hold()
        except Exception:
            logger.exception("Gesture callback failed for {}", gesture.name)
