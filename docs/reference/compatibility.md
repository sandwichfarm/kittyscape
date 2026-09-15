# Compatibility

**0.1.0.dev1 is an experimental local build.** MacOS arm64 qualification remains
open, as requested. Capability checks and a version floor do not establish
support for every intervening release.

## Linux qualification

The release record identifies the archive SHA-256, exact executables, embedded
Python versions, graphical backend, baseline profile, scenario results, and
screenshots for each row. A row is qualified only when its recorded archive
matches the artifact being evaluated.

[Read the release evidence](/evidence/release.json).

| Shell | Older version selected for qualification | Current version selected |
| --- | --- | --- |
| Bash | 5.2.15 | 5.3.20 |
| Zsh | 5.9 | 5.9.2 |
| Fish | 3.6.0 | 4.9.3 |

The matrix runs each shell version with kitty **0.38.1** and **0.48.2**, on
Linux x86_64 **Wayland** and **X11**. The Wayland fixture uses Hyprland; X11 uses a
separate Xvfb server. The extension itself does not depend on either compositor.
The machine-readable record is authoritative for executed rows and open gates;
this table describes the matrix, not an untested version range.

Kitty 0.38.1 supplies embedded Python 3.12.3. The portable 0.48.2 build supplies
3.14.6; the separately exercised Arch 0.48.2 build supplies 3.14.7. Runtime
imports, graphical behavior, and installation are tested inside kitty.

Bash 5.3.20 was built solely in a temporary directory after explicit approval.
Its GNU source archive and all twenty patches passed detached-signature checks.
The system shell was not replaced. Zsh and Fish current-version checks and
older Debian binary identities are recorded with the release evidence.

## Qualified behavior and profile limits

- Native directory and prompt reports are required. Bash, Zsh, and Fish share the
  same resolver; shell names alone do not prove integration is working.
- Normal no-image and PNG baselines, directory matching, tabs, splits, and
  independent OS windows have graphical fixtures.
- Current kitty supports tracked inherited image lists and observed absolute
  indices. Ordinary config reload keeps the selected index. Relative index
  changes cannot be reconstructed reliably and leave the window paused.
- Current dark/light automatic themes have a dedicated reload boundary.
  A theme change refreshes its inherited baseline; an explicit manual pause
  remains paused.
- A remote-control image upload supplies recoverable original bytes. A custom
  Python writer that supplies only a path leaves an unknown baseline: kitty does
  not expose the exact bytes it loaded. Resume refuses that profile.
- Original bytes are retained for the older kitty baseline. Its ordinary config
  reload keeps the previously displayed image, matching that kitty runtime's
  behavior, while rendering settings follow the reload.
- Rule images are static local PNGs within the documented
  [limits](./configuration.md). Additional formats are not qualified.

These outcomes are specific to the recorded fixtures. Direct C background
writers, unknown preexisting image state, and other unobserved profiles require
the [pause/change/resume workflow](../guide/kitty-settings.md).

## Unsupported automatic contexts

SSH, tmux, Zellij, containers, and nested interactive shells are not qualified
automatic contexts. Known unsupported launch environments and direct commands
use fallback and a diagnostic. Command detection cannot discover arbitrary shell
aliases or wrappers: pause before entering one of these contexts, leave it, and
explicitly resume from a local integrated shell.

Nested Bash was tested and does not inherit reliable native reports in the
default fixture. Kittyscape retains the unsupported-context latch after exit
until explicit resume. Noninteractive `bash -c` commands and ordinary arguments
such as `echo ssh` do not cause that latch.

Nushell 0.115.1 emitted native OSC 7 and OSC 133 reports in a disposable PTY.
It remains unqualified in the product; no shell adapter or graphical support
claim is shipped for it.

## Open platform gates

| Target | Status |
| --- | --- |
| macOS arm64, all three baseline shells | No test Mac available; release gate explicitly left open. |
| macOS system Bash 3.2 | Kitty's [native integration gate](https://github.com/kovidgoyal/kitty/blob/v0.48.2/shell-integration/bash/kitty.bash#L93) rejects Bash below 4; no adapter is shipped or qualified. |
| macOS Intel / Linux arm64 | Follow-up qualification; no architecture-specific graphical evidence. |
| Native Windows / other terminals | Outside this release scope. |

A Linux or unit-test pass does not close the macOS gate.
See [implementation findings](../development/compatibility-findings.md) for
the source/API decisions and [release checks](../development/release-checklist.md)
for the remaining publication boundaries.
