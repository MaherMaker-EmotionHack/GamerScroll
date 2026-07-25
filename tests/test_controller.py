"""Tests for the media controller gesture-to-action mapping."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Optional

import pytest

from gamerscroll.config import Config
from gamerscroll.controller import (
    MediaController,
    MediaStatus,
    TabTarget,
    TargetUnavailableError,
)
from gamerscroll.gestures import Gesture


@dataclass
class SentAction:
    chord: str
    browser_exe_name: Optional[str]
    target_id: Optional[str] = None


class FakeSender:
    """Records media actions instead of talking to CDP."""

    def __init__(self) -> None:
        self.actions: list[SentAction] = []
        self.error_message: Optional[str] = None
        self.unavailable_target_ids: set[str] = set()

    def __call__(
        self,
        host: str,
        port: int,
        chord: str,
        browser_exe_name: Optional[str] = None,
        target_id: Optional[str] = None,
    ) -> None:
        if self.error_message is not None:
            raise RuntimeError(self.error_message)
        if target_id in self.unavailable_target_ids:
            raise TargetUnavailableError("Pinned browser tab is no longer available.")
        self.actions.append(SentAction(chord, browser_exe_name, target_id))


class FakeTargetFinder:
    """Returns the current browser tab without talking to CDP."""

    def __init__(self, target: TabTarget) -> None:
        self.target = target

    def __call__(self, host: str, port: int, browser_exe_name: Optional[str]) -> TabTarget:
        return self.target


class FakeTargetVerifier:
    """Reports whether a session target is still present in CDP."""

    def __init__(self, available: bool) -> None:
        self.available = available

    def __call__(self, host: str, port: int, target_id: str) -> bool:
        return self.available


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

    assert sender.actions == [SentAction("Space", "comet.exe")]


def test_double_press_sends_next() -> None:
    sender = FakeSender()
    controller, _ = make_controller(sender)

    controller.handle_gesture(Gesture.DOUBLE_PRESS)

    assert sender.actions == [SentAction("ArrowDown", "comet.exe")]


def test_long_hold_sends_prev() -> None:
    sender = FakeSender()
    controller, _ = make_controller(sender)

    controller.handle_gesture(Gesture.LONG_HOLD)

    assert sender.actions == [SentAction("ArrowUp", "comet.exe")]


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


def test_pin_current_tab_targets_that_tab_for_later_gestures() -> None:
    sender = FakeSender()
    selected_tab = TabTarget("pinned-id", "YouTube", "https://www.youtube.com/watch?v=1")
    controller, _ = make_controller(sender)
    controller = MediaController(
        config=Config(browser_exe=r"C:\Browser\brave.exe"),
        send_action=sender,
        find_active_tab=FakeTargetFinder(selected_tab),
    )

    assert controller.pin_current_tab() == selected_tab

    controller.handle_gesture(Gesture.SHORT_PRESS)

    assert sender.actions == [SentAction("Space", "brave.exe", "pinned-id")]


def test_unpin_current_tab_returns_gestures_to_the_active_tab() -> None:
    sender = FakeSender()
    selected_tab = TabTarget("pinned-id", "YouTube", "https://www.youtube.com/watch?v=1")
    controller = MediaController(
        config=Config(browser_exe=r"C:\Browser\brave.exe"),
        send_action=sender,
        find_active_tab=FakeTargetFinder(selected_tab),
    )
    controller.pin_current_tab()

    controller.unpin_current_tab()
    controller.handle_gesture(Gesture.SHORT_PRESS)

    assert controller.pinned_tab is None
    assert sender.actions == [SentAction("Space", "brave.exe", None)]


def test_missing_pinned_tab_falls_back_to_the_active_tab() -> None:
    sender = FakeSender()
    sender.unavailable_target_ids.add("closed-tab")
    selected_tab = TabTarget("closed-tab", "Closed video", "https://www.youtube.com/watch?v=1")
    controller = MediaController(
        config=Config(browser_exe=r"C:\Browser\brave.exe"),
        send_action=sender,
        find_active_tab=FakeTargetFinder(selected_tab),
    )
    controller.pin_current_tab()

    controller.handle_gesture(Gesture.DOUBLE_PRESS)

    assert controller.pinned_tab is None
    assert sender.actions == [SentAction("ArrowDown", "brave.exe", None)]


def test_a_new_controller_session_has_no_pinned_tab() -> None:
    selected_tab = TabTarget("pinned-id", "YouTube", "https://www.youtube.com/watch?v=1")
    first_session = MediaController(
        config=Config(),
        find_active_tab=FakeTargetFinder(selected_tab),
    )
    first_session.pin_current_tab()

    restarted_session = MediaController(config=Config())

    assert first_session.pinned_tab == selected_tab
    assert restarted_session.pinned_tab is None


def test_refreshing_after_a_browser_restart_removes_the_pin() -> None:
    selected_tab = TabTarget("old-tab", "YouTube", "https://www.youtube.com/watch?v=1")
    controller = MediaController(
        config=Config(),
        find_active_tab=FakeTargetFinder(selected_tab),
        verify_target=FakeTargetVerifier(available=False),
    )
    controller.pin_current_tab()

    assert controller.refresh_pinned_tab() is None
    assert controller.pinned_tab is None


def test_unassigned_generic_binding_sends_no_command() -> None:
    sender = FakeSender()
    controller = MediaController(
        config=Config(generic_bindings={
            "short_press": None,
            "double_press": "ArrowDown",
            "long_hold": "ArrowUp",
        }),
        send_action=sender,
    )

    controller.handle_gesture(Gesture.SHORT_PRESS)

    assert sender.actions == []


def test_generic_profile_resolves_custom_bindings_for_unmatched_sites() -> None:
    controller = MediaController(
        config=Config(generic_bindings={
            "short_press": "Ctrl+L",
            "double_press": None,
            "long_hold": "Shift+N",
        }),
    )

    assert controller.resolve_generic_binding(Gesture.SHORT_PRESS) == "Ctrl+L"
    assert controller.resolve_generic_binding(Gesture.DOUBLE_PRESS) is None


def test_binding_test_uses_active_tab_even_when_a_tab_is_pinned() -> None:
    sender = FakeSender()
    pinned_tab = TabTarget("pinned-id", "YouTube", "https://www.youtube.com/watch?v=1")
    controller = MediaController(
        config=Config(),
        send_action=sender,
        find_active_tab=FakeTargetFinder(pinned_tab),
    )
    controller.pin_current_tab()

    controller.test_generic_binding("short_press")

    assert sender.actions == [SentAction("Space", None, None)]


def test_site_profile_controls_the_pinned_tab_and_its_subdomains() -> None:
    sender = FakeSender()
    pinned_tab = TabTarget("pinned-id", "YouTube Music", "https://music.youtube.com/watch")
    controller = MediaController(
        config=Config(site_profiles={
            "youtube.com": {
                "short_press": "K",
                "double_press": None,
                "long_hold": "Shift+P",
            }
        }),
        send_action=sender,
        find_active_tab=FakeTargetFinder(pinned_tab),
    )
    controller.pin_current_tab()

    controller.handle_gesture(Gesture.SHORT_PRESS)

    assert sender.actions == [SentAction("K", None, "pinned-id")]


def test_quick_profile_setup_uses_active_tab_and_creates_from_generic_profile() -> None:
    sender = FakeSender()
    active_tab = TabTarget("active-id", "YouTube", "https://www.youtube.com/shorts/1")
    controller = MediaController(
        config=Config(generic_bindings={
            "short_press": "Space",
            "double_press": None,
            "long_hold": "ArrowUp",
        }),
        send_action=sender,
        find_active_tab=FakeTargetFinder(active_tab),
    )

    setup = controller.begin_site_profile_setup()

    assert setup.target == active_tab
    assert setup.domain == "youtube.com"
    assert setup.bindings == {
        "short_press": "Space",
        "double_press": None,
        "long_hold": "ArrowUp",
    }


def test_quick_profile_setup_edits_the_existing_main_domain_profile() -> None:
    active_tab = TabTarget("active-id", "YouTube", "https://music.youtube.com/watch")
    controller = MediaController(
        config=Config(site_profiles={
            "youtube.com": {
                "short_press": "K",
                "double_press": None,
                "long_hold": "Shift+P",
            }
        }),
        find_active_tab=FakeTargetFinder(active_tab),
    )

    setup = controller.begin_site_profile_setup()

    assert setup.domain == "youtube.com"
    assert setup.bindings["short_press"] == "K"


def test_profile_setup_tests_captured_chord_against_its_active_target() -> None:
    sender = FakeSender()
    active_tab = TabTarget("active-id", "YouTube", "https://www.youtube.com/shorts/1")
    controller = MediaController(
        config=Config(),
        send_action=sender,
        find_active_tab=FakeTargetFinder(active_tab),
    )
    controller.begin_site_profile_setup()

    controller.test_site_profile_binding("K")

    assert sender.actions == [SentAction("K", None, "active-id")]


def test_saving_quick_setup_profile_changes_future_gesture_binding() -> None:
    active_tab = TabTarget("active-id", "YouTube", "https://www.youtube.com/shorts/1")
    config = Config()
    controller = MediaController(
        config=config,
        find_active_tab=FakeTargetFinder(active_tab),
    )
    setup = controller.begin_site_profile_setup()

    controller.save_site_profile(setup.domain, {
        "short_press": "K",
        "double_press": None,
        "long_hold": "Shift+P",
    })

    assert config.site_profiles["youtube.com"]["short_press"] == "K"
    assert controller.resolve_binding(Gesture.SHORT_PRESS, active_tab) == "K"


def test_unmatched_site_uses_generic_profile_when_other_profiles_exist() -> None:
    sender = FakeSender()
    active_tab = TabTarget("active-id", "YouTube", "https://www.youtube.com/shorts/1")
    controller = MediaController(
        config=Config(site_profiles={
            "vimeo.com": {
                "short_press": "K",
                "double_press": None,
                "long_hold": "Shift+P",
            }
        }),
        send_action=sender,
        find_active_tab=FakeTargetFinder(active_tab),
    )

    controller.handle_gesture(Gesture.SHORT_PRESS)

    assert sender.actions == [SentAction("Space", None, "active-id")]


def test_saved_site_profiles_can_be_listed_reset_and_deleted() -> None:
    config = Config(
        generic_bindings={
            "short_press": "Space",
            "double_press": None,
            "long_hold": "ArrowUp",
        },
        site_profiles={
            "youtube.com": {
                "short_press": "K",
                "double_press": "J",
                "long_hold": "Shift+P",
            },
            "vimeo.com": {
                "short_press": "Space",
                "double_press": "ArrowDown",
                "long_hold": "ArrowUp",
            },
        },
    )
    controller = MediaController(config)

    assert controller.list_site_profile_domains() == ["vimeo.com", "youtube.com"]

    controller.reset_site_profile("youtube.com")

    assert config.site_profiles["youtube.com"] == config.generic_bindings
    assert controller.delete_site_profile("youtube.com") is True
    assert controller.list_site_profile_domains() == ["vimeo.com"]


def test_deleted_site_profile_falls_back_to_generic_bindings() -> None:
    active_tab = TabTarget("active-id", "YouTube", "https://www.youtube.com/shorts/1")
    config = Config(site_profiles={
        "youtube.com": {
            "short_press": "K",
            "double_press": None,
            "long_hold": "Shift+P",
        }
    })
    controller = MediaController(config)

    assert controller.resolve_binding(Gesture.SHORT_PRESS, active_tab) == "K"
    assert controller.delete_site_profile("youtube.com") is True
    assert controller.resolve_binding(Gesture.SHORT_PRESS, active_tab) == "Space"
