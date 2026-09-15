# Kittyscape: test specification

Status: planned tests, none executed. Related: [requirements](prd-kittyscape.md), [matrix](compatibility-kittyscape.md).

## Evidence levels

1. Pure tests prove matching, validation, and state transitions.
2. Shell/process integration tests prove reporting and hook preservation.
3. Actual kitty graphical runs prove image scope, rendering preservation, and restoration.
4. Artifact installation and browser checks prove usable distribution and documentation.

Mocks cannot satisfy graphical-runtime acceptance. A Linux run cannot satisfy macOS acceptance.
Use isolated kitty configurations and temporary directories; never modify the daily-use terminal to run these tests.

## Required scenarios

| Test | Scenario and pass condition | Requirements |
| --- | --- | --- |
| T01 | Enter rule A, enter descendant, enter deeper rule B, leave both; exact expected image/fallback sequence. | R01, R03 |
| T02 | Run T01 with each baseline shell/platform/version row; record identical selection behavior. | R02, R15 |
| T03 | Prefix collisions, Unicode, whitespace, quotes, symlinks, filesystem case behavior, deleted cwd; documented outcomes. | R03, R10 |
| T04 | Two tabs and split panes with different directories; only selected-tab active pane controls its OS window. | R04 |
| T05 | Two OS windows including one unfocused; events and failures stay scoped to the right window. | R05 |
| T06 | Rapid alternating directory/focus events; stale completions never restore an older image. | R04, R11 |
| T07 | Nondefault layout, interpolation, tint, gap tint, opacity, colors; before/after runtime values and files match. | R06 |
| T08 | No-image and single-image baseline; switch, pause, disable, uninstall; original appearance returns. | R07, R09 |
| T09 | Configured image list, runtime-selected index, theme switch, per-window override, config reload; restore correct baseline or explicitly reject unsupported profile before activation. | R07, R08 |
| T10 | Invalid image, oversized image, unreadable file, disconnected control, malformed config; preserve shell usability and bounded diagnostics. | R08, R10 |
| T11 | Disabled reports, missing integration, nested shell, SSH, container, multiplexer; exact supported/degraded/unsupported behavior. | R02, R08 |
| T12 | Custom config root, symlink/include config, pre-existing files, repeated setup/removal; owned changes only, byte/metadata preservation. | R09 |
| T13 | External image writer and manual theme change; no fight loop, documented ownership/reload behavior. | R06, R07 |
| T14 | Repeated unchanged prompts; zero extra image uploads, no per-prompt helper process, bounded state after closing windows. | R11 |
| T15 | Follow docs from a clean supported environment using packaged artifacts; installation through removal works exactly as written. | R12, R15 |
| T16 | Root/subpath website builds, all links and search; correct destinations with no missing assets or console errors. | R13 |
| T17 | Light/dark, widths 320/768/1440, keyboard, 200% zoom, reduced motion, screen-reader structure across target browsers. | R14 |

T09 rejection is an honest compatibility outcome, not a pass for broad automatic restoration.
The release support table must exclude that profile until its positive scenario passes.

## Unit and state testing

Use table-driven fixtures for the resolver, configuration validation, and event state transitions.
Generate adversarial path inputs using available tools; add a property-testing dependency only if approved later.
Assert locality, deterministic longest match, duplicate rejection, and no executable evaluation.
Use fake event schedules to exercise startup, closure, failed apply, retry after input change, and lost ownership.
Verify tests fail under deliberate changes to path-boundary checks and active-pane guards, then restore the implementation.

## Real runtime proof

For every supported row, record OS/architecture/display backend, kitty/shell versions, configuration profile,
artifact identity, scenario IDs, timestamps, and results. Store sanitized logs and screenshots with that record.
Use distinctive licensed test images to identify backgrounds visually and compare configured rendering settings directly.
Measure event-to-display timing separately from resolver timing and image decoding/upload time.
Record hardware and fixture dimensions; do not infer performance from mocked timers.

Performance targets: resolver p95 <10 ms at 1,000 rules; warm local 1080p event-to-display p95 <250 ms.
Run at least 100 measured transitions after warmup. Idle test: 60 seconds with no directory/focus/config changes
produces no image uploads and no Kittyscape-originated polling in the preferred mode.

## Installation preservation proof

Capture file bytes, symlink targets, permissions, and owned-path inventory before setup.
Preview must write nothing to user configuration. Repeated apply must not duplicate entries.
Removal must preserve unrelated edits made after installation and recover the original appearance where owned.
An unreadable or invalid backup must stop destructive replacement and report the affected path.
No root permissions, shell replacement, terminal restart, or global package update may be an implicit test prerequisite.

## Site proof

Use the existing available browser tooling during implementation; do not install browsers without checking availability.
Run production build and link validation, then serve the artifact under both / and a non-root prefix.
Check essential reading/navigation with JavaScript disabled; local search may require JavaScript.
Assert no third-party runtime requests. Automated accessibility checks complement manual keyboard and screen-reader review.
Screenshots prove the specified visual layout, not terminal runtime behavior.

## Release gate

All claimed support rows and applicable T01–T17 cases must pass against the release artifact.
Static analysis, formatting/lint, typing where applicable, unit/integration tests, runtime evidence,
installation roundtrip, and docs build must be current. Record skipped checks with reasons and restrict claims accordingly.

## Current planning verification

This task validates only Markdown inventory, internal document links, required sections, and absence of implementation files.
It does not run runtime tests, install tooling, build a website, or assert product compatibility.
