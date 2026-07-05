"""Fix README.md Files table and add Future ideas section."""

from pathlib import Path


def main() -> None:
    p = Path("README.md")
    text = p.read_text(encoding="utf-8")

    # Strip out stale extension-related lines regardless of exact formatting.
    lines = text.splitlines()
    cleaned = []
    for line in lines:
        stripped = line.strip()
        if "relay_server.py" in stripped or "extension/" in stripped:
            continue
        cleaned.append(line)
    text = "\n".join(cleaned)

    # Build the new Files section.
    files_section = """## Files

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
| `gamerscroll/config.py` | Load/save `%APPDATA%\\GamerScroll\\config.json`. |
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
"""

    # Replace everything from ## Files to end of file.
    start = text.find("## Files")
    if start != -1:
        text = text[:start] + files_section + "\n## Known limitations\n\n"
        # Append known limitations text.
        text += (
            "- The browser must be launched with `--remote-debugging-port=<port>`. "
            "The app can do this automatically, but it will close existing browser windows first.\n"
            "- Scrolls the active/focused browser tab. If you switch tabs, you may need to click the desired tab first.\n"
            "- YouTube Shorts uses arrow-key navigation; normal pages use wheel scroll.\n"
        )
        print("Replaced Files section")
    else:
        print("Files section not found")

    p.write_text(text, encoding="utf-8")
    print("README.md updated")


if __name__ == "__main__":
    main()
