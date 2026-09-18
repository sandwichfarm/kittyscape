# Directory profile plan

## Contract

Rules may select one profile mode: `scoped` or `process`. Both modes reject
conflicts before native writes. Existing image rules remain valid.

```json
{
  "version": 1,
  "profiles": {
    "focus": {"mode": "scoped", "font_size": 13.0, "padding": 8, "margin": 4},
    "presentation": {"mode": "process", "config": "profiles/presentation.conf"}
  },
  "rules": [{"directory": "~/Talk", "image": "talk.gif", "profile": "presentation"}]
}
```

`scoped` supports only native runtime fields proven scoped. `process` accepts a
data-only allowlisted overlay file under the Kittyscape config root. Profile
selection never accumulates: resolver returns one effective profile for deepest
rule. Missing profiles, mode conflicts, invalid fields, unsafe overlay lines,
and reference-like fields fail during config load. Schema has no profile-to-profile references, so cycles cannot form.

## Slices

1. Probe kitty 0.38.1/0.48.2 APIs and write capability matrix.
2. Add profile schema, resolver selection, parser tests, conflict tests.
3. Add scoped adapter with baseline/ownership tests.
4. Add process overlay parser, base-derived reload transaction, arbitration.
5. Add isolated native X11/Wayland tests, docs, artifact checks, review.

## Acceptance

- scoped/process transitions restore owned values and cancel stale playback.
- process profile applies once per selected identity and preserves watcher/action
  lifecycle.
- external writes win; unchanged prompts produce no write or reload.
- private native runs prove two OS windows/multiple panes. macOS stays open.
