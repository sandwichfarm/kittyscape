# Actions

The installed configuration exposes lifecycle actions through a local kitty kitten. They apply to OS windows
in the current kitty process. Separate kitty processes keep separate state.

## Default keyboard controls

| Keys | Action |
| --- | --- |
| Ctrl+Shift+F6 | `status` |
| Ctrl+Shift+F7 | `pause` |
| Ctrl+Shift+F8 | `resume` |
| Ctrl+Shift+F9 | `reload` |
| Ctrl+Shift+F10 | `restore` |

Review these bindings during [installation preview](../guide/installation.md), especially if your configuration
already uses those keys. Status opens in a scrollback overlay so it does not print over the shell prompt.

## Lifecycle contract

| Action | Purpose | Failure and recovery |
| --- | --- | --- |
| `status` | Report diagnostic reason, pending work, active panes, image ownership, profile mode/controller, transition count, restoration state, and upload counts. | A missing report or unsupported profile is a diagnostic, not a support claim. |
| `reload` | Asynchronously validate `kittyscape.json`, refresh the image cache, and re-evaluate active contexts. | Malformed rules retain the last valid configuration. Fix the file and reload again. |
| `pause` | Restore owned baselines, then pause the instance, including windows opened later. | Windows changed by another writer keep that writer’s image. |
| `resume` | Resume using a known baseline captured at startup or an observed external write. | A window with an unknown baseline stays paused. Resume never guesses GPU state. |
| `restore` | Restore owned baselines and pause the instance, exactly like `pause`. Useful before removal. | Never overwrite a background installed by another writer. |

Setting `enabled` to `false`, then reloading, restores owned images and disables automatic switching.
Reload and disable do not rewrite `kitty.conf`.

A failed image restore remains labeled `restore-failed`. A failed profile restore is labeled
`profile-restore-failed`; ownership remains available for explicit `restore` or `reload` retry. Resume, reload, or a
changed directory can retry a transient apply failure. Unchanged prompts do not repeat failed writes or reloads.

Status includes a bounded, privacy-safe `detail` for configuration errors, such as a JSON line/column or
`rules[0].image`. A `filesystem-timeout` stops collection after five seconds, with the running read retained
as `filesystem_stalled`. No additional work is submitted behind it. Once the read finishes, a new event or
reload can recover.

## Ownership changes

An observed external background write pauses the affected OS window. Other OS windows keep their own state.
An explicit resume can continue when a current baseline is known. Unknown or ambiguous baselines stay paused
until a qualified startup/configuration establishes one.

The [runtime findings](../development/compatibility-findings.md) record the action behavior established in graphical tests.

## Privacy

Normal diagnostics are bounded and omit local directory names, usernames, image paths, and command lines.
The graphical test harness deliberately records fixture paths; review any additional logs before sharing.
Diagnostic actions use the local kitty process and need no remote-control listener.
