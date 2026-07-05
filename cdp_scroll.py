"""
GamerScroll — CDP version.

Scrolls a Chromium/Comet browser tab via the Chrome DevTools Protocol.
This bypasses extension restrictions and focus state entirely.

Setup:
  1. Close all Comet windows.
  2. Launch Comet with a debugging port:
       "C:\Path\To\comet.exe" --remote-debugging-port=9222
     (or create a shortcut that adds that flag)
  3. Open YouTube Shorts or any page you want to scroll.
  4. Run: .venv\python.exe cdp_scroll.py
  5. Press F13/F14 (via G HUB mouse button) -> the tab scrolls.
"""

import asyncio
import json
import threading

import requests
import websockets
from pynput import keyboard

# ---------------------------------------------------------------------------
# SETTINGS
# ---------------------------------------------------------------------------
CDP_PORT = 9222
CDP_HOST = "127.0.0.1"

SCROLL_DOWN_KEY = keyboard.Key.f13
SCROLL_UP_KEY = keyboard.Key.f14
SCROLL_AMOUNT = 400  # pixels per scroll command
SCROLL_X = 640
SCROLL_Y = 360

# ---------------------------------------------------------------------------
# CDP helpers
# ---------------------------------------------------------------------------

def list_tabs():
    try:
        resp = requests.get(f"http://{CDP_HOST}:{CDP_PORT}/json", timeout=2)
        resp.raise_for_status()
        return [t for t in resp.json() if t.get("type") == "page"]
    except Exception as e:
        print(f"[CDP] Cannot reach browser on port {CDP_PORT}: {e}")
        return []


def get_ws_url_for_active_tab():
    """Return the webSocketDebuggerUrl for the active tab."""
    tabs = list_tabs()
    if not tabs:
        print("[CDP] No page tabs found.")
        return None

    # Prefer the active/focused tab; fallback to first tab.
    for t in tabs:
        if t.get("active") or t.get("focused"):
            print(f"[CDP] Targeting active tab: {t.get('title')} ({t.get('url')})")
            return t.get("webSocketDebuggerUrl")
    print(f"[CDP] Targeting first tab: {tabs[0].get('title')} ({tabs[0].get('url')})")
    return tabs[0].get("webSocketDebuggerUrl")


async def send_cdp(ws, message_id, method, params):
    await ws.send(json.dumps({"id": message_id, "method": method, "params": params}))
    response = await ws.recv()
    data = json.loads(response)
    if "error" in data:
        raise RuntimeError(f"{method} error: {data['error']}")
    return data


async def send_scroll(action: str):
    ws_url = get_ws_url_for_active_tab()
    if not ws_url:
        return

    direction = 1 if action == "scroll_down" else -1
    delta = direction * SCROLL_AMOUNT
    key = "ArrowDown" if direction > 0 else "ArrowUp"
    vk = 40 if direction > 0 else 38

    try:
        async with websockets.connect(ws_url) as ws:
            # Method 1: Real mouse-wheel event at the compositor level.
            await send_cdp(ws, 1, "Input.dispatchMouseEvent", {
                "type": "mouseWheel",
                "x": SCROLL_X,
                "y": SCROLL_Y,
                "deltaX": 0,
                "deltaY": delta,
                "pointerType": "mouse",
            })
            print(f"[CDP] MouseWheel {action} ({delta}px)")

            # Method 2: Real keyboard events (works for YouTube Shorts).
            for event_type in ("keyDown", "keyUp"):
                await send_cdp(ws, 2 if event_type == "keyDown" else 3,
                               "Input.dispatchKeyEvent", {
                    "type": event_type,
                    "key": key,
                    "code": key,
                    "windowsVirtualKeyCode": vk,
                    "nativeVirtualKeyCode": vk,
                })
            print(f"[CDP] KeyEvent {key}")
    except Exception as e:
        print(f"[CDP] Scroll failed: {e}")


# ---------------------------------------------------------------------------
# Keyboard listener
# ---------------------------------------------------------------------------
loop = None


def on_press(key):
    if key == SCROLL_DOWN_KEY:
        if loop:
            asyncio.run_coroutine_threadsafe(send_scroll("scroll_down"), loop)
    elif key == SCROLL_UP_KEY:
        if loop:
            asyncio.run_coroutine_threadsafe(send_scroll("scroll_up"), loop)
    elif key == keyboard.Key.esc:
        print("[CDP] Esc pressed — stopping.")
        return False


def keyboard_listener():
    print("[CDP] Listening for F13 (down) and F14 (up). Press Esc to quit.")
    with keyboard.Listener(on_press=on_press) as listener:
        listener.join()


async def main():
    global loop
    loop = asyncio.get_running_loop()

    listener_thread = threading.Thread(target=keyboard_listener, daemon=True)
    listener_thread.start()

    print(f"[CDP] Ready. Make sure Comet is running with --remote-debugging-port={CDP_PORT}")
    await asyncio.Future()  # run forever


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n[CDP] Ctrl+C — bye.")
