# Kittyscape 0.1.0.dev1 local qualification

The local implementation, Linux qualification, source artifact, and static website are ready for review.
**macOS arm64 remains an open release gate by explicit user decision.** This is an experimental local build,
not a claim that the full version-1 platform target is complete. Nothing was published or deployed; no
repository was initialized and no project license was selected.

## Artifact identity

Source archive: `dist/kittyscape-0.1.0.dev1.tar.gz`.
SHA-256: `4d304c7c23dc343addd42500a05ca7c7607b3b5641ff60bae9324b99eb3a251a`.
The deterministic archive has 74 source files plus its manifest. Rebuilding after the final generated
website evidence was assembled produced the same archive hash. `dist/SHA256SUMS` records all delivery artifacts.

## Implementation and simplifications

- `kittyscape/{config,rules,images,compat,engine,watcher,action}.py`: one standard-library runtime shared by
  native Bash, Zsh, and Fish integration. Physical directory matching, strict JSON and bounded PNG loading,
  selected-pane/OS-window ownership, last-valid configuration, original-image restoration, and explicit controls.
- `packaging/{installer,builder}.py`, `setup.py`, `scripts/`: preview-first user-local installation/removal,
  backups and metadata/concurrent-change guards, deterministic manifests, and reproducible verification tools.
- `docs/`, VitePress config/theme, original SVG artwork, lockfile and bounded accessibility patch: one
  root/subpath website using system fonts, local search, and explicit compatibility limits.
- `tests/`: resolver/state/installer regressions and real graphical/browser verification. No new runtime
  dependency, shell adapter, daemon, idle polling, or package-manager installation was added.

The timer compatibility boundary avoids native callback lifetime hazards; cancellation removes a Python
registry entry and lets the native one-shot expire. A trailing 20ms quiet deadline keeps one pending timer
per OS window. Successful image changes refresh only the affected live pane, which fixes transparent
unfocused no-image restoration without global GPU invalidation. Unchanged selections do not upload again.

## Executed checks

| Check | Result |
| --- | --- |
| `make check` | 79 unit tests, 35 installation tests, static checks for 29 Python files passed. |
| Embedded Python unit suites | 79 passed in kitty 0.38.1 / Python 3.12.3 and kitty 0.48.2 / Python 3.14.6. |
| Installed Linux matrix | 96 fixtures passed: two kitty versions × six shell releases × two backends × two baselines × two startup modes. |
| Advanced native scenarios | 16 cases / 37 scenario records passed per backend, 74 total. |
| Old-kitty native config reload | Both backends preserved original PNG bytes/pixels while adopting changed layout. |
| Arch system kitty | Additional installed graphical row passed in kitty 0.48.2 / Python 3.14.7. |
| Warm 1080p image transitions | 100 measurements, p95 96.729ms; target below 250 ms. |
| Resolver | 1,000 rules, 200 measurements, p95 0.571ms; target below 10 ms. |
| Idle | 60 seconds, zero Kittyscape timer scheduling and zero image writes. |
| Website build/links | Both bases: 17 pages and 603 local link/asset checks passed. |
| Full browser baseline | Chromium149.0.7827.55, Firefox151.0, WebKit26.5:576 layout checks and672 axe scans passed. |
| Native exact 200% zoom | Chromium/Firefox:128 route/theme cases; WebKit GTK API:12 representative route/theme cases. |
| Final changed-document checks | Three engines, two routes, both bases/themes, three widths:72 layout,72 zero-violation axe,72 search flows passed. |
| Final website data assembly | All118 tested HTML/JS/CSS/SVG/routing-manifest files stayed byte-identical; only nonexecuted evidence data changed. |

Shell releases: Bash 5.2.15/5.3.20, Zsh 5.9/5.9.2, Fish 3.6.0/4.9.3. Kitty releases: 0.38.1/0.48.2.
The matrix includes no-image and single-PNG baselines, interactive and login startup, nondefault opacity 0.85,
layout/interpolation/tints/colors, tabs/splits, rapid focus, independent OS windows, install/restore/removal,
external image ownership, invalid configuration, and zero repeated image writes.

Authoritative records: [release.json](release.json), [X11 matrix](x11/matrix.json),
[Wayland matrix](wayland/matrix.json), [advanced X11](advanced-x11/result.json),
[advanced Wayland](advanced-wayland/result.json), [performance](performance/result.json),
[resolver](resolver-performance.json), [website proof](website/result.json),
[final website byte comparison](website/final-data-assembly.json).

## Exact environment and limits

Linux x86_64, Arch kernel 6.18.49-2-lts, Intel i7-11700K. X11 ran on explicitly reserved Xvfb displays.
Wayland ran in a private Hyprland compositor with a headless output, tiled visible windows on workspace 15,
and Mesa software rendering. Portable kitty used the system Wayland client library 1.26.0-1 through a
process-local preload. Its exact hash and environment are recorded in [renderer profile](isolation/renderer-profile.json).
These are qualification profiles, not a guarantee for every intervening kitty release or graphics stack.

Native WebKit exact 200% checks cover the homepage and two dense configuration routes in both themes/bases;
Chromium and Firefox cover the full route inventory at exact 200%. ARIA/semantic structure and keyboard
behavior were checked; a live screen-reader session was not performed. Unsupported-context fixtures use
local commands/environment/OSC inputs and do not claim real SSH, container, tmux, or Zellij support.
Unknown baseline state and unobserved image writers remain explicitly unsupported or paused as documented.

Bash 5.3.20 was built only under `/tmp/kittyscape-bash-5.3.20`, after explicit approval, with no installation.
The signed GNU source and 20 patches were verified. Binary: `/tmp/kittyscape-bash-5.3.20/build/bash`.
SHA-256: `c62d104046374b2d4bad53127f02dc9fcdb50e823f396f893494520e0761a8d9`.

## Desktop safety and cleanup

After the workspace 15 instruction, fixtures used only private displays/compositors; no host workspace
switching occurred. The private compositor processes/sockets and test displays 101/102/103 are stopped,
and there are no Kittyscape fixture windows on the host desktop. An earlier auto-display Xvfb experiment
conflicted with the desktop X0 socket; the active `X0 -> X0_` endpoint was restored and deliberately preserved.
The final `XOpenDisplay(":0")` check passed and Hyprland responded. See [cleanup proof](desktop-cleanup.json)
and [private compositor cleanup](isolation/cleanup-proof.json).

## Remaining gates

- Real macOS arm64 qualification, including the documented system-Bash limitation.
- Explicit repository ownership, project-license, distribution and hosting choices before publication.
- Any additional platform, image format, shell, or graphics profile requires its own recorded qualification.
