# Research Brief: Browser Extensions for Remote/Background Scrolling

## Goal
Find an existing browser extension (or a small combination of extensions) that lets a Windows desktop app control scrolling in the browser **while the browser is not focused** (e.g., while playing Valorant in fullscreen). The desktop app already has global hotkeys working; it needs a reliable way to tell the browser to scroll down/up on the current/active tab.

## Context
- Target browsers: Chromium-based (Comet, Chrome, Edge, Brave). Firefox/Safari are out of scope unless the solution is trivial.
- The current app uses the Chrome DevTools Protocol (CDP) which requires launching the browser with `--remote-debugging-port`. The user wants to avoid that by using an extension.
- Previous attempt: a Manifest V3 extension with a service-worker WebSocket client was shelved because Comet's internal `ExtensionsSettings` policy blocked content-script/scripting injection on some sites (e.g. YouTube). We need alternatives or a way around that restriction.

## Must-have criteria
1. Can receive commands from an external Windows process while the browser is running normally (no special launch flags).
2. Can scroll the current/active tab or simulate `ArrowDown`/`ArrowUp` key events for sites like YouTube Shorts.
3. Works when the browser window is not focused (i.e., the extension injects events into the page, not relying on OS-level window focus).
4. Supports Manifest V3 (Chrome Web Store policy) OR can be side-loaded as an unpacked extension if it's open-source.
5. Extension can be installed in Comet, Chrome, Edge, or Brave.

## Nice-to-have criteria
- Open-source so we can inspect/fork it.
- Native Messaging support (more robust than a local WebSocket server).
- Supports remote commands via HTTP/WebSocket from localhost.
- Can target the active tab explicitly rather than only the currently focused window.
- Has no cloud/telemetry requirement; works fully offline.
- Works on YouTube Shorts and other video/social feeds.

## Search directions for the research agent

### 1. Remote-control / automation extensions
Search terms:
- "Chrome extension remote control scroll"
- "browser extension websocket remote commands"
- "control browser from external app extension"
- "send hotkey to browser extension from desktop app"
- "Chrome extension native messaging scroll"

Places:
- Chrome Web Store
- Firefox Add-ons (only if a Manifest V2/V3 cross-browser version exists)
- GitHub repositories tagged `chrome-extension`, `browser-automation`, `remote-control`

### 2. Existing automation platforms with extensions
Look into whether these have a lightweight extension that could be repurposed:
- Selenium / WebDriver-based browser extensions
- Puppeteer Replay / Recorder extensions
- AutoHotkey-related Chrome extensions
- Stream Deck plugins that talk to Chrome

### 3. Specific known extensions to check
The agent should check if any of the following still exist and meet the criteria:
- Extensions that expose a local HTTP/WebSocket API.
- Extensions named like "Remote Browser", "Browser Remote", "WebSocket Client", "HTTP Request Blocker" with bidirectional capability.
- Extensions that support "external messaging" (`runtime.sendMessage` from native apps).

### 4. Native Messaging as an alternative
If no extension directly supports remote WebSocket commands, search for:
- Open-source Native Messaging hosts that can relay messages to an extension.
- Existing extensions that register a `chrome.runtime.onMessageExternal` listener.

### 5. Comet-specific considerations
- Does Comet honor `chrome.scripting.executeScript` on all sites?
- Are there Comet-specific policies or flags to allow extensions on all URLs?
- Does Comet support `chrome.tabs` / `chrome.windows` APIs fully?

## Evaluation template
For each candidate found, please fill in:

| Field | Notes |
|-------|-------|
| Name & link | |
| License / open source? | |
| Manifest version | |
| Communication method | WebSocket / HTTP / Native Messaging / `runtime.sendMessageExternal` / other |
| Can it scroll? | How? (`window.scrollBy`, `ArrowDown` events, etc.) |
| Active tab targeting? | Does it act on the active tab regardless of browser focus? |
| Works unfocused? | Confirmed by docs/reviews/code? |
| YouTube Shorts support? | |
| Comet compatible? | Any known restrictions |
| Offline / local only? | |
| Last updated | |
| Verdict | Use / Adapt / Skip |

## Deliverable
A short markdown report with the top 3-5 candidates ranked by how close they come to the must-have criteria, plus a recommendation on whether to:
- (a) use an existing extension as-is,
- (b) fork an open-source extension and modify it, or
- (c) build a custom extension from scratch.
