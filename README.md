<div align="center">

<img src="docs/public/cat-mark.svg" alt="Kittyscape cat logo" width="72" height="72">

# Kittyscape

*A different view for every directory.*

Directory-aware backgrounds for kitty, selected by the active pane.

[![GitHub stars](https://img.shields.io/github/stars/sandwichfarm/kittyscape?style=for-the-badge)](https://github.com/sandwichfarm/kittyscape/stargazers)
[![Docs deployment](https://img.shields.io/github/actions/workflow/status/sandwichfarm/kittyscape/deploy-pages.yml?branch=main&label=docs&style=for-the-badge)](https://github.com/sandwichfarm/kittyscape/actions/workflows/deploy-pages.yml)

[Documentation](https://sandwichfarm.github.io/kittyscape/) · [Quick start](#quick-start) · [Compatibility](docs/reference/compatibility.md)

</div>

## What is Kittyscape?

Kittyscape gives each project directory its own local PNG, JPEG, or GIF background.
It follows the active pane in each kitty OS window, using one rules file across
Bash, Zsh, and Fish. Leaving a matching directory restores that window’s known
original background, unless you configure a fallback image.

- **Nested rules:** the deepest matching physical directory wins, including paths with symlinks, spaces, and Unicode.
- **Independent windows:** each OS window follows its own active pane.
- **Animated backgrounds:** GIF playback with configurable timing and limits; static PNGs need no playback timer.
- **Settings profiles:** rules can select scoped font/spacing or allowlisted whole-process kitty settings.
- **Local operation:** no network image service or directory history; directory tracking uses kitty’s native reports.
- **Explicit controls:** inspect status, reload rules, pause, resume, or restore from the keyboard.

**Experimental development build: `0.2.0.dev0`.** Linux qualification evidence is recorded locally;
macOS arm64 remains an open release gate. The [compatibility matrix](docs/reference/compatibility.md)
contains exact test scope, evidence, and limitations.

## Quick start

You need kitty **0.38.1 or newer**, native shell integration for Bash, Zsh, or Fish,
and Git for the source checkout below. The installer checks required kitty APIs;
this version floor is not a guarantee of support for every release or platform.

```sh
git clone https://github.com/sandwichfarm/kittyscape.git
cd kittyscape
kitty +launch ./setup.py install
```

The installer adds the loader to kitty’s active configuration directory, creates
`~/.config/kittyscape/kittyscape.json` if absent, and opens a fresh configured
kitty window. Existing windows keep running. The rules directory follows
`XDG_CONFIG_HOME` when set; your existing rules file is never replaced.

Use `install --preview` to inspect changes, `--no-launch` to install without
opening a window, or `--kitty-config-dir` and `--config-dir` to select separate
kitty and rules directories. See [installation](docs/guide/installation.md) for
an isolated trial, bundle installation, and rollback.

### Give a directory a background

Edit your `kittyscape.json` with directories and image files that already exist:

```json
{
  "version": 1,
  "rules": [
    {"directory": "~/Projects/Little Garden", "image": "images/garden.png"},
    {"directory": "~/Projects/Little Garden/seedlings", "image": "images/seedlings.png"}
  ]
}
```

Relative image paths resolve beside the JSON file, so the first image above lives
at `~/.config/kittyscape/images/garden.png` with the default configuration path.
Save, press **Ctrl+Shift+F9** in the fresh window, then visit a matching directory:

```sh
cd ~/Projects/Little\ Garden
```

The first rule covers that directory and its descendants; the second takes over
inside `seedlings`. Leave both trees to restore the original background.
Use **Ctrl+Shift+F6** to inspect status if the image does not change.

### Image formats

| Format | Requirements | Behavior |
| --- | --- | --- |
| PNG | kitty’s embedded Python; no converter | Static background. |
| JPEG | ImageMagick’s `magick` command and system Python | Converted to a static background. |
| GIF | ImageMagick’s `magick` command and system Python | Animated playback, or the first frame when animation is disabled. |

Setup reports ImageMagick availability and does not install software. To use a
JPEG or GIF, change a rule’s `image` path. See [configuration](docs/guide/configuration.md)
for animation settings, fallback images, validation, and resource limits.

## Controls and removal

| Shortcut | Action |
| --- | --- |
| Ctrl+Shift+F6 | Show status and diagnostics. |
| Ctrl+Shift+F7 | Restore original backgrounds and pause. |
| Ctrl+Shift+F8 | Resume automatic switching where the baseline is known. |
| Ctrl+Shift+F9 | Reload rules after saving the JSON file. |
| Ctrl+Shift+F10 | Restore and pause before removal. |

Controls apply to all OS windows in the current kitty process. An observed write
from another background tool pauses the affected window; unknown baselines stay
paused. Review existing key bindings and the [action reference](docs/reference/actions.md).

SSH, tmux, Zellij, containers, and nested interactive shells are not qualified
automatic contexts. Follow the [pause/change/resume workflow](docs/guide/shells.md)
before entering them.

To remove Kittyscape, first restore each running instance with **Ctrl+Shift+F10**,
then run this from the source checkout or extracted bundle:

```sh
kitty +launch ./setup.py uninstall --apply
```

Removal preserves your rules file, unrelated configuration edits, and modified or
untracked files. See [uninstall and rollback](docs/guide/uninstall.md) for details.

## Documentation

| Guide | What it covers |
| --- | --- |
| [Getting started](docs/guide/getting-started.md) | Check directory switching and restoration. |
| [Installation](docs/guide/installation.md) | Preview, custom paths, manual setup, and bundles. |
| [Configuration reference](docs/reference/configuration.md) | Fields, defaults, image limits, and validation. |
| [Kitty settings](docs/guide/kitty-settings.md) | Rendering settings, themes, and background ownership. |
| [Troubleshooting](docs/guide/troubleshooting.md) | Diagnose missing images and paused windows. |
| [Compatibility](docs/reference/compatibility.md) | Exact test scope, baseline evidence, and open platform gates. |
| [Contributing](docs/contributing/index.md) | Runtime tests, isolated graphical checks, and release evidence. |

## Development

The main source directories are:

```text
kittyscape/
├── docs/          # VitePress site and user guides
├── kittyscape/    # Watcher, rules, media, and lifecycle controls
├── packaging/     # Installer and archive builder
├── scripts/       # Static checks and release tooling
├── tests/         # Unit, installation, runtime, and site checks
├── Makefile       # Local verification targets
└── setup.py       # Installer entry point, run through kitty
```

From the repository root, run the Python static checks, unit tests, and
installation tests, then build a local archive:

```sh
make check
python scripts/build_release.py
```

The archive, manifest, and checksums are written to `dist/`. Graphical runtime
qualification is separate and must use an isolated kitty instance.

The website uses pnpm, pinned in `package.json`; Node.js and pnpm are only needed
for documentation development:

```sh
pnpm install --frozen-lockfile
pnpm docs:dev
```

Before submitting site changes, run `pnpm docs:build`, `pnpm docs:build:subpath`,
and `pnpm docs:check`. See the [website guide](docs/development/website.md) for
browser checks and prerequisites.

For behavior changes, read the [requirements](.omx/plans/prd-kittyscape.md),
[test specification](.omx/plans/test-spec-kittyscape.md), and
[implementation findings](docs/development/compatibility-findings.md).
Include relevant test results with your pull request.

No project license has been selected.
