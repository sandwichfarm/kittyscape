# Website and artwork

The landing page and documentation are one static VitePress site. Search runs in the browser using a local index.
The site makes no analytics, external font, image, or search-service requests. Search queries are not persisted.

## Build locally

Website development needs Node.js and the pinned package manager. The extension’s runtime does not need Node.js.

```sh
pnpm install --frozen-lockfile
pnpm docs:dev
```

Build and validate both hosting layouts:

```sh
pnpm docs:build
pnpm docs:build:subpath
pnpm docs:check
pnpm docs:test
```

The root artifact is `docs/.vitepress/dist/`. The `/kittyscape/` artifact is `docs/.vitepress/dist-subpath/`.
Both are static files.

## GitHub Pages

`.github/workflows/deploy-pages.yml` deploys the `/kittyscape/` artifact after a
push to `main` or a manual run on `main`. The landing page resolves at the
project Pages root, and the documentation entry point resolves at `/docs/`
relative to that site. For this repository, those URLs are
`https://sandwichfarm.github.io/kittyscape/` and
`https://sandwichfarm.github.io/kittyscape/docs/`.

Before the first deployment, select **GitHub Actions** as the Pages publishing
source in the repository’s Pages settings. Pull requests build through local and
CI checks but do not deploy a preview site. The workflow keeps one deployment in
flight and publishes only the validated static artifact.

Browser checks use an existing Playwright installation. Set `PLAYWRIGHT_PATH` to its module path if it is not
available at `/usr/lib/node_modules/playwright`. Browser binaries must already be installed.
The verifier records unavailable browsers as a failed acceptance gate, rather than downloading them.
Accessibility checks use an existing `axe-core` installation. Set `AXE_PATH` to its `axe.min.js` file when
it is outside the normal module path. Neither test tool is added to the runtime bundle.
For an isolated WebKit library wrapper, set `WEBKIT_EXECUTABLE_PATH` to that existing launcher.
The headless suite includes a 720 CSS-pixel viewport at scale factor two as a layout check.
Native browser zoom is verified separately:

```sh
node tests/site/zoom.mjs
python tests/site/webkit_zoom.py
```

Run these sequentially: both reserve display `:103`, verify ownership, and refuse existing display resources.
The first uses native keyboard input in Chromium, Firefox, and WebKit. WebKit’s MiniBrowser shortcuts reach
207.36%, so that script retains an unverified exact-200% row. The second uses WebKitGTK’s public zoom API
to set exactly `2.0`, checks the resulting CSS viewport and native window dimensions, and records its own proof.
Read the combined evidence in the [release record](/evidence/release.json).

These native runners use the existing browser and library paths recorded in their source. Confirm those
paths and prerequisites on another machine. They create their test state under `/tmp` and leave desktop
configuration and installed browser files intact. Keep both built artifacts unchanged while a run is active.

To rerun only a failing browser during development, use `node tests/site/browser.mjs firefox`, for example.
Final acceptance includes the full headless suite and native zoom/keyboard evidence; filtered runs are labeled.

## Dependency choice

On September 15, 2026, the npm registry’s stable VitePress release was **1.6.4**, published August 5, 2025.
The `next` release was a prerelease, so this project pins the stable release.
The installed **pnpm 11.3.0**, published May 24, 2026, is pinned in `package.json`.
Dependency resolution uses a seven-day minimum release age.

The theme and search APIs were checked against the
[VitePress 1.6.4 source](https://github.com/vuejs/vitepress/tree/v1.6.4).
The theme imports `theme-without-fonts`; all typography uses the visitor’s system fonts.

The pinned dependency patch in `patches/` corrects local-search semantics and the theme switch’s initial
accessible name. Keep the patch, `pnpm-workspace.yaml`, and `pnpm-lock.yaml` together when copying the source
bundle. The existing upstream MIT notice is preserved.

## Asset provenance

| File | Origin | Use |
| --- | --- | --- |
| `docs/public/cat-mark.svg` | Original paths authored for Kittyscape on September 15, 2026. | Navigation mark and favicon. |
| `docs/public/terminal-cat.svg` | Original vector landscape, terminal, and resting cat authored for Kittyscape on September 15, 2026. | Static landing illustration. |

The artwork does not copy kitty’s mascot and contains no fetched or third-party artwork.
The terminal scene is an illustration, not evidence of a running extension.
The cat itself is decorative. The image’s text alternative describes the terminal scene.

A project license has not been selected. Publication still requires a licensing decision and review of
the bundled dependency notices. The local artwork’s provenance does not grant a publication license.

## Design constraints

Warm ivory, charcoal, muted sage, and small peach accents carry the visual design. Dark mode uses warm dark
surfaces. The layout keeps a 960 px home content width, fine borders, modest radii, and one illustration shadow.
There is no decorative animation. Reduced-motion settings suppress inherited theme transitions.

Browser checks cover navigation, open local-search states, light/dark mode, mobile overflow, keyboard focus,
zoom, JavaScript-disabled reading, and third-party requests. Site screenshots establish presentation;
kitty runtime behavior has its own [qualification record](../reference/compatibility.md).
