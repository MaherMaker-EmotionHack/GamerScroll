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
RecoveryFn = Callable[[], bool]


class MediaController:
    """Maps recognized gestures to CDP media actions.

    The controller owns the current configuration and status reporting; the
    actual CDP transport is injected via ``send_action`` so tests can substitute
    a fake.

    A ``check_health`` method probes the CDP endpoint and, if unreachable,
    invokes an optional ``on_recovery`` callback (e.g. relaunch the browser).
    After a configurable number of consecutive failures the controller
    degrades gracefully by disabling input until recovery succeeds.
    """

    def __init__(
        self,
        config: Config,
        send_action: Optional[SendActionFn] = None,
        on_status: Optional[Callable[[MediaStatus], None]] = None,
        on_recovery: Optional[RecoveryFn] = None,
        max_consecutive_failures: int = 5,
    ):
        self._config = config
        self._on_status = on_status
        self._on_recovery = on_recovery
        self._max_consecutive_failures = max_consecutive_failures
        self._lock = threading.Lock()
        self._send_action = send_action or self._default_send_action
        self._consecutive_failures = 0
        self._degraded = False

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
            if self._degraded:
                logger.info("Gesture {} ignored (degraded — CDP unreachable)", gesture.name)
                self._emit(False, "CDP unreachable — recovering.")
                return

        action = _GESTURE_TO_ACTION.get(gesture)
        if action is None:
            logger.warning("Unknown gesture: {}", gesture)
            return

        logger.debug("Executing media action {} for gesture {}", action.name, gesture.name)
        try:
            exe_name = Path(cfg.browser_exe).name if cfg.browser_exe else None
            self._send_action(cfg.cdp_host, cfg.cdp_port, action, exe_name)
            with self._lock:
                self._consecutive_failures = 0
            self._emit(True, action.name.replace("_", " ").title())
        except Exception as exc:
            logger.error("Media action {} failed: {}", action.name, exc)
            with self._lock:
                self._consecutive_failures += 1
                if self._consecutive_failures >= self._max_consecutive_failures:
                    self._degraded = True
                    logger.warning(
                        "CDP degraded after {} consecutive failures; "
                        "input disabled until recovery",
                        self._consecutive_failures,
                    )
            self._emit(False, str(exc))

    def check_health(self) -> bool:
        """Probe the CDP endpoint and attempt recovery if unreachable.

        Returns True if CDP is currently reachable.
        """
        from gamerscroll.cdp import check_cdp_reachable

        with self._lock:
            cfg = self._config
            host = cfg.cdp_host
            port = cfg.cdp_port

        reachable = check_cdp_reachable(host, port, timeout=2.0)
        if reachable:
            with self._lock:
                if self._degraded:
                    logger.info("CDP recovered — re-enabling input")
                self._degraded = False
                self._consecutive_failures = 0
            self._emit(True, "CDP reachable")
            return True

        logger.warning("CDP health check failed on port {}", port)
        if self._on_recovery:
            logger.info("Attempting CDP recovery via on_recovery callback")
            try:
                recovered = self._on_recovery()
            except Exception:
                logger.exception("Recovery callback raised an exception")
                recovered = False
            if recovered:
                with self._lock:
                    self._degraded = False
                    self._consecutive_failures = 0
                self._emit(True, "CDP recovered")
                return True

        with self._lock:
            self._degraded = True
        self._emit(False, "CDP unreachable")
        return False

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
