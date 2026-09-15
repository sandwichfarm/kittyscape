# Kitty theme switching decision

## Verdict

**NO-GO for Kittyscape-managed manual or directory-selected themes in this expansion.**

The native two-OS-window prototype ran on kitty 0.48.2:

```sh
python tests/runtime/extended.py --kitty /tmp/kittyscape-tools/kitty-0.48.2/bin/kitty \
  --shell /usr/bin/bash --backend x11 --case theme-local-scope
```

Evidence: `/tmp/kittyscape-extended-m8y3yrqp/result.json`.

`kitty.colors.patch_colors(..., configured=False, windows=(target,))` scopes terminal profiles but patches every tab
manager's tab bar and OS-window chrome. The prototype observed both tab bars change. That violates the required
per-OS-window isolation and exact restoration contract, including directory selection and GIF playback interactions.

## Boundary

Kittyscape does not parse or execute theme configuration, call `kitten themes` on directory events, download themes, or
add a theme field to rules. Includes, commands, fonts, keymaps, shell integration, remote control, environment expansion,
image settings, and remote inputs remain disallowed. No network or dependency is introduced.

Users can manually run Kitty's own theme or `set-colors` commands. Kittyscape treats those as external ownership changes;
it does not try to reconstruct arbitrary palette state. `set-colors --reset` is global startup reset, not restoration.

## Reconsideration contract

Re-open only under separate approval after kitty provides a reversible per-OS-window tab/chrome API, or a prototype proves
target-only snapshot/restore for panes, default/palette sentinels and tab chrome. It must cover new panes, OSC and remote
color writers, OS theme/config changes, failed restoration, and animated backgrounds on both target kitty versions. macOS
is unqualified.
