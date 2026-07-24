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
A physical interaction pattern on the Media Key that resolves to one Gesture Binding from the applicable Site Profile or Generic Profile. Three types: Short Press, Double Press, Long Hold.
_Avoid_: Click pattern, input sequence

**Short Press**:
Media Key released before the hold threshold elapses, with no second press within the double-click window. The Generic Profile binds it to Pause/Play.
_Avoid_: Single click, tap

**Double Press**:
A second Short Press arriving within the double-click window after the first release. The Generic Profile binds it to Next.
_Avoid_: Double click

**Long Hold**:
Media Key held past the hold threshold. Fires at the threshold mark, not on release. The Generic Profile binds it to Prev.
_Avoid_: Long press, hold

**Hold Threshold**:
Minimum time (ms) the Media Key must be held to register as a Long Hold. Default: 500ms.

**Double-Click Window**:
Time (ms) after a Short Press release during which a second press is treated as a Double Press. Default: 300ms.

**Debounce**:
Minimum time (ms) between recognized Gestures to prevent mechanical bounce. Default: 150ms.

### Actions

**Media Action**:
One of the three built-in operations used by the Generic Profile: Pause/Play, Next, or Prev.
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
Module that resolves a recognized Gesture to its Gesture Binding and sends its Keyboard Chord to the selected target tab via CDP. Formerly `Scroller`.
_Avoid_: Scroller, command dispatcher

**CDP Key Event**:
A `Input.dispatchKeyEvent` keyDown/keyUp pair, including any modifier keys, sent to the selected target tab via Chrome DevTools Protocol. The transport for all Gesture Bindings.
_Avoid_: CDP command, key injection

**Disabled**:
App-level state where the GestureDetector stops responding to the Media Key. Toggled from the tray menu. Formerly `paused`.
_Avoid_: Paused, suspended

### Targeting

**Pinned Tab**:
A browser tab explicitly selected by the user as the preferred recipient of Media Actions, regardless of which tab is currently active.
_Avoid_: Saved tab, locked tab

**Pin Lifetime**:
A Pinned Tab exists only while the current GamerScroll and browser session remain running. Restarting either begins with no Pinned Tab.
_Avoid_: Persistent pin, restored pin

**Pin Current Tab**:
The user flow for choosing a Pinned Tab: focus the desired tab in the browser, then select the GamerScroll control that pins the current tab.
_Avoid_: Tab picker, automatic pin

**Pin Status**:
The normal Settings display of the current Pinned Tab's title and main domain, with an explicit control to remove the pin.
_Avoid_: Fallback alert, persistent pin

**Profile Setup Target**:
The tab whose main domain GamerScroll uses when opening Site Profile settings. The user focuses it before configuring controls; it does not need to be a Pinned Tab.
_Avoid_: Required pin, profile picker

**Quick Profile Setup**:
The main Settings entry point that opens the Site Profile form for the currently focused Profile Setup Target.
_Avoid_: Required profile management

**Profile Management**:
The Settings page that lists saved Site Profiles and offers their lifecycle actions, including opening, resetting, and deleting a profile.
_Avoid_: Quick profile setup

**Target Fallback**:
The policy used when the Pinned Tab is unavailable. GamerScroll silently sends the Media Action to the currently active browser tab.
_Avoid_: Error mode, disabled mode

**Site Profile**:
A reusable set of Media Action controls selected automatically from the target tab's main domain. A profile applies to all matching tabs and subdomains of that main domain, not only to the tab that was originally pinned.
_Avoid_: Tab configuration, website preset

**Generic Profile**:
The built-in Gesture Bindings used when a target domain has no Site Profile. Users can test these controls first, then save a Site Profile only when that domain needs different bindings.
_Avoid_: Required profile, unconfigured error

**Gesture Binding**:
A keyboard control assigned to one Gesture in a Site Profile. It is sent to the selected target tab when that Gesture is recognized.
_Avoid_: Fixed action mapping, command preset

**Unassigned Binding**:
A Gesture Binding intentionally left without a Keyboard Chord in a Site Profile. Recognizing its Gesture sends no command.
_Avoid_: Generic fallback binding, missing configuration error

**Keyboard Chord**:
A single key or keys pressed simultaneously, such as `Space`, `Shift+N`, or `Ctrl+Right`. Gesture Bindings support Keyboard Chords only; they do not support ordered key sequences or text entry.
_Avoid_: Macro, key sequence

**Chord Capture**:
The editing interaction for a Gesture Binding: the user selects its input field and presses the desired Keyboard Chord.
_Avoid_: Key dropdown, manual key code entry

**Binding Test**:
A user-initiated check that sends a saved Gesture Binding to the Profile Setup Target immediately, without requiring a Pinned Tab.
_Avoid_: Live gaming test, automatic test
