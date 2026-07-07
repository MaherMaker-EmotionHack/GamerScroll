"""Tests for the media controller gesture-to-action mapping."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Optional

import pytest

from gamerscroll.config import Config
from gamerscroll.controller import MediaAction, MediaController, MediaStatus
from gamerscroll.gestures import Gesture


@dataclass
class SentAction:
    action: MediaAction
    browser_exe_name: Optional[str]


class FakeSender:
    """Records media actions instead of talking to CDP."""

    def __init__(self) -> None:
        self.actions: list[SentAction] = []
        self.error_message: Optional[str] = None

    def __call__(
        self,
        host: str,
        port: int,
        action: MediaAction,
        browser_exe_name: Optional[str] = None,
    ) -> None:
        if self.error_message is not None:
            raise RuntimeError(self.error_message)
        self.actions.append(SentAction(action, browser_exe_name))


def make_controller(
    sender: FakeSender,
    disabled: bool = False,
) -> tuple[MediaController, list[tuple[bool, str]]]:
    status_log: list[tuple[bool, str]] = []

    def on_status(status: MediaStatus) -> None:
        status_log.append((status.ok, status.message))

    config = Config(
        browser_exe=r"C:\Program Files\Comet\Application\comet.exe",
        disabled=disabled,
    )
    controller = MediaController(
        config=config,
        send_action=sender,
        on_status=on_status,
    )
    return controller, status_log


def test_short_press_sends_pause_play() -> None:
    sender = FakeSender()
    controller, _ = make_controller(sender)

    controller.handle_gesture(Gesture.SHORT_PRESS)

    assert sender.actions == [SentAction(MediaAction.PAUSE_PLAY, "comet.exe")]


def test_double_press_sends_next() -> None:
    sender = FakeSender()
    controller, _ = make_controller(sender)

    controller.handle_gesture(Gesture.DOUBLE_PRESS)

    assert sender.actions == [SentAction(MediaAction.NEXT, "comet.exe")]


def test_long_hold_sends_prev() -> None:
    sender = FakeSender()
    controller, _ = make_controller(sender)

    controller.handle_gesture(Gesture.LONG_HOLD)

    assert sender.actions == [SentAction(MediaAction.PREV, "comet.exe")]


def test_disabled_controller_ignores_gesture() -> None:
    sender = FakeSender()
    controller, status_log = make_controller(sender, disabled=True)

    controller.handle_gesture(Gesture.SHORT_PRESS)

    assert sender.actions == []
    assert status_log == [(False, "Media control is disabled.")]


def test_sender_error_emits_failure_status() -> None:
    sender = FakeSender()
    sender.error_message = "CDP unreachable"
    controller, status_log = make_controller(sender)

    controller.handle_gesture(Gesture.SHORT_PRESS)

    assert sender.actions == []
    assert status_log == [(False, "CDP unreachable")]


def test_update_config_changes_disabled_state() -> None:
    sender = FakeSender()
    controller, _ = make_controller(sender, disabled=False)

    new_config = Config(disabled=True)
    controller.update_config(new_config)
    controller.handle_gesture(Gesture.SHORT_PRESS)

    assert sender.actions == []


def test_unknown_gesture_is_ignored() -> None:
    sender = FakeSender()
    controller, status_log = make_controller(sender)

    controller.handle_gesture("unknown")  # type: ignore[arg-type]

    assert sender.actions == []
    assert status_log == []


def test_browser_exe_name_is_extracted_from_path() -> None:
    sender = FakeSender()
    config = Config(browser_exe=r"C:\Browser\brave.exe")
    controller = MediaController(config=config, send_action=sender)

    controller.handle_gesture(Gesture.SHORT_PRESS)

    assert sender.actions[0].browser_exe_name == "brave.exe"
