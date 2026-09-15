# Final focused frontend verification

Both site bases build successfully. Each contains 17 HTML pages and passes 603 local link/asset checks.
Node syntax checks and the VitePress configuration type check pass.

The focused browser matrix covers Contributing and Compatibility findings in Chromium 149.0.7827.55,
Firefox 151.0, and WebKit 26.5, at 320/768/1440 pixels, light/dark, root/subpath.
All 72 layout checks, 72 axe 4.12.0 scans (zero violations), and 72 local-search navigation flows pass.

The 33 frontend inputs differ from the previous 17c verification in exactly two files:
`docs/contributing/index.md` removes the volatile test count; `docs/development/compatibility-findings.md`
adds three lines describing scoped repaint. All 31 other inputs are byte-identical, including the pinned
search accessibility patch, custom theme, styles, SVGs, package lock, and browser harness.

All 120 built files remained byte-identical throughout this focused run. The snapshot contains 116
rendered HTML/JS/CSS/SVG files and 118 stable non-evidence files. `hashmap.json` is included in the
stable comparison; only the evidence subtree is excluded. Content hashing changed references and
asset filenames after the prose changes; 58 JS files, all four CSS files, and all four SVG files retain
the previous build's exact bytes. See `rebuild-output-comparison.json` for the full path lists.

Use `tested-asset-fingerprints.json` as the baseline for the parent's data-only evidence rebuild.
Compare both the exact path set and hash/byte values under `stable_non_evidence_files`.
`frontend-input-fingerprints.json` binds these outputs to the source. `result.json` records the archive
observed at completion separately, without implying runtime qualification from frontend tests.

This stage made no repository source edits and ran no headed browsers, native zoom reruns, or live
screen-reader session. The earlier full browser/native proof is referenced from `result.json`.
