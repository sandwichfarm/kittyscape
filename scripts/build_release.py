"""Build the source artifact with Python or kitty +runpy/runpy.run_path."""

import importlib.util
from pathlib import Path
import sys


if __name__ == "__main__":
    sys.dont_write_bytecode = True
    root = Path(__file__).resolve().parents[1]
    spec = importlib.util.spec_from_file_location("_kittyscape_builder", root / "packaging/builder.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    module.main(sys.argv[1:], source_dir=root)
