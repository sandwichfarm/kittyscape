# Kittyscape: research and unresolved decisions

Research checked September 15, 2026. Upstream capabilities are distinct from proposed Kittyscape behavior.

## Primary sources

| Source | What it establishes | What it does not establish |
| --- | --- | --- |
| [Kitty background remote control](https://sw.kovidgoyal.net/kitty/remote-control/#kitten-set-background-image) | Runtime image selection, OS-window scope, configured layout option, removal and configured-default controls. | Directory policy, automatic restoration of a previous image, or version compatibility for Kittyscape. |
| [Kitty background configuration](https://sw.kovidgoyal.net/kitty/conf/#opt-kitty.background_image) | Image layout, interpolation, tint, image lists, and interaction with automatic color themes. | That all historical releases support identical formats or image-list semantics. |
| [Kitty watchers](https://sw.kovidgoyal.net/kitty/launch/#watching-launched-windows) | Global/per-launch Python watchers, focus and command callbacks, scoped remote-control calls; internals are unstable. | A dedicated documented cwd-change callback or guaranteed callback/report ordering. |
| [Kitty shell integration](https://sw.kovidgoyal.net/kitty/shell-integration/) | Built-in Bash, Zsh, Fish integration and cwd reporting controls. | Universal-shell support, reliable nested/multiplexer behavior, or Kittyscape-specific integration. |
| [Kitty remote-control permissions](https://sw.kovidgoyal.net/kitty/remote-control/#fine-grained-permissions-for-remote-control) | Restricted authorization mechanisms exist. | The final minimal permissions for a proposed adapter transport; these need testing. |
| [VitePress overview](https://vitepress.dev/guide/what-is-vitepress) | Static Markdown-based websites with docs and customizable themes. | A requirement for a separate landing-page framework. |
| [VitePress home layout](https://vitepress.dev/reference/default-theme-home-page) | Home-page hero, actions, and optional features. | That current prerelease examples match the stable version eventually pinned. |
| [VitePress local search](https://vitepress.dev/reference/default-theme-search) | A built-in locally indexed search option. | Any need for a hosted search service. |
| [VitePress deployment](https://vitepress.dev/guide/deploy) | Static deployment and base-path configuration. | A selected host, domain, or authorization to publish this project. |

## Existing related projects

- [kitty-control](https://github.com/doctorfree/kitty-control): image selection and other runtime controls.
- [Pokemon-Terminal](https://github.com/LazoVelko/Pokemon-Terminal): themed backgrounds using kitty remote control.
- [terminal-background-tool](https://github.com/JasonBoyett/terminal-background-tool): manual/random background management.

Earlier search found no verified exact match documenting automatic directory-based switching for kitty.
That is a bounded search result, not proof that no such project exists. These projects are context, not dependencies.

## Corrections to avoid overpromising

A kitty watcher is a plausible shared-shell architecture, not proof that all shells expose the same directory events.
The distinction between OS-window backgrounds and pane-specific directory state is fundamental.
“Keep kitty settings” includes baseline restoration and theme/reload behavior, not just omitting a layout override.
The set-background-image removal value clears an image; it is not an automatic restore-original command.

## Questions to resolve through experiments, not user interviews

1. What exact minimum kitty version supports the selected mechanisms on each baseline platform?
2. Which callback/report ordering occurs after directory changes in Bash, Zsh, and Fish?
3. Can a supported interface provide the shell’s last reliable directory without unstable internal coupling?
4. How are effective per-window images, configured lists, and theme changes captured and restored?
5. Can external image writers/config reloads be detected reliably enough to enforce ownership?
6. Does a standard-library-only module bundle load consistently in kitty’s embedded Python across platforms?
7. Which image limits prevent unacceptable UI stalls without introducing conversion dependencies?
8. Which additional shells need adapters, and what minimal secure event transport works across those shells?

## Later publication decisions

Repository owner, license, domain, distribution channel, and hosting provider are intentionally unselected.
They do not block a useful implementation plan. Resolve them before publishing code, assets, packages, or a website.
