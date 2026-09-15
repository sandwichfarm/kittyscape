# Independent review — request changes

Two independent review lanes returned **REQUEST CHANGES / BLOCK**.

Fixed during review:

- Fallback media now rebuilds a top-level fallback selection instead of retaining broken rule options.
- Shared interpolation releases on no-match restoration as well as explicit restore/external/close paths.
- Tint and gap-tint are rejected at parse time; the native API probe proved they cannot be safely applied while preserving configured image lists.
- The theme decision is included in this worktree and future artifacts.
- Playback uses a monotonic source timeline and skips late frames under the FPS ceiling; an explicit unit regression covers a delayed frame choice.

Open blocking findings:

1. The converter now emits bounded concatenated PNGs on stdout; Kittyscape parses and validates the sequence in the parent. The owned ImageMagick policy disables disk cache/delegates and bounds memory/map/area at 256 MiB. Native artifact evidence: `/tmp/kittyscape-qualify-ci9wxcql`.
2. The worker uses a host system Python launcher because kitty's embedded `sys.executable` starts another kitty process; this diverges from the desired launcher contract.

Do not treat this expansion as merge-ready until those findings are resolved and re-reviewed.
