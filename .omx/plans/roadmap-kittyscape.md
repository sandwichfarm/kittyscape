# Kittyscape: implementation roadmap

Status: future work only. Do not execute this roadmap without a later implementation request.

## Order and dependencies

Start with capability experiments and guardrails. Runtime delivery follows the experiment results.
Website design can proceed independently after product terminology is stable, but installation documentation
and compatibility claims depend on proven runtime behavior.

## Slice 1: compatibility and restoration experiment

Future artifacts: docs/development/compatibility-findings.md, tests/runtime/, temporary isolated kitty fixtures.

- Establish formatting, static checks, test discovery, and a baseline failure fixture before production edits.
- Inspect exact stable kitty APIs and choose candidate minimum/current versions and shell releases.
- In disposable kitty instances, observe startup, directory reporting, command completion, and focus ordering.
- Prove reading/restoring effective image defaults, no-image state, per-window overrides, themes, and reloads.
- Prove watcher module imports in kitty’s embedded Python on Linux and macOS.
- Select native watcher or a minimal adapter combination and document the evidence and rejected alternatives.

Exit: a reproducible capability matrix and architecture decision. Missing target environments are explicit blockers
to support claims. No production installation or user configuration changes are required for the experiment.

## Slice 2: deterministic rules and configuration

Future paths: kittyscape/rules.py, kittyscape/config.py, tests/unit/.

- Implement data-only central rules, longest-root matching, normalization, fallback selection, and validation.
- Add red/green tests for nested paths, Unicode, sibling prefixes, symlinks, duplicates, and malformed inputs.
- Add last-valid-configuration behavior for reload errors.

Exit: R01 and R03 resolver cases pass; no terminal dependency in pure selection tests.
Do not claim visible image switching until slice 3 passes in real kitty.

## Slice 3: one real shell-to-image vertical slice

Future paths: kittyscape/watcher.py, kittyscape/compat.py, kittyscape/state.py, tests/runtime/.

- Integrate one baseline shell on one isolated graphical target using the selected transport.
- Implement startup, active-pane selection, scoped image updates, coalescing, success tracking, and restoration.
- Retain layout/tint/opacity and verify no configuration file writes.
- Handle invalid images and stale events without interrupting the terminal.

Exit: R01, R04–R07, R10–R11 pass in the selected real runtime, including two OS windows.

## Slice 4: portable shell and platform coverage

Future paths: integrations/ only when needed, kittyscape/compat.py, tests/shells/, tests/runtime/.

- Expand the same resolver and event contract to Bash, Zsh, and Fish on the baseline platform matrix.
- Test shell startup variants, OS-provided macOS Bash, prompt tools, and nested shells.
- Add capability diagnostics and explicit unsupported-context behavior.
- Evaluate Nushell as an additional-shell experiment; do not delay baseline reliability to advertise untested breadth.

Exit: R02, R08, R15 pass for the published support set, with exact versions recorded.
No Linux-only process lookup may silently replace the portable baseline contract.

## Slice 5: reversible setup and lifecycle

Future paths: packaging/, kittyscape/diagnostics.py, tests/installation/, lifecycle portions of kittyscape/.

- Package the chosen user-local installation layout and document manual setup.
- Provide preview/backup/apply/verify/rollback if a setup helper is justified; no root requirement.
- Implement status, explicit config reload, pause, resume, restore, and ownership conflict handling.
- Test custom config directories, includes, symlinks, pre-existing files, and repeated install/uninstall.
- Preserve diagnostics privacy and bound errors/cache/state.

Exit: R06–R10 pass for the shipped installation method and supported configuration profiles.

## Slice 6: VitePress landing page and complete docs

Future paths: docs/, docs/.vitepress/, docs/public/, website tooling manifest and lockfile.

- Build one VitePress site following the [site specification](site-kittyscape.md).
- Create the original cat illustration and static terminal scene with recorded asset provenance.
- Write tested installation, rules, shell, compatibility, lifecycle, troubleshooting, and contributor documentation.
- Run site build, local search, navigation, base-path, accessibility, browser, and responsive checks.

Exit: R12–R14 pass; all advertised support is backed by slice 4 evidence.

## Slice 7: release qualification and delivery preparation

Future paths: release checklist, versioned compatibility evidence, package manifest, changelog, CI workflows.

- Run the full [test specification](test-spec-kittyscape.md) against the release artifact.
- Validate lint, type/static checks, unit/integration/runtime suites, docs build, and artifact contents.
- Test installation and removal from the packaged artifact, not only from the checkout.
- Choose a license and verify third-party asset/dependency obligations before publishing.
- Choose repository owner, release channel, and static host; prepare release and deployment artifacts for review.
- After publication is separately authorized, verify downloadable checksums, clean installation, and live docs links.

Exit: release-ready local artifacts and documented evidence. Publication is not implied by this planning request.
Call delivery complete only after any subsequently requested release/deployment is verified live.

## Risk controls

| Risk | Control |
| --- | --- |
| Kitty internal API drift | Isolate access; capability probes; minimum/current runtime matrix. |
| Shell report timing errors | Record event order; bounded deferred application or explicit adapters. |
| Wrong tab/window background | Per-OS-window state and active-pane recheck before each application. |
| Default loss on disable/reload | Release-blocking baseline and ownership experiments. |
| Cross-shell marketing exceeds evidence | Support labels and release-specific matrix. |
| Installer damages user settings | Preview, backups, ownership tracking, idempotency, rollback tests. |
| Website scope expansion | One VitePress site, one illustration, three benefits, docs-first navigation. |

## Verification and handoff

Each slice must leave test evidence and its remaining gaps. Independent website work may use a separate contributor,
but runtime compatibility decisions and final integration have one owner. No required gate may be replaced by an
unrelated local green test. The plans are complete when coherent and reviewable; the product remains unimplemented.
