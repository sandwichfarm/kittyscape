# Getting started

Kittyscape selects a local background image from your shell’s directory. The active pane in the selected tab
controls the image for its **OS window**, meaning the outer window managed by your desktop.

::: warning Experimental local build
Qualification is still in progress. Read the [compatibility matrix](../reference/compatibility.md) and
[removal instructions](./uninstall.md) before changing a kitty configuration.
Use a disposable kitty configuration while evaluating this build.
:::

## Before you begin

You need kitty, a shell with working kitty directory reports, and local PNG images you can read.
The extension uses kitty’s embedded Python. Node.js is only needed to work on this documentation site.

Check the exact versions and configuration profiles in [compatibility](../reference/compatibility.md).
An installed shell executable alone does not establish working directory reports.

## Install in a test configuration

Follow [installation](./installation.md) to preview the user-local setup, review the owned files, and apply it
to an isolated configuration. Start a new kitty process with that configuration so the watcher observes the
original background before changing it. See [startup and existing windows](./installation.md#startup-and-existing-windows).

## Give two directories a background

Place `kittyscape.json` in the active kitty configuration directory. The following example gives a project
one image and a nested directory another. Replace the directory paths and provide the two PNG files.

```json
{
  "version": 1,
  "enabled": true,
  "rules": [
    {
      "directory": "~/Projects/Little Garden",
      "image": "images/garden.png"
    },
    {
      "directory": "~/Projects/Little Garden/seedlings",
      "image": "images/seedlings.png"
    }
  ]
}
```

Image paths here are relative to the directory containing `kittyscape.json`. They do not change meaning when
the shell moves. See [configuration](./configuration.md) for symlinks, nested rules, and fallback images.

## Check the result

In an isolated interactive shell, enter each directory. These quoted `cd` commands work in Bash, Zsh, and Fish:

```sh
cd ~/"Projects/Little Garden"
cd seedlings
cd ~
```

The expected sequence is garden image, seedlings image, then the captured original background.
A terminal that began with no image returns to no image. Restoration depends on the
[qualified baseline profile](../reference/compatibility.md).

Switch between two panes with different directories, then between tabs. The selected tab’s active pane
decides its OS window’s background. Check that two OS windows keep independent images.

If any check fails, use [troubleshooting](./troubleshooting.md), then [restore and remove](./uninstall.md).
