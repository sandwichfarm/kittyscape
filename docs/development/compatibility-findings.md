# Implementation findings

Experiment and implementation date: September 15, 2026.
The [release record](/evidence/release.json) binds final results to the exact local
artifact. MacOS arm64 remains an open qualification gate.

## One native implementation

Kitty 0.38.1 and 0.48.2 load the shared Python package through a global watcher.
Bash, Zsh, and Fish native directory reports and prompt/command markers supply
the same input contract. No shell adapter is required for the qualified root
shell profiles.

## Directory-selected settings profiles

Kitty 0.38.1 and 0.48.2 expose `os_window_font_size`, `Boss._change_font_size`, and
`Window.patch_edge_width`. Native fixtures verified OS-window font ownership and pane-local padding/margin restoration.
Readback comparison prevents restoration over later external values. A process profile passes a bounded allowlisted
overlay through kitty's native parser, then applies only font and spacing through targeted native APIs. This avoids
rewriting or rereading daily config, prevents profile-file replacement between validation and application, avoids
triggering executable daily `geninclude` directives, and leaves unrelated external color/palette state intact.

`current_focused_os_window_id()` selects the process controller. `last_focused_os_window_id()` preserves it during
temporary application focus loss. Process activation releases scoped owners across the process; release reapplies each
still-selected scoped profile. X11 and Wayland fixtures cover two OS windows, pane changes, scoped/process transitions,
base-derived process transitions, unchanged prompt deduplication, and animated GIF playback.

The earlier `patch_colors` experiment changed all tab bars. Direct pane `ColorProfile` mutation avoids that side effect,
but no qualified hook observes every OSC and native palette writer. Scoped and process colors remain unsupported.

Immediate command-completion callbacks can precede the prompt-ready state and
the final directory report. A 20 ms coalesced callback reads the settled report,
then rechecks the active pane in the selected tab before and after asynchronous
file work. Inactive-pane reports cannot write another pane’s selection. OS
windows have independent state, including when they lack desktop focus.

Startup waits for the first reliable local report. Unknown schemes, remote
hosts, malformed encoding, disappeared directories, and lost reports produce a
bounded diagnostic and the applicable fallback. Native kitty URI paths preserve
literal percent signs, question marks, and hashes; standard file URIs are
percent-decoded.

Nested Bash did not inherit native reporting in the real fixture. Direct
nested interactive shells and known unsupported contexts therefore use a
latched fallback until explicit resume. Noninteractive subprocesses retain the
last reliable shell report. Nushell’s native reports were observed in a
separate PTY, but product graphical qualification is not claimed.

## Embedded Python and bounded work

The package loads from its own path under a unique module name. It does not
alter the process import path or generate bytecode inside the installed bundle.
The runtime uses Python’s standard library; Node belongs to site development.

Filesystem work runs outside UI callbacks. Only one job is submitted to the
worker, with the latest pending request retained per OS window/config action.
A five-second timeout retains the running handle, stops further collectors, and
rejects additional work until the reader finishes. A later event can recover.
Closing, pausing, or losing ownership discards pending window work.

Native kitty timers snapshot raw callback pointers before dispatch. Cancelling a
later timer inside that batch can free its callback too early; a minimal fixture
reproduced a native crash without loading Kittyscape. The compatibility module
keeps one stable dispatcher and cancels only its Python callback entry, allowing
the native one-shot to expire safely. Event bursts retain one timer per OS window.

Kitty’s native loop keeps Python’s interpreter lock between callbacks, so the
pending-work collector yields with `sleep(0)`. A successful image change posts
a main-loop wakeup so the renderer paints it without another shell command.
Removing an image from a transparent window also needs explicit screen damage.
Kittyscape refreshes only that OS window’s active pane after a successful write,
so an unfocused window repaints without requiring another command.
The real pixel-based fixture measures 100 transitions; a separate 60-second idle
fixture checks zero Kittyscape timers and image writes. See the release record
for the measured values and hardware rather than inferring timing from mocks.

The image cache is limited to 64 entries and 32 MiB of encoded data. PNG loading
validates container CRCs, encoding, dimensions, bounded decompression, scanline
lengths, and filters before calling kitty’s decoder. Rule images are limited to
16 MiB, 4096 pixels per dimension, 16 million pixels, and 64 MiB decoded data.

## Restoration and ownership

Kitty exposes whether an OS window has an image, but no getter for its exact
effective image bytes, selected list index, or layout override. Configured
filenames are insufficient for arbitrary preexisting GPU state.

The watcher captures known startup state and observes successful kitty-side
image writes in one compatibility module. It never changes shared defaults
during a directory event. On current kitty, restoring an inherited baseline
uses the recorded global image index, preserving kitty’s loaded image cache and
removing the temporary layout override. Ordinary reloads retain the observed
absolute index. The older runtime restores retained PNG bytes.

Successful external byte uploads provide a recoverable baseline and pause the
affected OS window. Explicit resume is required. Path-only custom writes,
oversized retained payloads, unknown existing windows, and relative index
increments cannot supply a trustworthy baseline and remain paused. Direct C
writers bypass the observation boundary and require manual coordination.

Normal option reloads and native dark/light theme changes have a separate
suspension boundary. Theme image updates replace the inherited baseline;
explicit manual pauses remain paused. Older kitty reloads preserve its existing
image bytes while adopting new rendering settings. Layout overrides are
preserved only where that kitty version implements them.

## Qualification tools and isolation

The graphical suite uses distinctive deterministic 1920×1080 PNG fixtures.
X11 runs on an explicitly reserved Xvfb display. Wayland requires a separate
Hyprland instance with a private runtime directory under `/tmp` and workspace 15
active inside that instance. The verifier refuses the daily compositor runtime
and never switches the operator’s workspace. `grim -T` exports only the exact
fixture toplevel.

Always reserve a known-unused test display explicitly. Refuse existing socket
or lock paths and clean up only the test process that the runner started.

Bash 5.3.20 was built from signed GNU sources and patches in a temporary
directory, after explicit permission. Older Bash/Zsh/Fish and portable kitty
binaries were extracted into temporary directories; no host package or default
shell was replaced. Exact identities accompany the release evidence.

## Sources

- [Watcher callbacks](https://sw.kovidgoyal.net/kitty/launch/#watching-launched-windows)
- [Native shell integration](https://sw.kovidgoyal.net/kitty/shell-integration/)
- [Kitty 0.38.1 source](https://github.com/kovidgoyal/kitty/tree/v0.38.1)
- [Kitty 0.48.2 source](https://github.com/kovidgoyal/kitty/tree/v0.48.2)
- [PNG specification](https://www.w3.org/TR/png-3/)
- [GNU Bash sources and patches](https://ftp.gnu.org/gnu/bash/)
- [Standard foreign-toplevel list protocol](https://wayland.app/protocols/ext-foreign-toplevel-list-v1)
