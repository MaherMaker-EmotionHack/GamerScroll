# Resolution: Define Accessible Visual Validation

This contract defines the acceptance checks for the **Control Deck** and the concise tray entry point. It applies to the implemented UI and its UI-automation or manual validation; it does not add a second control model, browser-chrome shortcut support, or a tray dashboard.

## Baseline requirements

- The Control Deck preserves this reading and tab order: **readiness**, **Control target**, **Gesture map**, then Site Profile context and secondary setup. A user can determine whether GamerScroll is ready, where the next Gesture will be sent, and the current bindings without relying on color, hover, or tooltips.
- Every interactive control is reachable with `Tab` and `Shift+Tab` and exposes a programmatic role, accessible name, and state through Windows accessibility APIs. Buttons use `Enter` and `Space`; checkboxes use `Space`; native comboboxes use `Up` and `Down` to change the selection; and spin controls use `Up` and `Down` to adjust the value. Standard Qt controls may provide the role and native key handling; the application supplies the visible text or accessible name.
- Focus never disappears. The focused control has a 2 px visual boundary with at least 3:1 contrast against adjacent colors. The boundary remains visible when the accent is unavailable or indistinguishable by combining the accent with a neutral outline, fill change, or both.
- Status is always conveyed by a plain-language label and a familiar status icon as well as a semantic color. `Checking browser connection`, `Ready`, `Listening disabled`, `Browser unavailable`, `Pinned Tab unavailable`, and `Setup required` are not color-only states.
- During loading, readiness announces `Checking browser connection` and exposes an indeterminate progress state without suggesting that control is ready. Before browser setup or when no browser target is available, readiness announces `Setup required` and offers `Complete browser setup` as its one recovery action.
- When CDP is unavailable for a configured browser, readiness announces `Browser unavailable: <browser> is not connected for page input`. It does not present a ready target or imply that Gesture Bindings will be delivered, and it offers `Reconnect browser` as its one recovery action. This state does not redirect to initial setup.
- When listening is disabled, readiness announces `Listening disabled: Gesture Bindings will not be sent` and offers `Enable GamerScroll` as its one recovery action. Activating it returns focus to the readiness status and announces `Ready` or the applicable degraded state.
- When a Pinned Tab disappears, GamerScroll silently routes the next Gesture Binding to the active browser tab without interrupting play. When the Control Deck is viewed, both its readiness strip and Control target card state `Pinned Tab unavailable: control returned to the active browser tab` and expose `Pin Current Tab` as its single recovery action.
- The Gesture map and Generic and Site Profile editors are generated from the developer-owned Gesture Registry. They show Short Press, Double Press, Triple Press, and Long Hold, plus every future registered Gesture, as one binding row each; a newly introduced row is `Unassigned` until configured. Triple Press is `Unassigned` in the Generic Profile by default.
- Keyboard Chords use `Cascadia Mono` or the system monospace fallback. All other UI text uses `Segoe UI Variable`, `Segoe UI`, then the system UI fallback. Icons supplement a text label; they do not replace it.
- Page-level Keyboard Chords are Gesture Binding data, delivered to the selected target through CDP Key Events. The contract must not describe `F11`, ordered key sequences, browser-chrome shortcuts, or operating-system controls as available Gesture Bindings.

## Keyboard And Accessible Names

The following names are the required accessible names. Their visible labels may be followed by the target, profile, or state when that context makes the action safer.

| Area | Control | Required accessible name and behavior |
| --- | --- | --- |
| Window navigation | Control, Profiles, Input & timing, Advanced | Each is exposed as a tab with its selected state. Arrow keys move between tabs when the tab strip has focus; `Enter` or `Space` activates the focused tab. |
| Readiness | Contextual recovery action | Name the specific action, for example `Reconnect browser`, `Complete browser setup`, or `Enable GamerScroll`. The name does not use a generic `Fix` or `Retry` label. The action appears after status text in tab order. |
| Readiness | Loading state | `Checking browser connection`, exposed as an indeterminate progress state. It is not interactive and does not announce ready controls. |
| Readiness | Empty setup state | `Setup required: select a browser and Chromium Profile to begin`. Its sole recovery action is `Complete browser setup`. |
| Readiness | Browser unavailable state | `Browser unavailable: <browser> is not connected for page input`. It does not announce a ready Control target, and its sole recovery action is `Reconnect browser`. |
| Readiness | Disabled state | `Listening disabled: Gestures will not be sent`. Its sole recovery action is `Enable GamerScroll`; after activation, focus returns to readiness and its resulting state is announced. |
| Control target | Pin Current Tab | `Pin current tab: <title>, <main domain>` when a focused tab is available. Activation pins that tab for the current session. |
| Control target | Unpin | `Unpin current control target: <title>, <main domain>`. It is unavailable when no Pinned Tab exists. |
| Control target | Target mode and details | A non-interactive summary announces either `Pinned this session` or `Active browser tab`, followed by title, main domain, browser, and Chromium Profile. After a missing-pin fallback, it instead announces `Pinned Tab unavailable: control returned to the active browser tab` before the active-target details. It is not announced as a button or tab picker. |
| Gesture map | Gesture row | Each row exposes the Gesture name, Media Key hint, Keyboard Chord or `Unassigned`, Binding Label when supplied, and profile source. Rows are navigable content, not unlabeled clickable cards. |
| Gesture map | Test | `Test <Gesture> binding on <Profile Setup Target title>, <main domain>`. It is disabled with an explanatory tooltip and accessible description when no Profile Setup Target is available. It must state that it ignores the Pinned Tab. |
| Profile context | Quick Profile Setup | `Quick Profile Setup for focused browser tab`. It appears beside the active profile on Control and as a secondary action on Profiles. It opens or proposes the Site Profile for the Profile Setup Target without changing the Pinned Tab. |
| Profile context | Manage profiles | `Manage saved Site Profiles`. |
| Profile context | Active profile summary | A non-interactive summary announces either `Generic Profile: used for sites without a Site Profile` or `Site Profile: <main domain>: used for this domain and its subdomains`. |
| Profiles page | Profile list | `Saved Site Profiles`. Generic Profile is first, followed by saved main domains. `Up` and `Down` move selection, the selected profile is exposed as selected, and `Enter` or `Space` opens the selected profile editor. |
| Profile editor | Profile Setup Target banner | A persistent, non-interactive banner announces `Profile Setup Target: <title>, <main domain>. Test sends directly to this focused page and ignores the Pinned Tab.` |
| Profile editor | Binding Label | `<Gesture> Binding Label`. Blank is valid and is announced as `No label`. |
| Profile editor | Keyboard Chord | `<Gesture> Keyboard Chord`, read-only. It announces the captured chord or `Unassigned`; it is not presented as editable text. |
| Profile editor | Capture | `Capture <Gesture> Keyboard Chord`. While capture is active, instructions identify `Escape` as cancel and exclude ordered sequences and text entry. |
| Profile editor | Clear | `Clear <Gesture> binding`. It leaves the binding `Unassigned`. |
| Profile editor | Test | Same target-specific name as the Gesture map Test action. |
| Profile management | Open, Reset to Generic, Delete | `Open Site Profile: <main domain>`, `Reset Site Profile <main domain> to Generic Profile`, and `Delete Site Profile: <main domain>`. Reset and delete require named confirmations describing all affected bindings and the Generic Profile fallback. The confirmation buttons are named `Reset Site Profile`, `Delete Site Profile`, and `Cancel`; `Cancel` receives initial focus, and `Escape` dismisses the confirmation. |
| Input & timing | Media Key capture | `Capture Media Key`. The current Phantom Key is announced before activation. `Escape` cancels capture. |
| Input & timing | Hold Threshold, Press Sequence Window, Debounce | Each spin control includes its unit in the accessible name and announces its current value. `Up` and `Down` adjust its value. Do not retain the obsolete `Double-click window` terminology. |
| Advanced | Theme preference | `Theme preference` with `System`, `Light`, and `Dark` options. The selected option is exposed as selected, and `Up` and `Down` change it through the native combobox behavior. |
| Advanced | Accent override | `Accent color override`. Its current swatch has a textual color name or value, and the native color picker is keyboard operable. `Use Windows accent color` clears the override. |
| Advanced | Browser and Chromium Profile setup | The selectors are named `Browser` and `Chromium Profile`; `Up` and `Down` change their native combobox selections. The port spin control is named `CDP port` and announces its value. |
| Advanced | Browse browser executable | `Browse for browser executable`. It opens a native file picker with `Browser executable` as its accessible dialog name. |
| Advanced | Automatic browser launch | `Launch browser automatically if CDP is not available`. Its checked state is exposed; `Space` changes it. Its warning text remains associated with the checkbox. |
| Advanced | Launch or restart browser | `Restart <browser> with CDP enabled`. It is never the default action. Confirmation names the browser, warns that existing browser windows will close, and offers `Restart browser` and `Cancel`. |
| Window actions | Save, Cancel, Close | Each has its visible label as its accessible name. `Escape` closes a modal editor without saving. Saving returns focus to the invoking control and announces the resulting status. If exiting with unsaved work requires confirmation, its buttons are named `Exit without saving` and `Cancel`, with initial focus on `Cancel`. |
| Tray activation | Open Control Deck | A primary tray activation opens the Control Deck. The tray tooltip identifies GamerScroll plus its current textual state. |
| Tray keyboard navigation | Tray menu | When the native tray menu has focus, `Up` and `Down` move through enabled items, `Enter` or `Space` activates the focused item, and `Escape` closes the menu. Standard Windows access to the notification area remains responsible for reaching the tray icon; GamerScroll does not replace it with a custom flyout. |
| Tray menu | Enable or Disable | The action is named `Enable GamerScroll` when disabled and `Disable GamerScroll` when listening. The menu never uses `Pause`. |
| Tray menu | Launch Browser | `Launch browser with CDP enabled`. If it would close browser windows, it opens the same named confirmation used by Advanced. |
| Tray menu | Settings | `Open GamerScroll settings`. |
| Tray menu | Exit | `Exit GamerScroll`. It asks for confirmation only if an unfinished, unsaved editor is open. |

## Theme And Contrast Contract

| Mode | Required behavior |
| --- | --- |
| System | The default preference. Follows the Windows application light/dark preference. Changes apply without hiding status, focus, or hierarchy. |
| Light | Uses the Gaming Companion light neutrals: canvas `#F3F3F3`, surface `#FFFFFF`, subtle surface `#F8F8F8`, divider `#DEDEDE`, primary text `#242424`, and secondary text `#707070`. |
| Dark | Uses the Gaming Companion dark neutrals: canvas `#1E1E23`, surface `#25252B`, subtle surface `#2D2D34`, divider `#42424B`, primary text `#F4F4F6`, and secondary text `#B8B8C0`. |
| Windows contrast theme | Defers all essential foreground, background, selection, and focus colors to the active Windows contrast palette. Do not force custom canvas, graphite, accent, semantic-color, or disabled-opacity values that obscure system colors. Borders, icons, and the Gesture Wheel use current foreground/background colors. |

- Body text, labels, Keyboard Chords, status text, and essential iconography meet WCAG 2.1 AA: 4.5:1 for normal text and 3:1 for large text and essential non-text visual indicators. Disabled controls may be visually subdued only when their disabled state remains legible and programmatically exposed.
- Light secondary text `#707070` is not used directly on the light canvas `#F3F3F3`, where it does not meet the 4.5:1 normal-text threshold. Place it on white surface `#FFFFFF` or use an accessible stronger foreground for text on the canvas.
- The Windows accent is reserved for active navigation, selected controls, primary actions, and focus. It never solely conveys readiness, warning, error, Pinned Tab state, or disabled state.
- An in-app accent override is optional and must meet the required contrast for every text, focus, and essential-control pairing before use. Windows contrast themes ignore both the Windows accent and the in-app override in favor of the system contrast palette.
- Semantic ready, warning, and error treatments preserve an icon and explicit label in Light and Dark. In Windows contrast themes, the label and icon remain while their colors come from the system palette.
- The tray icon has a dedicated monochrome **Gesture Wheel** variant. At 16 px it uses a one-color foreground and transparent or system background, retains the wheel/notched-input silhouette, and contains no text, color-dependent meaning, caret, controller, weapon, or media-play glyph. One Gesture Wheel source design is exported in `assets/icon.ico` at 16, 20, 24, 32, 48, and 256 px, has a graphite application-icon variant, and is also used by the runtime fallback.

## DPI And Text-Scaling Validation

Validate the Control Deck at 100%, 150%, 200%, and 300% Windows text scaling, plus 100%, 150%, 200%, and 300% display scaling where supported. Validate both a typical desktop window and a 320 effective-pixel-wide Control Deck, the narrowest supported width.

- No text, focus outline, icon, status label, Keyboard Chord, or action is clipped, overlaps, or becomes unreachable. Horizontal scrolling is permitted only within an intentionally scrollable code or tab-strip region; the main window does not require horizontal scrolling.
- The readiness strip remains first. Its icon, status label, explanation, and one contextual recovery action can wrap vertically rather than truncate.
- The Control target remains immediately after readiness. Its target mode, tab title, main domain, browser, Chromium Profile, and Pin or Unpin action remain associated and readable. Long tab titles truncate only after the full title is exposed through an accessible description or tooltip.
- The Gesture map remains after the Control target. At narrow widths or large text it reflows each row into a labeled vertical unit while preserving Gesture, chord or `Unassigned`, Binding Label, profile source, then Test. Column headers do not disappear unless equivalent per-row labels are visible to sighted and assistive-technology users.
- Site Profile context and secondary actions follow the Gesture map. Actions wrap without changing their meanings or moving ahead of the readiness, Control target, or Gesture map sections.
- Icon-only affordances are not introduced as a density response. Touch and pointer targets remain at least 32 x 32 device-independent pixels, and focused controls remain wholly visible after automatic scrolling.
- The tray menu uses native menu scaling and does not substitute an image-only flyout. The monochrome Gesture Wheel remains distinguishable at every notification-area icon size Windows selects.

## Validation Evidence

For each supported theme and scaling combination, capture the following evidence before release:

1. Keyboard traversal from window entry through the final Control Deck action and back, including visible focus, disabled controls, a modal confirmation, and return focus.
2. A screen-reader or Windows accessibility-inspection pass that verifies the names and states in the Keyboard And Accessible Names table, including the current readiness state, target mode, each Gesture row, and all tray menu actions.
3. Screenshots of loading, empty setup, ready, disabled, Browser unavailable (CDP), and missing-Pinned-Tab states that show an icon, plain-language label, and contextual recovery action without relying on color. Browser unavailable says that Gesture Bindings cannot be delivered and offers only `Reconnect browser`; the missing-Pinned-Tab state appears in both readiness and Control target, states that control returned to the active browser tab, and offers only `Pin Current Tab`.
4. Contrast measurements for every token pairing used by text and essential controls in Light and Dark, plus a Windows contrast-theme screenshot proving that system colors override custom theme colors.
5. Screenshots at every required text and display scaling level showing readiness, Control target, and Gesture map in that order, with no clipping or overlapping controls.
6. Notification-area checks of the monochrome Gesture Wheel at 16, 20, 24, 32, and 48 px against light, dark, and Windows contrast backgrounds, plus the 256 px graphite application-icon variant and the runtime fallback.
7. Generic Profile and Site Profile screenshots and accessibility-inspection output proving that the profile type, Site Profile main-domain scope, and per-row profile source are available without color or visual inference.

This contract is an input to the [GamerScroll redesign specification](../0007-write-gamerscroll-redesign-specification.md).
