"""Media controller: maps gestures to CDP media actions."""

from __future__ import annotations

import threading
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Optional

from loguru import logger

from gamerscroll.config import (
    Config,
    GESTURE_BINDING_NAMES,
    main_domain_from_url,
    normalize_keyboard_chord,
)
from gamerscroll.gestures import Gesture


_GESTURE_TO_BINDING_NAME: dict[Gesture, str] = {
    Gesture.SHORT_PRESS: "short_press",
    Gesture.DOUBLE_PRESS: "double_press",
    Gesture.LONG_HOLD: "long_hold",
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
        """Return the Site Profile domain for this tab."""
        return main_domain_from_url(self.url)


@dataclass(frozen=True)
class SiteProfileSetup:
    """The active tab and editable bindings used by Quick Profile Setup."""

    target: TabTarget
    domain: str
    bindings: dict[str, str | None]


class TargetUnavailableError(Exception):
    """Raised when a session-only pinned CDP target has disappeared."""


SendActionFn = Callable[[str, int, str, Optional[str], Optional[str]], None]
FindActiveTabFn = Callable[[str, int, Optional[str]], TabTarget]
VerifyTargetFn = Callable[[str, int, str], bool]
PinChangedFn = Callable[[Optional[TabTarget]], None]
RecoveryFn = Callable[[], bool]


class MediaController:
    """Resolves gestures to Generic Profile chords and sends them through CDP.

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
        self._profile_setup_target: Optional[TabTarget] = None

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
        """Dispatch a recognized gesture to the selected target's profile."""
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

        if gesture not in _GESTURE_TO_BINDING_NAME:
            logger.warning("Unknown gesture: {}", gesture)
            return
        target = pinned_tab
        if target is None and cfg.site_profiles:
            try:
                target = self._find_active_tab(
                    cfg.cdp_host,
                    cfg.cdp_port,
                    Path(cfg.browser_exe).name if cfg.browser_exe else None,
                )
            except Exception as exc:
                self._record_action_failure("profile target", exc)
                return

        chord = self.resolve_binding(gesture, target) if target else self.resolve_generic_binding(gesture)
        if chord is None:
            logger.info(
                "Gesture {} has no assigned binding for {}",
                gesture.name,
                target.main_domain if target else "Generic Profile",
            )
            self._emit(True, f"{gesture.name.replace('_', ' ').title()} is unassigned.")
            return

        logger.debug(
            "Sending {} chord {} for gesture {}",
            target.main_domain if target else "Generic Profile",
            chord,
            gesture.name,
        )
        try:
            exe_name = Path(cfg.browser_exe).name if cfg.browser_exe else None
            self._send_action(
                cfg.cdp_host,
                cfg.cdp_port,
                chord,
                exe_name,
                target.target_id if target else None,
            )
            with self._lock:
                self._consecutive_failures = 0
            self._emit(True, f"Sent {chord}")
        except TargetUnavailableError as exc:
            if pinned_tab is None:
                self._record_action_failure(chord, exc)
                return
            logger.info("Pinned tab '{}' disappeared; falling back to active tab", pinned_tab.title)
            self.unpin_current_tab()
            try:
                fallback_target: Optional[TabTarget] = None
                if cfg.site_profiles:
                    fallback_target = self._find_active_tab(cfg.cdp_host, cfg.cdp_port, exe_name)
                fallback_chord = (
                    self.resolve_binding(gesture, fallback_target)
                    if fallback_target
                    else self.resolve_generic_binding(gesture)
                )
                if fallback_chord is None:
                    self._emit(True, f"{gesture.name.replace('_', ' ').title()} is unassigned.")
                    return
                self._send_action(
                    cfg.cdp_host,
                    cfg.cdp_port,
                    fallback_chord,
                    exe_name,
                    fallback_target.target_id if fallback_target else None,
                )
                with self._lock:
                    self._consecutive_failures = 0
                self._emit(True, f"Sent {fallback_chord}")
            except Exception as exc:
                self._record_action_failure(chord, exc)
        except Exception as exc:
            self._record_action_failure(chord, exc)

    def resolve_generic_binding(self, gesture: Gesture) -> str | None:
        """Return the Generic Profile binding used when no Site Profile matches."""
        binding_name = _GESTURE_TO_BINDING_NAME.get(gesture)
        if binding_name is None:
            logger.warning("Unknown gesture: {}", gesture)
            return None
        with self._lock:
            chord = self._config.generic_bindings.get(binding_name)
        return normalize_keyboard_chord(chord) if chord is not None else None

    def resolve_binding(self, gesture: Gesture, target: TabTarget) -> str | None:
        """Return the target's Site Profile binding or its Generic fallback."""
        binding_name = _GESTURE_TO_BINDING_NAME.get(gesture)
        if binding_name is None:
            logger.warning("Unknown gesture: {}", gesture)
            return None
        with self._lock:
            profile = self._config.site_profiles.get(target.main_domain)
            chord = profile.get(binding_name) if profile is not None else self._config.generic_bindings.get(binding_name)
        return normalize_keyboard_chord(chord) if chord is not None else None

    def test_generic_binding(self, binding_name: str) -> None:
        """Send a saved Generic Profile chord to the active setup tab.

        Binding tests intentionally ignore the session pin so configuration can
        be tested against the tab the user focused before opening Settings.
        """
        if binding_name not in GESTURE_BINDING_NAMES:
            logger.warning("Unknown Generic Profile binding requested for test: {}", binding_name)
            return
        with self._lock:
            cfg = self._config
        chord = normalize_keyboard_chord(cfg.generic_bindings.get(binding_name))
        if chord is None:
            self._emit(False, "This binding is unassigned.")
            return
        try:
            exe_name = Path(cfg.browser_exe).name if cfg.browser_exe else None
            self._send_action(cfg.cdp_host, cfg.cdp_port, chord, exe_name, None)
            self._emit(True, f"Test sent {chord}")
        except Exception as exc:
            self._record_action_failure(chord, exc)

    def begin_site_profile_setup(self) -> SiteProfileSetup:
        """Create or edit the Site Profile for the active Profile Setup Target."""
        with self._lock:
            cfg = self._config
        exe_name = Path(cfg.browser_exe).name if cfg.browser_exe else None
        target = self._find_active_tab(cfg.cdp_host, cfg.cdp_port, exe_name)
        domain = target.main_domain
        if not domain:
            raise ValueError("The active browser tab has no usable domain.")
        with self._lock:
            bindings = dict(cfg.site_profiles.get(domain, cfg.generic_bindings))
            self._profile_setup_target = target
        return SiteProfileSetup(target=target, domain=domain, bindings=bindings)

    def test_site_profile_binding(self, chord: str) -> None:
        """Send a captured Site Profile chord to the Profile Setup Target."""
        normalized = normalize_keyboard_chord(chord)
        if normalized is None:
            self._emit(False, "This binding is unassigned.")
            return
        with self._lock:
            cfg = self._config
            target = self._profile_setup_target
        if target is None:
            self._emit(False, "Open Quick Profile Setup before testing a binding.")
            return
        try:
            exe_name = Path(cfg.browser_exe).name if cfg.browser_exe else None
            self._send_action(cfg.cdp_host, cfg.cdp_port, normalized, exe_name, target.target_id)
            self._emit(True, f"Test sent {normalized}")
        except Exception as exc:
            self._record_action_failure(normalized, exc)

    def save_site_profile(self, domain: str, bindings: dict[str, str | None]) -> None:
        """Update the persistent Site Profile selected by Quick Profile Setup."""
        with self._lock:
            self._config.set_site_profile(domain, bindings)

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

    def _record_action_failure(self, chord: str, exc: Exception) -> None:
        logger.error("Keyboard chord {} failed: {}", chord, exc)
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
        chord: str,
        browser_exe_name: Optional[str] = None,
        target_id: Optional[str] = None,
    ) -> None:
        from gamerscroll.cdp import TargetUnavailableError as CDPTargetUnavailableError
        from gamerscroll.cdp import send_key_chord_sync

        try:
            send_key_chord_sync(
                host,
                port,
                chord,
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
