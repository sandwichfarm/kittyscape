# Final acceptance: Kittyscape 0.1.0.dev1

Reviewed: 2026-09-15T15:24:46.087933+00:00

## Verdict

**APPROVED for the authorized local delivery. Architecture: CLEAR.**
No remaining concrete implementation or evidence blocker was found within the named Linux qualification profiles.
The final source bundle, reversible user-local setup, shared runtime, and root/subpath VitePress site have current
supporting evidence. This verdict does not claim completion of the full version-1 platform target: **macOS arm64
remains an explicit open gate, as directed by the user.**

No package publication, website deployment, repository initialization, or project-license selection is approved or
implied. Those actions were outside this implementation request.

## Identity and evidence integrity

- Source archive: `kittyscape-0.1.0.dev1.tar.gz`
- Archive SHA-256: `4d304c7c23dc343addd42500a05ca7c7607b3b5641ff60bae9324b99eb3a251a`
- Manifest SHA-256: `ba6f8cea33626d40110f06a91de380cad6f9dd7a4bdfd27fb047f4588364ba0a`
- Independently verified all **74 source-file sizes and hashes**, archive inventory, and manifest identity. Current
  source matches the archived files; the separately generated qualification JSON is intentionally distinct from the
  source bundle's explicit unqualified-build placeholder.
- Independently validated **96 unique installed-runtime rows**, including every expected combination and all **1,344
  scenario records**. Every row has the final archive identity, expected native versions/profile, and matching kitty
  and shell executable hashes. Screenshot files are present.
- Independently checked both advanced suites: **16 cases / 37 passed scenario records per backend**, bound to the same
  final archive. The older-kitty reload results and additional Arch-kitty row use that archive as well.
- Independently compared all **118 tested website functional files and routing manifests** with the final built files.
  Their bytes remain identical after final evidence-data assembly. The final release JSON and its 96 runtime rows and
  screenshots resolve within the built site evidence tree.

Primary local records: [release](../release.json), [report](../REPORT.md), [X11 matrix](../x11/matrix.json),
[Wayland matrix](../wayland/matrix.json), [advanced X11](../advanced-x11/result.json),
[advanced Wayland](../advanced-wayland/result.json), [website](../website/result.json),
[final website byte comparison](../website/final-data-assembly.json).

## Fresh verification performed in this audit

`PYTHONDONTWRITEBYTECODE=1 make check` passed against the source matching the final archive:

- **79 unit tests**
- **35 installation tests**
- **Static checks for 29 Python files**

The release records additionally report **79 embedded-runtime unit tests** in kitty 0.38.1 / Python 3.12.3 and
kitty 0.48.2 / Python 3.14.6. The installed graphical matrix directly establishes package loading in those runtimes.
No graphical scenario was rerun by this reviewer.

## R01-R15 acceptance

| Requirement | Verdict and evidence |
| --- | --- |
| R01 directory selection and fallback | PASS. Final installed rows assert the A/deeper-B/unmatched pixel sequence and restoration. |
| R02 shell/platform parity | PASS for the recorded Linux profiles: Bash 5.2.15/5.3.20, Zsh 5.9/5.9.2 and Fish 3.6.0/4.9.3, both kitty versions/backends/baselines/startup modes. macOS remains OPEN. |
| R03 physical path semantics | PASS. Pure adversarial/component/symlink/case tests and final graphical punctuation, Unicode, symlink, directory-stack and disappeared-cwd cases agree with the documented policy. |
| R04 selected tab/pane targeting | PASS. Final native rows check displayed colors during tab/split focus changes; inactive-pane activity cannot override the selected pane. |
| R05 independent OS windows | PASS. Final two-window cases assert both images and restore the first window while the second remains unchanged. |
| R06 rendering and configuration preservation | PASS. Final rows preserve layout, interpolation, tint, gap tint, colors and nondefault opacity 0.85; runtime writes remain scoped and configured=False. |
| R07 baseline restoration | PASS for claimed profiles. No-image/single-PNG baselines, observed byte overrides, current absolute list indices and native themes restore as recorded. Unknown/path-only/relative-index profiles remain rejected or paused. |
| R08 unsupported capabilities | PASS. Capability/report checks and final advanced rejection cases preserve usable shells and expose explicit reasons. No unqualified remote or multiplexer support is claimed. |
| R09 reversible installation | PASS. Final rows use generated installed configuration, attest the installed engine origin, and verify preview/apply/repeat/restore/remove. The fresh installation suite covers rollback, conflicts, symlinks, concurrent changes and metadata preservation. |
| R10 failure handling | PASS. Final invalid-image/config/report fixtures plus current fault regressions cover bounded diagnostics, last-valid configuration, retry, visible restore failure, stalled I/O and cancellation safety. |
| R11 deduplication and bounded work | PASS. Final unchanged-prompt/state-release checks, bounded timer/worker/cache regressions, measured performance and idle records support the claims. |
| R12 documentation and quickstart | PASS. Docs describe shipped controls, setup/removal, profiles and recovery. Source packaging includes the VitePress entry, patch and explicit evidence placeholder. Final evidence is supplied separately without changing the source identity. |
| R13 root/subpath documentation links | PASS. Both final bases have 17 HTML pages and 603 local link/asset checks; local search and final evidence destinations are verified. |
| R14 accessible responsive site | PASS within the recorded browser test scope. Three-engine layout/contrast/semantic/keyboard evidence, native zoom and final changed-document checks support the site. Limits below remain explicit. |
| R15 release-specific evidence | PASS for the named Linux rows. Archive, manifests, executable identities, profile restrictions, scenario records and screenshots are bound together. No intervening-version or unmodified portable-Wayland claim is made. |

## T01-T17 acceptance mapping

| Tests | Final supporting evidence |
| --- | --- |
| T01-T02 | The 96 installed-artifact rows cover the required directory sequence across the complete configured Linux matrix. |
| T03 | Core directory stacks/punctuation plus advanced physical/symlink/deleted-cwd cases and current resolver tests. |
| T04-T06 | Final native tab/split/rapid-focus and independent-window pixel assertions. Timer and trailing-deadline regressions remain green. |
| T07 | Recorded nondefault rendering snapshots and unchanged configuration files, including opacity 0.85. |
| T08 | No-image/single-image pause/restore, advanced disable/re-enable, and installed-artifact restoration/removal. |
| T09 | Both advanced suites, current absolute-index/reload/theme/override results, and older-kitty reload records. Rejected profiles are not promoted to support. |
| T10 | Both advanced error suites and current fault-path tests. The selected runtime has no remote-control transport to disconnect; native apply failures are covered by fault regressions. |
| T11 | Disabled-report, lost/remote-report, nested-shell and declared unsupported-context fixtures. Their scope is stated accurately. |
| T12 | Fresh 35-test preservation/rollback suite and final installed-artifact lifecycle rows. |
| T13 | Final external byte-writer ownership, explicit resume and native theme/reload cases. |
| T14 | Zero extra image writes on unchanged prompts, closed-state pruning, bounded worker/timer tests and the final idle observation. |
| T15 | Archive/manifest integrity, installed runtime-origin attestations, documented setup-through-removal, source-site inventory and website build evidence. |
| T16 | Final root/subpath build/link results, local search flows and tested asset identities. |
| T17 | Three-engine layout/themes/reduced-motion/semantic/keyboard records and exact native zoom evidence, with the explicit coverage limits below. |

macOS portions of T02/T15 remain open under the user's explicit exception. No mock, Linux run, or browser screenshot is
used as macOS proof.

## Performance verification

[Performance](../performance/result.json) records **100 measured 1920x1080 transitions** after warmup. Recomputing the
95th-percentile sample gives **96.728879 ms**, below the 250 ms target. Its 60-second idle observation records **zero
scheduled Kittyscape timers and zero image writes**.

[Resolver](../resolver-performance.json) records 1,000 rules, 100 warmups and 200 measurements: **p95 0.571323 ms**,
below the 10 ms target. [Environment](../environment.json) identifies the CPU, kernel and fixture dimensions.

## Website evidence and limits

The complete browser baseline passed in Chromium **149.0.7827.55**, Firefox **151.0**, and WebKit **26.5**:
**576 layout checks and 672 axe scans**. The final two changed documentation routes then passed **72 layout checks,
72 zero-violation axe scans and 72 local-search flows** across both themes/bases and all three widths/engines.
The final evidence-data rebuild preserved all 118 previously tested functional files and routing manifests.

Native exact-200-percent zoom evidence covers **128 route/theme cases in Chromium and Firefox** and **12 representative
homepage/dense-configuration cases through the WebKitGTK 2.53.3 public zoom API**. WebKit is not represented as having
full-route native-zoom coverage. ARIA/semantic structure and keyboard behavior were checked; **no live screen-reader
session was performed**. These stated limits must remain visible.

Earlier failed browser attempts are retained as historical evidence; the passing final native receipts are
`website/native-chromium-firefox/zoom-results.json` and `website/native-webkit/webkit-native-results.json`.

## Compatibility and desktop boundaries

Qualification is for Linux x86_64 and the exact recorded builds. Wayland uses a private Hyprland compositor, visible
tiled fixture windows on workspace 15, Mesa software rendering and the named host Wayland-client preload. It does
not establish unmodified portable-Wayland behavior or every graphics stack. X11 uses reserved private Xvfb displays.

The [cleanup record](../desktop-cleanup.json) and [private-session cleanup](../isolation/cleanup-proof.json) record
stopped private processes/sockets, no fixture windows on the host, responsive Hyprland and restored/reachable desktop
Xwayland access. This reviewer launched no GUI, switched no host workspace, and edited no source or host configuration.

## Final boundary

All required work for the authorized **local delivery with macOS left open** is supported by current evidence.
Keep the macOS gate and named qualification limits; publication, hosting, repository and project-license choices
remain separate decisions. No unrelated work is recommended by this review.
