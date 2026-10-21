# GamerScroll — Agent Instructions

## Project overview

GamerScroll is a **Windows-only Python/PyQt6 system-tray application** that sends page-level media controls to a background Chromium browser (Chrome, Edge, Brave, Comet) while a fullscreen game has focus. One Media Key (default F13, mapped from Logitech G HUB) resolves to Short Press, Double Press, or Long Hold. Site Profiles or Generic Profile bindings select the Keyboard Chord sent through **Chrome DevTools Protocol (CDP)**.

- User docs and setup: [`README.md`](./README.md)
- For CLI/core/IPC work or prioritization, read [`ROADMAP.md`](./ROADMAP.md): it defines the next phase and keeps CLI/MCP proposals distinct from shipped behavior.
- Before submissions or binary redistribution, read [`docs/submission-readiness.md`](./docs/submission-readiness.md) and [`THIRD_PARTY_NOTICES.md`](./THIRD_PARTY_NOTICES.md).
- Design rationale and abandoned approaches: [`PLAN.md`](./PLAN.md)
- Shelved extension-based relay: [`FUTURE.md`](./FUTURE.md)
- Extension research template: [`RESEARCH_BRIEF_EXTENSIONS.md`](./RESEARCH_BRIEF_EXTENSIONS.md)

## Architecture

```text
[Mouse button via Logitech G HUB] → [F13]
        ↓
[pynput global media-key listener in gamerscroll/hotkeys.py]
        ↓
[gamerscroll/gestures.py GestureDetector]
        ↓
[gamerscroll/controller.py MediaController] → [gamerscroll/cdp.py]
        ↓
[ HTTP GET localhost:9222/json  →  WebSocket CDP ]
        ↓
[ Chromium renderer: Space / ArrowDown / ArrowUp key events ]
```

- `gamerscroll/__main__.py` is the composition root: creates `Config`, `GestureDetector`, `MediaController`, `HotkeyListener`, `TrayManager`, wires Qt signals, and starts the event loop.
- `gamerscroll/cdp.py` is the only module that talks to the browser.
- `gamerscroll/browser.py` is the only module that launches/terminates browser processes.
- `gamerscroll/config.py` is the only module that owns the JSON config schema and `%APPDATA%\GamerScroll\config.json` persistence.
- `gamerscroll/startup.py` is the only module that touches the Windows registry or single-instance mutex.
- `gamerscroll/gui.py`, `gamerscroll/tray.py` own all Qt UI code.

## Build / run commands

Run from source:

```powershell
.venv\Scripts\python.exe -m gamerscroll
```

Run with console debug output:

```powershell
.venv\Scripts\python.exe -m gamerscroll --log-level DEBUG --console
```

Build the single `.exe`:

```powershell
.\scripts\build.ps1
# output: dist\GamerScroll.exe
```

Regenerate the icon:

```powershell
.venv\Scripts\python.exe scripts\make_icon.py
```

## Conventions

- Every Python module starts with `from __future__ import annotations`.
- Use `from loguru import logger` for all logging.
- Configuration lives in the `Config` dataclass in `gamerscroll/config.py`; call `Config.load()` / `Config.save()`.
- Type hints are required (`Optional`, `Callable`, `Path | None`, etc.).
- Qt signals are the preferred mechanism for UI → core communication (see `__main__.py` for examples).
- Asset paths must support frozen PyInstaller execution via `sys._MEIPASS` (see `gamerscroll/tray.py`).
- Windows-specific code (registry, mutex, Win32 process APIs) must stay isolated in `browser.py` and `startup.py`.

## Common pitfalls

- **Browser must run with `--remote-debugging-port=<port>`**. Auto-launch in `browser.py` closes existing browser windows first; warn users about losing unsaved work.
- **Normal dispatch prefers the session-only Pinned Tab**, falling back to the active browser page when the pin is lost. Binding Test uses the Profile Setup Target and ignores the pin. Keep those routes distinct.
- **YouTube Shorts uses `Space` for pause/play and arrow keys for navigation**, so `cdp.py` sends `Input.dispatchKeyEvent` pairs for those keys.
- **Gesture timing is configurable** via `hold_threshold_ms`, `double_click_window_ms`, and `debounce_ms` in `Config`.
- **Long hold fires at the threshold mark**, not on release; keep the timer logic in `gestures.py` consistent with that contract.
- **Single-instance mutex** (`Global\GamerScrollSingleInstanceMutex`) prevents two copies from running.
- **pynput key names are lowercase**; the GUI normalizes captured keys to lowercase (`keyboard.Key[key_name]`).
- **Logs redact the Windows user profile path**, but can still expose tab titles and debugger addresses. Use fictional pages and a dedicated browser profile; sanitize diagnostics before sharing.

## Extension / future work

Do not start implementing the extension-based relay unless explicitly asked. Background research and criteria are captured in [`FUTURE.md`](./FUTURE.md) and [`RESEARCH_BRIEF_EXTENSIONS.md`](./RESEARCH_BRIEF_EXTENSIONS.md).
