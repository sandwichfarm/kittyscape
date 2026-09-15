"""Run a resumable, archive-bound Linux matrix using operator-provided test tools."""

import argparse
import hashlib
import itertools
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tarfile
import tempfile


def checksum(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def extract(archive, output):
    with tarfile.open(archive) as source:
        names = {Path(member.name).parts[0] for member in source.getmembers()}
        assert len(names) == 1, "Expected one archive root"
        source.extractall(output, filter="data")
    return output / names.pop()


def cases(toolchain):
    axes = (toolchain["kitty"], toolchain["shells"], toolchain.get("backends", ["x11", "wayland"]),
            toolchain.get("baselines", ["none", "single"]), toolchain.get("startup", ["interactive", "login"]))
    return itertools.product(*axes)


def identifier(case):
    kitty, shell, backend, baseline, startup = case
    return f"kitty-{kitty['version']}_{shell['name']}-{shell['version']}_{backend}_{baseline}_{startup}"


def executable_identities(toolchain):
    entries = toolchain["kitty"] + toolchain["shells"]
    return [{"path": entry["path"], "sha256": checksum(entry["path"]), "version": entry["version"]} for entry in entries]


def case_executables(case):
    return {name: checksum(entry["path"]) for name, entry in zip(("kitty", "shell"), case[:2])}


def command(case, bundle, archive, toolchain):
    kitty, shell, backend, baseline, startup = case
    result = [sys.executable, "-B", str(bundle / "tests/runtime/installed.py"), "--bundle", str(bundle),
              "--archive", str(archive), "--kitty", kitty["path"], "--shell", shell["path"],
              "--backend", backend, "--baseline", baseline]
    if startup == "login":
        result.append("--login")
    if shell.get("zsh_modules"):
        result.extend(("--zsh-modules", shell["zsh_modules"]))
    if backend == "x11":
        result.extend(("--display", toolchain["x11"]["display"], "--framebuffer", toolchain["x11"]["framebuffer"]))
    return result


def validate_result(result, case, archive_hash):
    kitty, shell, backend, baseline, startup = case
    assert result["error"] is None, result["error"]
    assert result["artifact"]["sha256"] == archive_hash
    assert result["kitty"]["kitty"] == list(map(int, kitty["version"].split(".")))
    assert re.search(r"(?<!\d)" + re.escape(shell["version"]) + r"(?!\d)", result["shell"]), result["shell"]
    assert (result["backend"], result["baseline"], result["startup"]) == (backend, baseline, startup)
    required = {
        "T09-install-preview", "T09-install-apply-repeat", "artifact-installed-runtime-origin",
        "T01-T03-T07-restoration", "T03-directory-stack", "T14-unchanged-prompts", "T08-pause-resume-restore",
        "T04-T06-tabs-splits-focus", "T05-independent-OS-windows", "T14-window-state-release",
        "T13-external-writer-resume", "T10-last-valid-configuration", "T08-installed-explicit-restore",
        "T09-artifact-uninstall-preview-apply-repeat",
    }
    assert required <= {row["scenario"] for row in result["scenarios"] if row["result"] == "pass"}


def preserve(source, destination, replacements):
    destination.mkdir(parents=True, exist_ok=True)
    selected = [path for path in source.iterdir() if path.suffix in (".json", ".jsonl", ".log", ".png")]
    for path in selected:
        if path.suffix == ".png":
            shutil.copy2(path, destination / path.name)
        else:
            content = path.read_text()
            for old, new in replacements.items():
                content = content.replace(str(old), new)
            (destination / path.name).write_text(content)


def run_case(case, context):
    archive, bundle, output, toolchain, archive_hash = context
    name = identifier(case)
    destination = output / "runtime" / name
    saved = destination / "result.json"
    binaries = case_executables(case)
    if saved.is_file():
        result = json.loads(saved.read_text())
        assert result.get("executables") == binaries, "Saved fixture uses different executable builds"
        validate_result(result, case, archive_hash)
        return {"id": name, "result": "pass", "evidence": str(saved.relative_to(output)), "reused": True}
    args = command(case, bundle, archive, toolchain)
    process = subprocess.run(args, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                             env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"})
    roots = [line.removeprefix("Evidence: ") for line in process.stdout.splitlines() if line.startswith("Evidence: ")]
    destination.mkdir(parents=True, exist_ok=True)
    (destination / "command.log").write_text(process.stdout)
    if process.returncode or not roots:
        raise RuntimeError(f"{name} failed: {destination / 'command.log'}")
    root = Path(roots[-1])
    result = json.loads((root / "result.json").read_text())
    validate_result(result, case, archive_hash)
    assert case_executables(case) == binaries, "An executable changed during qualification"
    result["executables"] = binaries
    (root / "result.json").write_text(json.dumps(result, indent=2) + "\n")
    preserve(root, destination, {root: "$FIXTURE", bundle: "$BUNDLE", archive: "$ARCHIVE"})
    return {"id": name, "result": "pass", "evidence": str(saved.relative_to(output)), "command": args}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("archive", type=Path)
    parser.add_argument("--toolchain", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    archive, output = args.archive.resolve(), args.output.resolve()
    output.mkdir(parents=True, exist_ok=True)
    toolchain = json.loads(args.toolchain.read_text())
    archive_hash = checksum(archive)
    metadata = {"archive": archive.name, "sha256": archive_hash, "toolchain": toolchain,
                "executables": executable_identities(toolchain), "rows": []}
    with tempfile.TemporaryDirectory(prefix="kittyscape-release-") as temporary:
        bundle = extract(archive, Path(temporary))
        context = (archive, bundle, output, toolchain, archive_hash)
        for case in cases(toolchain):
            row = run_case(case, context)
            metadata["rows"].append(row)
            (output / "matrix.json").write_text(json.dumps(metadata, indent=2) + "\n")
            print(f"PASS {len(metadata['rows'])}: {row['id']}", flush=True)
    print(f"Qualified {len(metadata['rows'])} installed graphical fixtures: {output / 'matrix.json'}", flush=True)


if __name__ == "__main__":
    main()
