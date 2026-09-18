# Directory profile execution receipts

Artifact: `kittyscape-0.2.0.dev0.tar.gz`

- Digests and byte counts: `dist/ARTIFACTS.json` and `dist/SHA256SUMS`
- Manifest files verified by installed harness: 85
- `make check`: 110 unit tests and 40 installation tests passed.
- VitePress root/subpath builds passed; `docs:check` validated 18 pages and 641 links/assets per base.
- Native matrix: 12/12 passed. Kitty 0.38.1 and 0.48.2; X11 and Wayland; Bash, Zsh, and Fish.
- Native scenario: two OS windows, multiple panes, scoped/process transitions, process arbitration, base-derived reload,
  unchanged-prompt deduplication, restoration, and animated GIF playback.
- Extracted artifact: profile scenario passed; installed harness passed install preview/apply/repeat, runtime origin,
  configuration selection/restoration, uninstall preview/apply/repeat.
- macOS: open; no test Mac available.

Machine-readable evidence:

- `native-matrix.json`
- `installed-x11.json`
