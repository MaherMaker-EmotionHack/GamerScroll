# Future Plans

## Extension-based approach (on hold)

A browser-extension relay could let GamerScroll control the browser without launching it with `--remote-debugging-port`. We explored this in an earlier version and kept it out of the main app for now because Comet's internal `ExtensionsSettings` policy blocks content-script/scripting injection on some sites (e.g. YouTube).

If that policy restriction is removed in a future Comet release, or if you switch to Chrome/Edge/Brave, the extension approach can be revived. A minimal design would be:

1. **Manifest V3 extension** with a service-worker WebSocket client listening on `ws://127.0.0.1:8765`.
2. **Python relay server** (`relay_server.py`) that listens for the configured global hotkeys and forwards `scroll_down` / `scroll_up` JSON messages to the extension.
3. **Content script** injected into all pages that either calls `window.scrollBy()` or dispatches `ArrowDown` / `ArrowUp` key events for YouTube Shorts.
4. **Fallback to `chrome.scripting.executeScript`** if the content script is not reachable.

For this to work reliably the extension needs explicit host permission for the target sites (e.g. YouTube) and the browser must not block script injection.

Files that were removed when the approach was shelved:
- `extension/`
- `relay_server.py`
- `RESEARCH_BRIEF_EXTENSIONS.md`

To restart work on this later, search the repository history or recreate those files from the design above.
