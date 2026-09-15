# Kittyscape: compatibility strategy

Status: targets only. No combination has been tested yet.

## Meaning of support labels

- Supported: release-specific runtime evidence covers every required core scenario.
- Experimental: integration exists, but a named acceptance gap remains.
- Unsupported: do not enable automatically; explain the limitation and preserve terminal usability.
- Planned: design target with no implementation evidence. All targets below currently have this status unless excluded.

## Target matrix

| Environment | Target level | Required evidence |
| --- | --- | --- |
| Linux x86_64, Wayland | Version 1 supported | Real kitty runtime with Bash, Zsh, Fish; primary desktop acceptance. |
| Linux x86_64, X11 | Version 1 supported | Separate disposable graphical runner; never change the user’s display session. |
| macOS arm64 | Version 1 supported | Real kitty app, its embedded Python, and all three baseline shells. |
| Linux arm64 / macOS Intel | Follow-up qualification | Architecture-specific runtime evidence before promotion. |
| Bash, Zsh, Fish | Baseline shells | Oldest selected supported release and current stable at qualification time. |
| Nushell | First additional-shell target | Reporting adapter/native reporting experiment plus the core scenarios. |
| POSIX sh, dash, ksh, other shells | Best-effort design targets | Documented reporting adapter or explicit unsupported automatic mode. |
| SSH and remote shell directories | Deferred | Host-aware mapping and local-image policy would need separate design and tests. |
| tmux / Zellij | Deferred automatic mode | Inner-pane identity and active-directory reporting require dedicated integration. |
| Shells inside containers | Deferred automatic mode | Verify process visibility and distinguish container paths from host paths. |
| Native Windows and non-kitty terminals | Outside version 1 | No compatibility claims. |

The baseline macOS shell test must include the OS-provided Bash if it can satisfy the contract.
Do not silently require a newer shell or replace the user’s shell. If it fails, state the minimum and the unsupported case.

## Kitty and runtime versions

- Choose the minimum kitty release through feature probing and runtime experiments, not guesswork.
- Test that minimum and the latest stable release qualified for each release; add an intermediate regression version when needed.
- Test prerelease kitty separately as advisory; it cannot substitute for stable support.
- Verify global watcher loading, required events, scoped background control, directory freshness, and restoration independently.
- Test embedded Python compatibility; system Python success is not kitty runtime proof.
- Existing configuration includes, custom directories, and theme files belong in the matrix.
- Publish tested versions, OS, architecture, display backend, integration mode, date, and result for every row.

## Capability selection

Prefer native kitty integration for Bash/Zsh/Fish. Validate that reporting remains enabled and fresh.
If a shell does not emit the required reports, use a documented thin adapter when available.
Adapter events carry only the necessary pane identity, local directory, and event ordering information.
The actual transport and escaping contract must be verified before documentation promises it.

Do not infer support solely from the shell executable name. Missing integration, disabled cwd reports,
disabled prompt marks, nested shells, multiplexers, and remote sessions can alter behavior.
Capability diagnostics must distinguish these from invalid user rules or unavailable images.

Local process-directory inspection may be offered later as an explicitly selected degraded mode.
It must say whether it follows the shell or a foreground program and cannot claim remote/multiplexer correctness.

## Portable behavior rules

- No Hyprland-specific runtime dependency; kitty owns rendering and window targeting.
- No Linux /proc dependency in the baseline portable path.
- No assumptions about GNU-only commands, Homebrew paths, XDG variables being present, or a particular login shell.
- Handle Unicode, spaces, shell metacharacters, long paths, symlinks, and case-sensitive/case-insensitive filesystems.
- Preserve existing prompt hooks, prompt tools, shell exit status, and ordinary interactive startup behavior.
- Unsupported features fail with useful diagnostics, not silent installation changes.
- Use only tested image formats and limits; PNG is the initial common denominator.

## Distribution and maintenance

Initial release candidate: a downloadable source bundle with manual user-local installation and verification instructions.
Choose any helper CLI packaging after the embedded-runtime experiment; avoid requiring users to build from source.
Package-manager recipes can follow a stable installation contract and separately verified artifacts.
Document uninstall and rollback for every installation method that is actually shipped.

Keep one support table shared by release notes and the website. Never call an entire platform supported
because unit tests ran on that platform. Missing macOS or X11 access remains a visible release gate.
