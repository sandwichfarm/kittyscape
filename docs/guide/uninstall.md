# Uninstall and rollback

Removal has two parts: restore the running OS windows that Kittyscape still owns, then remove its user-local
configuration entry and installed files. A file removal alone cannot restore an already-running window.

::: warning Restore before removing files
The setup helper cannot unload a watcher from an already-running kitty process. Restore and pause those
instances first. No public package is available yet; these instructions apply to the local development bundle.
:::

## Restore first

Use **Ctrl+Shift+F10**, the [restore action](../reference/actions.md), while the watcher is loaded.
This restores owned baselines and pauses the whole instance, including windows opened later.
Check the original image in each affected OS window, including the no-image case.
Restoration must skip windows whose background was replaced by another tool.

If ownership or baseline capture is uncertain, preserve the current working terminal and inspect
[restoration guidance](./kitty-settings.md). Do not clear every window’s background.

## Remove owned setup

From the extracted bundle, preview removal, then apply it:

```sh
kitty +launch ./setup.py uninstall --kitty-config-dir ~/.config/kitty
kitty +launch ./setup.py uninstall --kitty-config-dir ~/.config/kitty --apply
```

Use the same kitty configuration directory chosen during installation. You can also run the installed helper,
for example `kitty +launch '/tmp/kittyscape trial/kittyscape/0.2.0.dev0/setup.py' uninstall
--kitty-config-dir ~/.config/kitty --apply` as one command.

Review the preview’s owned-file list. Uninstall removes the exact marked include block while preserving
later unrelated edits. It removes only unchanged owned files. Modified or untracked files are retained and
reported; the backup and receipt remain when retained content still needs review.

The helper preserves `kittyscape.json`, user images, shell startup files, included configurations, and existing
symlink relationships. Repeated removal handles the already-removed state without duplicating changes.

Open a fresh isolated kitty instance and confirm that its ordinary background and rendering preferences remain intact.
Keep the backup until both running-window and fresh-window checks pass.

## Roll back an installation

Rollback is the appropriate operation when you want to undo an installation and the installed configuration
has not received later edits:

```sh
kitty +launch ./setup.py rollback --kitty-config-dir ~/.config/kitty
kitty +launch ./setup.py rollback --kitty-config-dir ~/.config/kitty --apply
```

Rollback requires the original backup to be readable and match its recorded hash. The installed `kitty.conf`
must also remain unchanged. Otherwise rollback refuses to overwrite user work. Use uninstall to preserve later
unrelated edits, or reconcile the conflict manually after reading the retained files.

The acceptance check compares file bytes, permissions, symlink targets, and unrelated content with the
pre-install snapshot. See the [runtime and packaging evidence](../development/compatibility-findings.md).

## Manual removal

For a [manual installation](./installation.md#manual-installation), restore/pause the running instance first.
Remove the exact include line you added, then remove only the include file and versioned bundle recorded in
your inventory. Preserve edited files, rules, images, and unrelated content for review.

Do not use helper uninstall for a manual installation without an ownership receipt. Open a fresh isolated
kitty instance and verify its normal background. Keep your backup until both running and fresh instances pass.
