# Release checks

The local source bundle and static site are prepared separately from publication.
The [release record](/evidence/release.json) contains immutable artifact identity,
the tested matrix, validation results, and open gates.

The source archive includes an explicitly unqualified placeholder at that link.
An archive cannot contain its own final checksum. After qualification, replace
`docs/public/evidence/release.json` with the resulting record before building the
separate static site. Rebuilding the source archive ignores that generated record
and preserves its original identity.

## Reproduce the local checks

```sh
make check
pnpm install --frozen-lockfile
pnpm docs:build
pnpm docs:build:subpath
pnpm docs:check
python scripts/build_release.py
```

Use the browser and native-runtime commands in
[contributing](../contributing/index.md). The release record stores the exact
commands and test-tool versions used. Graphical tests use disposable configs and
explicitly reserved display servers; never point them at a daily terminal.
Wayland tests require workspace 15 in a separate Hyprland instance with
`XDG_RUNTIME_DIR` under `/tmp`. They never switch the daily desktop workspace.

Before accepting a local artifact, verify:

- Archive and manifest checksums match the recorded qualification.
- Installation preview, apply, repeat, restore, removal, and rollback preserve
  user bytes, symlinks, permissions, and supported extended attributes.
- Matching, focus, independent OS windows, rendering, baseline restoration,
  config/theme reload, and failure recovery pass in the actual kitty runtime.
- Repeated unchanged prompts add no image writes, and the idle fixture schedules
  no timers or uploads. Performance includes 100 measured 1080p transitions.
- Root and subpath site builds, local search, responsive layouts, keyboard use,
  contrast, reduced motion, and native 200% zoom pass in the named browsers.
- Supported claims link to executed, artifact-specific evidence.

## Publication boundaries

MacOS arm64 qualification remains open because no machine is available. The
full version-1 platform target is therefore incomplete.

Repository owner, project license, distribution channel, domain, and hosting
provider remain unselected. Before any publication, select those explicitly and
review the existing dependency licenses and original asset provenance. The
pinned VitePress patch preserves its upstream MIT license. This local build
does not publish a package or deploy a website.
