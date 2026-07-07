"""Media controller: maps gestures to CDP media actions."""

from __future__ import annotations

import threading
from dataclasses import dataclass
from enum import Enum, auto
from pathlib import Path
from typing import Callable, Optional

from loguru import logger

from gamerscroll.config import Config
from gamerscroll.gestures import Gesture


class MediaAction(Enum):
    """CDP-key actions supported by the controller."""

    PAUSE_PLAY = auto()
    NEXT = auto()
    PREV = auto()


_GESTURE_TO_ACTION: dict[Gesture, MediaAction] = {
    Gesture.SHORT_PRESS: MediaAction.PAUSE_PLAY,
    Gesture.DOUBLE_PRESS: MediaAction.NEXT,
    Gesture.LONG_HOLD: MediaAction.PREV,
}

_ACTION_TO_KEY: dict[MediaAction, str] = {
    MediaAction.PAUSE_PLAY: "Space",
    MediaAction.NEXT: "ArrowDown",
    MediaAction.PREV: "ArrowUp",
}


@dataclass
class MediaStatus:
    ok: bool
    message: str


SendActionFn = Callable[[str, int, MediaAction, Optional[str]], None]


class MediaController:
    """Maps recognized gestures to CDP media actions.

    The controller owns the current configuration and status reporting; the
    actual CDP transport is injected via ``send_action`` so tests can substitute
    a fake.
    """

    def __init__(
        self,
        config: Config,
        send_action: Optional[SendActionFn] = None,
        on_status: Optional[Callable[[MediaStatus], None]] = None,
    ):
        self._config = config
        self._on_status = on_status
        self._lock = threading.Lock()
        self._send_action = send_action or self._default_send_action

    def update_config(self, config: Config) -> None:
        """Replace the active configuration."""
        with self._lock:
            old = self._config
            self._config = config
        logger.debug(
            "MediaController config updated: port={}, disabled={}",
            config.cdp_port, config.disabled,
        )
        # Avoid unused-variable lint while preserving context if needed later.
        _ = old

    def handle_gesture(self, gesture: Gesture) -> None:
        """Dispatch a recognized gesture to the corresponding media action."""
        with self._lock:
            cfg = self._config
            if cfg.disabled:
                logger.info("Gesture {} ignored (disabled)", gesture.name)
                self._emit(False, "Media control is disabled.")
                return

        action = _GESTURE_TO_ACTION.get(gesture)
        if action is None:
            logger.warning("Unknown gesture: {}", gesture)
            return

        logger.debug("Executing media action {} for gesture {}", action.name, gesture.name)
        try:
            exe_name = Path(cfg.browser_exe).name if cfg.browser_exe else None
            self._send_action(cfg.cdp_host, cfg.cdp_port, action, exe_name)
            self._emit(True, action.name.replace("_", " ").title())
        except Exception as exc:
            logger.error("Media action {} failed: {}", action.name, exc)
            self._emit(False, str(exc))

    def _emit(self, ok: bool, message: str) -> None:
        if self._on_status:
            self._on_status(MediaStatus(ok=ok, message=message))

    @staticmethod
    def _default_send_action(
        host: str,
        port: int,
        action: MediaAction,
        browser_exe_name: Optional[str] = None,
    ) -> None:
        from gamerscroll.cdp import send_key_event_sync

        key = _ACTION_TO_KEY.get(action)
        if key is None:
            raise ValueError(f"No CDP key mapping for action {action}")
        send_key_event_sync(host, port, key, browser_exe_name=browser_exe_name)
