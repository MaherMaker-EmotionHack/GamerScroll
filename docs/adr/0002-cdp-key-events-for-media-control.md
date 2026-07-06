# CDP key events for media control instead of Windows media keys

GamerScroll sends media commands (pause/play, next, prev) as CDP `Input.dispatchKeyEvent` calls to the active browser tab, instead of using Windows system media keys (VK_MEDIA_PLAY_PAUSE etc.).

**Considered options:**
- **Windows media keys** — dead simple, one API, but can't navigate YouTube Shorts (next/prev short is page navigation, not media transport). Also sends to whatever app is the system-wide current media source, not necessarily the browser.
- **CDP + JavaScript injection** — site-specific selectors for maximum reliability, but fragile (site UI changes break selectors) and requires a per-site profile system.
- **CDP key events** (chosen) — consistent with the existing scroll architecture, works for YouTube Shorts (Space/ArrowDown/ArrowUp), no per-site selectors needed.

**Why chosen:** YouTube Shorts responds to Space (pause), ArrowDown (next), and ArrowUp (prev) natively. CDP key events are already implemented in `cdp.py` for scrolling. This reuses the existing transport with minimal new code.

**Consequences:** Reels (Instagram/Facebook) may not respond to the same keys — if support is needed later, a site-profile system (option 3) would be required. The current scope is YouTube Shorts only.