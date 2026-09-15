# Shells

Kittyscape uses one kitty-side watcher and the directory reports from kitty’s native shell integration.
Bash, Zsh, and Fish share the same resolver and configuration. The current build does not need a separate
rules engine or per-prompt helper process in each shell.

::: warning Read the tested rows
A native integration existing upstream is not a Kittyscape support claim. Consult the exact
[shell and platform evidence](../reference/compatibility.md), including missing target environments.
:::

## Bash, Zsh, and Fish

Run the shell inside an isolated kitty instance with native shell integration enabled.
Kittyscape needs fresh working-directory reports and prompt/command marks. Disabling those parts of
kitty shell integration prevents reliable directory timing.

Use the same [configuration example](./getting-started.md) for all three shells. Verify startup, `cd`, nested
directories, directory stacks where supported, and pane/tab focus changes before calling a row qualified.
Do not replace your normal shell or overwrite an existing prompt hook to make a test pass.

The [runtime findings](../development/compatibility-findings.md) record report ordering and the selected
deferred update mechanism. A command-end callback can occur before the new directory report is ready.

## Missing reports

If no trustworthy local report exists, the watcher must not guess from a foreground subprocess’s directory.
Use [status and diagnostics](../reference/actions.md) to distinguish missing shell integration from a bad
rule or unreadable image. At startup, the existing background stays in place until reliable state is available.

## Nested shells and prompt tools

Nested interactive shells are outside automatic mode. The tested nested Bash did not inherit reliable
native reports. A direct nested Bash, Zsh, or Fish command uses fallback and keeps an unsupported-context
diagnostic until explicit resume after leaving the nested shell. Ordinary noninteractive commands such as
`bash -c 'pwd'` retain the outer shell’s image.

Command detection does not resolve aliases or arbitrary wrappers. Pause before using an unsupported
context. Customized prompt hooks need working native reports and their own qualification; no hook is
rewritten by Kittyscape. See [compatibility](../reference/compatibility.md).

## Other contexts

| Context | Current guidance |
| --- | --- |
| Nushell | Additional-shell experiment; no automatic-support claim. |
| POSIX sh, dash, ksh, other shells | No qualified reporting adapter in this build. |
| SSH and remote paths | Deferred. A remote path must never be mistaken for a host-local image path. |
| tmux and Zellij | Automatic inner-pane directory selection is deferred. |
| Shells inside containers | Host/container path identity is not qualified. |
| Other terminals and native Windows | Outside the first release target. |

Avoid enabling automatic switching in unsupported contexts. Use a normal kitty background until the
necessary directory and pane identity contract has been qualified.
