"""Native X11 smoke test for direct JPEG/GIF selection and animated backgrounds."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import subprocess
import time

from qualify import Session, _is_color


class MediaSession(Session):
    def _write_kitty_config(self):
        super()._write_kitty_config()
        self.jpeg = self.root / "oriented.jpg"
        self.static_gif = self.root / "static.gif"
        self.animated_gif = self.root / "animated.gif"
        subprocess.run(["/usr/bin/magick", "-size", "1920x1080", "xc:red", str(self.jpeg)], check=True)
        subprocess.run(["/usr/bin/magick", "-size", "1920x1080", "xc:green", str(self.static_gif)], check=True)
        subprocess.run(["/usr/bin/magick", "-size", "1920x1080", "xc:red", "-delay", "12",
                        "-size", "1920x1080", "xc:green", "-delay", "12", "-size", "1920x1080", "xc:blue",
                        "-delay", "12", "-loop", "0", str(self.animated_gif)], check=True)
        self.config_file.write_text(json.dumps({"version": 1, "animation": {"fps_limit": 12}, "rules": [
            {"directory": str(self.dirs["A"]), "image": str(self.animated_gif)},
            {"directory": str(self.dirs["B"]), "image": str(self.jpeg)},
            {"directory": str(self.dirs["nested"]), "image": str(self.static_gif)},
        ]}))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--kitty", type=Path, default=Path("/usr/bin/kitty"))
    parser.add_argument("--shell", type=Path, default=Path("/usr/bin/bash"))
    parser.add_argument("--bundle", type=Path, required=True)
    parser.add_argument("--backend", choices=("x11", "wayland"), default="x11")
    parser.add_argument("--display", default=":105")
    parser.add_argument("--framebuffer", required=True)
    args = parser.parse_args()
    args.baseline, args.login = "none", False
    session = MediaSession(args)
    try:
        session.cd(session.dirs["A"])
        session.settle(session.dirs["A"])
        observed = []
        deadline = time.monotonic() + 5
        while time.monotonic() < deadline and not _has_rgb_cycle(observed):
            color = session.pixel()
            if not observed or color != observed[-1]:
                observed.append(color)
            time.sleep(0.08)
        assert _has_rgb_cycle(observed), observed
        session.cd(session.dirs["B"])
        session.settle(session.dirs["B"])
        session.wait(lambda: _is_color(session.pixel(), False), "JPEG display")
        session.cd(session.dirs["nested"])
        session.settle(session.dirs["nested"])
        session.wait(lambda: _is_color(session.pixel(), True), "static GIF display")
        session.action("restore")
        print(json.dumps({"status": "passed", "frames": observed, "evidence": str(session.root)}))
    finally:
        session.close()


def _has_rgb_cycle(colors):
    red = any(_is_color(color, False) for color in colors)
    green = any(_is_color(color, True) for color in colors)
    blue = any(color[2] > color[0] + 25 and color[2] > color[1] + 25 for color in colors)
    return red and green and blue


if __name__ == "__main__":
    main()
