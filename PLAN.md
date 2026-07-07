# GamerScroll — Plan

## Goal
A small Windows system-tray app that controls media playback (pause/play, next, prev) in a background Chromium browser tab while a fullscreen game has focus — no alt-tab, no losing the game's input.

## The core problem
While gaming, the game window captures keyboard/mouse input. We need:
1. A **trigger** the game doesn't swallow.
2. A way to send media commands to a **background** browser tab without bringing it to the foreground.

## Chosen architecture

**Language:** Python
**Stack:**
- `pynput` — global media-key listener
- `PyQt6` — system tray icon and settings window
- `requests` + `websockets` — Chrome DevTools Protocol (CDP) client
- `pywin32` — Windows registry, mutex, and browser process helpers
- `loguru` — logging

**Approach:** A tray app that listens for a single phantom key (default `F13`) from a Logitech G HUB macro. A gesture detector turns that one key into three actions:

| Gesture | Media action | CDP key |
|---------|--------------|---------|
| Short press | Pause/Play | `Space` |
| Double press | Next | `ArrowDown` |
| Long hold | Prev | `ArrowUp` |

The app then sends the corresponding `Input.dispatchKeyEvent` to the active browser tab via CDP. The browser never needs focus.

```
[Logitech mouse button]
        ↓
[Logitech G HUB macro → F13]
        ↓
[GamerScroll tray app (pynput listener)]
        ↓
[GestureDetector]
        ↓
[MediaController]
        ↓
[CDP: HTTP GET localhost:9222/json → WebSocket]
        ↓
[Chromium renderer: Space / ArrowDown / ArrowUp]
```

## Why CDP and not PostMessage / Windows media keys?

- **PostMessage to an HWND** is browser-agnostic but cannot target the active tab reliably, and many modern sites ignore synthetic wheel/key messages.
- **Windows media keys** (`VK_MEDIA_PLAY_PAUSE`) control the system-wide current media source, not necessarily the browser, and cannot navigate YouTube Shorts.
- **CDP key events** inject directly into Chromium's input pipeline, work on the active tab, and send the exact keys YouTube Shorts expects (`Space`, `ArrowDown`, `ArrowUp`).

## Trigger: Logitech mouse button via G HUB macro

**Target game:** Valorant (Riot Vanguard aggressively captures input).
**Target browser:** Chromium-based (Chrome, Edge, Brave, Comet).

### Why this works
Valorant + Vanguard swallow most global hotkeys, but `F13`–`F24` are phantom keys that Windows and Vanguard never claim. A single G HUB macro emits `F13`, and GamerScroll's gesture detector disambiguates three actions from that one key.

### G HUB setup (one-time, manual)
- Open G HUB → your mouse → Assignments.
- Pick a spare button → Assign → System / Macro → keystroke `F13`.
- Use the same button with gesture timing in-game:
  - **Tap** → pause/play
  - **Double-tap** → next
  - **Hold ~500 ms** → prev

> Note: do **not** bind the macro to mouse buttons the game already uses. Use a sniper button or unused thumb button.

## Gesture timing

Defaults (configurable in Settings):
- **Hold threshold:** 500 ms — press held longer than this fires `Prev` at the threshold mark.
- **Double-click window:** 300 ms — a second press within this window after release becomes `Next`.
- **Debounce:** 150 ms — minimum time between recognized gestures to ignore mechanical bounce.

## Configurable settings

- Browser executable and profile
- CDP port
- Media key
- Hold threshold, double-click window, debounce
- Auto-launch browser with CDP
- Start with Windows
- Log level

## UI

- System tray icon with tooltip status.
- Right-click tray: **Disable / Enable**, **Launch Browser**, **Settings**, **Exit**.
- Settings window for browser, media key, gesture timing, logging, and startup.
- Test buttons in settings to manually trigger Pause/Play, Next, and Prev.

## Project structure

```
GamerScroll/
├── PLAN.md
├── README.md
├── AGENTS.md
├── CONTEXT.md
├── requirements.txt
├── requirements-dev.txt
├── pyproject.toml
├── gamerscroll/
│   ├── __main__.py          # entry point: composition root
│   ├── browser.py           # browser detection, launch, termination
│   ├── cdp.py               # CDP connection and key-event commands
│   ├── config.py            # JSON config schema and persistence
│   ├── controller.py        # gesture → media action → CDP
│   ├── gestures.py          # single-key gesture detector
│   ├── gui.py               # PyQt6 settings window
│   ├── hotkeys.py           # pynput global media-key listener
│   ├── logger.py            # Loguru setup
│   ├── startup.py           # single-instance mutex + Windows Run registry
│   └── tray.py              # Qt system tray icon and menu
├── tests/                   # pytest suite
├── scripts/
│   ├── build.ps1            # PyInstaller build
│   ├── run_dev.ps1          # run from source
│   └── make_icon.py         # regenerate icon
├── assets/
│   └── icon.ico
└── GamerScroll.spec         # PyInstaller spec
```

## Failure feedback

On startup the app checks whether the CDP endpoint is reachable. If not, it:
1. Logs a warning.
2. Shows "CDP not reachable" in the tray tooltip.
3. Plays the Windows default beep so the user knows something is wrong.

## Future ideas

See `FUTURE.md` for shelved ideas, including the browser-extension relay approach.
