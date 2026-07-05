"""Global hotkey listener using pynput."""

from __future__ import annotations

import threading
import time
from typing import Callable, Optional

from loguru import logger
from pynput import keyboard


KeyName = str
ActionCallback = Callable[[], None]


class HotkeyListener:
    """Listen for global key presses and dispatch to scroll callbacks."""

    def __init__(
        self,
        down_key: KeyName,
        up_key: KeyName,
        on_scroll_down: ActionCallback,
        on_scroll_up: ActionCallback,
        cooldown_ms: float = 200.0,
    ):
        self.down_key = down_key
        self.up_key = up_key
        self.on_scroll_down = on_scroll_down
        self.on_scroll_up = on_scroll_up
        self._cooldown_s = max(0.0, cooldown_ms / 1000.0)
        self._listener: Optional[keyboard.Listener] = None
        self._thread: Optional[threading.Thread] = None
        self._last_trigger = 0.0

    @staticmethod
    def _parse(key_name: str) -> keyboard.Key:
        key_name = key_name.strip().lower()
        try:
            return keyboard.Key[key_name]
        except KeyError:
            # Single character key, e.g. 'a', '1'.
            return keyboard.KeyCode.from_char(key_name)

    def _maybe_trigger(self, callback: ActionCallback) -> None:
        now = time.monotonic()
        if now - self._last_trigger < self._cooldown_s:
            logger.debug("Hotkey trigger ignored due to cooldown")
            return
        self._last_trigger = now
        callback()

    def start(self) -> None:
        if self._listener is not None:
            logger.debug("Hotkey listener already running")
            return

        logger.info("Starting hotkey listener (down='{}', up='{}')", self.down_key, self.up_key)
        try:
            down_key = self._parse(self.down_key)
            up_key = self._parse(self.up_key)
        except ValueError as exc:
            logger.error("Failed to parse hotkey: {}", exc)
            raise

        pressed: set[keyboard.Key] = set()

        def on_press(key):
            if key in pressed:
                return None
            pressed.add(key)
            if key == down_key:
                logger.debug("Scroll-down key pressed")
                self._maybe_trigger(self.on_scroll_down)
                return None
            if key == up_key:
                logger.debug("Scroll-up key pressed")
                self._maybe_trigger(self.on_scroll_up)
                return None
            return None

        def on_release(key):
            pressed.discard(key)
            return None

        self._listener = keyboard.Listener(on_press=on_press, on_release=on_release)
        self._thread = threading.Thread(target=self._listener.run, daemon=True)
        self._thread.start()
        logger.info("Hotkey listener thread started")

    def stop(self) -> None:
        if self._listener:
            logger.info("Stopping hotkey listener")
            self._listener.stop()
            self._listener = None

    def restart(self, down_key: KeyName, up_key: KeyName) -> None:
        logger.info("Restarting hotkey listener with new keys (down='{}', up='{}')", down_key, up_key)
        self.stop()
        self.down_key = down_key
        self.up_key = up_key
        self.start()
