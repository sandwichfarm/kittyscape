# Kittyscape: product requirements

Status: proposed, planning only. Date: September 15, 2026.

## Outcome

Give each project a recognizable kitty background without changing how the terminal renders images.
One configuration should work across supported shells. Setup and removal should be understandable and reversible.
A small, cute landing page should introduce the project and lead directly into complete VitePress documentation.

## Requirements from the user

- Dynamically choose backgrounds based on the current directory.
- Retain kitty background image configuration and rendering preferences.
- Support multiple shells and pursue broad compatibility.
- Document installation, usage, compatibility, and troubleshooting.
- Include a simple, minimalist, cute landing page linking to VitePress docs.
- Produce plans now; write no application, website, configuration, or test code.

## Product behavior

### Directory and focus

- Track the interactive shell’s last reliable directory, not transient directories of subprocesses.
- Within each kitty OS window, the selected tab’s active pane determines its image.
- Focus changes re-evaluate the destination pane even when its shell has not run a command.
- Activity in an inactive tab or pane must not change the visible background.
- Separate OS windows retain independent backgrounds, including unfocused OS windows.
- On startup, wait for trustworthy directory information; retain the existing background until then.
- Unknown, remote, or unsupported contexts use the fallback policy and expose a diagnostic reason.

### Rules

- User-owned central configuration maps absolute directory roots to local image paths.
- A rule applies to its directory and descendants; the deepest matching directory wins.
- Match path components, so a rule for “app” does not match “application”.
- Reject duplicate normalized roots rather than relying on file order.
- Use physical, normalized local paths for both rules and directory reports; document symlink behavior.
- Resolve relative image paths against the configuration directory, never the shell’s current directory.
- Unmatched directories restore the applicable original kitty background, including no image.
- Provide an optional explicit fallback image for users who want one; restoration remains the default.
- Do not execute or automatically load configuration from visited repositories.

### Preservation and failure

- Change only the runtime image; preserve layout, interpolation, tint, gap tint, opacity, and theme colors.
- Do not rewrite kitty.conf or shell startup files during ordinary operation.
- Never change the configured image for future windows as a side effect of a directory event.
- Skip repeated application when the effective image and relevant rendering context have not changed.
- Missing, invalid, or oversized images use the fallback policy and a bounded diagnostic.
- Failure to apply an image leaves the existing usable terminal intact and never prints over the prompt.
- Disable and uninstall restore the captured baseline only for windows still owned by Kittyscape.
- If another tool takes ownership, stop automatic writes until explicit resume; see the architecture gate.

## Acceptance criteria

| ID | Observable requirement |
| --- | --- |
| R01 | Entering a configured directory or descendant selects its image; leaving restores the fallback. |
| R02 | Identical rules produce identical selections in Bash, Zsh, and Fish on each released supported platform. |
| R03 | Nested, unrelated, Unicode, space-containing, and symlinked paths follow the documented matching policy. |
| R04 | Switching tabs or panes updates the correct OS window; inactive-shell events never override it. |
| R05 | Two OS windows with different active directories display independently selected images. |
| R06 | Runtime and persistent rendering settings remain unchanged through switching, errors, and restoration. |
| R07 | No-image, single-image, and any claimed multi-image/theme defaults restore correctly. |
| R08 | Unsupported capabilities are reported before enablement, without installing or altering unrelated software. |
| R09 | Installation and removal pass a preview, apply, repeat, and rollback check without losing user content. |
| R10 | Missing files, malformed rules, permission errors, and lost directory reports do not interrupt shell use. |
| R11 | Repeated unchanged events perform zero additional image uploads after the first successful application. |
| R12 | Quickstart, reference, troubleshooting, compatibility, and uninstall docs match tested behavior. |
| R13 | Landing-page documentation links work at both a domain root and a repository subpath. |
| R14 | Landing page and docs pass keyboard, contrast, reduced-motion, zoom, and mobile-width checks. |
| R15 | Every “supported” platform/shell/version claim links to release-specific test evidence. |

## Proposed scope

First release target: Linux and macOS, Bash/Zsh/Fish, local directory rules, static images, native kitty windows/tabs/splits.
PNG is the baseline image format. Additional formats require capability checks and test evidence.
Exact minimum kitty and shell versions are outputs of the compatibility experiment, not assumptions.

Nushell and other shells are extension targets through a documented reporting contract.
SSH, containers, tmux, and Zellij require explicit qualification; do not market them as supported by default.
Native Windows support, other terminals, animated backgrounds, image generation, HTTP image serving,
wallpaper downloads, automatic color themes, project-local executable hooks, and a GUI settings app are outside version 1.

## Nonfunctional targets

These are future measurement targets, not current performance claims:

- Warm local rule selection: p95 below 10 ms for 1,000 rules on a recorded reference machine.
- Correct displayed image: p95 within 250 ms of a reliable directory/focus event with local 1080p PNG fixtures.
- No periodic polling in the preferred integration path and no helper process spawned per prompt.
- Normal operation is offline, with no telemetry or persistent directory history.
- Runtime uses kitty’s Python environment and standard library where feasible; Node is for website development only.

## Completion boundary

Version 1 is complete only after the supported matrix, actual kitty runtime behavior, reversible installation,
documentation, and landing page pass the linked test specification. A local unit-test pass is insufficient.
Public release and deployment remain separate delivery actions requiring a chosen repository and host.
