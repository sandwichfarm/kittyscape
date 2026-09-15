"""Build a deterministic local source bundle with an inventory and checksums."""

import argparse
import ast
import gzip
import hashlib
import io
import json
from pathlib import Path
import re
import tarfile


def release_version(root):
    parsed = ast.parse((root / "kittyscape/__init__.py").read_text())
    for node in parsed.body:
        if isinstance(node, ast.Assign) and any(isinstance(target, ast.Name) and target.id == "__version__" for target in node.targets):
            version = ast.literal_eval(node.value)
            if isinstance(version, str) and re.fullmatch(r"[0-9][0-9A-Za-z.+-]*", version):
                return version
    raise ValueError("Missing literal kittyscape.__version__")


def archive_files(root):
    top_level = (
        "setup.py", "README.md", "CHANGELOG.md", "package.json", "pnpm-lock.yaml", "pnpm-workspace.yaml",
        ".npmrc", ".gitignore", "Makefile",
    )
    files = {root / name for name in top_level if (root / name).is_file()}
    patterns = (
        ("kittyscape", "*.py"), ("packaging", "*.py"), ("examples", "*.json"),
        ("tests", "*.py"), ("tests", "*.mjs"), ("tests/runtime", "*.example.json"), ("scripts", "*.py"), ("docs", "*.md"),
        ("docs/public", "*.svg"), ("docs/.vitepress", "*.mjs"), ("docs/.vitepress", "*.js"), ("docs/.vitepress", "*.css"),
        ("docs/.vitepress", "*.vue"), ("docs/.vitepress", "*.ts"), (".omx/plans", "*.md"),
        ("patches", "*.patch"),
        ("patches", "*.md"),
    )
    for folder, pattern in patterns:
        files.update((root / folder).rglob(pattern))
    result = {}
    for path in sorted(files):
        if entry := archive_entry(root, path):
            result[entry[0]] = entry[1]
    required = {"setup.py", "README.md", "kittyscape/__init__.py", "kittyscape/watcher.py", "kittyscape/action.py", "packaging/installer.py"}
    if missing := required - result.keys():
        raise ValueError(f"Incomplete release source: {', '.join(sorted(missing))}")
    record = {
        "schema": 1, "status": "source-build-unqualified", "artifact": None, "matrix": [],
        "notice": "Run the documented release checks and attach their archive-bound evidence to the separately built site.",
    }
    result["docs/public/evidence/release.json"] = (json.dumps(record, indent=2) + "\n").encode()
    return result


def archive_entry(root, path):
    relative = path.relative_to(root)
    excluded = {"__pycache__", "node_modules", "dist", "dist-subpath", "cache", "evidence"}
    if excluded.intersection(relative.parts):
        return None
    if path.is_symlink() or not path.resolve().is_relative_to(root):
        raise ValueError(f"Refusing to bundle a symlink: {relative}")
    return str(relative), path.read_bytes()


def build_release(source_dir, output_dir):
    """Return the archive path; timestamps and file order do not affect its identity."""
    root = Path(source_dir).resolve()
    output = Path(output_dir).resolve()
    version = release_version(root)
    name = f"kittyscape-{version}"
    payload = archive_files(root)
    manifest = {"schema": 1, "name": "kittyscape", "version": version,
                "files": [{"path": path, "size": len(data), "sha256": hashlib.sha256(data).hexdigest()}
                          for path, data in sorted(payload.items())]}
    manifest_data = (json.dumps(manifest, indent=2) + "\n").encode()
    payload["manifest.json"] = manifest_data
    output.mkdir(parents=True, exist_ok=True)
    archive_path = output / f"{name}.tar.gz"
    with archive_path.open("wb") as raw:
        with gzip.GzipFile(filename="", mode="wb", fileobj=raw, mtime=0) as compressed:
            with tarfile.open(mode="w", fileobj=compressed, format=tarfile.PAX_FORMAT) as archive:
                for path, data in sorted(payload.items()):
                    info = tarfile.TarInfo(f"{name}/{path}")
                    info.size = len(data)
                    info.mode = 0o644
                    info.mtime = 0
                    archive.addfile(info, io.BytesIO(data))
    manifest_path = output / f"{name}.manifest.json"
    manifest_path.write_bytes(manifest_data)
    checksums = [f"{hashlib.sha256(path.read_bytes()).hexdigest()}  {path.name}" for path in (archive_path, manifest_path)]
    (output / "SHA256SUMS").write_text("\n".join(checksums) + "\n")
    return archive_path


def main(argv, *, source_dir):
    parser = argparse.ArgumentParser(description="Build local Kittyscape artifacts; does not publish or choose a license.")
    parser.add_argument("--output", type=Path, default=Path(source_dir) / "dist")
    args = parser.parse_args(argv)
    print(build_release(source_dir, args.output))
