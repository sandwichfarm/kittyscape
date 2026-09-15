"""Preview-first installation with explicit file ownership and reversible edits."""

import argparse
import ast
import errno
import hashlib
import json
import os
import platform
from pathlib import Path
import re
import shlex
import shutil
import stat
import subprocess
import tempfile


BEGIN = "# BEGIN KITTYSCAPE (managed by setup.py)"
END = "# END KITTYSCAPE"
RECEIPT = "kittyscape/install-receipt.json"
BACKUP = "kittyscape/kitty.conf.backup"
NOTICE = (
    "A fresh Kittyscape window opens after installation. Existing kitty windows keep their original state; "
    "restore and pause them before removal."
)
DEFAULT_RULES = b'{\n  "version": 1,\n  "enabled": true,\n  "rules": []\n}\n'


class InstallError(ValueError):
    """A setup operation cannot preserve the user's files as requested."""


def kitty_capabilities():
    """Reject missing runtime APIs; presence alone is not a compatibility claim."""
    try:
        from kitty import fast_data_types as native
        from kitty.boss import Boss
        from kitty.constants import version
        from kitty.launch import load_watch_modules
        from kitty.window import Watchers
    except ImportError as error:
        raise InstallError(f"Kitty runtime is unavailable or incomplete; use kitty +launch ./setup.py. {error}") from error
    watcher = Watchers()
    loader_constants = getattr(getattr(load_watch_modules, "__code__", None), "co_consts", ())
    checks = {"kitty >= 0.38.1": tuple(version) >= (0, 38, 1),
              "watcher on_load": "on_load" in loader_constants,
              "Screen.last_reported_cwd": hasattr(getattr(native, "Screen", object), "last_reported_cwd")}
    checks.update({f"watcher.{name}": hasattr(watcher, name) for name in ("on_cmd_startstop", "on_focus_change", "on_resize")})
    checks.update({f"Boss.{name}": callable(getattr(Boss, name, None)) for name in ("set_background_image", "apply_new_options")})
    checks.update({f"native.{name}": callable(getattr(native, name, None))
                   for name in ("add_timer", "remove_timer", "wakeup_main_loop", "get_options", "os_window_has_background_image")})
    if missing := [name for name, available in checks.items() if not available]:
        raise InstallError("Missing required kitty capabilities: " + ", ".join(missing))
    return {"kitty": ".".join(map(str, version)), "python": platform.python_version(), "required_apis": "present",
            "qualification": "Capability check only; consult the release-specific tested compatibility matrix."}


def media_capabilities():
    """Describe optional local media conversion without installing anything."""
    executable = shutil.which("magick")
    if not executable:
        return {"png": "available", "jpeg_gif": "converter-unavailable"}
    try:
        version = subprocess.run([executable, "--version"], check=True, capture_output=True, text=True, timeout=2)
        identity = version.stdout.splitlines()[0]
    except (OSError, subprocess.SubprocessError):
        return {"png": "available", "jpeg_gif": "converter-unavailable"}
    return {"png": "available", "jpeg_gif": "available", "converter": executable, "converter_version": identity}


def digest(data):
    return hashlib.sha256(data).hexdigest()


def read_regular(path):
    """Read a regular file without following a final symlink or updating Linux atime."""
    flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0) | getattr(os, "O_NONBLOCK", 0)
    try:
        fd = os.open(path, flags | getattr(os, "O_NOATIME", 0))
    except PermissionError:
        fd = os.open(path, flags)
    with os.fdopen(fd, "rb") as stream:
        if not stat.S_ISREG(os.fstat(stream.fileno()).st_mode):
            raise InstallError(f"Expected a regular file: {path}")
        return stream.read()


def version_of(source):
    """Read the version assignment without executing runtime package code."""
    parsed = ast.parse(read_regular(source / "kittyscape/__init__.py"))
    for node in parsed.body:
        if isinstance(node, ast.Assign) and any(isinstance(target, ast.Name) and target.id == "__version__" for target in node.targets):
            value = ast.literal_eval(node.value)
            if isinstance(value, str) and re.fullmatch(r"[0-9][0-9A-Za-z.+-]*", value):
                return value
    raise InstallError("The bundle has no valid literal kittyscape.__version__")


def config_root(path):
    root = Path(path).expanduser().absolute().resolve()
    if any(character in str(root) for character in "\r\n\x00$"):
        raise InstallError("The configuration path cannot contain a newline, NUL, or dollar sign")
    if root.exists() and not root.is_dir():
        raise InstallError(f"The configuration directory is not a directory: {root}")
    return root


def rules_config_path(directory):
    root = Path(directory).expanduser().absolute().resolve()
    if any(character in str(root) for character in "\r\n\x00"):
        raise InstallError("The Kittyscape configuration path cannot contain a newline or NUL")
    if root.exists() and not root.is_dir():
        raise InstallError(f"The Kittyscape configuration directory is not a directory: {root}")
    path = root / "kittyscape.json"
    if path.is_symlink() and not path.exists():
        raise InstallError(f"The Kittyscape configuration symlink has no target: {path}")
    if path.exists() and not path.is_file():
        raise InstallError(f"The Kittyscape configuration path is not a regular file: {path}")
    return path


def confined(root, relative):
    path = Path(relative)
    if path.is_absolute() or ".." in path.parts or not path.parts:
        raise InstallError(f"Invalid relative path in ownership metadata: {relative}")
    target = root / path
    if not target.parent.resolve().is_relative_to(root):
        raise InstallError(f"Owned path parent escaped the configuration directory: {relative}")
    return target


def config_snapshot(root):
    path = root / "kitty.conf"
    link = os.readlink(path) if path.is_symlink() else None
    if link is not None and not path.exists():
        raise InstallError(f"The kitty.conf symlink has no target: {path}")
    target = path.resolve()
    exists = target.exists()
    snapshot = {"target": str(target), "link": link, "existed": exists, "data": b"", "metadata": None, "identity": None}
    if exists:
        info = target.stat()
        if info.st_nlink > 1:
            raise InstallError("Hard-linked kitty.conf requires manual installation; setup preserves symlinks only")
        snapshot.update(data=read_regular(target), metadata=file_metadata(target), identity=(info.st_dev, info.st_ino))
    return snapshot


def validate_bundle(source):
    manifest = source / "manifest.json"
    if not manifest.exists():
        return None
    payload = json.loads(read_regular(manifest))
    if payload.get("schema") != 1 or payload.get("version") != version_of(source):
        raise InstallError("The bundle manifest schema or version is invalid")
    hashes = {}
    for entry in payload.get("files", []):
        path = confined(source, entry["path"])
        if entry["path"] in hashes or path.is_symlink() or digest(read_regular(path)) != entry["sha256"]:
            raise InstallError(f"The bundle failed its manifest check: {entry['path']}")
        hashes[entry["path"]] = entry["sha256"]
    return hashes


def bundle_candidates(source):
    paths = {source / "setup.py"}
    for directory in ("kittyscape", "packaging"):
        paths.update((source / directory).rglob("*.py"))
    if (source / "README.md").is_file():
        paths.add(source / "README.md")
    return paths


def read_bundle_file(source, path, manifest):
    name = path.relative_to(source)
    if path.is_symlink() or not path.resolve().is_relative_to(source):
        raise InstallError(f"Bundle file must not be a symlink: {name}")
    data = read_regular(path)
    if manifest is not None and manifest.get(str(name)) != digest(data):
        raise InstallError(f"Installed code is missing from the verified manifest: {name}")
    return data


def bundle_files(source):
    manifest = validate_bundle(source)
    paths = bundle_candidates(source)
    required = {"setup.py", "kittyscape/__init__.py", "kittyscape/watcher.py", "kittyscape/action.py", "packaging/installer.py"}
    relative = {str(path.relative_to(source)) for path in paths if path.is_file()}
    if missing := required - relative:
        raise InstallError(f"Incomplete bundle; missing: {', '.join(sorted(missing))}")
    result = {}
    for path in sorted(paths):
        name = path.relative_to(source)
        if "__pycache__" in name.parts or any(part.startswith(".") for part in name.parts):
            continue
        result[str(name)] = read_bundle_file(source, path, manifest)
    return result


def generated_config(root, version):
    package = root / "kittyscape" / version / "kittyscape"
    lines = ["# Owned by Kittyscape setup; edit your rules in kittyscape.json.", f"watcher {package / 'watcher.py'}"]
    for number, action in enumerate(("status", "pause", "resume", "reload", "restore"), 6):
        lines.append(f"map ctrl+shift+f{number} kitten {shlex.quote(str(package / 'action.py'))} {action}")
    return ("\n".join(lines) + "\n").encode()


def expected_payload(source, root, version, rules_path):
    prefix = f"kittyscape/{version}/"
    payload = {prefix + path: data for path, data in bundle_files(source).items()}
    payload[prefix + "kittyscape/location.json"] = (json.dumps({"config": str(rules_path)}, indent=2) + "\n").encode()
    payload["kittyscape.conf"] = generated_config(root, version)
    return payload


def ensure_parents(path, created):
    missing = []
    parent = path.parent
    while not parent.exists():
        missing.append(parent)
        parent = parent.parent
    for directory in reversed(missing):
        directory.mkdir(mode=0o700)
        created.append(directory)


def write_new(path, data, *, mode=0o644):
    """Publish a complete new file atomically, refusing any existing destination."""
    fd, temporary = tempfile.mkstemp(prefix=".kittyscape-", dir=path.parent)
    try:
        with os.fdopen(fd, "wb") as stream:
            os.fchmod(stream.fileno(), mode)
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        os.link(temporary, path, follow_symlinks=False)
    finally:
        os.unlink(temporary)


def copy_metadata(source, destination):
    info = source.stat()
    current = destination.stat()
    if (current.st_uid, current.st_gid) != (info.st_uid, info.st_gid):
        os.chown(destination, info.st_uid, info.st_gid)
    shutil.copystat(source, destination, follow_symlinks=False)


def file_metadata(path):
    info = path.stat()
    return {"mode": stat.S_IMODE(info.st_mode), "uid": info.st_uid, "gid": info.st_gid, "mtime_ns": info.st_mtime_ns,
            "xattrs": extended_attributes(path)}


def extended_attributes(path):
    """Fingerprint xattr values without storing their potentially private contents."""
    if not hasattr(os, "listxattr"):
        return {}
    try:
        names = os.listxattr(path, follow_symlinks=False)
    except OSError as error:
        if error.errno in (errno.ENOTSUP, errno.EOPNOTSUPP):
            return {}
        raise
    return {name: digest(os.getxattr(path, name, follow_symlinks=False)) for name in sorted(names)}


def check_config_unchanged(root, snapshot):
    if config_snapshot(root) != snapshot:
        raise InstallError("kitty.conf changed during the operation; no configuration was replaced or deleted. Inspect it before retrying")


def replace_config(target, data, *, metadata_source=None, expected_config=None):
    fd, temporary_name = tempfile.mkstemp(prefix=".kittyscape-", dir=target.parent)
    temporary = Path(temporary_name)
    try:
        with os.fdopen(fd, "wb") as stream:
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        if metadata_source is not None:
            copy_metadata(metadata_source, temporary)
        if expected_config is not None:
            check_config_unchanged(*expected_config)
        os.replace(temporary, target)
    finally:
        temporary.unlink(missing_ok=True)


def load_receipt(root):
    path = root / RECEIPT
    if not path.exists() and not path.is_symlink():
        return None
    if path.is_symlink():
        raise InstallError("The ownership receipt must not be a symlink")
    receipt = json.loads(read_regular(path))
    if receipt.get("schema") != 1 or receipt.get("config_root") != str(root):
        raise InstallError("The ownership receipt is invalid for this configuration directory")
    validate_receipt_files(root, receipt)
    validate_receipt_directories(root, receipt)
    return receipt


def validate_receipt_files(root, receipt):
    version = receipt.get("version", "")
    if not re.fullmatch(r"[0-9][0-9A-Za-z.+-]*", version):
        raise InstallError("The receipt version is invalid")
    for name, checksum in receipt["files"].items():
        if not (name == "kittyscape.conf" or name.startswith(f"kittyscape/{version}/")):
            raise InstallError(f"The receipt claims an unowned path: {name}")
        confined(root, name)
        if not re.fullmatch(r"[a-f0-9]{64}", checksum):
            raise InstallError(f"The receipt has an invalid checksum: {name}")


def validate_receipt_directories(root, receipt):
    prefix = f"kittyscape/{receipt['version']}"
    for name in receipt["created_dirs"]:
        if name not in (".", "kittyscape", prefix) and not name.startswith(prefix + "/"):
            raise InstallError(f"The receipt claims an unowned directory: {name}")
        if name != ".":
            confined(root, name)


def checked_backup(root, receipt):
    path = confined(root, BACKUP)
    if path.is_symlink():
        raise InstallError("The backup must not be a symlink")
    data = read_regular(path)
    if digest(data) != receipt["original_sha256"]:
        raise InstallError("The kitty.conf backup is corrupt; no files were changed")
    return data


def matching_file(path, checksum, metadata=None):
    if path.is_symlink() or not path.is_file():
        return False
    return digest(read_regular(path)) == checksum and (metadata is None or file_metadata(path) == metadata)


def checked_current(root, receipt):
    current = config_snapshot(root)
    if current["target"] != receipt["config_target"] or current["link"] != receipt["config_link"]:
        raise InstallError("kitty.conf changed target since installation; no files were changed")
    return current


def check_repeat(root, receipt, payload, version):
    checked_backup(root, receipt)
    current = checked_current(root, receipt)
    hashes = {name: digest(data) for name, data in payload.items()}
    valid_files = all(matching_file(confined(root, name), checksum, receipt["file_metadata"].get(name))
                      for name, checksum in hashes.items())
    same_install = receipt["version"] == version and receipt["files"] == hashes and receipt["state"] == "installed"
    if not same_install or not valid_files or current["data"].count(receipt["block"].encode()) != 1:
        raise InstallError("Existing installation differs or was edited; uninstall it safely before reinstalling")


def install(bundle_root, config_dir, *, rules_dir=None, apply=False):
    """Preview or install a bundle; repeated identical installs are no-ops."""
    source = Path(bundle_root).resolve()
    root = config_root(config_dir)
    rules_path = rules_config_path(root if rules_dir is None else rules_dir)
    create_rules = rules_dir is not None
    version = version_of(source)
    payload = expected_payload(source, root, version, rules_path)
    if receipt := load_receipt(root):
        check_repeat(root, receipt, payload, version)
        return {"status": "already-installed", "action": "install", "notice": NOTICE,
                "kitty_config_dir": str(root), "config_dir": str(rules_path.parent), "config_file": str(rules_path)}
    snapshot = config_snapshot(root)
    block = new_install_block(root, snapshot["data"], payload)
    result = {"status": "preview", "action": "install", "kitty_config_dir": str(root),
              "config_dir": str(rules_path.parent), "config_file": str(rules_path),
              "config_created": create_rules and not rules_path.exists() and not rules_path.is_symlink(), "version": version,
              "files": sorted(payload), "config_append": block, "generated_config": payload["kittyscape.conf"].decode(), "notice": NOTICE}
    if apply:
        result["config_created"] = apply_install(root, snapshot, payload, block, version,
                                                   rules_path=rules_path if create_rules else None)
        result["status"] = "installed"
    return result


def new_install_block(root, before, payload):
    if BEGIN.encode() in before or END.encode() in before:
        raise InstallError("An existing Kittyscape block has no ownership receipt; use manual recovery")
    for name in (*payload, RECEIPT, BACKUP):
        path = confined(root, name)
        if path.exists() or path.is_symlink():
            raise InstallError(f"Refusing to overwrite an unowned destination: {path}")
    separator = "\n" if before and not before.endswith(b"\n") else ""
    return f"{separator}{BEGIN}\ninclude {root / 'kittyscape.conf'}\n{END}\n"


def write_payload(root, payload, created_files, created_dirs):
    for name, data in payload.items():
        path = confined(root, name)
        ensure_parents(path, created_dirs)
        write_new(path, data)
        created_files.append(path)


def make_receipt(root, snapshot, payload, block, version, *, created_dirs):
    return {"schema": 1, "state": "installed", "version": version, "config_root": str(root),
            "config_target": snapshot["target"], "config_link": snapshot["link"], "config_existed": snapshot["existed"],
            "original_sha256": digest(snapshot["data"]), "installed_sha256": digest(snapshot["data"] + block.encode()),
            "block": block, "files": {name: digest(data) for name, data in payload.items()},
            "file_metadata": {name: file_metadata(root / name) for name in payload},
            "created_dirs": [str(path.relative_to(root)) for path in created_dirs if path.is_relative_to(root)]}


def undo_created_files(created_files, created_dirs):
    for path in reversed(created_files):
        path.unlink(missing_ok=True)
    for path in reversed(created_dirs):
        try:
            path.rmdir()
        except OSError:
            pass


def apply_install(root, snapshot, payload, block, version, *, rules_path):
    created_dirs = []
    created_files = []
    config_created = False
    backup = root / BACKUP
    target = Path(snapshot["target"])
    try:
        ensure_parents(backup, created_dirs)
        write_new(backup, snapshot["data"], mode=0o600)
        created_files.append(backup)
        if snapshot["existed"]:
            copy_metadata(target, backup)
        write_payload(root, payload, created_files, created_dirs)
        if rules_path is not None and not rules_path.exists() and not rules_path.is_symlink():
            ensure_parents(rules_path, created_dirs)
            write_new(rules_path, DEFAULT_RULES, mode=0o600)
            created_files.append(rules_path)
            config_created = True
        receipt = make_receipt(root, snapshot, payload, block, version, created_dirs=created_dirs)
        write_new(root / RECEIPT, (json.dumps(receipt, indent=2) + "\n").encode(), mode=0o600)
        created_files.append(root / RECEIPT)
        if config_snapshot(root) != snapshot:
            raise InstallError("kitty.conf changed during setup; retry after inspecting it")
        replace_config(target, snapshot["data"] + block.encode(), metadata_source=backup if snapshot["existed"] else None,
                       expected_config=(root, snapshot))
        return config_created
    except BaseException:
        undo_created_files(created_files, created_dirs)
        raise


def launch_kitty(kitty_executable, config_dir):
    """Open a new OS window that loads the watcher without restarting existing kitty processes."""
    process = subprocess.Popen([str(kitty_executable), "--config", str(Path(config_dir) / "kitty.conf"),
                                "--directory", str(Path.home())], start_new_session=True)
    return {"status": "started", "pid": process.pid}


def display_result(result):
    """Render concise human output; --json remains available for scripts."""
    action = result.get("action", "install")
    status = result.get("status", "error")
    if status == "error":
        return "Kittyscape could not finish\n\n" + result.get("error", "Unknown setup error")
    if action == "install":
        return display_install(result)
    if action in ("uninstall", "rollback"):
        return f"Kittyscape {status}\n\nRules kept: {result.get('config_dir', 'unchanged')}"
    return json.dumps(result, indent=2)


def display_install(result):
    status = result["status"]
    lines = ["  /\\_/\\", f" ( o.o )  {install_heading(status)}", "  > ^ <", "", f"Rules: {result['config_file']}"]
    lines.append(install_detail(result))
    media = result.get("media", {})
    lines.append("Media: PNG" if media.get("jpeg_gif") != "available" else "Media: PNG, JPEG, GIF via ImageMagick")
    if status == "preview":
        lines.append("Run the same command without --preview to install and open a fresh kitty window.")
    elif result.get("fresh_window", {}).get("status") == "started":
        lines.append("A fresh kitty window is open. Save your rules, then press Ctrl+Shift+F9 there.")
    return "\n".join(lines)


def install_heading(status):
    if status == "installed":
        return "Kittyscape is ready"
    if status == "already-installed":
        return "Kittyscape is already installed"
    return "Kittyscape preview"


def install_detail(result):
    if result.get("config_created"):
        return "A starter rules file is waiting for your directories and PNGs."
    return "Your existing rules file is unchanged."


def removal_content(current, receipt, original, *, rollback):
    data = current["data"]
    if rollback:
        if digest(data) != receipt["installed_sha256"]:
            raise InstallError("Rollback would lose later kitty.conf edits; use uninstall to preserve them")
        return original
    block = receipt["block"].encode()
    count = data.count(block)
    if count == 1:
        return data.replace(block, b"", 1)
    if count == 0 and receipt["state"] in ("removed", "removing"):
        return data
    if count == 0 and digest(data) == receipt["original_sha256"]:
        return data
    raise InstallError("The managed include block was changed or duplicated; resolve it manually before removal")


def retained_files(root, receipt):
    retained = []
    for name, checksum in receipt["files"].items():
        path = confined(root, name)
        if (path.exists() or path.is_symlink()) and not matching_file(path, checksum, receipt["file_metadata"].get(name)):
            retained.append(name)
    return sorted(retained + untracked_files(root, receipt))


def untracked_files(root, receipt):
    retained = []
    installed = confined(root, f"kittyscape/{receipt['version']}")
    for path in installed.rglob("*"):
        name = str(path.relative_to(root))
        if (path.is_file() or path.is_symlink()) and name not in receipt["files"]:
            retained.append(name)
    return retained


def remove_owned_files(root, receipt):
    for name, checksum in receipt["files"].items():
        path = confined(root, name)
        if matching_file(path, checksum, receipt["file_metadata"].get(name)):
            path.unlink()
    return retained_files(root, receipt)


def update_receipt(root, receipt):
    path = root / RECEIPT
    data = (json.dumps(receipt, indent=2) + "\n").encode()
    if read_regular(path) != data:
        replace_config(path, data, metadata_source=path)


def finish_removal(root, receipt, retained):
    if retained:
        receipt["state"] = "removed"
        update_receipt(root, receipt)
    else:
        (root / BACKUP).unlink()
        (root / RECEIPT).unlink()
    for relative in reversed(receipt["created_dirs"]):
        path = root if relative == "." else confined(root, relative)
        try:
            path.rmdir()
        except OSError:
            pass


def remove_installation(config_dir, *, apply, rollback):
    root = config_root(config_dir)
    action = "rollback" if rollback else "uninstall"
    receipt = load_receipt(root)
    if receipt is None:
        return {"status": "already-removed", "action": action, "notice": NOTICE}
    original = checked_backup(root, receipt)
    current = checked_current(root, receipt)
    check_rollback_metadata(root, receipt, current, rollback=rollback)
    data = removal_content(current, receipt, original, rollback=rollback)
    retained = retained_files(root, receipt)
    result = {"status": "preview", "action": action, "config_dir": str(root), "retained": retained, "notice": NOTICE}
    if not apply:
        return result
    receipt["state"] = "removing"
    update_receipt(root, receipt)
    remove_config_block(root, receipt, current, data, rollback=rollback)
    retained = remove_owned_files(root, receipt)
    finish_removal(root, receipt, retained)
    result["retained"] = retained
    result["status"] = "removed-with-retained-files" if retained else "rolled-back" if rollback else "removed"
    return result


def check_rollback_metadata(root, receipt, current, *, rollback):
    if rollback and receipt["config_existed"] and file_metadata(Path(current["target"])) != file_metadata(root / BACKUP):
        raise InstallError("Rollback would replace changed config metadata; use uninstall to preserve it")


def remove_config_block(root, receipt, current, data, *, rollback):
    check_config_unchanged(root, current)
    target = Path(current["target"])
    if data != current["data"]:
        metadata = root / BACKUP if rollback else target
        if not receipt["config_existed"] and not data:
            check_config_unchanged(root, current)
            target.unlink(missing_ok=True)
        else:
            replace_config(target, data, metadata_source=metadata, expected_config=(root, current))


def uninstall(config_dir, *, apply=False):
    """Remove the exact owned block and unchanged files, retaining subsequent edits."""
    return remove_installation(config_dir, apply=apply, rollback=False)


def rollback(config_dir, *, apply=False):
    """Restore a verified backup only when no subsequent config edits would be lost."""
    return remove_installation(config_dir, apply=apply, rollback=True)


def main(argv, *, bundle_root, default_config_dir, default_rules_dir, kitty_executable):
    parser = argparse.ArgumentParser(description="Install Kittyscape with a separate user configuration directory.")
    parser.add_argument("action", choices=("install", "uninstall", "rollback"))
    parser.add_argument("--kitty-config-dir", type=Path, default=default_config_dir, help="Kitty configuration directory to include the loader")
    parser.add_argument("--config-dir", type=Path, default=default_rules_dir, help="Kittyscape rules directory, defaulting to ~/.config/kittyscape")
    parser.add_argument("--preview", action="store_true", help="Show the install or removal plan without changing files")
    parser.add_argument("--json", action="store_true", help="Print machine-readable output for automation")
    parser.add_argument("--apply", action="store_true", help="Compatibility alias; install already applies unless --preview is used")
    parser.add_argument("--no-launch", action="store_true", help="Install without opening a fresh configured kitty window")
    args = parser.parse_args(argv)
    try:
        result = install_result(args, bundle_root, kitty_executable) if args.action == "install" else removal_result(args)
    except (OSError, ValueError, KeyError, TypeError) as error:
        result = {"status": "error", "error": str(error), "action": args.action}
        print(json.dumps(result, indent=2) if args.json else display_result(result))
        return 1
    print(json.dumps(result, indent=2) if args.json else display_result(result))
    return 0


def install_result(args, bundle_root, kitty_executable):
    capabilities = kitty_capabilities()
    result = install(bundle_root, args.kitty_config_dir, rules_dir=args.config_dir, apply=not args.preview)
    result["capabilities"] = capabilities
    result["media"] = media_capabilities()
    if result["status"] in ("installed", "already-installed") and not args.no_launch:
        result["fresh_window"] = launch_kitty(kitty_executable, args.kitty_config_dir)
    return result


def removal_result(args):
    action = {"uninstall": uninstall, "rollback": rollback}[args.action]
    return action(args.kitty_config_dir, apply=not args.preview and args.apply)
