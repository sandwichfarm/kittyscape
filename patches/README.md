# VitePress 1.6.4 accessibility patch

`vitepress@1.6.4.patch` is applied through `pnpm-workspace.yaml` and bound to its
content hash in `pnpm-lock.yaml`. Keep all three files in source artifacts.
It changes two upstream default-theme components; VitePress remains pinned to 1.6.4.

## Search semantics

`VPLocalSearchBox.vue` exposes the overlay as a named modal dialog and the input
as a named combobox with a listbox. Each result anchor owns its option role,
identity, and selected state. Its surrounding list item is presentational.
This removes the nested button/control and option/link structures reported by axe.
The footer’s labeled keyboard glyphs have an image role so their accessible names
are valid; a plain `kbd` does not support those naming attributes.

Result options use `tabindex="-1"`: Arrow keys change the active descendant while
DOM focus stays in the input, and Enter navigates to the selected result. Tab
visits the dialog controls. Pointer links, detailed excerpts, existing keyboard
handlers, Escape, backdrop dismissal, classes, and styles remain in place.
The structure follows the [WAI-ARIA combobox pattern](https://www.w3.org/WAI/ARIA/apg/patterns/combobox/).

## Initial switch name

`VPSwitchAppearance.vue` computes its localized title directly, instead of
initializing an empty title and waiting for a client-only post-render effect.
The theme switch therefore has an accessible name in server-rendered HTML and
throughout hydration. Its toggle handler and appearance are unchanged.

## Verification and maintenance

Run both production builds, `pnpm docs:check`, and `pnpm docs:test`. The independent
`tests/site/zoom.mjs` verifier covers native keyboard navigation and open search/menu
accessibility at browser zoom. Preserve any unresolved browser zoom gate.
Also check empty results, populated results, detailed excerpts, no results, reset,
Arrow/Enter selection, pointer navigation, Escape, and backdrop dismissal.

Before changing the VitePress version or removing this patch, repeat those checks
against the replacement. A closed-page accessibility scan does not cover the dialog.

The original VitePress MIT license and copyright notice are unchanged. This patch
does not select a license for Kittyscape.
