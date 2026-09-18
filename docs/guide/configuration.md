# Configuration

Kittyscape reads `kittyscape.json` from its own configuration directory:
`~/.config/kittyscape/kittyscape.json` by default. Rules are shared by every
qualified shell in that kitty instance. The file is data only; directory visits
never execute project hooks. Use `install --config-dir /path/to/kittyscape` to
choose another rules directory without moving kitty’s own configuration.

## Match a directory

Each rule has a directory root and a local PNG, JPEG, or GIF image. A rule applies to that directory and its descendants.
The deepest matching root wins, regardless of rule order.

```json
{
  "version": 1,
  "rules": [
    { "directory": "~/Projects/Little Garden", "image": "images/garden.png" },
    { "directory": "~/Projects/Little Garden/seedlings", "image": "images/seedlings.png" }
  ]
}
```

JPEG and GIF use ImageMagick when it is available. Animated GIFs replace the OS-window background frame by frame;
set `"animation": {"enabled": false}` to display only the coalesced first frame. The default is a 24 FPS ceiling,
source timing, and source loop count. `validate_bytes: false` skips only Kittyscape's semantic PNG validation; it does
not disable size, decoding, timeout, or cache limits.

The first rule matches `Little Garden/notes`. The second wins inside `Little Garden/seedlings`.
A root ending in `app` never matches a sibling named `application`.

## Select kitty settings

Add named profiles beside `rules`. One rule may select one profile. Scoped profiles change OS-window font size and
active-pane spacing. Process profiles point to a central allowlisted kitty overlay and affect every OS window in the
same kitty process.

```json
{
  "version": 1,
  "profiles": {
    "focus": {"mode": "scoped", "font_size": 13, "padding": 8},
    "present": {"mode": "process", "config": "profiles/present.conf"}
  },
  "rules": [
    {"directory": "~/Projects/Little Garden", "image": "images/garden.png", "profile": "focus"},
    {"directory": "~/Talks", "image": "images/slides.gif", "profile": "present"}
  ]
}
```

Save `present.conf` beneath this configuration directory, then run reload. Process overlays never use repository-local
files. See [directory profiles](../reference/configuration.md#directory-profiles) for supported fields and arbitration.

## Paths and symlinks

- Directory roots must exist and be absolute after expanding a leading `~/` home shortcut.
- Rule roots and reported directories use physical, normalized paths. A symlinked route and its target
  therefore select the same rule.
- Duplicate roots after normalization are rejected. File order does not resolve ambiguity.
- Relative image paths resolve against the configuration file’s directory.
- Unicode, spaces, and punctuation are ordinary path characters. Use valid JSON escaping for backslashes and quotes.
- Paths are never expanded as shell commands. Arbitrary environment expressions are not interpolated.
- Matching does not lowercase every path; filesystem case behavior matters.

The [compatibility matrix](../reference/compatibility.md) distinguishes verified filesystem behavior from
platforms that still require qualification.

## Leaving a project

With no matching rule, Kittyscape restores the original background it captured for that OS window,
including the absence of an image. It does not use removal as a universal replacement for restoration.

An optional fallback image changes that choice:

```json
{
  "version": 1,
  "rules": [],
  "fallback": "images/quiet.png"
}
```

The fallback path follows the same local-image rules. See the [restoration limitations](./kitty-settings.md)
before using themes, image lists, or another background writer.

An unmatched directory using a valid fallback is normal: status can show `owned: true` with an empty `reason`.
If a matching rule’s image is invalid, the fallback can still display while `image-unavailable-or-invalid`
identifies the failed rule image. A later valid selection clears that diagnostic, even when the displayed
image does not need another upload. Pause and restore still return the original background.

## Reload safely

Changes are explicit; there is no filesystem watcher or per-prompt configuration reload.
Use **Ctrl+Shift+F9**, the shipped [reload action](../reference/actions.md), after saving JSON.
Reload returns before validation and image work finish. **Ctrl+Shift+F6** shows pending work and the
configuration `revision`; a successful reload advances that revision. A malformed reload retains the last
valid rules and reports a bounded diagnostic with the relevant field or JSON location. Correct the file
and reload again to recover.

To disable automatic updates, set `enabled` to `false` and reload. This restores owned backgrounds.
For a temporary pause with the same restoration behavior, use **Ctrl+Shift+F7**.

See [configuration fields](../reference/configuration.md) for defaults, validation errors, and image limits.
