"""Media controller: maps gestures to CDP media actions."""

from __future__ import annotations

import threading
from dataclasses import dataclass
from enum import Enum, auto
from pathlib import Path
from typing import Callable, Optional
from urllib.parse import urlparse

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


@dataclass(frozen=True)
class TabTarget:
    """A CDP tab that can receive media controls during this session."""

    target_id: str
    title: str
    url: str

    @property
    def main_domain(self) -> str:
        """Return a compact domain label for the Settings pin status."""
        hostname = urlparse(self.url).hostname or ""
        labels = hostname.split(".")
        return ".".join(labels[-2:]) if len(labels) >= 2 else hostname


class TargetUnavailableError(Exception):
    """Raised when a session-only pinned CDP target has disappeared."""


SendActionFn = Callable[[str, int, MediaAction, Optional[str], Optional[str]], None]
FindActiveTabFn = Callable[[str, int, Optional[str]], TabTarget]
VerifyTargetFn = Callable[[str, int, str], bool]
PinChangedFn = Callable[[Optional[TabTarget]], None]
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
        find_active_tab: Optional[FindActiveTabFn] = None,
        verify_target: Optional[VerifyTargetFn] = None,
        on_pin_changed: Optional[PinChangedFn] = None,
        max_consecutive_failures: int = 5,
    ):
        self._config = config
        self._on_status = on_status
        self._on_recovery = on_recovery
        self._max_consecutive_failures = max_consecutive_failures
        self._lock = threading.Lock()
        self._send_action = send_action or self._default_send_action
        self._find_active_tab = find_active_tab or self._default_find_active_tab
        self._verify_target = verify_target or self._default_verify_target
        self._on_pin_changed = on_pin_changed
        self._consecutive_failures = 0
        self._degraded = False
        self._pinned_tab: Optional[TabTarget] = None

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
            pinned_tab = self._pinned_tab
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
            self._send_action(
                cfg.cdp_host,
                cfg.cdp_port,
                action,
                exe_name,
                pinned_tab.target_id if pinned_tab else None,
            )
            with self._lock:
                self._consecutive_failures = 0
            self._emit(True, action.name.replace("_", " ").title())
        except TargetUnavailableError as exc:
            if pinned_tab is None:
                self._record_action_failure(action, exc)
                return
            logger.info("Pinned tab '{}' disappeared; falling back to active tab", pinned_tab.title)
            self.unpin_current_tab()
            try:
                self._send_action(cfg.cdp_host, cfg.cdp_port, action, exe_name, None)
                with self._lock:
                    self._consecutive_failures = 0
                self._emit(True, action.name.replace("_", " ").title())
            except Exception as exc:
                self._record_action_failure(action, exc)
        except Exception as exc:
            self._record_action_failure(action, exc)

    @property
    def pinned_tab(self) -> Optional[TabTarget]:
        """Return the session-only pinned tab, if one is currently available."""
        with self._lock:
            return self._pinned_tab

    def pin_current_tab(self) -> TabTarget:
        """Pin the active browser tab for this GamerScroll session."""
        with self._lock:
            cfg = self._config
        exe_name = Path(cfg.browser_exe).name if cfg.browser_exe else None
        tab = self._find_active_tab(cfg.cdp_host, cfg.cdp_port, exe_name)
        with self._lock:
            self._pinned_tab = tab
        self._notify_pin_changed(tab)
        logger.info("Pinned browser tab: {} ({})", tab.title, tab.main_domain)
        return tab

    def unpin_current_tab(self) -> None:
        """Remove the session-only pin so gestures use the active tab again."""
        with self._lock:
            self._pinned_tab = None
        self._notify_pin_changed(None)
        logger.info("Removed pinned browser tab")

    def refresh_pinned_tab(self) -> Optional[TabTarget]:
        """Clear a pin whose CDP target disappeared after a browser restart."""
        with self._lock:
            cfg = self._config
            pinned_tab = self._pinned_tab
        if pinned_tab is None:
            return None
        try:
            available = self._verify_target(cfg.cdp_host, cfg.cdp_port, pinned_tab.target_id)
        except Exception as exc:
            logger.debug("Could not verify pinned tab '{}': {}", pinned_tab.title, exc)
            return pinned_tab
        if available:
            return pinned_tab
        logger.info("Pinned tab '{}' is no longer available", pinned_tab.title)
        self.unpin_current_tab()
        return None

    def _notify_pin_changed(self, pinned_tab: Optional[TabTarget]) -> None:
        if self._on_pin_changed:
            self._on_pin_changed(pinned_tab)

    def _record_action_failure(self, action: MediaAction, exc: Exception) -> None:
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
            self.refresh_pinned_tab()
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
                self.refresh_pinned_tab()
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
        target_id: Optional[str] = None,
    ) -> None:
        from gamerscroll.cdp import TargetUnavailableError as CDPTargetUnavailableError
        from gamerscroll.cdp import send_key_event_sync

        key = _ACTION_TO_KEY.get(action)
        if key is None:
            raise ValueError(f"No CDP key mapping for action {action}")
        try:
            send_key_event_sync(
                host,
                port,
                key,
                browser_exe_name=browser_exe_name,
                target_id=target_id,
            )
        except CDPTargetUnavailableError as exc:
            raise TargetUnavailableError(str(exc)) from exc

    @staticmethod
    def _default_find_active_tab(
        host: str,
        port: int,
        browser_exe_name: Optional[str] = None,
    ) -> TabTarget:
        from gamerscroll.cdp import find_active_tab

        tab = find_active_tab(host, port, browser_exe_name=browser_exe_name)
        return TabTarget(tab.target_id, tab.title, tab.url)

    @staticmethod
    def _default_verify_target(host: str, port: int, target_id: str) -> bool:
        from gamerscroll.cdp import TargetUnavailableError as CDPTargetUnavailableError
        from gamerscroll.cdp import find_tab_ws

        try:
            find_tab_ws(host, port, target_id)
            return True
        except CDPTargetUnavailableError:
            return False
