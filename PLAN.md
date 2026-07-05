# GamerScroll — Plan

## Goal
A small Windows app that lets you scroll a browser window (on another monitor) with a single button press while a game has focus — no alt-tab, no losing the game's input.

## The core problem
While gaming, the game window captures keyboard/mouse input. We need:
1. A **trigger** the game doesn't swallow.
2. A way to scroll a **background** browser window without bringing it to the foreground.

## Recommended architecture

**Language:** Python (simple, fast to build, good Win32 + hotkey libs)
**Stack:**
- `keyboard` or `pynput` — global hotkey listener
- `pywin32` — find the target browser HWND and send scroll messages
- (optional) `pygetwindow` — locate window by title
- (optional) `pygame` / `vgamepad` — if we want a controller/joystick button as trigger

**Approach:** A tray app that listens for a chosen hotkey (or joystick button). When fired, it locates the target browser window by title and sends `WM_VSCROLL` / `WM_MOUSEWHEEL` / `Page Down` directly to that HWND via `PostMessage`. The browser scrolls in the background; the game keeps focus.

```
[Hotkey/Joystick] → [GamerScroll tray app] → PostMessage(WM_MOUSEWHEEL) → [Browser HWND]
```

## Why PostMessage and not Playwright/Selenium?
- Playwright requires launching Chrome with `--remote-debugging-port`. Fine for power users, but heavy setup.
- PostMessage to an existing HWND works with **any already-open** Chrome/Edge/Firefox window — zero browser config.
- The downside: scroll target must be the browser *window*, and some browsers route wheel to the focused tab. We'll mitigate by sending `WM_KEYDOWN` for `Page Down` / arrow keys, which is the most reliable.

## Trigger (chosen): Logitech mouse button via G HUB macro

**Target game: Valorant** (Riot Vanguard kernel anti-cheat — swallows most global hotkeys).
**Target browser: Chrome.**
**Trigger device: Logitech mouse.**

### Why this approach
Valorant + Vanguard aggressively captures input, so a plain global hotkey (`Ctrl+Alt+J`) is unreliable mid-match. The reliable path with a Logitech mouse:

1. In **Logitech G HUB**, bind a spare mouse button (sniper button, or a side button you don't use in Valorant) to a **G-key macro** that emits `F13` (scroll down) and `F14` (scroll up).
2. `F13`/`F14` are "phantom" keys — Windows and most apps (including Vanguard) never claim them, so the keystroke reaches our app even while Valorant has focus.
3. GamerScroll listens globally for `F13`/`F14` and sends `Page Down`/`Page Up` (or wheel) to the Chrome window via `PostMessage`.

### G HUB setup (one-time, manual)
- Open G HUB → your mouse → Assignments.
- Pick the spare button → Assign → System / Macro → keystroke `F13`.
- Repeat for another button → `F14`.
- (Optional) Bind a third button to `F15` for "scroll to top" etc.

> Note: do **not** bind the macro to mouse buttons Valorant already uses (left/right/fire/abilities). Use the sniper button or a thumb button you've left unbound.

## Scroll modes
- `Page Down` / `Page Up` — one screen per press
- `Arrow Down` / `Arrow Up` — small step
- `Mouse wheel` — configurable tick count
- Continuous scroll while held (optional)

## Configurable settings
- Target window title substring (e.g. "Chrome", "Edge", "— Firefox")
- Hotkey combo
- Scroll amount / mode
- Auto-start with Windows (optional)

## UI
- System tray icon with a small settings window.
- Right-click tray: Settings / Pause / Quit.
- Hotkey can be re-bound from settings.

## Project structure
```
GamerScroll/
├── PLAN.md
├── requirements.txt
├── gamerscroll/
│   ├── __main__.py          # entry point, tray icon
│   ├── hotkey.py            # hotkey/joystick listener
│   ├── scroller.py          # Win32 PostMessage scroll logic
│   ├── window_finder.py     # locate target HWND by title
│   ├── config.py            # load/save settings (JSON)
│   └── tray.py              # tray icon + settings dialog
├── config.json              # user settings
└── README.md
```

## MVP (phase 1) — single file first
One file `gamer_scroll.py` that:
1. Registers a global hotkey (`Ctrl+Alt+J` = down, `Ctrl+Alt+K` = up).
2. Finds the first window whose title contains "Chrome" (configurable).
3. Sends `Page Down` / `Page Up` to that HWND.
4. Runs until Esc pressed.

Prove it works against a real game, then split into the package above and add the tray UI.

## Resolved choices
- **Browser:** Comet (window title match: `" - Comet"`)
- **Game:** Valorant
- **Trigger:** Logitech mouse button → G HUB macro → `F13` (down) / `F14` (up)
- **Language:** Python
- **Mode:** one press = one page (`Page Down`/`Page Up`); add hold-to-repeat later if wanted

## MVP (phase 1) — building now
One file `gamer_scroll.py`:
1. Listens globally for `F13` (scroll down) and `F14` (scroll up).
2. Finds the Comet browser window by title substring `" - Comet"`.
3. Sends `Page Down` / `Page Up` to that HWND via `PostMessageW`.
4. Tiny console output, runs until `Ctrl+C`.
5. Settings (window title, hotkeys, scroll mode) at the top of the file for easy tweaking.
