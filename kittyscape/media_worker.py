"""Apply Linux decoder limits before replacing this process with ImageMagick."""

from __future__ import annotations

import os
from pathlib import Path
import resource
import sys


ADDRESS_SPACE_LIMIT = 512 * 1024 * 1024
CPU_LIMIT_SECONDS = 5
FILE_LIMIT = 64 * 1024 * 1024


def main(argv: list[str]) -> None:
    executable = Path(argv[0]).resolve(strict=True)
    resource.setrlimit(resource.RLIMIT_AS, (ADDRESS_SPACE_LIMIT, ADDRESS_SPACE_LIMIT))
    resource.setrlimit(resource.RLIMIT_CPU, (CPU_LIMIT_SECONDS, CPU_LIMIT_SECONDS))
    resource.setrlimit(resource.RLIMIT_FSIZE, (FILE_LIMIT, FILE_LIMIT))
    os.execv(executable, [str(executable), *argv[1:]])


if __name__ == "__main__":
    main(sys.argv[1:])
