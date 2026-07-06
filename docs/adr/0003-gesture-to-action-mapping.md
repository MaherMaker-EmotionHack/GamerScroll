# Gesture-to-action mapping: short=pause, double=next, long=prev

Short Press maps to Pause/Play, Double Press maps to Next, Long Hold maps to Prev.

**Considered options:**
- **Short=next, double=prev, long=pause** — next is instant, but pause (the most frequent action) has 500ms latency.
- **Short=pause, double=next, long=prev** (chosen) — most frequent action is fastest; "hold to go back" has a natural rewind metaphor.
- **Short=pause, double=prev, long=next** — "hold to fast-forward" metaphor, but prev gets the faster double-press.

**Why chosen:** Pause/Play is the most frequent action during media consumption and should have the lowest latency. Next is second most frequent and tolerates the ~300ms double-press window. Prev is least frequent and benefits from the deliberate long-hold gesture — accidentally going back is more annoying than accidentally going forward.

**Consequences:** This is a muscle-memory decision. The mapping is not user-configurable in the UI (only timing thresholds are) to prevent accidental remapping that would break learned reflexes.