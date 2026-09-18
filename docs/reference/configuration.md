# Configuration fields

The configuration is a JSON object in `kittyscape.json`, in Kittyscape’s own
configuration directory. The default path is `~/.config/kittyscape/kittyscape.json`.
It is user-owned data. No visited repository is searched for configuration.

## Top-level fields

| Field | Type | Default | Meaning |
| --- | --- | --- | --- |
| `version` | Integer | Required | Schema version. This build uses `1`. |
| `enabled` | Boolean | `true` | Enable automatic directory selection. |
| `rules` | Array | `[]` | Directory/image mappings. An empty array is valid. |
| `fallback` | String or `null` | `null` | Local image used when no rule matches; omission or `null` selects baseline restoration. |
| `validate_bytes` | Boolean | `true` | Run Kittyscape's semantic PNG validator. `false` keeps all resource and file-integrity limits. |
| `background` | Object | Omitted | Requested layout and dynamic per-window opacity. Top-level `linear` is process-wide; tint fields are rejected pending a safe native scope. |
| `animation` | Object | enabled, 24 FPS, source loop | GIF enablement, speed, FPS ceiling, and loop policy. |
| `profiles` | Object | `{}` | Named scoped or whole-process settings profiles. |

Unknown fields, repeated JSON fields, unsupported versions, wrong types, and duplicate normalized roots are
validation errors. The UTF-8 JSON file must be a regular file at most 1 MiB, with at most 10,000 rules.
Invalid reloads retain the last valid configuration.

## Rule fields

| Field | Type | Meaning |
| --- | --- | --- |
| `directory` | String | Existing absolute directory root, or a path beginning with the user’s `~/` home shortcut. |
| `image` | String | Local PNG, JPEG, or GIF path; relative values resolve beside the configuration file. |
| `profile` | String | Optional name from top-level `profiles`. |

## Directory profiles

Each profile has exactly one mode. A rule selects one profile name. Deepest rule wins; parent profiles do not accumulate.

```json
{
  "version": 1,
  "profiles": {
    "focus": {"mode": "scoped", "font_size": 13, "padding": 8},
    "talk": {"mode": "process", "config": "profiles/talk.conf"}
  },
  "rules": [
    {"directory": "~/Work", "image": "work.jpg", "profile": "focus"},
    {"directory": "~/Talk", "image": "talk.gif", "profile": "talk"}
  ]
}
```

Scoped font size affects one kitty OS window. Padding and margin affect only the active pane. Kittyscape snapshots each
live value before its first write and restores it only while the current value still equals Kittyscape's last write.
An external font or spacing write therefore wins. Changing the active pane restores owned pane spacing before applying
the new pane's profile.

The active pane in the focused OS window selects the whole-process profile. Temporary application focus loss retains
the last focused OS window. A process profile affects every OS window in that kitty process and suspends all scoped
profiles. On release, targeted native setters restore still-owned font/spacing baselines and reconcile scoped selections.
Each process-to-process transition derives values from the live baseline plus only the new overlay. External divergence
becomes the new restoration baseline before the next transition.

Process overlay files must be regular UTF-8 files of at most 1 MiB beneath the Kittyscape configuration directory;
symlink escapes are rejected. Allowed fields are `font_size`, `window_padding_width`, and `window_margin_width`.
Native values are validated before mutation. Colors, palette, layout, and opacity remain unsupported in process
overlays because kitty's full option reload cannot preserve unrelated pane/tab writes at field scope. Includes,
mappings, launch commands, environment, watcher, shell integration, remote control, and every unlisted field reject
before mutation. There is no profile inheritance or reference syntax, so profile cycles cannot be expressed;
reference-like fields are unknown-field errors.

The deepest component ancestor wins. Symlinked roots and reported directories are physically normalized.
A sibling that merely starts with the same characters does not match.
For a symlinked JSON file, relative images still resolve beside the selected configuration path, not beside
the symlink target.

## Images

Rule and fallback images must be local PNG, JPEG, or GIF files. JPEG/GIF normalization requires local ImageMagick and a
system Python launcher for its bounded worker; setup reports ImageMagick availability and never installs either dependency.
HTTP URLs, executable providers, and automatic downloads are outside this build.
The image must be a readable local file. A missing, invalid, or oversized image uses the fallback policy
and a bounded diagnostic instead of interrupting the shell.

| Limit | Maximum |
| --- | --- |
| Encoded file size | 16 MiB |
| Width or height | 4,096 pixels each |
| Pixel count | 16,000,000 pixels |
| Decoded image data | 64 MiB |

Static PNG, JPEG, and GIF files are accepted. Animated GIFs retain bounded frames and timers. The shared image cache is
bounded to 32 MiB.
The [runtime findings](../development/compatibility-findings.md) distinguish validation tests from measured
decoding and display performance.

## Path examples

| Value | Interpretation |
| --- | --- |
| `~/Projects/Little Garden` | Home-relative shortcut expanded to a physical absolute directory root. |
| `/example/Projects/app` | Matches this directory and descendants, never `/example/Projects/application`. |
| `images/quiet.png` | Image beside the JSON file under `images/`. |
| `$(command)/image.png` | No shell evaluation; command interpolation is not supported. |

The [configuration guide](../guide/configuration.md) includes a complete two-rule example and exit-to-default behavior.
