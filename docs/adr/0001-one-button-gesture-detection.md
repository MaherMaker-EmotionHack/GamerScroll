# One phantom key with gesture detection instead of multiple keys

GamerScroll uses a single phantom key (F13) with three gestures (short press, double press, long hold) to control three media actions, instead of binding three separate phantom keys (F13/F14/F15) to three buttons.

**Considered options:**
- **Multiple keys** — one key per action, zero latency, but requires 3 G HUB macros and 3 mouse buttons (or modifier+key combos).
- **Multi-click** — one key, click-count disambiguation, but every action has latency (wait to see if more clicks come).
- **Click + hold duration** (chosen) — one key, short press is instant, double press and long hold have acceptable latency.

**Why chosen:** The user has one spare mouse button. Short press (the most frequent action — pause/play) fires with only the double-click-window delay (~300ms). Long hold fires at the threshold mark (~500ms) for immediate feedback. This minimizes G HUB setup (one macro) while keeping the primary action responsive.

**Consequences:** Double press and long hold have inherent latency that can't be eliminated. The timing thresholds are configurable in the UI to tune the feel.