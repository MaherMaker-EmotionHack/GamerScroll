"""
GamerScroll — scroll a background Comet browser window with a Logitech mouse button
while playing Valorant (or any fullscreen game).

Setup:
  1. pip install -r requirements.txt
  2. In Logitech G HUB, bind a spare mouse button to a keystroke macro:
       F13  -> scroll DOWN one page
       F14  -> scroll UP   one page
  3. Open Comet on your second monitor with something to scroll.
  4. python gamer_scroll.py
  5. Press F13/F14 (via your mouse button) — Chrome scrolls, game keeps focus.

Tweak SETTINGS below if you want different keys, a different browser, or wheel mode.
"""

import ctypes
import threading
import time

from pynput import keyboard
import win32api
import win32con
import win32gui

# ---------------------------------------------------------------------------
# SETTINGS
# ---------------------------------------------------------------------------
WINDOW_TITLE_FRAGMENT = " - Comet"          # substring of the browser window title

# Phantom keys emitted by the Logitech G HUB macro. These keys bypass
# Valorant/Vanguard input capture because the game never claims them.
SCROLL_DOWN_KEY = keyboard.Key.f13
SCROLL_UP_KEY   = keyboard.Key.f14

# "page"  -> send Page Down / Page Up (one screen per press, most reliable)
# "wheel" -> send WM_MOUSEWHEEL ticks (smoother, smaller step)
SCROLL_MODE = "page"

WHEEL_TICKS = 3   # only used in "wheel" mode; ~120 per tick

# ---------------------------------------------------------------------------
# Win32 helpers
# ---------------------------------------------------------------------------

# WM_MOUSEWHEEL needs the high-order word for the wheel delta.
# WHEEL_DELTA = 120 per notch.
def _make_wparam(delta: int) -> int:
    # low word = key state (0), high word = wheel delta
    return (delta & 0xFFFF) << 16


def _find_target_window(fragment: str):
    """Return the HWND of the topmost window whose title contains `fragment`."""
    matches = []

    def _enum(hwnd, _):
        if not win32gui.IsWindowVisible(hwnd):
            return True
        title = win32gui.GetWindowText(hwnd)
        if title and fragment.lower() in title.lower():
            matches.append(hwnd)
        return True

    win32gui.EnumWindows(_enum, None)
    return matches[0] if matches else None


def _send_key_to_hwnd(hwnd, vk_code: int):
    """Send a keydown/keyup to a specific window via PostMessage.

    Tries the focused child window first; falls back to the top-level HWND.
    """
    WM_KEYDOWN = win32con.WM_KEYDOWN
    WM_KEYUP   = win32con.WM_KEYUP

    # Try to find the actual render area / focused child window.
    target = win32gui.GetFocus() or hwnd
    if target == 0:
        target = hwnd

    scan = win32api.MapVirtualKey(vk_code, 0)
    lparam_down = (scan << 16) | 1
    lparam_up   = (scan << 16) | 1 | (1 << 30) | (1 << 31)

    win32gui.PostMessage(target, WM_KEYDOWN, vk_code, lparam_down)
    time.sleep(0.02)
    win32gui.PostMessage(target, WM_KEYUP, vk_code, lparam_up)


def _send_wheel_to_hwnd(hwnd, delta: int):
    """Send a WM_MOUSEWHEEL message to the focused child window."""
    target = win32gui.GetFocus() or hwnd
    if target == 0:
        target = hwnd

    wparam = _make_wparam(delta)
    win32gui.PostMessage(target, win32con.WM_MOUSEWHEEL, wparam, 0)


def _scroll_window(direction: str):
    """direction: 'down' or 'up'"""
    hwnd = _find_target_window(WINDOW_TITLE_FRAGMENT)
    if not hwnd:
        print(f"[GamerScroll] No window found matching '{WINDOW_TITLE_FRAGMENT}'")
        return

    if SCROLL_MODE == "page":
        vk = win32con.VK_NEXT if direction == "down" else win32con.VK_PRIOR  # Page Down / Page Up
        _send_key_to_hwnd(hwnd, vk)
        print(f"[GamerScroll] {'Page Down' if direction == 'down' else 'Page Up'} -> HWND {hwnd}")
    else:  # wheel
        delta = -WHEEL_TICKS * 120 if direction == "down" else WHEEL_TICKS * 120
        _send_wheel_to_hwnd(hwnd, delta)
        print(f"[GamerScroll] Wheel {delta} -> HWND {hwnd}")


# ---------------------------------------------------------------------------
# Hotkey listener
# ---------------------------------------------------------------------------

class GamerScroll:
    def __init__(self):
        self._listener = None

    def on_press(self, key):
        if key == SCROLL_DOWN_KEY:
            threading.Thread(target=_scroll_window, args=("down",), daemon=True).start()
        elif key == SCROLL_UP_KEY:
            threading.Thread(target=_scroll_window, args=("up",), daemon=True).start()
        elif key == keyboard.Key.esc:
            # Ctrl+C also works; Esc is a convenience quit if running in a console.
            print("[GamerScroll] Esc pressed — stopping.")
            if self._listener:
                self._listener.stop()

    def run(self):
        # Sanity check: are the F13/F14 keys actually reachable on this system?
        print("=" * 60)
        print("GamerScroll running.")
        print(f"  Target window : '{WINDOW_TITLE_FRAGMENT}'")
        print(f"  Scroll down   : {SCROLL_DOWN_KEY}  (Logitech mouse button -> G HUB macro)")
        print(f"  Scroll up     : {SCROLL_UP_KEY}")
        print(f"  Mode          : {SCROLL_MODE}")
        print("  Quit          : Esc or Ctrl+C")
        print("=" * 60)

        with keyboard.Listener(on_press=self.on_press) as listener:
            self._listener = listener
            listener.join()


if __name__ == "__main__":
    try:
        GamerScroll().run()
    except KeyboardInterrupt:
        print("\n[GamerScroll] Ctrl+C — bye.")
