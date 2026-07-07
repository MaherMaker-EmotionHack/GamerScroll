"""Chrome DevTools Protocol connection and scroll commands."""

from __future__ import annotations

import asyncio
import json
import re
import time
from typing import Any, List, Optional

import requests
import websockets
from loguru import logger


class CDPError(Exception):
    """Raised when a CDP operation fails."""


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

    def callback(hwnd, _):
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
    url = f"http://{host}:{port}/json"
    logger.debug("Fetching CDP tab list from {}", url)
    try:
        resp = requests.get(url, timeout=timeout)
        resp.raise_for_status()
    except requests.RequestException as exc:
        raise CDPError(f"Cannot reach browser on port {port}: {exc}") from exc

    tabs = [t for t in resp.json() if t.get("type") == "page"]
    if not tabs:
        raise CDPError("No page tabs found.")

    logger.debug("Found {} page tab(s)", len(tabs))

    # 1. Prefer the tab explicitly marked active/focused by CDP.
    for t in tabs:
        if t.get("active") or t.get("focused"):
            ws_url = t.get("webSocketDebuggerUrl")
            title = t.get("title", "")
            logger.info("Selected active/focused tab: {} ({})", title, ws_url)
            return ws_url

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
                    ws_url = t.get("webSocketDebuggerUrl")
                    logger.info("Selected tab by window title match '{}': {}", expected, ws_url)
                    return ws_url

    # 3. Fallback to the first tab.
    ws_url = tabs[0].get("webSocketDebuggerUrl")
    title = tabs[0].get("title", "")
    logger.info("No active tab found; falling back to first tab: {} ({})", title, ws_url)
    return ws_url


_KEY_CODES: dict[str, int] = {
    "Space": 32,
    "ArrowDown": 40,
    "ArrowUp": 38,
}


async def send_key_event(
    host: str,
    port: int,
    key: str,
    browser_exe_name: Optional[str] = None,
) -> None:
    """Send a keyDown/keyUp pair for a single key via CDP.

    Args:
        key: The CDP key name, e.g. ``"Space"``, ``"ArrowDown"``, ``"ArrowUp"``.
        browser_exe_name: Optional executable name used to resolve the active tab.
    """
    ws_url = find_active_tab_ws(host, port, browser_exe_name=browser_exe_name)
    if not ws_url:
        raise CDPError("No target tab available.")

    vk_code = _KEY_CODES.get(key)
    if vk_code is None:
        raise CDPError(f"Unsupported CDP key: {key}")

    # Include `text` for Space so Chromium generates a keypress/input event.
    text = " " if key == "Space" else None

    logger.debug("Sending CDP key event: {}", key)
    try:
        async with websockets.connect(ws_url) as ws:
            for idx, event_type in enumerate(("keyDown", "keyUp"), start=1):
                params: dict[str, Any] = {
                    "type": event_type,
                    "key": key,
                    "code": key,
                    "windowsVirtualKeyCode": vk_code,
                    "nativeVirtualKeyCode": vk_code,
                }
                if text is not None:
                    params["text"] = text
                await ws.send(json.dumps({
                    "id": idx,
                    "method": "Input.dispatchKeyEvent",
                    "params": params,
                }))
                await ws.recv()
            logger.debug("CDP key event completed successfully")
    except websockets.WebSocketException as exc:
        raise CDPError(f"WebSocket error: {exc}") from exc
    except OSError as exc:
        raise CDPError(f"Connection error: {exc}") from exc


def send_key_event_sync(
    host: str,
    port: int,
    key: str,
    browser_exe_name: Optional[str] = None,
    *,
    max_retries: int = 3,
    base_delay: float = 0.5,
) -> None:
    """Synchronous wrapper around :func:`send_key_event` with retry.

    Retries with exponential backoff on transient connection errors so a
    brief browser hiccup doesn't immediately fail the gesture.
    """
    last_exc: Optional[Exception] = None
    for attempt in range(1, max_retries + 1):
        try:
            asyncio.run(send_key_event(host, port, key, browser_exe_name=browser_exe_name))
            return
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
                logger.error("CDP key event failed after {} attempts: {}", max_retries, exc)
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
