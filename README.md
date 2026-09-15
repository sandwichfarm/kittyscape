# Kittyscape

*A different view for every directory.*

Directory-aware backgrounds for kitty, with your image settings intact.
Kittyscape uses the active pane in each OS window to select a local PNG from a
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
- Targets OS windows independently and preserves kitty's rendering settings.
- Provides status, reload, pause, resume, and restore controls.
- Runs offline using kitty's embedded Python and standard library.

Kittyscape keeps one current report per live pane. It records no directory
history and performs no idle polling. SSH, multiplexers, containers, nested
interactive shells, and unknown image baselines require the documented
[unsupported-context workflow](docs/guide/shells.md).

## Try the local bundle

Read [compatibility](docs/reference/compatibility.md) and
[removal](docs/guide/uninstall.md) before setup. Use a disposable configuration
while evaluating this build.

From the extracted bundle directory:

```sh
kitty +launch ./setup.py install --config-dir /tmp/kittyscape-demo
kitty +launch ./setup.py install --config-dir /tmp/kittyscape-demo --apply
```

The first command previews changes. The second applies only the owned files and
include block, with an ownership receipt and backup. Create
`/tmp/kittyscape-demo/kittyscape.json` with existing directories and PNG files:

```json
{
  "version": 1,
  "rules": [
    {"directory": "~/Projects/Little Garden", "image": "images/garden.png"},
    {"directory": "~/Projects/Little Garden/seedlings", "image": "images/seedlings.png"}
  ]
}
```

Relative image paths resolve beside this JSON file. Start a separate kitty with
`KITTY_CONFIG_DIRECTORY=/tmp/kittyscape-demo kitty`. Use **Ctrl+Shift+F6** for
status, **F7** with the same modifiers to pause and restore, **F8** to resume,
**F9** to reload rules, and **F10** to restore and pause before removal.

The controls affect all OS windows in that kitty process. Another image writer
pauses the affected window until explicit resume. Unknown baselines stay paused.

```sh
kitty +launch ./setup.py uninstall --config-dir /tmp/kittyscape-demo
kitty +launch ./setup.py uninstall --config-dir /tmp/kittyscape-demo --apply
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
