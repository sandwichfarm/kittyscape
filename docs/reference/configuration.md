# Configuration fields

The configuration is a JSON object in `kittyscape.json`, in kitty’s active configuration directory.
It is user-owned data. No visited repository is searched for configuration.

## Top-level fields

| Field | Type | Default | Meaning |
| --- | --- | --- | --- |
| `version` | Integer | Required | Schema version. This build uses `1`. |
| `enabled` | Boolean | `true` | Enable automatic directory selection. |
| `rules` | Array | `[]` | Directory/image mappings. An empty array is valid. |
| `fallback` | String or `null` | `null` | Local image used when no rule matches; omission or `null` selects baseline restoration. |

Unknown fields, repeated JSON fields, unsupported versions, wrong types, and duplicate normalized roots are
validation errors. The UTF-8 JSON file must be a regular file at most 1 MiB, with at most 10,000 rules.
Invalid reloads retain the last valid configuration.

## Rule fields

| Field | Type | Meaning |
| --- | --- | --- |
| `directory` | String | Existing absolute directory root, or a path beginning with the user’s `~/` home shortcut. |
| `image` | String | Local PNG path; relative values resolve beside the configuration file. |

The deepest component ancestor wins. Symlinked roots and reported directories are physically normalized.
A sibling that merely starts with the same characters does not match.
For a symlinked JSON file, relative images still resolve beside the selected configuration path, not beside
the symlink target.

## Images

Rule and fallback images must be local static PNGs. HTTP URLs, executable providers, and automatic downloads are outside this build.
The image must be a readable local file. A missing, invalid, or oversized image uses the fallback policy
and a bounded diagnostic instead of interrupting the shell.

| Limit | Maximum |
| --- | --- |
| Encoded file size | 16 MiB |
| Width or height | 4,096 pixels each |
| Pixel count | 16,000,000 pixels |
| Decoded image data | 64 MiB |

Only static PNGs are accepted. The shared image cache is bounded to 32 MiB.
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
