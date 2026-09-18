# Kitty profile capability matrix

| Field | Native API | Actual scope | Profile status |
| --- | --- | --- | --- |
| Font size | `Boss._change_font_size` | OS window | Scoped and process modes. Live readback gates scoped restoration. |
| Padding | `Window.patch_edge_width` | Pane | Scoped mode; four live edges captured and ownership checked. |
| Margin | `Window.patch_edge_width` | Pane | Scoped mode; four live edges captured and ownership checked. |
| Background layout | `set_background_image` | OS window | Existing image-rule field; rejected in process overlays to avoid competing ownership. |
| Dynamic opacity | `_set_os_window_background_opacity` | OS window | Existing image-rule field; startup capability gate remains. |
| Terminal colors/palette | Native config reload | Whole process | Unsupported: field-level preservation of unrelated pane/tab writers is unavailable. |
| Terminal colors/palette | Direct `ColorProfile` writes | Pane | Not supported: no qualified observer covers all OSC/native external writers. |
| Tint/gap tint | Native background options | Process | Accepted limitation remains; not profile-controlled. |
| Process config | `kitty.config.load_config` plus targeted native setters | Entire kitty process | Snapshot-derived font/spacing transaction; unchanged identity skips writes. |

Sources: kitty 0.38.1 and 0.48.2 `boss.py`, `window.py`, `rc/set_spacing.py`, and disposable X11/Wayland runs.
The narrower direct color-profile route avoids `patch_colors` tab-bar writes but cannot observe every external color
writer, so exact restoration remains unqualified. Scoped and process terminal colors stay unsupported.
