# GamerScroll — Media Control for Gamers

A Windows system-tray app that controls media playback (pause/play, next, prev) in a background Chromium browser tab while a fullscreen game has focus. It listens for a single phantom key (F13) from a Logitech mouse via G HUB and disambiguates three media actions through gesture detection.

## Language

### Input

**Phantom Key**:
A function key (F13–F24) that Windows and most games (including Valorant/Vanguard) never claim, so the keystroke reaches GamerScroll even while a game has focus.
_Avoid_: Hotkey, shortcut, macro

**Media Key**:
The single phantom key bound to the media button gesture detector. Default: F13.
_Avoid_: Trigger key, action key

**Gesture**:
A physical interaction pattern on the Media Key that maps to one Media Action. Three types: Short Press, Double Press, Long Hold.
_Avoid_: Click pattern, input sequence

**Short Press**:
Media Key released before the hold threshold elapses, with no second press within the double-click window. Maps to Pause/Play.
_Avoid_: Single click, tap

**Double Press**:
A second Short Press arriving within the double-click window after the first release. Maps to Next.
_Avoid_: Double click

**Long Hold**:
Media Key held past the hold threshold. Fires at the threshold mark, not on release. Maps to Prev.
_Avoid_: Long press, hold

**Hold Threshold**:
Minimum time (ms) the Media Key must be held to register as a Long Hold. Default: 500ms.

**Double-Click Window**:
Time (ms) after a Short Press release during which a second press is treated as a Double Press. Default: 300ms.

**Debounce**:
Minimum time (ms) between recognized Gestures to prevent mechanical bounce. Default: 150ms.

### Actions

**Media Action**:
One of three operations sent to the browser: Pause/Play, Next, or Prev.
_Avoid_: Command, event

**Pause/Play**:
Toggles video playback in the active browser tab. Sent as CDP `Space` key event.
_Avoid_: Toggle, play-pause

**Next**:
Advances to the next short/reel. Sent as CDP `ArrowDown` key event.
_Avoid_: Skip, forward

**Prev**:
Returns to the previous short/reel. Sent as CDP `ArrowUp` key event.
_Avoid_: Back, rewind

### Architecture

**GestureDetector**:
Module that tracks Media Key press/release timestamps and identifies which Gesture occurred, using timer threads for hold-threshold and double-click-window detection.
_Avoid_: Input handler, key listener

**MediaController**:
Module that maps a recognized Gesture to the corresponding Media Action and sends it via CDP. Formerly `Scroller`.
_Avoid_: Scroller, command dispatcher

**CDP Key Event**:
A single `Input.dispatchKeyEvent` (keyDown + keyUp) sent to the active browser tab via Chrome DevTools Protocol. The transport for all Media Actions.
_Avoid_: CDP command, key injection

**Disabled**:
App-level state where the GestureDetector stops responding to the Media Key. Toggled from the tray menu. Formerly `paused`.
_Avoid_: Paused, suspended