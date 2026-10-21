# GamerScroll

Media control for gamers. Pause/play, skip, and go back in YouTube Shorts (or any browser tab) with a single Logitech mouse button while a fullscreen game has focus — no alt-tabbing required.

## Requirements

- Windows, with Python 3.10 or newer and Git installed. CI uses Python 3.12.
- A supported Chromium browser; see [Browser support](#browser-support).
- For mouse gestures, a mouse-button mapping that emits the Media Key (for example,
  Logitech G HUB mapped to `F13`).

The current application is a Python/PyQt6 tray utility using `pynput`, `pywin32`,
`requests`, `websockets`, `loguru`, and `tldextract`. Linux and macOS are not supported
by the current Windows integration.

## Quick start

Open PowerShell. Clone the repository and create a virtual environment:

```powershell
git clone https://github.com/MaherMaker-EmotionHack/GamerScroll.git
cd GamerScroll
py -3 -m venv .venv
```

1. **Install dependencies**

   ```powershell
   .venv\Scripts\python.exe -m pip install -r requirements.txt
   ```

2. **Run the app**

   ```powershell
   .venv\Scripts\python.exe -m gamerscroll
   ```

   A system tray icon appears. Right-click it and choose **Settings**.

3. **Pick your browser**

   - Select Chrome, Edge, Brave, or Comet from the detected list.
   - Choose a profile (usually `Default`).
   - Set the CDP port (default `9222`).

4. **Launch the browser with CDP**

   - In settings, click **Launch Browser Now**.
   - This closes any existing browser windows and restarts it with `--remote-debugging-port=<port>`.

5. **Configure your media key and Generic Profile**

   - Default media key: `F13`.
   - Default gestures:
     - **Short press** → Pause/Play
     - **Double press** → Next
     - **Long hold** → Prev
   - Adjust **Hold threshold**, **Double-click window**, and **Debounce** to tune the feel.
   - The Generic Profile applies when a site has no Site Profile. Capture one key or
     a simultaneous page shortcut such as `Shift+N`, clear a binding to disable its gesture,
     then save and use **Test** to send it to the focused browser tab without pinning.

6. **Set up a Site Profile when a website needs different controls (optional)**

   - Focus the website in your browser, then open **Settings → Quick Profile Setup**.
   - GamerScroll creates the profile from the Generic Profile when needed, or opens the
     existing profile for editing. One profile applies to the site's main domain and all
     of its subdomains.
   - Capture a binding, use **Test** to send it to the focused Profile Setup Target, then
     save it. Site Profiles persist across restarts; a Pinned Tab does not.

7. **Use it**

   - Open YouTube Shorts.
   - Focus your fullscreen game.
   - Press your bound mouse button with the right gesture — the browser responds in the background.

## Build a single `.exe`

Install the development/build dependencies first:

```powershell
.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
.\scripts\build.ps1
```

Output: `dist\GamerScroll.exe`

Run it directly, or place it in your startup folder. You can also enable **Start with Windows** in the app settings.
The build spec includes the Public Suffix List data required by Site Profiles, so always
rebuild the executable after changing dependencies or the build spec.

Before sharing a binary, follow the source and dependency-license checklist in
[THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md).

## Development checks

```powershell
.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
.venv\Scripts\python.exe -m mypy gamerscroll
.venv\Scripts\python.exe -m pytest tests/ -v
```

GitHub Actions runs these checks and builds the Windows executable. A separate
job scans the full fetched Git history with Gitleaks.

## Settings file

Configuration is stored at:

```
%APPDATA%\GamerScroll\config.json
```

## Architecture

```
[Logitech mouse button]
        ↓
[Logitech G HUB macro → F13]
        ↓
[GamerScroll tray app (global media-key listener)]
        ↓
[GestureDetector: short press / double press / long hold]
        ↓
[MediaController maps gesture → media action]
        ↓
[HTTP GET localhost:9222/json → find active tab WebSocket]
        ↓
[WebSocket CDP key events]
        ↓
[Chromium/Comet renderer]
        ↓
Space / ArrowDown / ArrowUp key event
```

## How it works

The app uses the **Chrome DevTools Protocol (CDP)**. It sends real `Input.dispatchKeyEvent` (`Space`, `ArrowDown`, `ArrowUp`) to the active browser tab. Because these events are injected into Chromium's own input pipeline, the browser does **not** need to be focused.

A single phantom key (default `F13`) is interpreted by a gesture detector:

| Gesture | Action | CDP key |
|---------|--------|---------|
| Short press | Pause/Play | `Space` |
| Double press | Next | `ArrowDown` |
| Long hold | Prev | `ArrowUp` |

## What bindings can control

GamerScroll is a remote control for a compatible media webpage, not for the browser application itself. It sends keyboard events to the selected webpage renderer through CDP.

- A binding works only when the target site exposes that control as an in-page keyboard shortcut, such as `Space`, arrow keys, or Prime Video's `F`.
- Browser-chrome shortcuts such as `Ctrl+N` (new window), `Ctrl+D` (bookmark), tab switching, and the address bar are outside this transport's scope.
- For reliable gaming use, pin the intended media tab before focusing the game. Binding Test intentionally uses the focused setup tab without a pin.

## Browser support

Chromium-based browsers only:

- Google Chrome
- Microsoft Edge
- Brave
- Comet / Perplexity

Other browsers (Firefox, Safari) use different protocols and are not supported.

## Anti-cheat / safety notes

- Does not touch Valorant's process or memory.
- Does not install drivers or use low-level input interception.
- Uses Chromium's own documented DevTools Protocol on `127.0.0.1` only.
- Logitech G HUB macros are standard userspace automation.

## Logging

GamerScroll writes a rotating log file to:

```
%APPDATA%\GamerScroll\logs\gamerscroll.log
```

In dev mode you can also print logs to the console:

```powershell
.venv\Scripts\python.exe -m gamerscroll --log-level DEBUG --console
```

Useful log levels: `DEBUG`, `INFO`, `WARNING`, `ERROR`. You can also change the level permanently in **Settings → Logging**.

If a frozen `.exe` reports a missing `tldextract\.tld_set_snapshot` file, close all
running GamerScroll instances and rebuild with `powershell.exe -ExecutionPolicy Bypass -File .\scripts\build.ps1`.

## Files

| File / folder | Purpose |
|---------------|---------|
| `gamerscroll/` | Main Python package. |
| `gamerscroll/__main__.py` | Entry point: tray, gesture detector, media controller, single-instance guard. |
| `gamerscroll/logger.py` | Loguru setup, rotation, redaction, exception hooks. |
| `gamerscroll/gui.py` | PyQt6 settings window. |
| `gamerscroll/tray.py` | Qt system tray icon and menu. |
| `gamerscroll/browser.py` | Browser detection, profile enumeration, launch/relaunch. |
| `gamerscroll/cdp.py` | CDP connection and key-event commands. |
| `gamerscroll/gestures.py` | Single-key gesture detector state machine. |
| `gamerscroll/controller.py` | Maps gestures to CDP media actions. |
| `gamerscroll/hotkeys.py` | Global `pynput` media-key listener. |
| `gamerscroll/config.py` | Load/save `%APPDATA%\GamerScroll\config.json`. |
| `gamerscroll/startup.py` | Single-instance mutex + Windows Run registry. |
| `assets/icon.ico` | App icon (also used by PyInstaller). |
| `GamerScroll.spec` | PyInstaller spec. |
| `scripts/build.ps1` | Build the single `.exe`. |
| `scripts/run_dev.ps1` | Run from source. |
| `scripts/make_icon.py` | Regenerate the icon. |
| `scripts/fix_readme.py` | Fix README formatting. |
| `launch_comet_cdp.ps1` | Helper to launch Comet with CDP enabled. |
| `cdp_scroll.py` | Original working CDP prototype (kept for reference). |
| `gamer_scroll.py` | Failed Win32 `PostMessage` attempt (kept for reference). |
| `FUTURE.md` | Future ideas, including the shelved extension approach. |
| `requirements.txt` | Python dependencies. |

## Roadmap

The next planned development phase is a headless CLI for the existing media-control
services, with structured results that people and agents can use. This is planned
work: the current `python -m gamerscroll` entry point starts the tray application
and supports logging flags only.

See [ROADMAP.md](ROADMAP.md) for the 26–38 hour implementation plan and acceptance
criteria. An MCP adapter is a later possibility. Existing UI redesign proposals
remain separate from this phase. Shelved extension ideas remain in
[FUTURE.md](FUTURE.md).

## Privacy during development

Use a dedicated browser profile and fictional local test pages for development,
recordings, and issue reports. Current diagnostics can include tab titles, domains,
and debugger addresses; user-path redaction does not sanitize those values. Inspect
logs and screenshots before sharing them. Keep browser data in the ignored
`local-browser-profile/` directory and unsanitized artifacts in `local-artifacts/`.
Keep `.env`, tokens, private keys, cookies, and browser profiles out of Git.
GamerScroll does not require an AI API key.

## Ownership and license

GamerScroll is personally owned and maintained by
[MaherMaker-EmotionHack](https://github.com/MaherMaker-EmotionHack).
Existing commits are attributed to the owner's `MaherTheMaker` account.

Copyright (C) 2026 MaherMaker-EmotionHack. Licensed under **GPL-3.0-only**;
see [LICENSE](LICENSE), [NOTICE](NOTICE), and
[THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md).

Project-submission preparation and checks are recorded in
[docs/submission-readiness.md](docs/submission-readiness.md).

## Known limitations

- The browser must be launched with `--remote-debugging-port=<port>`. The app can do this automatically, but it will close existing browser windows first.
- Media commands prefer a session-only Pinned Tab; otherwise they resolve the active browser tab, with a first-page fallback if it cannot be identified.
- Optimized for YouTube Shorts. Other reel sites (Instagram, Facebook) may not respond to the same keys.
- Bindings are page-level only. Browser UI shortcuts such as `Ctrl+N` and `Ctrl+D` cannot be triggered through CDP page input.
