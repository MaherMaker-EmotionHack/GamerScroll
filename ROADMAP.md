# GamerScroll roadmap

## Current behavior and next goal

GamerScroll currently ships a Windows Python/PyQt6 tray application with one Media
Key, three Gestures, Generic and Site Profiles, session-only Pinned Tabs, and CDP
page-input dispatch. `python -m gamerscroll` starts that application; its current
command-line flags configure logging. There is no headless control CLI or MCP server.

The next goal is to expose the same local media-control services through a headless
CLI, so people and agents can inspect state and invoke the existing controls without
opening Settings or synthesizing global keystrokes. The tray application stays usable
throughout the work. The CLI controls ordinary application functionality; this phase
adds no model training, evaluation, inference service, or ML infrastructure.

## Planned work

All milestones below are pending. Estimates are planning ranges, not completed hours.
The total is **26–38 hours**, excluding a later MCP adapter and UI rewrites.

### 1. Separate the application core — 5–7 hours

- Extract application services and structured command results from the Qt composition
  root; reuse MediaController, Config, and the CDP transport.
- Load Qt, global Media Key listeners, registry, and startup services only for their
  respective desktop commands.
- Preserve the existing tray entry point and current profile/target behavior.

Acceptance: injected fake browser/config adapters can exercise the core without a
QApplication, global key hooks, registry writes, or browser launch. Existing Windows
behavior tests still pass.

### 2. Add a headless CLI — 7–10 hours

- Add an installed console entry point, command help, and argument validation.
- Implement status, target discovery, explicit-target Gesture dispatch, and profile
  inspection/editing through the shared services.
- Support JSON results on stdout, diagnostics on stderr, stable error codes, and
  bounded completion. Document a proposed result envelope before implementing it.
- Distinguish unassigned bindings, rejected input, CDP dispatch, and page behavior.

Proposed commands, **not available yet**:

```text
gamerscroll status --json
gamerscroll targets list --json
gamerscroll gesture short-press --target <id> --json
gamerscroll profiles list --json
```

Acceptance: process-level tests check stdout JSON, stderr, exit status, validation,
timeouts, and profile persistence against deterministic fake/local browser targets.
One-shot commands neither create tray windows nor register startup/global key hooks.

### 3. Share the running tray session — 5–8 hours

- Add a Windows local IPC adapter restricted to the current user, with a versioned,
  bounded request/response protocol for the shared application services.
- Use the running application's Pinned Tab, Disabled state, and configuration when
  connected; report standalone mode explicitly when the tray app is absent.
- Keep pins session-only. Serialize shared state changes and write configuration
  atomically so simultaneous tray/CLI operations cannot corrupt settings.

Acceptance: integration tests cover tray present/absent, concurrent requests,
unauthorized/malformed requests, application restart, pin loss, and config writes.
Separate CLI invocations can use a pin owned by the running tray session.

### 4. Make browser dispatch dependable — 5–7 hours

- Match CDP response IDs, inspect protocol errors, and apply explicit connection and
  response deadlines. A received message alone is not proof of dispatch success.
- Make target selection explicit for agent commands; an unavailable explicit target
  fails rather than redirecting an action to an unrelated tab.
- Preserve the established tray fallback policy separately from explicit CLI targets.
- Avoid blindly retrying commands with uncertain outcomes: repeating pause/play can
  undo a successful first dispatch. Report uncertainty for caller handling.
- Keep browser control local. Status must be read-only; browser termination/relaunch
  requires an explicit command and confirmation/opt-in for noninteractive callers.

Acceptance: tests cover error replies, mismatched IDs, slow responses, disappearing
targets, ambiguous delivery, and a fullscreen application retaining foreground focus.
Results claim dispatch only, unless page-specific outcome verification exists.

### 5. Package, document, and validate — 4–6 hours

- Publish reproducible Windows install/run instructions for the CLI and tray app.
- Add synthetic local media/test pages and CLI/core/IPC checks to Windows CI.
- Review diagnostic redaction, dependency notices, and binary/source distribution.
- Record a manual Windows check using a dedicated browser profile and fictional pages.

Acceptance: a clean Windows environment can install and run the documented commands;
CI and manual validation cover the published behavior. License notices accompany
redistributed artifacts, and source corresponds to the built revision.

## Existing UI proposals

[Issue #18](https://github.com/MaherMaker-EmotionHack/GamerScroll/issues/18) describes
a Python Control Deck redesign; [issue #19](https://github.com/MaherMaker-EmotionHack/GamerScroll/issues/19)
describes a WPF visual-shell alternative. Both remain proposals outside this CLI
phase. Choose one UI direction before starting a rewrite; their visual and framework
decisions are not simultaneous requirements. No UI issue is represented as completed.

Before copying AmpUp source, fonts, icons, or other assets, record the exact upstream
revision and applicable redistribution license or written permission, including
required attribution. The existing issue's permission statement alone is not a
third-party license inventory. Use GamerScroll-original assets until that evidence
is available in the repository.

## Later possibilities

An MCP adapter may map a small set of typed tools onto the same application services
after the CLI contracts stabilize. Specify its scope and confirm any project-program
eligibility questions before adding it. The browser-extension relay remains shelved.
