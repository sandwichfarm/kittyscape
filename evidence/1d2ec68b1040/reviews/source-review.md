# Kittyscape final cleanup and acceptance audit

Reviewed 2026-09-15T13:58:56.945462+00:00. Read-only source review; no GUI launches.

## Verdict

**Architecture: CLEAR for the current bounded implementation. Delivery qualification: incomplete.**
The six original preservation/recovery findings and the unbounded executor backlog are resolved. The new native timer
lifetime workaround is correctly confined to compatibility code, preserves one-shot semantics, and coalesces one timer
per OS window. No architectural redesign or unrelated cleanup is warranted.

Do not count the final 96-row installed-artifact matrix, advanced runtime reruns, final performance/idle run, or final
site/browser reruns as passed until their authoritative results exist. macOS arm64 remains explicitly open per the user.

## Concrete findings from this pass

### Resolved before the artifact cut

1. **Source bundle omitted the VitePress theme entry.** `packaging/builder.py:33` now includes `.js`; read-only archive
   inventory confirms `docs/.vitepress/theme/index.js` is present. This retains the custom theme and system-font import.
2. **Source bundle omitted the evidence-link target.** `packaging/builder.py:47-51` now generates an explicit unqualified
   `docs/public/evidence/release.json` placeholder. Final archive-bound evidence belongs in the separately assembled site
   and evidence artifacts, avoiding a circular source-archive hash. Inventory confirms the placeholder has null artifact
   identity and an empty matrix. Verify the extracted source site builds and passes links under both bases.
3. **T07 used default opacity.** `tests/runtime/qualify.py:79` now uses `background_opacity 0.85`. The final native runtime
   run must prove before/after preservation at this nondefault value; its previous opacity-1 result cannot substitute.

### Evidence-integrity issue resolved before the final cut

4. **Matrix cache reuse now binds executable builds.** `scripts/qualify_release.py:98-103` compares saved per-row
   kitty/shell SHA-256 identities before reuse. `:115-117` checks that those binaries did not change during a new run,
   then records their hashes. The earlier same-version replacement gap is closed in current source. The parent also
   reports a successful empirical same-version replacement rejection check.

### Native timer crash workaround: source and targeted native proof verified

- The failed old-kitty Bash login fixture is `/tmp/kittyscape-qualify-v80a5ylt/result.json`: core image/restoration,
  directory-stack and unchanged-prompt steps passed; the process then died during focus qualification. Its recorded
  error is a reset control connection, not a passed row.
- Upstream kitty snapshots raw callback pointers for all due timers; cancellation can free a later callback still in
  that batch. The raw native reproduction in `/tmp/kittyscape-timer-repro-nvokznh9/kitty.log` also records a segmentation
  fault without Kittyscape. The login profile separately emits systemd OSC 3008 messages from
  `/etc/profile.d/80-systemd-osc-context.sh`; this explains a login-only timing difference, not a proven primary cause.
- Current `kittyscape/compat.py:78-79,98-114` keeps one persistent bound dispatcher, stores callbacks in a registry,
  cancels only registry entries, and lets native one-shots expire. `kittyscape/engine.py:175-181` reuses one pending
  window timer and reads the latest generation when it fires. This removes the dangerous native cancellation path.
- Fresh independent checks after the fix: **77 unit tests passed; static checks passed for 29 Python files**.
  The tests cover a canceled callback already present in a simulated native dispatch batch and 500-event coalescing.
- Targeted native proof was inspected after the change: `/tmp/kittyscape-qualify-f3d3vjhv/result.json` records a passing
  kitty 0.38.1 / Bash 5.2.15 login rerun, including core restoration, directory stacks, focus, two OS windows and lifecycle.
  Its rendering snapshot includes opacity 0.85. `/tmp/kittyscape-safe-timer-repro-bx7btkyq/result.json` records 32 paired-timer
  rounds each on kitty 0.38.1 and 0.48.2, zero canceled callbacks executed and exit code zero. Its compat.py SHA matches
  the current source. These close the targeted crash regression; final archive-bound matrix and performance/idle
  qualification remain pending.

Primary source evidence:
[kitty 0.38.1 timer dispatch](https://github.com/kovidgoyal/kitty/blob/v0.38.1/glfw/backend_utils.c#L179),
[Python callback cleanup](https://github.com/kovidgoyal/kitty/blob/v0.38.1/kitty/child-monitor.c#L970).

## R01-R15 audit

| Requirement | Current conclusion | Evidence still needed for final acceptance |
| --- | --- | --- |
| R01 directory selection/restoration | Implemented; pure and earlier real-pixel fixtures exist. | T01 on the final archive across the configured Linux rows. |
| R02 Bash/Zsh/Fish parity | One shared resolver/native-report boundary implemented. | Complete final Linux matrix; the targeted old-login regression now passes. macOS remains open. |
| R03 path semantics | Component-boundary, physical-path, duplicate, Unicode/case, adversarial and symlink tests exist. | Final T03 runtime cases, including disappeared cwd, plus archive-bound results. |
| R04 active pane/tab targeting | Generation and active-pane rechecks remain intact; current harness checks displayed colors. | T04/T06 final native focus runs after timer workaround. |
| R05 independent OS windows | Per-window state and actual per-window pixel assertions exist. | T05 final two-window rows, including first-window restore without changing the second. |
| R06 rendering/config preservation | Image writes remain scoped and configured=False; installer owns only explicit files/block. | T07 nondefault opacity 0.85 and other settings before/after on final artifact. |
| R07 baseline restoration | No-image/single-image and claimed current index/theme/override paths implemented; unknown profiles reject. | Final T08/T09/T13 profile-specific evidence; do not turn rejected profiles into supported ones. |
| R08 unsupported capability diagnostics | Missing reports, known unsupported contexts and unknown baselines retain explicit diagnostics. | Final T09-T11 rejection cases and exact limits documented with their evidence. |
| R09 reversible installation | Ownership, immediate config guards, xattr fingerprints and rollback checks reviewed; earlier 35-test suite passed. | Fresh final-artifact preview/apply/repeat/restore/remove and rollback/preservation results. |
| R10 usable failure behavior | Safe config details, retry, visible restore failure, bounded filesystem queue/timeout implemented. | Native timer regression recovery and final image/report/error cases. |
| R11 no redundant writes/bounded state | Digest/context deduplication, bounded cache/queue, cleanup and timer coalescing implemented. | Final 100-transition p95, 60-second idle, resolver p95 at 1000 rules, recorded hardware/fixtures. |
| R12 truthful docs/quickstart | Docs describe implemented controls and explicit unsupported cases; packaging omissions fixed. | Copy-test the extracted archive, rebuild its site, and replace final evidence placeholder only in assembled site. |
| R13 root/subpath links | One VitePress site with local links/search; required routes and link validator exist. | Final root/subpath production builds and link/search results, including evidence JSON. |
| R14 accessibility/responsive UI | Original artwork, system fonts, restrained custom theme and bounded VitePress semantic patch reviewed. | Final Chromium/Firefox/WebKit layout/keyboard/contrast/reduced-motion/structure and native 200 percent evidence. |
| R15 release-specific support evidence | Current public record remains qualification-in-progress with null artifact and empty matrix. | Immutable final archive and executable identities, executed rows, stable evidence links and honest open gates. |

## T01-T17 gate inventory

| Test | Required final gate |
| --- | --- |
| T01 | Exact A/descendant/deeper-B/unmatched pixel sequence from installed artifact. |
| T02 | All configured Linux version/backend/baseline/startup rows; macOS explicitly open. |
| T03 | Final physical/symlink/punctuation/case/deleted-cwd evidence plus pure adversarial tests. |
| T04 | Final displayed-image proof for selected tabs and split panes. |
| T05 | Final independent displayed backgrounds in both OS windows. |
| T06 | Final rapid-focus/stale-result proof after native timer workaround. |
| T07 | Nondefault layout/interpolation/tints/colors and opacity 0.85 preserve runtime values/files. |
| T08 | No-image/single-image pause/disable/restore/removal behavior on final artifact. |
| T09 | Final claimed image-list/absolute-index/theme/override/reload cases or explicit preactivation rejection. |
| T10 | Final corrupt/oversized/unreadable image and invalid-config cases; current unit fault paths complement them. |
| T11 | Exact unsupported results; API/OSC injection fixtures must not be described as real SSH/container support. |
| T12 | Final installer preservation suite, symlink/include/custom-root/conflict/repeat/rollback evidence. |
| T13 | Final external-write pause/resume and theme ownership/restoration evidence. |
| T14 | Final unchanged-prompt/closed-state/60-second-idle proof; bounded queue/timer regressions remain green. |
| T15 | Archive integrity, installed engine origin, documented setup-through-removal, extracted-site reproducibility. |
| T16 | Final root/subpath build/link/search/no-third-party-request records. |
| T17 | Final browser layout/themes/reduced-motion/keyboard/structure plus exact native zoom records. |

The installed matrix driver supplies the core scenarios; advanced cases and performance require separate named runs.
None of the unexecuted final rows is counted as a pass in this audit.

## Workspace-15 constraint

Current `tests/runtime/qualify.py:89-93` requires a private compositor runtime below `/tmp` and active workspace 15
before Wayland launch. The launch uses workspace 15 silently; capture can move only the matched owned fixture window
to workspace 15 without following it. The previous special-workspace toggle calls are gone. Private compositor setup
is still owned by the parent and compatibility agent. Native X11/browser checks use reserved private Xvfb displays;
this audit ran none of them and did not switch any host workspace.

## Cleanup conclusion

Keep the current ownership and compatibility boundaries. No extra daemon, adapters, database, framework, or broad
refactor is needed. The timer wrapper and executable-evidence binding are justified by concrete failure evidence.
The original plans remain requirements, not implementation status pages. Update only product docs/evidence with final
results and preserve the explicit experimental/macOS labels.

Tier 2 graph coverage was checked. The indexed generation is stale for changed files; exact current sources were
read directly. Documentation and scripts are excluded from the graph and were also read directly. No source files,
host configuration, or publication state changed during this audit. This report is the only retained audit file.
