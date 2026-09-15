# Private Wayland qualification environment

**Stopped 2026-09-15T15:10:59.770387+00:00.** All owned processes and private sockets were removed. See `cleanup-proof.json`.
The remaining notes describe the completed session and its reusable bootstrap.

Ready and left running for the parent matrix. No further probe windows remain. The daily compositor was never used as the nested
parent, and no host workspace-switch command was sent.

## Live handles

- Supervisor PID: `2150745`.
- Hyprland PID: `2150892`.
- Runtime directory: `/tmp/kswl-xzdvy13g` (private, mode 0700).
- Hyprland signature: `efb50993780079460b0cbed1363e2166a2de1d9f_1789480785_464689180`.
- Client socket: `/tmp/kswl-xzdvy13g/wayland-2`.
- IPC socket: `/tmp/kswl-xzdvy13g/hypr/efb50993780079460b0cbed1363e2166a2de1d9f_1789480785_464689180/.socket.sock`.
- Private output: `KITTYSCAPE-HEADLESS`, 1280×800 at 60 Hz.
- Private workspace 15 is active. A private window rule routes `kittyscape-qualification` there and floats it at 960×640.
- Complete client environment: `/tmp/kittyscape-private-wayland-27ldgord/environment.json`.
- Full process/version/output state: `session.json` in this directory.

Use the complete JSON environment for direct client/test-runner subprocesses. The parent switched its test harness to direct Popen,
with guards requiring a runtime under `/tmp` and workspace 15 active in the selected private instance. No host workspace switch is needed.

```python
import json
import subprocess
from pathlib import Path

env = json.loads(Path('/tmp/kittyscape-private-wayland-27ldgord/environment.json').read_text())
subprocess.run(
    ['/usr/bin/python', '-B', '/home/sandwich/Develop/kittyscape/tests/runtime/installed.py',
     '--bundle', '<extracted artifact>', '--archive', '<original archive>',
     '--kitty', '<tested kitty>', '--shell', '<tested shell>', '--backend', 'wayland'],
    env=env, check=True,
)
```

## Actual pixel proof

The installed distro kitty 0.48.2 and upstream portable kitty 0.38.1 and 0.48.2 mapped as native Wayland windows on private workspace 15.
Each was captured using `grim -T` with an identifier obtained from the private `ext-foreign-toplevel-list-v1` protocol. Both portable
captures were 960×640 and returned exact RGB `(40, 90, 61)` at the sampled point, matching configured background `#285a3d`.
Xwayland's runtime option was explicitly false. Each proof process was closed afterward.

- `proof.json`: initial distro-kitty capture.
- `portable-0.38.1-proof.json` and `portable-0.48.2-proof.json`: portable-binary proofs, including renderer-profile metadata.
- `portable-0.38.1-private-kitty-grim-T.png` and `portable-0.48.2-private-kitty-grim-T.png`: actual captures.
- Both portable PNG SHA256 values: `f8633ee76c6f60c312dbbde1c2bd2316206a449570e49d2912db5bc340bb70b9`.

### Explicit library qualification profile

The older portable bundle failed EGL initialization until the host Wayland client library was preloaded. Mesa/vendor flags alone,
`LD_LIBRARY_PATH=/usr/lib`, an explicit Wayland EGL platform, and host C++/GCC preloads did not resolve it. The successful process-local
setting is `LD_PRELOAD=/usr/lib/libwayland-client.so.0`. This is an empirical compatibility workaround, not a claim that the unmodified
portable runtime works with this host graphics stack.

- Host package: `wayland 1.26.0-1`.
- Resolved library: `/usr/lib/libwayland-client.so.0.26.0`.
- SHA256: `39c83ae7b73d22f18b4f81da14749c4535c304b7e62910a2f1aae682f279cc9d`.
- Other proven flags: `LIBGL_ALWAYS_SOFTWARE=1` and
  `__EGL_VENDOR_LIBRARY_FILENAMES=/usr/share/glvnd/egl_vendor.d/50_mesa.json`.
- Complete profile and comparison evidence: `renderer-profile.json`, `egl-variants.json`, and `egl-preload-variants.json`.

## Isolation and bootstrap

The installed Hyprland 0.56.2/Aquamarine 0.15.0 cannot obtain a standalone headless allocator without another backend. An installed
Wayfire 0.11.0 headless parent supplies the render allocator, and Hyprland creates its own explicit headless output after IPC startup.
Wayfire's socket is private `wayland-1`; Hyprland's socket is private `wayland-2`. Neither connects to the user's `/run/user/...` display.

Both compositor processes run with a read-only root filesystem, writable `/tmp`, separate network/IPC namespaces, and a private `/dev`
that exposes only `/dev/dri/renderD129`. Physical DRM card nodes and input devices are absent. PID namespaces are shared intentionally,
so the existing verifier's PID-based ownership and cleanup checks still identify real host PIDs. No source compilation or system
installation was used.

Both configurations disable Xwayland. The private D-Bus daemon has no service-activation directories. `HYPRLAND_NO_SD_VARS=1` disables
Hyprland's systemd/activation-environment updates, and HOME plus all XDG directories point into temporary storage.

Reusable temporary bootstrap: `/tmp/kittyscape-wayland-research/private_session.py`.

```sh
python -B /tmp/kittyscape-wayland-research/private_session.py start
```

It prints a new root/runtime/supervisor identity, validates the private configuration, starts the headless parent and nested compositor,
creates a headless output, activates private workspace 15, and publishes `environment.json`/`session.json` when ready.
Earlier failed attempts are preserved separately; they exposed a private D-Bus receive-policy omission and the need to create the
headless output explicitly. They did not connect to the daily compositor.

After the parent finishes all matrix runs, stop only this supervisor and its owned children:

```sh
python -B /tmp/kittyscape-wayland-research/private_session.py stop \
  --root /tmp/kittyscape-private-wayland-27ldgord
```

Do not run that cleanup while the parent's matrix is active. The stop command verifies the supervisor command line before signaling it.

## Primary sources checked before launch

- [Hyprland 0.56.2 backend selection and systemd environment guards](https://github.com/hyprwm/Hyprland/blob/v0.56.2/src/Compositor.cpp).
- [Aquamarine 0.15 allocator requirements](https://github.com/hyprwm/aquamarine/blob/v0.15.0/src/backend/Backend.cpp).
- [Aquamarine nested Wayland backend](https://github.com/hyprwm/aquamarine/blob/v0.15.0/src/backend/Wayland.cpp).
- [wlroots 0.20.2 documented headless/render environment](https://gitlab.freedesktop.org/wlroots/wlroots/-/blob/0.20.2/docs/env_vars.md).
- [Hyprland window-rule syntax](https://wiki.hypr.land/Configuring/Basics/Window-Rules/).
- Installed Wayfire `core.xml` documents `xwayland=false`; its actual headless backend startup was verified in `wayfire.log`.

This is a private test-environment proof. Final artifact behavior, the full Wayland matrix, and macOS qualification remain separate.
