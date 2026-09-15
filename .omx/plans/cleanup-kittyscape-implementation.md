# Bounded implementation cleanup

Scope: only files added during this implementation. Original README/plans remain
the delivery contract; updates to product documentation must describe implemented
behavior and exact qualification evidence.

Behavior lock: current unit/config/PNG/event/ownership regressions; installer
roundtrip and preservation tests; real current/older kitty core scenarios; current
X11 pixel-based 100-transition performance and 60-second idle observation.

1. Delete unused imports and temporary debugging branches from production/test code.
2. Separate long event/selection decisions at existing responsibility boundaries
   until runtime functions satisfy the workspace complexity limit. Preserve the
   event generation checks, ownership state, and last-valid configuration contract.
3. Simplify PNG/container guards and report decoding without introducing dependencies
   or expanding supported profiles.
4. Keep website custom code and installer logic unchanged unless a concrete redundant
   or dead path is found. Review those separately from writing the cleanup.
5. Run unit and installation suites, static AST policy checks, then repeat final
   graphical and website gates against the packaged artifact.

Parent owns engine/watcher/qualification cleanup. A bounded helper may own
compat/images/action simplification. The final architect review is separate from
implementation; repeat a changed-files cleanup audit after that review, as required
by Ralph, before final regression verification.
