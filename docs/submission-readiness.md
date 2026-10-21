# Project submission readiness

## Project identity

- Project: **GamerScroll**.
- Repository: https://github.com/MaherMaker-EmotionHack/GamerScroll
- Relationship: creator and sole personal owner, as confirmed by the owner on
  2026-10-22. The owner also confirmed that `MaherTheMaker` and
  `MaherMaker-EmotionHack` are their accounts.
- License for original project material: **GNU GPL version 3 only (GPL-3.0-only)**.
- Planned work: the pending 26–38 hour CLI phase in [ROADMAP.md](../ROADMAP.md).

Draft project description for the owner to adapt into their own words:

> GamerScroll is a Windows desktop utility that lets gamers control media in a
> background Chromium tab without leaving a fullscreen game. It is written in
> Python with PyQt6 and uses Chrome DevTools Protocol for page-level keyboard
> controls. I plan to expose the existing controls through a headless CLI with
> structured output, shared tray-session state, and dependable automated tests.

## Repository preparation

- Root LICENSE and NOTICE define the chosen license; README and package metadata
  agree with that choice.
- README documents the audience, stack, Windows prerequisites, setup, and checks.
- ROADMAP distinguishes existing features from pending CLI work and later MCP/UI ideas.
- Existing commits are retained; this preparation adds normal commits to the original
  repository rather than replacing its history.
- Secret scanning runs over full fetched history in CI. Keep real browser profiles,
  credentials, logs, and other people's data out of commits and test recordings.

## Recorded scan

On 2026-10-22, Gitleaks **8.30.1**, using its default rules and full redaction, scanned
all **23 commits** reachable from the fetched original repository refs at
`65485a333db4f1258e775dcf1b8b0e36a422a585` and reported **no findings**.

```text
gitleaks git --redact=100 --log-opts="--all" --no-banner .
```

The tool's official archive checksum was verified before execution. This result is
a bounded automated check, not proof that every secret or personal datum is absent.
Rescan the final submitted revision and inspect any sample files/recordings manually.
If a credential is found, revoke it and remove it from history before submission;
preserve normal history otherwise.

## Before submitting the form

- [ ] Merge the repository-preparation changes and confirm GitHub detects the license
      on the default branch; the form must match it.
- [ ] Confirm the personal ownership statement also covers the absence of employer,
      client, school, NDA, or company claims and use of their resources.
- [ ] Confirm the roadmap reflects work the owner really intends to undertake.
- [ ] Review repository data and shared artifacts, then check the final revision's
      secret-scan result.
- [ ] Submit the original repository URL and the owner's actual account/role details.
      Do not invent users, releases, deployments, merged PRs, or contribution history.
- [ ] Request the program's **extra approval for GPLv3**, as required by its supplied
      project instructions. Wait for that approval and the selected-project terms
      and setup before starting paid project sessions.

The program excludes projects processing other people's personal or regulated data.
Keep this phase limited to local media controls and fictional development fixtures;
confirm eligibility with the organizers if actual data flows or scope are uncertain.
A CLI/MCP roadmap does not by itself establish program approval.

Repository preparation does not submit the application, sign contributor terms, or
certify acceptance. Binary redistribution has a separate checklist in
[THIRD_PARTY_NOTICES.md](../THIRD_PARTY_NOTICES.md).
