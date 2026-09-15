# Installation

The development build uses a user-local bundle loaded by kitty. No root privileges, shell framework,
system Python package, Node.js runtime, or network image service belongs in the extension’s normal runtime path.

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

## Choose the active configuration

Kittyscape’s JSON file belongs in kitty’s active configuration directory, alongside the configuration used
for that instance. A custom directory must be passed explicitly to the setup helper.
Do not assume every instance uses `~/.config/kitty`.

The helper preserves supported symlinked configurations, included files, and existing content.
See the [runtime findings](../development/compatibility-findings.md) for the qualified cases.

The helper rejects configuration paths containing a newline, NUL, or dollar sign, because those paths cannot
be represented safely in its kitty include. It also rejects a dangling `kitty.conf` symlink or a hard-linked
`kitty.conf`. Resolve the reported condition without replacing unrelated user data.

## Extract and preview

The local build produces the archive, a manifest, and `SHA256SUMS` in the repository’s `dist/` directory.
Compare the archive’s SHA-256 digest with `SHA256SUMS` before extracting it. On Linux, use `sha256sum`;
on macOS, use `shasum -a 256`.
The [release record](/evidence/release.json) identifies the artifact, executed checks, and open gates.

From the directory containing the archive:

```sh
tar -xzf kittyscape-0.1.0.dev1.tar.gz
cd kittyscape-0.1.0.dev1
kitty +launch ./setup.py install --config-dir '/tmp/kittyscape trial'
```

These commands work in Bash, Zsh, and Fish. Choose your own unused test directory in place of
`/tmp/kittyscape trial`. The final command is a **preview**: it reports the exact files, appended include,
and generated keyboard mappings without changing the selected configuration.

The helper runs in kitty’s embedded Python through `+launch`. It does not require a system Python installation.

## Apply and verify

After reviewing the preview:

```sh
kitty +launch ./setup.py install --config-dir '/tmp/kittyscape trial' --apply
kitty +launch ./setup.py install --config-dir '/tmp/kittyscape trial' --apply
```

Repeating a valid installation is idempotent: it does not append another include block or silently replace
modified installed files. Conflicts are reported so existing content can be preserved.

Create `kittyscape.json` in the test directory using the [getting-started example](./getting-started.md).
The helper never creates, rewrites, or removes this user-owned rules file. Provide the referenced local images
and use directory roots that already exist.

Open a separate kitty instance using that configuration:

```sh
env KITTY_CONFIG_DIRECTORY='/tmp/kittyscape trial' kitty
```

This selects the complete configuration directory, including any automatic theme files, for the new process.

Check **Ctrl+Shift+F6** for status, then follow the image-switching and restoration checks in
[getting started](./getting-started.md#check-the-result). The generated [lifecycle bindings](../reference/actions.md)
use Ctrl+Shift+F6 through Ctrl+Shift+F10. Review any existing bindings on those keys before using a personal configuration.

Finish the evaluation with [restore, removal, and rollback](./uninstall.md). A file-level installation check
does not prove graphical restoration or qualify another platform.

## Startup and existing windows

Load the watcher before creating the OS windows it will manage. A fresh kitty process started with the
selected configuration, as above, provides a known startup baseline.

Adding the watcher to an already-running process cannot recover the original image of its existing OS
windows. Those windows report `baseline-unknown` and stay paused. Open a new OS window after the watcher
is loaded, or start a fresh kitty process. A new tab or split inside an unknown OS window does not establish
a new baseline.

## What the helper owns

All paths below are relative to the selected configuration directory.

| Path | Purpose |
| --- | --- |
| `kittyscape/0.1.0.dev1/` | Versioned runtime and setup bundle. |
| `kittyscape/0.1.0.dev1/kittyscape/location.json` | Absolute path to the selected `kittyscape.json`. |
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
{ "config": "/tmp/kittyscape trial/kittyscape.json" }
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
[startup requirement](#startup-and-existing-windows), then run the same isolated checks.

A manual installation has no helper ownership receipt. Follow the
[manual removal instructions](./uninstall.md#manual-removal) using your recorded inventory.

## Updates and recovery

Keep the previous local bundle and valid configuration until the new artifact passes its checks.
Use the shipped rollback path if installation cannot be verified. The [release notes](../releases.md)
record compatibility changes; an unqualified upgrade must not inherit the previous version’s support label.
