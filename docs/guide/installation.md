# Installation

The development build uses a user-local bundle loaded by kitty. No root privileges, shell framework,
Node.js runtime, or network image service belongs in the extension’s normal runtime path. JPEG/GIF normalization invokes
the existing system Python launcher only to impose OS limits before starting ImageMagick; it does not install Python packages.

::: warning Experimental local artifact
There is no public download or published package yet. The local release candidate is
`kittyscape-0.1.0.dev1.tar.gz`. Full platform qualification remains in progress; use the
[compatibility matrix](../reference/compatibility.md) to see the remaining gates.
:::

## Prerequisites

Read the exact [compatibility matrix](../reference/compatibility.md). Test an isolated kitty instance before
enabling a daily-use configuration. See [uninstall and rollback](./uninstall.md) before applying any setup change.

The helper checks kitty 0.38.1 or newer and the watcher, timer, image, and directory APIs before changing files.
This is a capability check, not a platform support claim.

## One-step install

From the extracted bundle directory, run:

```sh
kitty +launch ./setup.py install
```

The command applies the owned loader files, creates
`~/.config/kittyscape/kittyscape.json` when it does not exist, and opens a new
kitty OS window with the watcher loaded. No kitty restart is required.

The loader is installed into kitty’s active configuration directory, usually
`~/.config/kitty`. Your directory rules are separate and live in the Kittyscape
configuration directory. The helper never overwrites or removes the rules file,
including during uninstall.

Use `--preview` to inspect changes without writing files. Use
`--kitty-config-dir /path/to/kitty` for a non-default kitty configuration and
`--config-dir /path/to/kittyscape` for a different rules location. `--no-launch`
installs only, which is useful for automation.

The helper rejects kitty configuration paths containing a newline, NUL, or dollar sign, because those paths
cannot be represented safely in its include. It also rejects a dangling `kitty.conf` symlink or a hard-linked
`kitty.conf`. Resolve the reported condition without replacing unrelated user data.

## Extract and configure

The local build produces the archive, a manifest, and `SHA256SUMS` in the repository’s `dist/` directory.
Compare the archive’s SHA-256 digest with `SHA256SUMS` before extracting it. On Linux, use `sha256sum`;
on macOS, use `shasum -a 256`.
The [release record](/evidence/release.json) identifies the artifact, executed checks, and open gates.

From the directory containing the archive:

```sh
tar -xzf kittyscape-0.1.0.dev1.tar.gz
cd kittyscape-0.1.0.dev1
kitty +launch ./setup.py install
```

These commands work in Bash, Zsh, and Fish. The helper runs in kitty’s embedded
Python through `+launch`; it does not require a system Python installation.

Immediately edit the created rules file with the [getting-started example](./getting-started.md):

```sh
$EDITOR ~/.config/kittyscape/kittyscape.json
```

Save it, then use **Ctrl+Shift+F9** in the fresh window to reload the rules.
The fresh window starts at your home directory and has a known baseline before
the first image change. Repeating a valid installation is idempotent: it does
not append another include block or replace an existing rules file.

Check **Ctrl+Shift+F6** for status, then follow the image-switching and restoration checks in
[getting started](./getting-started.md#check-the-result). The generated [lifecycle bindings](../reference/actions.md)
use Ctrl+Shift+F6 through Ctrl+Shift+F10. Review any existing bindings on those keys before using a personal configuration.

Finish the evaluation with [restore, removal, and rollback](./uninstall.md). A file-level installation check
does not prove graphical restoration or qualify another platform.

## Existing windows

The installer does not restart kitty or modify an existing OS window’s image.
Kitty loads watcher changes only for newly created windows, and an already open
window has no trustworthy original background for Kittyscape to restore. The
installer therefore opens a fresh configured OS window immediately. Keep using
your current windows normally; move work into the new window when you want
directory backgrounds.

## What the helper owns

All runtime paths below are relative to the selected kitty configuration directory.

| Path | Purpose |
| --- | --- |
| `kittyscape/0.1.0.dev1/` | Versioned runtime and setup bundle. |
| `kittyscape/0.1.0.dev1/kittyscape/location.json` | Absolute path to the user-owned rules file. |
| `kittyscape.conf` | Watcher entry and lifecycle key mappings. |
| Marked block in `kitty.conf` | One include for `kittyscape.conf`. |
| `kittyscape/kitty.conf.backup` | Original configuration snapshot for verified rollback. |
| `kittyscape/install-receipt.json` | Ownership and integrity information. |

Existing symlinked `kitty.conf` files and included files retain their relationships. The helper checks owned-file
hashes before replacement or removal. It preserves later unrelated configuration edits during uninstall.

## Manual installation

The helper is optional. For manual setup, use an empty destination, keep a backup and a written inventory of
your changes, and copy the extracted bundle into `kittyscape/0.1.0.dev1/` beneath the selected configuration root.
Do not overwrite an existing directory.

Create `kittyscape/location.json` **inside the copied bundle**, with the selected absolute JSON path.
Its full location is `kittyscape/0.1.0.dev1/kittyscape/location.json` beneath the configuration root:

```json
{ "config": "/home/you/.config/kittyscape/kittyscape.json" }
```

Create a separate include file containing the watcher entry and whichever lifecycle mappings you want.
For the example directory above:

```text
watcher /tmp/kittyscape trial/kittyscape/0.1.0.dev1/kittyscape/watcher.py
map ctrl+shift+f6 kitten '/tmp/kittyscape trial/kittyscape/0.1.0.dev1/kittyscape/action.py' status
map ctrl+shift+f7 kitten '/tmp/kittyscape trial/kittyscape/0.1.0.dev1/kittyscape/action.py' pause
map ctrl+shift+f8 kitten '/tmp/kittyscape trial/kittyscape/0.1.0.dev1/kittyscape/action.py' resume
map ctrl+shift+f9 kitten '/tmp/kittyscape trial/kittyscape/0.1.0.dev1/kittyscape/action.py' reload
map ctrl+shift+f10 kitten '/tmp/kittyscape trial/kittyscape/0.1.0.dev1/kittyscape/action.py' restore
```

Add one `include /absolute/path/to/your/include.conf` line to the intended kitty configuration. Keep your
`kittyscape.json` and images separate from runtime files. Follow the
[existing-windows requirement](#existing-windows), then run the same isolated checks.

A manual installation has no helper ownership receipt. Follow the
[manual removal instructions](./uninstall.md#manual-removal) using your recorded inventory.

## Updates and recovery

Keep the previous local bundle and valid configuration until the new artifact passes its checks.
Use the shipped rollback path if installation cannot be verified. The [release notes](../releases.md)
record compatibility changes; an unqualified upgrade must not inherit the previous version’s support label.
