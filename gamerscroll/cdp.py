"""Chrome DevTools Protocol connection and scroll commands."""

from __future__ import annotations

import asyncio
import json
import re
import time
from dataclasses import dataclass
from typing import Any, List, Optional

import requests
import websockets
from loguru import logger

from gamerscroll.config import normalize_keyboard_chord


class CDPError(Exception):
    """Raised when a CDP operation fails."""


class TargetUnavailableError(CDPError):
    """Raised when a requested CDP page target is no longer present."""


@dataclass(frozen=True)
class CDPTab:
    """The CDP data needed to identify and reconnect to a page tab."""

    target_id: str
    title: str
    url: str
    websocket_url: str


def _get_page_tabs(
    host: str,
    port: int,
    timeout: float,
    *,
    allow_empty: bool = False,
) -> list[dict[str, Any]]:
    """Fetch the current page tabs from Chrome's JSON discovery endpoint."""
    url = f"http://{host}:{port}/json"
    logger.debug("Fetching CDP tab list from {}", url)
    try:
        resp = requests.get(url, timeout=timeout)
        resp.raise_for_status()
    except requests.RequestException as exc:
        raise CDPError(f"Cannot reach browser on port {port}: {exc}") from exc

    tabs = [tab for tab in resp.json() if tab.get("type") == "page"]
    if not tabs and not allow_empty:
        raise CDPError("No page tabs found.")
    logger.debug("Found {} page tab(s)", len(tabs))
    return tabs


def _to_cdp_tab(tab: dict[str, Any]) -> Optional[CDPTab]:
    target_id = tab.get("id")
    websocket_url = tab.get("webSocketDebuggerUrl")
    if not isinstance(target_id, str) or not isinstance(websocket_url, str):
        return None
    return CDPTab(
        target_id=target_id,
        title=str(tab.get("title", "")),
        url=str(tab.get("url", "")),
        websocket_url=websocket_url,
    )


def _get_browser_window_titles(exe_name: str) -> List[str]:
    """Return titles of windows owned by the browser process."""
    try:
        import win32gui
        import win32process
        import psutil
    except Exception as exc:
        logger.debug("Cannot enumerate browser windows: {}", exc)
        return []

    titles: List[str] = []

    def callback(hwnd: int, _: Any) -> bool:
        if not win32gui.IsWindowVisible(hwnd):
            return True
        try:
            _, pid = win32process.GetWindowThreadProcessId(hwnd)
            proc = psutil.Process(pid)
            if proc.name().lower() == exe_name.lower():
                title = win32gui.GetWindowText(hwnd)
                if title:
                    titles.append(title)
        except Exception:
            pass
        return True

    try:
        win32gui.EnumWindows(callback, None)
    except Exception as exc:
        logger.debug("EnumWindows failed: {}", exc)
    return titles


def _tab_title_from_window_title(window_title: str) -> str:
    """Strip the browser suffix (e.g. ' - Comet') from a window title."""
    # Common suffixes used by Chromium browsers.
    for suffix in [" - Comet", " - Chrome", " - Microsoft Edge", " - Brave"]:
        if window_title.endswith(suffix):
            return window_title[: -len(suffix)]
    return window_title


def find_active_tab_ws(
    host: str,
    port: int,
    timeout: float = 2.0,
    browser_exe_name: Optional[str] = None,
) -> Optional[str]:
    """Return the webSocketDebuggerUrl for the active/focused tab, or best guess."""
    return find_active_tab(host, port, timeout, browser_exe_name).websocket_url


def find_active_tab(
    host: str,
    port: int,
    timeout: float = 2.0,
    browser_exe_name: Optional[str] = None,
) -> CDPTab:
    """Return the active/focused CDP page tab, falling back to the first page."""
    tabs = _get_page_tabs(host, port, timeout)

    # 1. Prefer the tab explicitly marked active/focused by CDP.
    for t in tabs:
        if t.get("active") or t.get("focused"):
            selected = _to_cdp_tab(t)
            if selected is not None:
                logger.info("Selected active/focused tab: {} ({})", selected.title, selected.websocket_url)
                return selected

    # 2. Try to match the browser window title(s) against tab titles.
    if browser_exe_name:
        window_titles = _get_browser_window_titles(browser_exe_name)
        logger.debug("Browser window titles: {}", window_titles)
        for wt in window_titles:
            expected = _tab_title_from_window_title(wt)
            if not expected:
                continue
            for t in tabs:
                if t.get("title", "").strip() == expected.strip():
                    selected = _to_cdp_tab(t)
                    if selected is not None:
                        logger.info(
                            "Selected tab by window title match '{}': {}",
                            expected,
                            selected.websocket_url,
                        )
                        return selected

    # 3. Fallback to the first tab.
    selected = _to_cdp_tab(tabs[0])
    if selected is None:
        raise CDPError("Selected page tab has no usable debugger target.")
    logger.info(
        "No active tab found; falling back to first tab: {} ({})",
        selected.title,
        selected.websocket_url,
    )
    return selected


def find_tab_ws(host: str, port: int, target_id: str, timeout: float = 2.0) -> str:
    """Return a pinned target's WebSocket URL or report that it disappeared."""
    for tab in _get_page_tabs(host, port, timeout, allow_empty=True):
        if tab.get("id") == target_id:
            selected = _to_cdp_tab(tab)
            if selected is not None:
                return selected.websocket_url
    raise TargetUnavailableError("Pinned browser tab is no longer available.")


_SPECIAL_KEYS: dict[str, tuple[str, int]] = {
    "Space": ("Space", 32),
    "Enter": ("Enter", 13),
    "Tab": ("Tab", 9),
    "Escape": ("Escape", 27),
    "Backspace": ("Backspace", 8),
    "Delete": ("Delete", 46),
    "Insert": ("Insert", 45),
    "Home": ("Home", 36),
    "End": ("End", 35),
    "PageUp": ("PageUp", 33),
    "PageDown": ("PageDown", 34),
    "ArrowDown": ("ArrowDown", 40),
    "ArrowUp": ("ArrowUp", 38),
    "ArrowLeft": ("ArrowLeft", 37),
    "ArrowRight": ("ArrowRight", 39),
}
_MODIFIERS: dict[str, tuple[str, str, int, int]] = {
    "Ctrl": ("Control", "ControlLeft", 17, 2),
    "Alt": ("Alt", "AltLeft", 18, 1),
    "Shift": ("Shift", "ShiftLeft", 16, 8),
    "Meta": ("Meta", "MetaLeft", 91, 4),
}


def _key_event_data(key: str) -> tuple[str, str, int]:
    """Map a normalized binding key to CDP ``key``, ``code``, and VK values."""
    if key in _SPECIAL_KEYS:
        code, virtual_key = _SPECIAL_KEYS[key]
        return key, code, virtual_key
    if len(key) == 1 and "A" <= key <= "Z":
        return key, f"Key{key}", ord(key)
    if len(key) == 1 and "0" <= key <= "9":
        return key, f"Digit{key}", ord(key)
    if re.fullmatch(r"F(?:[1-9]|1[0-9]|2[0-4])", key):
        number = int(key[1:])
        return key, key, 111 + number
    raise CDPError(f"Unsupported CDP key: {key}")


def _parse_chord(chord: str) -> tuple[list[str], str]:
    """Validate a serialized simultaneous chord and split modifiers from its key."""
    normalized = normalize_keyboard_chord(chord)
    if normalized is None:
        raise CDPError(f"Invalid keyboard chord: {chord}")
    parts = normalized.split("+")
    modifiers = parts[:-1]
    key = parts[-1]
    return modifiers, key


async def send_key_event(
    host: str,
    port: int,
    key: str,
    browser_exe_name: Optional[str] = None,
    target_id: Optional[str] = None,
) -> None:
    """Send a keyDown/keyUp pair for a single key via CDP.

    Args:
        key: The CDP key name, e.g. ``"Space"``, ``"ArrowDown"``, ``"ArrowUp"``.
        browser_exe_name: Optional executable name used to resolve the active tab.
    """
    await send_key_chord(
        host,
        port,
        key,
        browser_exe_name=browser_exe_name,
        target_id=target_id,
    )


async def send_key_chord(
    host: str,
    port: int,
    chord: str,
    browser_exe_name: Optional[str] = None,
    target_id: Optional[str] = None,
) -> None:
    """Send one key or simultaneous keyboard chord to a CDP page target."""
    modifiers, key = _parse_chord(chord)
    ws_url = (
        find_tab_ws(host, port, target_id)
        if target_id is not None
        else find_active_tab_ws(host, port, browser_exe_name=browser_exe_name)
    )
    if not ws_url:
        raise CDPError("No target tab available.")

    main_key, main_code, main_vk = _key_event_data(key)
    modifier_mask = sum(_MODIFIERS[modifier][3] for modifier in modifiers)
    text = " " if main_key == "Space" and not modifiers else None
    logger.debug("Sending CDP keyboard chord: {}", chord)
    try:
        async with websockets.connect(ws_url) as ws:
            events: list[tuple[str, str, str, int, int]] = []
            active_modifiers = 0
            for modifier in modifiers:
                modifier_key, modifier_code, modifier_vk, modifier_bit = _MODIFIERS[modifier]
                active_modifiers |= modifier_bit
                events.append(("keyDown", modifier_key, modifier_code, modifier_vk, active_modifiers))
            events.extend([
                ("keyDown", main_key, main_code, main_vk, modifier_mask),
                ("keyUp", main_key, main_code, main_vk, modifier_mask),
            ])
            for modifier in reversed(modifiers):
                modifier_key, modifier_code, modifier_vk, modifier_bit = _MODIFIERS[modifier]
                active_modifiers &= ~modifier_bit
                events.append(("keyUp", modifier_key, modifier_code, modifier_vk, active_modifiers))

            for idx, (event_type, event_key, code, vk_code, event_modifiers) in enumerate(events, start=1):
                params: dict[str, Any] = {
                    "type": event_type,
                    "key": event_key,
                    "code": code,
                    "windowsVirtualKeyCode": vk_code,
                    "nativeVirtualKeyCode": vk_code,
                    "modifiers": event_modifiers,
                }
                if text is not None and event_key == "Space":
                    params["text"] = text
                await ws.send(json.dumps({
                    "id": idx,
                    "method": "Input.dispatchKeyEvent",
                    "params": params,
                }))
                await ws.recv()
            logger.debug("CDP keyboard chord completed successfully")
    except websockets.WebSocketException as exc:
        raise CDPError(f"WebSocket error: {exc}") from exc
    except OSError as exc:
        raise CDPError(f"Connection error: {exc}") from exc


def send_key_event_sync(
    host: str,
    port: int,
    key: str,
    browser_exe_name: Optional[str] = None,
    target_id: Optional[str] = None,
    *,
    max_retries: int = 3,
    base_delay: float = 0.5,
) -> None:
    """Synchronous wrapper around :func:`send_key_event` with retry.

    Retries with exponential backoff on transient connection errors so a
    brief browser hiccup doesn't immediately fail the gesture.
    """
    send_key_chord_sync(
        host,
        port,
        key,
        browser_exe_name=browser_exe_name,
        target_id=target_id,
        max_retries=max_retries,
        base_delay=base_delay,
    )


def send_key_chord_sync(
    host: str,
    port: int,
    chord: str,
    browser_exe_name: Optional[str] = None,
    target_id: Optional[str] = None,
    *,
    max_retries: int = 3,
    base_delay: float = 0.5,
) -> None:
    """Synchronous retrying wrapper around :func:`send_key_chord`."""
    last_exc: Optional[Exception] = None
    for attempt in range(1, max_retries + 1):
        try:
            asyncio.run(
                send_key_chord(
                    host,
                    port,
                    chord,
                    browser_exe_name=browser_exe_name,
                    target_id=target_id,
                )
            )
            return
        except TargetUnavailableError:
            raise
        except CDPError as exc:
            last_exc = exc
            if attempt < max_retries:
                delay = base_delay * (2 ** (attempt - 1))
                logger.warning(
                    "CDP key event attempt {}/{} failed ({}); retrying in {:.1f}s",
                    attempt, max_retries, exc, delay,
                )
                time.sleep(delay)
            else:
                logger.error("CDP keyboard chord failed after {} attempts: {}", max_retries, exc)
    if last_exc:
        raise last_exc


def check_cdp_reachable(host: str, port: int, timeout: float = 2.0) -> bool:
    """Return True if the CDP HTTP endpoint is reachable and has at least one page tab."""
    try:
        find_active_tab_ws(host, port, timeout=timeout)
        return True
    except Exception:
        return False


async def send_scroll(
    host: str,
    port: int,
    direction: int,
    amount: int,
    x: int,
    y: int,
    browser_exe_name: Optional[str] = None,
) -> None:
    """Send one scroll tick via CDP.

    Args:
        direction: +1 for down, -1 for up.
        amount: pixels per scroll.
        x, y: viewport coordinates for the mouse-wheel event.
        browser_exe_name: Optional executable name used to resolve the active tab.
    """
    ws_url = find_active_tab_ws(host, port, browser_exe_name=browser_exe_name)
    if not ws_url:
        raise CDPError("No target tab available.")

    delta = direction * amount
    key = "ArrowDown" if direction > 0 else "ArrowUp"
    vk_code = 40 if direction > 0 else 38

    logger.debug(
        "Sending CDP scroll direction={} amount={} coords=({}, {})",
        direction, amount, x, y,
    )
    try:
        async with websockets.connect(ws_url) as ws:
            # Mouse wheel event.
            await ws.send(json.dumps({
                "id": 1,
                "method": "Input.dispatchMouseEvent",
                "params": {
                    "type": "mouseWheel",
                    "x": x,
                    "y": y,
                    "deltaX": 0,
                    "deltaY": delta,
                    "pointerType": "mouse",
                },
            }))
            await ws.recv()

            # Arrow key events for YouTube Shorts and keyboard-driven sites.
            for idx, event_type in enumerate(("keyDown", "keyUp"), start=2):
                await ws.send(json.dumps({
                    "id": idx,
                    "method": "Input.dispatchKeyEvent",
                    "params": {
                        "type": event_type,
                        "key": key,
                        "code": key,
                        "windowsVirtualKeyCode": vk_code,
                        "nativeVirtualKeyCode": vk_code,
                    },
                }))
                await ws.recv()
            logger.debug("CDP scroll commands completed successfully")
    except websockets.WebSocketException as exc:
        raise CDPError(f"WebSocket error: {exc}") from exc
    except OSError as exc:
        raise CDPError(f"Connection error: {exc}") from exc


def send_scroll_sync(
    host: str,
    port: int,
    direction: int,
    amount: int,
    x: int,
    y: int,
    browser_exe_name: Optional[str] = None,
) -> None:
    """Synchronous wrapper around :func:`send_scroll`."""
    asyncio.run(send_scroll(host, port, direction, amount, x, y, browser_exe_name=browser_exe_name))
