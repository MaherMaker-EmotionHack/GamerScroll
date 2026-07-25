# Pinned tabs and main-domain site profiles

GamerScroll will send each Gesture Binding to a session-only Pinned Tab when one exists; otherwise it targets the active browser tab. If the pinned tab disappears, it silently falls back to the active tab. A persistent Site Profile is selected by the target's main (registrable) domain, sharing one profile across subdomains; an unmatched domain uses the Generic Profile.

**Considered options:** Persisting a tab across restarts could misdirect controls after CDP identities change, and exact-host profiles would distinguish YouTube Music from YouTube but add management overhead. The chosen model starts fresh after either app or browser restart and keeps one lean profile per main domain.

**Consequences:** A profile contains independent, optional Keyboard Chords for Short Press, Double Press, and Long Hold. Users capture and test chords from a focused site without pinning it; Settings also provides Profile Management. Chords are webpage-renderer input only, not browser-chrome shortcuts such as `Ctrl+N` or `Ctrl+D`. This supersedes the fixed, non-configurable mapping in ADR-0003 while retaining CDP keyboard events as the transport.
