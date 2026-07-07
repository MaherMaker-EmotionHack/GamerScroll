"""Global media-key listener using pynput."""

from __future__ import annotations

import threading
from typing import Any, Callable, Optional

from loguru import logger
from pynput import keyboard


KeyName = str
PressCallback = Callable[[], None]
ReleaseCallback = Callable[[], None]


class HotkeyListener:
    """Listen for a single global media key and dispatch press/release events.

    The listener is deliberately thin: timing interpretation (short press,
    double press, long hold) lives in :class:`gamerscroll.gestures.GestureDetector`.
    """

    def __init__(
        self,
        media_key: KeyName,
        on_press: PressCallback,
        on_release: ReleaseCallback,
    ):
        self.media_key = media_key
        self.on_press = on_press
        self.on_release = on_release
        self._listener: Optional[keyboard.Listener] = None
        self._thread: Optional[threading.Thread] = None

    @staticmethod
    def _parse(key_name: str) -> keyboard.Key:
        key_name = key_name.strip().lower()
        try:
            return keyboard.Key[key_name]
        except KeyError:
            # Single character key, e.g. 'a', '1'.
            return keyboard.KeyCode.from_char(key_name)

    def start(self) -> None:
        if self._listener is not None:
            logger.debug("Hotkey listener already running")
            return

        logger.info("Starting hotkey listener (media_key='{}')", self.media_key)
        try:
            media_key = self._parse(self.media_key)
        except ValueError as exc:
            logger.error("Failed to parse media key: {}", exc)
            raise

        pressed: set[Any] = set()

        def on_press(key: Any) -> None:
            if key is None or key in pressed:
                return
            pressed.add(key)
            if key == media_key:
                logger.debug("Media key pressed")
                try:
                    self.on_press()
                except Exception:
                    logger.exception("Media key press callback failed")

        def on_release(key: Any) -> None:
            if key is None or key not in pressed:
                return
            pressed.discard(key)
            if key == media_key:
                logger.debug("Media key released")
                try:
                    self.on_release()
                except Exception:
                    logger.exception("Media key release callback failed")

        self._listener = keyboard.Listener(on_press=on_press, on_release=on_release)
        self._thread = threading.Thread(target=self._listener.run, daemon=True)
        self._thread.start()
        logger.info("Hotkey listener thread started")

    def stop(self) -> None:
        if self._listener:
            logger.info("Stopping hotkey listener")
            self._listener.stop()
            self._listener = None

    def restart(self, media_key: KeyName) -> None:
        logger.info("Restarting hotkey listener with media_key='{}'", media_key)
        self.stop()
        self.media_key = media_key
        self.start()
