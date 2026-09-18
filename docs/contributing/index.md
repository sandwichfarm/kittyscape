# Contributing

Kittyscape is a local development build. The runtime, support matrix, and distribution artifact are qualified
together. Publication, hosting, repository ownership, and licensing remain separate decisions.

## Start with evidence

Read the repository’s `README.md` and all documents in `.omx/plans/` before changing behavior.
The requirements and T01–T17 scenarios are the acceptance contract.
See the [compatibility findings](../development/compatibility-findings.md) for selected mechanisms and unresolved gates.

Use one shared rules implementation. Keep kitty-internal access in the compatibility boundary.
Do not duplicate matching logic in shell adapters. Add an adapter only when a measured reporting gap requires one.

## Runtime checks

From the repository or extracted source bundle:

```sh
make check
```

This runs `scripts/check.py`, the unit suite, and the installation suite.
Static checks cover Python syntax, duplicate definitions,
function size, argument count, line length, and branch complexity.

The tests cover matching, configuration, lifecycle, error recovery, installation preservation, and
deliberate mutations of ownership and targeting guards. Graphical qualification is a separate step.

## Qualify the installed artifact

Build the local archive with `python scripts/build_release.py`. Keep its extracted directory and original
archive together for `tests/runtime/installed.py`. The driver verifies their manifests and file hashes,
installs through the generated include, and checks that kitty loaded the installed engine. It then runs
the graphical scenarios and verifies restore, removal, and repeated removal.

For an X11 display and framebuffer you have already reserved and started:

```sh
python tests/runtime/installed.py \
  --archive /path/to/kittyscape-0.2.0.dev0.tar.gz \
  --bundle /path/to/extracted/kittyscape-0.2.0.dev0 \
  --kitty /path/to/kitty \
  --shell /path/to/bash \
  --backend x11 \
  --display :104 \
  --framebuffer /tmp/kittyscape-x11-test/frames/Xvfb_screen0 \
  --baseline single
```

Replace the paths and display with your owned test environment. `--baseline none` tests an original
no-image window; `--performance` adds 100 measured transitions after warmup and a 60-second idle check.
Use `--zsh-modules` or `--shell-lib-dirs` when a selected test binary needs its staged modules or libraries.

For Wayland, use the same archive, bundle, kitty, and shell arguments with `--backend wayland`.
The runner requires a separate Hyprland instance with `XDG_RUNTIME_DIR` under `/tmp` and workspace 15
active inside that instance. It never switches the daily desktop workspace. `grim -T` captures only the
exact owned kitty toplevel. Configure new fixture windows to stay on workspace 15 in that private instance.

`tests/runtime/extended.py` supplies additional path, image-error, theme, and unsupported-context cases.
It owns the reserved display `:102` and refuses to start when that display’s lock or socket already exists.
Use its `--bundle` argument to select the code under test. The installed-artifact driver supplies the
separate installation and runtime-origin proof.

For each graphical row, record artifact identity, OS, architecture, display backend, kitty/shell versions,
scenario IDs, timestamps, and sanitized evidence. A workstation test does not qualify another target environment.
The [release record](/evidence/release.json) is the source for completed qualification rows and open gates.

## Run the configured matrix

Copy `tests/runtime/toolchain.example.json` into a private working directory and replace its placeholder
paths with the test tools you have prepared. Keep conventional executable names (`bash`, `zsh`, and `fish`)
inside versioned directories so kitty can identify the native shell integration.

```sh
python scripts/qualify_release.py \
  /path/to/kittyscape-0.2.0.dev0.tar.gz \
  --toolchain /path/to/your/toolchain.json \
  --output /tmp/kittyscape-release-evidence
```

The template defines 96 installed fixtures: two kitty versions, six shell releases, two display backends,
two baseline profiles, and interactive/login startup. This is the configured test scope, not a pass count.
The batch driver extracts the archive, runs `installed.py`, and writes each completed row to `matrix.json`.
It can reuse saved rows after validating their archive hash, versions, backend, baseline, and startup mode.

The installed driver’s `--login` flag selects login startup with private fixture startup files.
Core scenarios include `pushd`/`popd` directory-stack transitions. Only the executed result records establish
which combinations passed; consult the release record rather than inferring support from the template.

## Isolate desktop testing

Use temporary configurations and separate kitty instances. Do not alter shell startup files, the daily-use
terminal, desktop configuration, or system packages as a test prerequisite.
Capture original settings and file metadata before installation, and verify removal from the packaged artifact.

For X11, choose an explicit free display number after checking both its lock and socket, including symlinks.
Never use `Xvfb -displayfd`, the desktop’s display, or another test process’s display. Keep the owned Xvfb
process alive for the entire run and stop only that process afterward. The installed-artifact driver expects
the framebuffer to exist; it does not start Xvfb for you.

Graphical automation enables socket-only remote control in its disposable kitty configuration. Ordinary
Kittyscape setup uses local key mappings and does not enable a remote-control listener.

## Website checks

The [website guide](../development/website.md) contains setup, build, and browser commands.
Use one VitePress site, local search, system fonts, and the existing original SVG artwork.
Validate root and subpath hosting, keyboard navigation, mobile widths, color contrast, and reduced motion.

## Release gate

Follow the [release checklist](../development/release-checklist.md). Only completed, artifact-specific rows
establish qualification. macOS arm64 remains an open gate; the release record lists any other missing evidence.

Do not publish, deploy, choose a license, or imply a public download until those actions are authorized.
No contribution or publication license has been selected for this local build.
