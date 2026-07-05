# GamerScroll

Control browser scrolling with a Logitech mouse button while playing Valorant (or any fullscreen game) without alt-tabbing.

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

5. **Configure hotkeys**

   - Default: `F13` scrolls down, `F14` scrolls up.
   - Click **Capture** next to each field to rebind them.

6. **Use it**

   - Open YouTube Shorts or any scrollable page.
   - Focus Valorant (or another fullscreen game).
   - Press your bound mouse button — the browser scrolls/advances in the background.

## Build a single `.exe`

```powershell
.\scripts\build.ps1
```

Output: `dist\GamerScroll.exe`

Run it directly, or place it in your startup folder. You can also enable **Start with Windows** in the app settings.

## Settings file

Configuration is stored at:

```
%APPDATA%\GamerScroll\config.json
```

## Architecture

```
[Logitech mouse button]
        ↓
[Logitech G HUB macro → F13/F14]
        ↓
[GamerScroll tray app (global hotkey listener)]
        ↓
[HTTP GET localhost:9222/json → find active tab WebSocket]
        ↓
[WebSocket CDP commands]
        ↓
[Chromium/Comet renderer]
        ↓
window.scrollBy()  OR  ArrowDown/ArrowUp key event
```

## How it works

The app uses the **Chrome DevTools Protocol (CDP)**. It sends real `Input.dispatchMouseEvent` (mouse wheel) and `Input.dispatchKeyEvent` (arrow keys) to the active browser tab. Because these events are injected into Chromium's own input pipeline, the browser does **not** need to be focused.

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

## Files

| File / folder | Purpose |
|---------------|---------|
| `gamerscroll/` | Main Python package. |
| `gamerscroll/__main__.py` | Entry point: tray, hotkeys, config, single-instance guard. |
| `gamerscroll/gui.py` | PyQt6 settings window. |
| `gamerscroll/tray.py` | Qt system tray icon and menu. |
| `gamerscroll/browser.py` | Browser detection, profile enumeration, launch/relaunch. |
| `gamerscroll/cdp.py` | CDP connection and scroll commands. |
| `gamerscroll/hotkeys.py` | Global `pynput` hotkey listener. |
| `gamerscroll/scroller.py` | Orchestrates hotkey events → CDP scroll. |
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
- Scrolls the active/focused browser tab. If you switch tabs, you may need to click the desired tab first.
- YouTube Shorts uses arrow-key navigation; normal pages use wheel scroll.
