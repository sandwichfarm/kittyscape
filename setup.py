"""Run with kitty +launch ./setup.py; this also implements the custom-kitten main API."""

import importlib.util
import json
import os
from pathlib import Path
import sys


def main(args):
    """Use kitty's embedded Python to preview or apply user-local setup."""
    sys.dont_write_bytecode = True
    root = Path(__file__).resolve().parent
    spec = importlib.util.spec_from_file_location("_kittyscape_setup", root / "packaging/installer.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    try:
        from kitty.constants import config_dir, kitty_exe
    except ImportError:
        print(json.dumps({"status": "error", "error": "Use kitty +launch ./setup.py to run with kitty's embedded Python."}))
        raise SystemExit(1) from None

    default_rules_dir = Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config")) / "kittyscape"
    raise SystemExit(module.main(args[1:], bundle_root=root, default_config_dir=config_dir,
                                 default_rules_dir=default_rules_dir, kitty_executable=kitty_exe()))


if __name__ == "__main__":
    main(sys.argv)
