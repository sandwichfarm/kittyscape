# Kittyscape: landing page and documentation plan

Status: design specification only. No site source or assets exist yet.

## Direction

Simple, minimalist, and cute. A quiet utility page with a small cat and a terminal scene.
Use one VitePress site for both the landing page and docs, with a lightly customized default theme.
VitePress supports a home layout and Markdown documentation, so a second frontend application is unnecessary.
See [research](research-kittyscape.md) for upstream references.

## Landing page composition

1. Compact navigation: cat mark + Kittyscape, Docs, GitHub when a real repository exists, theme toggle.
2. Hero: “Kittyscape” and “A different view for every directory.”
3. One explanatory sentence: “Directory-aware backgrounds for kitty, with your image settings intact.”
4. Primary action: “Read the docs”, linking to the getting-started page. Secondary: “See compatibility”.
5. One small terminal illustration: a project path, a landscape background, and a resting cat at the edge.
6. Three short benefits: follows your directory; keeps your kitty settings; works across supported shells.
7. A restrained footer with documentation, source, release, and actual license links when available.

Avoid pricing, testimonials, counters, mailing lists, badges suggesting nonexistent support, and long feature grids.
Before release, show “In development” and describe capabilities as planned. Do not publish fictional install commands.

## Visual specification

- Warm ivory canvas, dark charcoal text, muted sage primary accent, restrained peach details.
- Dark mode uses warm near-black surfaces and softened accent colors; maintain readable text contrast.
- One self-authored cat outline with a tail that echoes a terminal prompt; no mascot copied from kitty or other projects.
- System sans-serif for prose and system monospace for terminal text; no external font requests.
- Main content around 960 px maximum width, generous whitespace, modest 8–12 px corner radii.
- Flat surfaces, fine borders, and one subtle shadow under the terminal illustration.
- No gradient blobs, glass effects, oversized feature cards, or decorative motion required to understand the page.
- Local, license-cleared illustration assets; record provenance before publication.

Prefer a static illustration initially. A later two-state demo may switch between two sample directory/background pairs
on explicit button activation. It must work with keyboard input and provide a static reduced-motion experience.
An illustration must not be presented as a screenshot proving runtime behavior.

## Proposed routes and future files

All paths here are planned source files under docs/; route paths are relative to the configured site base.

| Source | Route | Purpose |
| --- | --- | --- |
| index.md | / | Landing page. |
| guide/getting-started.md | /guide/getting-started | Prerequisites, supported installation, first two directory rules, verification. |
| guide/installation.md | /guide/installation | Linux/macOS, manual/helper methods, previews and backups. |
| guide/configuration.md | /guide/configuration | Configuration location, matching, images, fallback, symlinks. |
| guide/shells.md | /guide/shells | Bash/Zsh/Fish setup and validated additional-shell adapters. |
| guide/kitty-settings.md | /guide/kitty-settings | Preserved settings, tabs/splits, themes, reload, external writers. |
| guide/troubleshooting.md | /guide/troubleshooting | Symptom → diagnostic → remedy; permissions and missing events. |
| guide/uninstall.md | /guide/uninstall | Pause, restore, remove owned files/entries, rollback verification. |
| reference/compatibility.md | /reference/compatibility | Exact tested matrix and unsupported contexts. |
| reference/configuration.md | /reference/configuration | Schema fields, defaults, validation, path semantics, limits. |
| reference/actions.md | /reference/actions | Only shipped controls and their failure behavior. |
| contributing/index.md | /contributing/ | Local setup, tests, runtime fixtures, contribution and release rules. |
| releases.md | /releases | User-visible changes and compatibility changes. |

Future site setup lives in docs/.vitepress/ with small theme overrides and local assets in docs/public/.
Use VitePress local search, a stable sidebar, readable code blocks, and previous/next navigation.
Keep core content and documentation links readable without JavaScript.

## Documentation contracts

- Each feature documents purpose, prerequisites, expected result, limitations, and recovery.
- Explain OS windows versus kitty panes early, with one small diagram if useful.
- Explain the difference between changing an image and changing opacity, tint, or theme.
- Every supported shell has a copy-tested setup path; do not label shell-specific snippets as universal shell syntax.
- Use examples with paths containing spaces and a nested rule, including exit-to-default behavior.
- Diagnostic examples use anonymized paths and do not encourage publishing secrets or directory history.
- Getting started links to compatibility and uninstall before any setup changes.
- Document restore/pause/resume and coexistence with theme or wallpaper tools truthfully.
- Never publish planned behavior as a shipped reference page without implementation evidence.

## Site acceptance

- All navigation, search results, sidebar items, fragments, and CTAs resolve in root and subpath deployments.
- No broken internal links, generated warnings, missing assets, or browser console errors.
- Test widths 320, 768, and 1440 px; no page-level horizontal overflow. Code blocks may scroll independently.
- Keyboard-only navigation, visible focus, skip link, meaningful heading order, and 200% zoom pass.
- WCAG AA contrast target: 4.5:1 normal text, 3:1 large text and essential UI boundaries.
- Decorative mascot is hidden from assistive technology; informative imagery has meaningful alternatives.
- Light/dark mode and reduced motion pass in Chromium, Firefox, and WebKit.
- Search is local; no analytics, external font loads, or runtime third-party network calls.
- Target landing illustration at or below 150 KB and additional custom JavaScript at or below 10 KB gzip.
- Automated accessibility checks have zero serious/critical issues; manual checks remain required.

## Build and hosting plan

Use the stable VitePress release selected at implementation time, respecting the workspace dependency cooldown.
The upstream website currently exposes prerelease documentation; verify stable-version APIs before coding.
Pin the package-manager version and commit a lockfile when implementation is authorized.
Build a static artifact; validate links with a non-root base before selecting a host.
GitHub Pages is a reasonable future option, but no repository, domain, or deployment is assumed or created now.

## Risks and mitigation

Keep custom theme code small to avoid VitePress upgrade friction. Use local search to avoid credentials and services.
Measure image weight instead of adding animated media by default. Couple support badges and install examples
to the release evidence so the landing page cannot overstate compatibility.
