# Desktop socket recovery during qualification

An early Xvfb automatic display-selection experiment used display 0 and left a
conflicting filesystem socket at `/tmp/.X11-unix/X0`. Its temporary process ended.
The desktop's existing Xwayland process and listener `/tmp/.X11-unix/X0_` remained
live. A direct connection to X0 failed while X0_ succeeded.

The stale X0 socket was quarantined at
`/tmp/kittyscape-x11-experiment/replaced-X0.socket`. X0 was restored as a symlink
to the existing X0_ listener. A real `libX11.XOpenDisplay(":0")` then passed.
No compositor or Xwayland process was restarted, and no desktop config was edited.

Keep the live X0 link and X0_ listener intact. All subsequent tests use explicit,
checked Xvfb displays 101/102/103. The final handoff must verify desktop X11
connectivity again and report the recovery honestly. This operational note is
not part of the distributable source bundle.
