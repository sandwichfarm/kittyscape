# Kitty settings and restoration

Kittyscape selects an image. Kitty remains responsible for layout, interpolation, tint, gap tint, opacity,
and theme colors. Changing any of those settings is a separate kitty configuration action.

## One image per OS window

A kitty **pane** is a terminal inside an OS window. Tabs contain panes, but the background belongs to the
outer OS window:

```text
OS window A                         OS window B
└─ selected tab                      └─ selected tab
   ├─ active pane → image A             └─ active pane → image B
   └─ inactive pane → no override
```

Changing focus re-evaluates the newly active pane. Background activity in an inactive pane or unselected
tab must not override the visible selection. An unfocused OS window still owns independent state.

## What stays unchanged

Runtime switching preserves effective rendering settings and persistent configuration files in the
qualified profiles. It does not set the default image for future windows. Repeating an unchanged image
and rendering context adds no image upload.

These are measured runtime behaviors. The [findings](../development/compatibility-findings.md) identify the
profiles and versions for which preservation has been verified.

## Restoring the baseline

The baseline is the effective original image for an OS window, captured before Kittyscape changes it.
No image and a single image are different baseline states. Leaving a rule, disabling the extension,
or restoring it uses that baseline while Kittyscape still owns the window. The watcher must observe the
window’s startup; see [existing windows](./installation.md#existing-windows).

Removing the current image is correct only when the baseline contained no image.
A configured image list, runtime-selected image, theme change, or per-window override may need additional
baseline information. Such profiles are qualified separately; see [compatibility](../reference/compatibility.md).

## Themes, reloads, and other writers

Do not let two background tools contend over the same OS window. If another writer replaces an image,
Kittyscape must relinquish ownership and avoid overwriting that change during restoration.

Use **Ctrl+Shift+F7** to restore owned backgrounds and pause before manual changes. Review status with
**Ctrl+Shift+F6**, then explicitly resume with **Ctrl+Shift+F8** only when the current baseline is known.
An observed external write pauses only its affected OS window; an explicit pause affects the whole instance,
including windows opened later. See the full [action reference](../reference/actions.md).

Unknown baselines remain paused. Resume does not read back or guess unknown GPU image state.
Current kitty’s dark/light theme changes use a dedicated boundary: owned images are restored before
the native change, the new theme baseline is recorded, and previously unpaused windows resume. A manual
pause survives the theme change. Ordinary reloads preserve observed absolute image-list indices.

On kitty 0.38.1, an ordinary reload retains the previously displayed original image bytes while rendering
settings follow the reload, matching that version’s native behavior. The newer global image-index API is
not assumed on older versions.

A path-only custom Python writer cannot provide the exact bytes kitty loaded. Its baseline remains unknown,
even if that path currently exists. Use a fresh OS window with a known startup baseline, or an observed
byte-based image upload through kitty’s own authorized control mechanism. Direct C writers and relative
image-index changes remain outside concurrent automatic mode.

## Recovery

If switching or restoration looks wrong, pause automatic updates, inspect diagnostics, and preserve the
working terminal. Follow [uninstall and rollback](./uninstall.md) to remove only Kittyscape-owned setup.
Do not change opacity or remove your normal theme to hide a restoration error.
