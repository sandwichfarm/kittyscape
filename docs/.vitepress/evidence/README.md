# Website verification

Verified September 15, 2026. These are local static-site results, not kitty runtime qualification.

## Results

- VitePress 1.6.4: root and `/kittyscape/` production builds passed without warnings.
- Static checks: 16 HTML pages and 537 internal links/assets per hosting base; no missing targets or fragments.
- Chromium 149.0.7827.55, Firefox 151.0, WebKit 26.5: each passed 30 route checks, 180 layout checks,
  and 210 axe-core 4.12.0 scans. All 15 content routes were checked at 320, 768, and 1440 px in both themes and bases.
- Zero serious/critical accessibility violations and zero reported color-contrast violations.
- Local search result navigation, keyboard skip/CTA navigation, mobile keyboard menu/theme control,
  JavaScript-disabled reading/navigation, reduced motion, and zoom-equivalent layout passed in each browser/base.
- No browser console errors, failed resource responses, or third-party runtime requests.
- TypeScript 6.0.2 checked the VitePress JavaScript configuration with `--checkJs`; Node syntax checks passed
  for the site configuration, theme entry, and browser/static-check scripts.
- Three JSON guide examples loaded through the actual configuration parser with temporary existing roots.
- Original terminal illustration: 2,461 bytes (1,059 gzip). Cat mark: 382 bytes (227 gzip).
  Custom theme source: 373 bytes gzip. Compiled landing page route: 1,150 bytes gzip in this build.
- Manually reviewed desktop, mobile, dark-mode, and documentation screenshots. Essential light control
  borders have 3.38:1 contrast; dark switch borders have 3.76:1 contrast.

The zoom check models a 1440-pixel window at 200% zoom using a 720 CSS-pixel viewport and scale factor two.
It does not automate browser chrome zoom commands, which headless Chromium did not apply.
Semantic roles, names, headings, and landmarks were checked; no live screen-reader application session is claimed.

## Commands

```sh
pnpm install --frozen-lockfile
pnpm docs:build
pnpm docs:build:subpath
pnpm docs:check
tsc --allowJs --checkJs --noEmit --module nodenext --target es2022 --skipLibCheck docs/.vitepress/config.mjs
```

The final complete browser run used the existing matching Playwright installation and browser cache:

```sh
WEBKIT_EXECUTABLE_PATH=/tmp/kittyscape-webkit-wxpv4ff1/webkit-launch.sh \
PLAYWRIGHT_PATH=/home/sandwich/.npm/_npx/e41f203b7505f1fb/node_modules/playwright-core \
AXE_PATH=/home/sandwich/.npm/_npx/0f94ee7615faf582/node_modules/axe-core/axe.min.js \
pnpm docs:test
```

The cached WebKit launcher overwrites `LD_LIBRARY_PATH`. A temporary wrapper recreated its own bundle-path
environment and added `/tmp/kittyscape-webkit-wxpv4ff1/usr/lib/x86_64-linux-gnu` for missing host libraries.
Official Ubuntu libicu74, libxml2, and libflite1 packages were extracted into that temporary directory after
their SHA-256 digests matched official package metadata. URLs and digests are in `webkit-library-provenance.json`.
No host packages or browser cache files were changed, and no browser binary was downloaded.

## Evidence files

- `static-results.json`: static link/asset and size checks.
- `browser-results.json`: complete unfiltered three-browser result.
- `configuration-examples.json`: JSON documentation examples checked against the parser.
- `webkit-library-provenance.json`: official temporary-library package sources and checksums.
- `artifact-manifest.json`: hashes of the verified production artifact files.
- `*-root-*` and `*-subpath-*`: current screenshots at specified widths and themes.
- `.omx/state/site/ralph-progress.json`: final visual verdict against the written site specification.

Early failed screenshots remain labeled `initial`, `revised`, or `failure` for diagnostic history.
Any later content or theme changes require a new production build and appropriate site checks.

## Search accessibility patch follow-up

The final production artifacts include `patches/vitepress@1.6.4.patch`, hash
`3052b445758b6a68fea67b8c0725bcc1dab315b09f71a124c0ec7a673b905666`.
The refreshed full site run again passed 540 responsive checks and 630 axe scans.
An additional 24 search flows and 96 empty/results/details/no-results axe states
passed in all three engines, both bases, 320/1440 widths, and both themes.
Proof: `/tmp/kittyscape-search-a11y-evidence/README.md`.

Exact native browser zoom is now verified separately, including WebKit at native
zoom level 2.0 with a fixed 1440x1000 window and 720 CSS-pixel content width. Combined
evidence is `/tmp/kittyscape-browser-zoom-webkit-native-h68e5p0k/final-zoom-evidence.json`.
The earlier viewport-scale check above remains accurately labeled.
