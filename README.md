# GamerScroll

Media control for gamers. Pause/play, skip, and go back in YouTube Shorts (or any browser tab) with a single Logitech mouse button while a fullscreen game has focus — no alt-tabbing required.

## Quick start

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
     a simultaneous shortcut such as `Ctrl+L`, clear a binding to disable its gesture,
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

```powershell
.\scripts\build.ps1
```

Output: `dist\GamerScroll.exe`

Run it directly, or place it in your startup folder. You can also enable **Start with Windows** in the app settings.
The build spec includes the Public Suffix List data required by Site Profiles, so always
rebuild the executable after changing dependencies or the build spec.

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

## Future ideas

See `FUTURE.md` for planned or shelved ideas, including the browser-extension relay approach.

## Known limitations

- The browser must be launched with `--remote-debugging-port=<port>`. The app can do this automatically, but it will close existing browser windows first.
- Media commands target the active/focused browser tab. If you switch tabs, you may need to click the desired tab first.
- Optimized for YouTube Shorts. Other reel sites (Instagram, Facebook) may not respond to the same keys.
- Bindings are page-level only. Browser UI shortcuts such as `Ctrl+N` and `Ctrl+D` cannot be triggered through CDP page input.
