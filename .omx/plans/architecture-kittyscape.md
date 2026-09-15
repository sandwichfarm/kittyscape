# Kittyscape: architecture and decisions

Status: proposed. All source paths below are future targets.
Related: [requirements](prd-kittyscape.md), [compatibility](compatibility-kittyscape.md), [research](research-kittyscape.md).

## Decision: prefer one kitty-side implementation, gated by proof

Start with a small Python watcher installed through kitty’s documented watcher mechanism.
Keep rules and state independent of the shell. Use documented watcher callbacks and remote-control operations
where possible. Keep any necessary kitty-internal access confined to one compatibility module.
Kitty explicitly warns that its internals are unstable; the watcher is a candidate architecture, not a compatibility guarantee.

| Option | Benefits | Costs and decision |
| --- | --- | --- |
| Kitty watcher using existing shell integration | One installation; focus events; no per-prompt subprocess | Preferred if directory freshness and restoration can be proven on the target matrix. |
| Shared Python core plus thin shell reporting adapters | Explicit event contract; broader shell coverage | Fallback for missing native events; adapters report state only and never duplicate rule logic. |
| External polling controller | Can inspect some local process directories without prompt integration | Deferred opt-in fallback; process identity, SSH, latency, permissions, and idle cost complicate correctness. |

Do not ship all three mechanisms initially. Experiment first, select the smallest reliable combination,
and document the decision before implementing the production transport.

## Proposed boundaries

| Future path | Responsibility |
| --- | --- |
| kittyscape/watcher.py | Lifecycle, focus, and command callbacks; schedule a bounded update. |
| kittyscape/compat.py | Capability detection, trustworthy directory lookup, scoped control, and baseline access. |
| kittyscape/rules.py | Pure path normalization and deterministic directory-to-image selection. |
| kittyscape/config.py | Read and validate user-owned configuration; retain last valid rules on reload failure. |
| kittyscape/state.py | Per-pane reported directory and per-OS-window image ownership. |
| kittyscape/diagnostics.py | Bounded warnings and explicit, privacy-conscious diagnostic output. |
| integrations/ | Only the shell adapters proven necessary by the experiment. |
| tests/ | Rule tests, event ordering tests, install tests, and real kitty scenarios. |
| docs/ | One VitePress source tree for landing page and documentation. |

These are responsibility boundaries, not a requirement to create seven abstractions or classes.
Combine small modules if doing so leaves the compatibility boundary clear.

## Event flow

1. Identify the source pane and its OS window; record directory reports without changing other windows.
2. Validate report origin, locality, and encoding; distinguish unknown state from a valid unmatched directory.
3. Coalesce command and focus events; check the newest valid state after the shell’s directory report settles.
4. Recheck that the pane is active in the selected tab immediately before applying an image.
5. Select the longest directory-root match or the fallback and verify the local image is usable.
6. Apply only when the selected image/context differs from the last successful application.
7. Record success, not attempted success; discard stale completions after focus or generation changes.

Kitty documents command and focus callbacks, but not a dedicated directory-change callback.
Do not assume command completion implies the new directory has already been reported.
The experiment must establish event ordering and a bounded deferred update, or select a reporting adapter.
Never block kitty’s UI callback with filesystem walks, image conversion, network I/O, or shell subprocesses.

## Directory semantics

- Rules use explicit directory roots, so discovering Git repositories is unnecessary in version 1.
- A shell report is authoritative for shell-directory semantics; a foreground program’s cwd is not a silent substitute.
- Builtin directory changes, push/pop directory stacks, shell nesting, and startup all require fixtures.
- Physical-path normalization must respect the actual filesystem’s case behavior, not lowercase every path.
- A disappearing directory yields a diagnostic and fallback; never accidentally match a similarly named sibling.
- Parse remote location reports as structured host/path information; never treat their paths as local files.
- Noninteractive processes and unsupported multiplexers have explicit fallback behavior.

## Configuration contract

Proposed location: kitty’s active configuration directory, in a Kittyscape-owned data file.
Respect custom kitty configuration locations rather than assuming ~/.config/kitty.
Prefer a small JSON document to avoid another parser dependency or an unnecessary Python-version floor.

Planned fields: schema version, directory/image rules, optional fallback image, and enabled state.
Validation rejects unknown fields, duplicate normalized roots, relative directory roots, invalid types,
and unsupported schema versions with actionable locations. Configuration is data only.
Expand a leading home shortcut in documented path fields, but never interpolate commands or arbitrary environment expressions.
Use an explicit reload action; automatic config watching is unnecessary for version 1.
Malformed reloads retain the last valid configuration and report one error per failing revision.

## Image ownership and baseline restoration

Capture each OS window’s effective original image before its first Kittyscape change, including absence of an image.
Capture effective layout and other relevant rendering state for comparison, without modifying it.
Do not confuse the current displayed image with a configured glob or a default shared by future windows.
Never use “none” as a universal reset: it removes an image and does not restore an earlier one.

Restoration is a release-blocking experiment. Verify how the supported kitty versions expose the effective baseline,
especially multi-image selections, per-window overrides, automatic light/dark themes, and configuration reloads.
If baseline recovery is not reliable, narrow the supported configuration profiles and require an explicit fallback
for those cases; clearly mark that this does not satisfy full automatic restoration support.

State tracks baseline, desired image, last successful image, generation, enabled/paused state, and ownership.
Plan explicit status, reload, pause, resume, and restore actions, exposed through the mechanism chosen in the experiment.
Command names and installation syntax are not yet a public API.

For external background changes, pause Kittyscape on detected ownership loss.
For kitty configuration/theme reloads, invalidate stale rendering caches and recapture the intended new baseline
before resuming only when ownership can be established. If changes cannot be detected reliably, document the
required pause/change/resume workflow and list concurrent background writers as unsupported.
Do not implement endless contention with another tool.

## Installation and dependencies

Prefer a user-local, versioned bundle of Python files loaded by kitty and one documented configuration entry.
First prove module loading on both Linux and macOS; do not assume kitty’s embedded Python behaves like system Python.
No pip, Node, shell framework, image server, or service manager should be required for the normal runtime path.

An eventual setup helper must provide preview, backup, apply, verify, and rollback, with idempotent repetition.
It must handle spaces, symlinked configurations, includes, and custom config directories without overwriting user files.
Manual installation and removal remain documented alternatives. Never enable unrestricted remote control as a default.
Adapter authorization must be limited to the necessary operation and target; validate the exact mechanism first.

## Failure and privacy boundaries

- Read images only from user-configured local paths; reject remote URLs and executable providers.
- Apply bounded file-size and decoded-dimension checks supported by the chosen integration; establish limits experimentally.
- Invalid images cannot crash the watcher or create infinite retry loops.
- Default logs omit directory names, usernames, image paths, and command lines; debug disclosure is explicit.
- No persistent per-directory history, background network requests, analytics, or remote-control TCP listener.
- Closing a pane/window releases its state; repeated errors are deduplicated and recover after valid input changes.

## Rejected expansion

No database, daemon by default, plugin marketplace, general event bus, recursive repository scanning,
or duplicated rules engines. The first release has one resolver and the minimum event integrations needed.

## Decisions still requiring evidence

Native event reliability, exact support floors, baseline recovery, reload/ownership detection, image limits,
adapter authorization, and distribution packaging must be resolved in roadmap slice 1.
Document the selected options and rejected alternatives with test evidence before downstream work starts.
