"""Tests for CDP retry logic and controller health-check (issue #9)."""

from __future__ import annotations

from unittest.mock import patch, MagicMock

import pytest

from gamerscroll.cdp import CDPError, check_cdp_reachable, send_key_event_sync
from gamerscroll.config import Config
from gamerscroll.controller import MediaController, MediaStatus
from gamerscroll.gestures import Gesture


def test_send_key_event_sync_retries_on_failure() -> None:
    """send_key_event_sync should retry on CDPError before giving up."""
    call_count = 0

    def mock_run(coro):
        nonlocal call_count
        call_count += 1
        raise CDPError("Connection refused")

    with patch("gamerscroll.cdp.asyncio.run", side_effect=mock_run):
        with patch("gamerscroll.cdp.time.sleep", return_value=None):
            with pytest.raises(CDPError, match="Connection refused"):
                send_key_event_sync("127.0.0.1", 9222, "Space", max_retries=3, base_delay=0.01)

    assert call_count == 3  # retried 3 times


def test_send_key_event_sync_succeeds_on_second_attempt() -> None:
    """send_key_event_sync should succeed if the second attempt works."""
    call_count = 0

    def mock_run(coro):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            raise CDPError("Connection refused")
        # Second attempt succeeds (coro is already consumed, so just return)
        return None

    with patch("gamerscroll.cdp.asyncio.run", side_effect=mock_run):
        with patch("gamerscroll.cdp.time.sleep", return_value=None):
            send_key_event_sync("127.0.0.1", 9222, "Space", max_retries=3, base_delay=0.01)

    assert call_count == 2


def test_check_cdp_reachable_returns_true_when_ok() -> None:
    with patch("gamerscroll.cdp.find_active_tab_ws", return_value="ws://tab"):
        assert check_cdp_reachable("127.0.0.1", 9222) is True


def test_check_cdp_reachable_returns_false_on_error() -> None:
    with patch("gamerscroll.cdp.find_active_tab_ws", side_effect=CDPError("nope")):
        assert check_cdp_reachable("127.0.0.1", 9222) is False


def make_controller_with_health(
    send_action=None,
    on_recovery=None,
    max_failures: int = 3,
) -> tuple[MediaController, list[tuple[bool, str]]]:
    status_log: list[tuple[bool, str]] = []

    def on_status(status: MediaStatus) -> None:
        status_log.append((status.ok, status.message))

    config = Config(browser_exe=r"C:\Browser\comet.exe")
    controller = MediaController(
        config=config,
        send_action=send_action,
        on_status=on_status,
        on_recovery=on_recovery,
        max_consecutive_failures=max_failures,
    )
    return controller, status_log


def test_controller_degrades_after_consecutive_failures() -> None:
    """After max_consecutive_failures, the controller enters degraded mode."""
    failures = []

    def failing_send(host, port, action, browser_exe_name=None):
        raise RuntimeError("CDP unreachable")

    controller, status_log = make_controller_with_health(
        send_action=failing_send,
        max_failures=3,
    )

    # First two failures should not degrade.
    controller.handle_gesture(Gesture.SHORT_PRESS)
    controller.handle_gesture(Gesture.SHORT_PRESS)
    assert not controller._degraded

    # Third failure triggers degradation.
    controller.handle_gesture(Gesture.SHORT_PRESS)
    assert controller._degraded

    # Subsequent gestures are ignored while degraded.
    controller.handle_gesture(Gesture.SHORT_PRESS)
    assert any("CDP unreachable" in msg for _, msg in status_log)


def test_controller_check_health_recovers() -> None:
    """check_health should clear degraded state when CDP becomes reachable."""
    controller, status_log = make_controller_with_health()
    controller._degraded = True
    controller._consecutive_failures = 5

    with patch("gamerscroll.cdp.check_cdp_reachable", return_value=True):
        result = controller.check_health()

    assert result is True
    assert controller._degraded is False
    assert controller._consecutive_failures == 0


def test_controller_check_health_triggers_recovery() -> None:
    """check_health should call on_recovery when CDP is unreachable."""
    recovery_called = []

    def on_recovery():
        recovery_called.append(True)
        return True  # recovery succeeded

    controller, _ = make_controller_with_health(on_recovery=on_recovery)

    with patch("gamerscroll.cdp.check_cdp_reachable", side_effect=[False, True]):
        result = controller.check_health()

    assert result is True
    assert len(recovery_called) == 1
    assert controller._degraded is False


def test_controller_check_health_degrades_when_recovery_fails() -> None:
    """check_health should set degraded when recovery callback returns False."""
    def on_recovery():
        return False

    controller, _ = make_controller_with_health(on_recovery=on_recovery)

    with patch("gamerscroll.cdp.check_cdp_reachable", return_value=False):
        result = controller.check_health()

    assert result is False
    assert controller._degraded is True


def test_controller_check_health_no_recovery_callback() -> None:
    """check_health should degrade gracefully when no recovery callback is set."""
    controller, _ = make_controller_with_health(on_recovery=None)

    with patch("gamerscroll.cdp.check_cdp_reachable", return_value=False):
        result = controller.check_health()

    assert result is False
    assert controller._degraded is True


def test_controller_resets_failures_on_success() -> None:
    """A successful action should reset the consecutive failure counter."""
    call_count = 0

    def flaky_send(host, port, action, browser_exe_name=None):
        nonlocal call_count
        call_count += 1
        if call_count <= 1:
            raise RuntimeError("transient")
        # Second call succeeds

    controller, _ = make_controller_with_health(
        send_action=flaky_send,
        max_failures=3,
    )

    controller.handle_gesture(Gesture.SHORT_PRESS)  # fails
    assert controller._consecutive_failures == 1

    controller.handle_gesture(Gesture.SHORT_PRESS)  # succeeds
    assert controller._consecutive_failures == 0
    assert not controller._degraded