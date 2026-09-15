# Troubleshooting

Start with the [tested compatibility rows](../reference/compatibility.md) and the [status action](../reference/actions.md).
Diagnose an isolated kitty instance before changing a daily-use configuration.

## Symptoms and recovery

| Symptom | Check | Recovery |
| --- | --- | --- |
| No image change after `cd` | Is native shell integration reporting a fresh local directory? Is the pane active? | Verify [shell setup](./shells.md) and the rule root. Do not infer shell state from a running program. |
| A nested directory gets the parent image | Does the deeper rule normalize to the directory being visited? | Check physical paths and remove duplicate roots; [reload valid rules](./configuration.md#reload-safely). |
| The image works only from one directory | Is the image path relative to the JSON file, and does that file exist? | Put the image at the configured local path or correct the path. |
| Reload reports invalid configuration | Unknown field, duplicate root, schema version, malformed JSON, or wrong value type. | Fix the named validation problem. The last valid configuration remains active. |
| Image cannot be read | File access, PNG validity, dimensions, size, or a vanished file. | Use a readable PNG within the [limits](../reference/configuration.md#images). Avoid changing global permissions. |
| Image changes in the wrong window | Active-pane targeting or stale event handling has failed. | Pause the affected instance and report a sanitized reproduction. This is not expected supported behavior. |
| The original image does not return | Baseline profile or ownership cannot be established. | Stop automatic updates and inspect [restoration limits](./kitty-settings.md#restoring-the-baseline). Do not clear a valid original image. |
| Status says `baseline-unknown` after manual setup | The OS window existed before the watcher loaded, or an external writer’s exact image is unknown. | Follow the [existing-windows requirement](./installation.md#existing-windows). Resume cannot reconstruct unknown image state. |
| A fallback displays but an image error remains | A matching rule’s image failed even though the fallback is usable. | Fix the rule image and reload. A normal unmatched-directory fallback has no image-error reason. |
| Switching pauses after another tool runs | Another background writer may have taken ownership. | Choose one owner and follow the documented explicit resume workflow. |
| A remote or multiplexer directory is ignored | That context is not qualified for automatic reporting. | Use a normal kitty background in that context. |
| Setup finds an existing owned-name file | A user file or previous installation conflicts. | Keep the file. Review preview/rollback information before any replacement. |
| Status says `filesystem-timeout` | A local filesystem operation did not finish within five seconds. | Restore normal access to the file or directory, then issue a new event or reload. Queued work stays bounded and no idle collector continues. |
| Pause reports `restore-failed` | The original image could not be applied. | Keep the installation intact, fix the cause, and retry restore before removal. Ownership remains held so recovery is possible. |

## Useful diagnostic details

Record the Kittyscape artifact identity, kitty version, shell/version, OS/architecture/display backend,
configuration profile, and the shortest sequence that reproduces the problem.
Include whether focus, a theme reload, or another writer ran before the failure.

Default diagnostics omit directory names, usernames, image paths, and command lines.
Additional test or kitty logs can disclose local paths; inspect them before sharing.
Use neutral example paths such as `/example/Project One`, and remove credentials and unrelated command history.

## Keep a usable terminal

Rule and image failures appear in status while the shell remains usable. If a failure interrupts the prompt,
pause/restore, then use [removal and rollback](./uninstall.md).
Do not enable unrestricted remote control or install unrelated software as a troubleshooting shortcut.
