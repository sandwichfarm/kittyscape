"""Verify old kitty retains captured PNG bytes while native reload updates layout."""

import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time

sys.dont_write_bytecode = True


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--bundle", type=Path, required=True)
    parser.add_argument("--archive", type=Path, required=True)
    parser.add_argument("--kitty", type=Path, default=Path("/tmp/kittyscape-tools/kitty-0.38.1/bin/kitty"))
    parser.add_argument("--shell", type=Path, default=Path("/tmp/kittyscape-bash-5.3.20/build/bash"))
    parser.add_argument("--backend", choices=("x11", "wayland"), default="x11")
    parser.add_argument("--display", default=":101")
    parser.add_argument("--framebuffer", default="/tmp/kittyscape-x11-experiment/frames/Xvfb_screen0")
    options = parser.parse_args()
    options.bundle = options.bundle.resolve(strict=True)
    sys.path.insert(0, str(options.bundle / "tests/runtime"))
    import extended
    from installed import installer_module, verify_artifact

    assert extended.PROJECT == options.bundle, "Verifier must use the archived helpers"
    artifact = verify_artifact(options, installer_module())
    assert artifact["sha256"] == "4d304c7c23dc343addd42500a05ca7c7607b3b5641ff60bae9324b99eb3a251a", artifact
    root = Path(tempfile.mkdtemp(prefix="kittyscape-old-reload-proof-"))
    kitten = root / "k.py"
    observer = extended.KITTEN.replace("import json\n", "import json, hashlib\n", 1)
    observer = observer.replace('"bytes": len(baseline.data)',
                                '"bytes": len(baseline.data), "sha256": hashlib.sha256(baseline.data).hexdigest()', 1)
    kitten.write_text(observer)
    args = argparse.Namespace(**vars(options), baseline="single", extra=(), themes=False, kitten=str(kitten))
    session = extended.ExtendedSession.__new__(extended.ExtendedSession)
    result = {"scenario": "T09-old-kitty-native-reload", "status": "failed", "artifact": artifact,
              "backend": options.backend, "display": options.display if options.backend == "x11" else os.environ.get("WAYLAND_DISPLAY"),
              "platform": os.uname().sysname, "architecture": os.uname().machine,
              "shell": subprocess.check_output([str(options.shell), "--version"], text=True).splitlines()[0],
              "script_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
              "created_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())}
    try:
        session.__init__(args)
        assert session.runtime["kitty"] == [0, 38, 1], session.runtime
        result["runtime"] = session.runtime
        result["evidence"] = str(session.root)
        verify_reload(session, extended, result)
        result["status"] = "passed"
    except Exception as error:
        result["error"] = repr(error)
        if getattr(session, "pid", None):
            result["failure"] = session.observe("old-reload-failure")
        raise
    finally:
        (root / "result.json").write_text(json.dumps(result, indent=2) + "\n")
        print("Result: " + str(root / "result.json"), flush=True)
        if getattr(session, "pid", None):
            session.close()


def verify_reload(session, extended, result):
    original_pixel = extended.baseline(session)
    assert original_pixel[2] > original_pixel[0] + 45, original_pixel
    original_sha = hashlib.sha256(session.images["baseline"].read_bytes()).hexdigest()
    result["original_png_sha256"] = original_sha
    before = session.observe("old-reload-original-blue")
    assert before["native"]["baseline"]["sha256"] == original_sha, before
    extended.select(session, "A")
    selected = session.observe("old-reload-rule-A")
    extended.reload_config(session, session.images["B"], "mirror-tiled")
    session.wait(lambda: session.inspect()["background_image_layout"] == "mirror-tiled", "reloaded rendering layout")
    session.wait(lambda: extended.state(session)["owned"] and extended._is_color(session.pixel(), False), "rule A after reload")
    reloaded = session.observe("old-reload-new-config-original-cache")
    session.cd(session.home)
    session.settle(session.home)
    session.wait(lambda: session.pixel() == original_pixel, "original blue PNG restoration after native reload")
    restored = session.observe("old-reload-restored-original-blue")
    assert not extended.state(session)["owned"] and restored["inspect"]["has_image"], restored
    assert restored["inspect"]["background_image"] == str(session.images["B"]), restored
    assert restored["inspect"]["background_image_layout"] == "mirror-tiled", restored
    assert restored["native"]["baseline"]["sha256"] == original_sha, restored
    stable = ("background_image_linear", "background_tint", "background_tint_gaps", "background_opacity", "background", "foreground")
    assert all(before["inspect"][key] == restored["inspect"][key] for key in stable)
    result["observations"] = {"before": before, "rule_A": selected, "after_reload": reloaded, "restored": restored}
    result["conclusion"] = "Original PNG bytes and blue pixels restored; configured image points to B and rendering layout is mirror-tiled."
    session.record("T09-old-kitty-retains-PNG-adopts-layout", {"before_pixel": original_pixel, "after_pixel": restored["pixel"],
                                                            "layout": restored["inspect"]["background_image_layout"],
                                                            "png_sha256": original_sha})


if __name__ == "__main__":
    main()
