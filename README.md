# Kittyscape

*A different view for every directory.*

Directory-aware backgrounds for kitty, with your image settings intact.
Kittyscape uses the active pane in each OS window to select a local PNG, JPEG, or GIF from a
central rules file. Leaving a matching directory restores that window's known
original background.

**Experimental local build: 0.1.0.dev1.** Linux qualification is in progress.
macOS arm64 remains an open release gate because no test machine is available.
Exact versions, tested profiles, and limitations are in the
[compatibility matrix](docs/reference/compatibility.md).

## What it does

- Shares one resolver across Bash, Zsh, and Fish using kitty's native reports.
- Chooses the deepest matching physical directory, including nested rules,
  symlinks, spaces, and Unicode paths.
- Targets OS windows independently and preserves known background state.
- Plays animated GIF frames as OS-window backgrounds; static PNG remains idle.
- Provides status, reload, pause, resume, and restore controls.
- Runs offline using kitty's embedded Python and standard library.

Kittyscape keeps one current report per live pane. It records no directory
history and performs no idle polling. SSH, multiplexers, containers, nested
interactive shells, and unknown image baselines require the documented
[unsupported-context workflow](docs/guide/shells.md).

## Install

From an extracted bundle, one command installs the loader, creates your
editable rules file, and opens a fresh configured kitty window:

```sh
kitty +launch ./setup.py install
```

The loader lives in kitty’s active configuration directory. Your rules live in
their own directory: `~/.config/kittyscape/kittyscape.json` by default. The
installer never replaces an existing rules file and leaves it behind on uninstall.

Edit that file immediately with existing directories and local image files:

```json
{
  "version": 1,
  "rules": [
    {"directory": "~/Projects/Little Garden", "image": "images/garden.jpg"},
    {"directory": "~/Projects/Little Garden/seedlings", "image": "images/seedlings.gif"}
  ]
}
```

Relative image paths resolve beside this JSON file. The installer opens a fresh
kitty window with the watcher loaded. Use **Ctrl+Shift+F6** for status,
**F7** with the same modifiers to pause and restore, **F8** to resume, **F9**
to reload rules after every save, and **F10** to restore and pause before removal.

The installer does not restart existing kitty processes or alter their current
windows. It opens a new OS window with the watcher already loaded, so the new
window works immediately and has a known baseline. To target a non-default kitty
configuration or rules location, pass `--kitty-config-dir` or `--config-dir`.
Use `--preview` to inspect changes without writing files and `--no-launch` for
automation.

PNG works without a converter. JPEG and GIF need a local ImageMagick `magick` executable and the system Python launcher
used for the bounded conversion worker; setup reports ImageMagick availability and never installs software. `validate_bytes: false` skips Kittyscape's PNG semantic validator only. File-size,
dimension, frame, timeout, and cache bounds remain enforced.

The controls affect all OS windows in that kitty process. Another image writer
pauses the affected window until explicit resume. Unknown baselines stay paused.

```sh
kitty +launch ./setup.py uninstall --apply
```

Restore each running instance first. Removal preserves the user-owned JSON,
unrelated configuration edits, and modified or untracked files. See
[installation](docs/guide/installation.md) for manual setup and rollback.

## Documentation and development

The landing page and documentation are one VitePress site:

```sh
pnpm install --frozen-lockfile
pnpm docs:dev
```

Local verification and artifact preparation:

```sh
make check
pnpm docs:build
pnpm docs:build:subpath
pnpm docs:check
python scripts/build_release.py
```

The archive, manifest, and checksums are written to `dist/`. The site builds to
`docs/.vitepress/dist/` and `docs/.vitepress/dist-subpath/`. Browser and graphical
test prerequisites are described in [contributing](docs/contributing/index.md).
Runtime test evidence must come from an isolated graphical kitty instance.

The original [requirements](.omx/plans/prd-kittyscape.md),
[test specification](.omx/plans/test-spec-kittyscape.md), and
[implementation findings](docs/development/compatibility-findings.md) remain
available for review. Publication, deployment, and a project license are separate
decisions; this workspace does not select them.
