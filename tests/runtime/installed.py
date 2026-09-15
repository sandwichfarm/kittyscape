"""Graphical qualification of an installed, manifest-verified release artifact."""

import argparse
import hashlib
import importlib.util
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tarfile
import time

from qualify import PROJECT, Session, _is_color, core_scenarios, focus_scenarios, lifecycle_scenarios, performance_scenario

sys.dont_write_bytecode = True


def installer_module():
    spec = importlib.util.spec_from_file_location("_kittyscape_installed_validator", PROJECT / "packaging/installer.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def verify_artifact(args, installer):
    """Bind the archive, archived manifest, and extracted files before launching kitty."""
    args.bundle = args.bundle.resolve(strict=True)
    args.archive = args.archive.resolve(strict=True)
    hashes = installer.validate_bundle(args.bundle)
    assert hashes, "Extracted artifact must have a verified manifest"
    manifest = (args.bundle / "manifest.json").read_bytes()
    version = installer.version_of(args.bundle)
    checksum = verify_archive_members(args.archive, version, manifest, hashes)
    return {"archive": str(args.archive), "sha256": checksum,
            "manifest_sha256": hashlib.sha256(manifest).hexdigest(), "files_verified": len(hashes),
            "version": version, "extracted_bundle": str(args.bundle)}


def verify_archive_members(path, version, manifest, hashes):
    prefix = f"kittyscape-{version}/"
    expected = {prefix + name: checksum for name, checksum in hashes.items()}
    expected[prefix + "manifest.json"] = hashlib.sha256(manifest).hexdigest()
    content = path.read_bytes()
    with tarfile.open(fileobj=io.BytesIO(content)) as archive:
        entries = archive.getmembers()
        members = {entry.name: entry for entry in entries}
        assert len(members) == len(entries), "Archive contains duplicate members"
        assert set(members) == set(expected), "Archive inventory differs from its verified manifest"
        for name, checksum in expected.items():
            assert members[name].isfile(), f"Archive member is not a regular file: {name}"
            assert hashlib.sha256(archive.extractfile(members[name]).read()).hexdigest() == checksum, name
    return hashlib.sha256(content).hexdigest()


def file_record(path, installer):
    if path.is_symlink():
        return {"symlink": os.readlink(path)}
    return {"sha256": hashlib.sha256(installer.read_regular(path)).hexdigest(), "metadata": installer.file_metadata(path)}


def tree_record(root, installer):
    return {str(path.relative_to(root)): file_record(path, installer)
            for path in sorted(root.rglob("*")) if path.is_file() or path.is_symlink()}


class InstalledSession(Session):
    """Use generated installed configuration while retaining the existing scenario runner."""

    def __init__(self, args):
        self.installer = installer_module()
        self.artifact = verify_artifact(args, self.installer)
        self.setup_calls = []
        try:
            super().__init__(args)
        except Exception as error:
            if hasattr(self, "root"):
                (self.root / "startup-failure.json").write_text(json.dumps({"error": repr(error), "setup": self.setup_calls}, indent=2))
                print("Evidence: " + str(self.root), flush=True)
            if getattr(self, "pid", None):
                self.close()
            raise

    def _write_kitty_config(self):
        super()._write_kitty_config()
        direct = f"watcher {self.args.bundle / 'kittyscape/watcher.py'}\n"
        content = self.conf.read_text()
        assert content.count(direct) == 1, "Base fixture's direct product watcher changed"
        self.conf.write_text(content.replace(direct, "", 1))

    def _launch(self):
        # The installer's kitty-config directory is deliberately distinct from
        # the user-owned rules directory.  Moving the fixture before setup
        # also makes every later runtime scenario exercise location.json.
        rules_root = self.root / "kittyscape-rules"
        rules_root.mkdir()
        rules_file = rules_root / "kittyscape.json"
        self.config_file.replace(rules_file)
        self.config_file = rules_file
        self.rules_root = rules_root
        self.install_root = self.root / "kittyscape" / self.artifact["version"]
        self.preinstall_conf = self.conf.read_bytes()
        self.preinstall_conf_record = file_record(self.conf, self.installer)
        rules = file_record(self.config_file, self.installer)
        before = tree_record(self.root, self.installer)
        assert self.setup("install", preview=True)["status"] == "preview"
        assert tree_record(self.root, self.installer) == before, "Install preview wrote fixture files"
        self.record("T09-install-preview", {"writes": 0})
        assert self.setup("install")["status"] == "installed"
        installed = tree_record(self.root, self.installer)
        assert self.setup("install")["status"] == "already-installed"
        assert tree_record(self.root, self.installer) == installed, "Repeated install changed files"
        assert file_record(self.config_file, self.installer) == rules, "Installation changed user rules"
        self.original_conf = self.conf.read_bytes()
        self.record("T09-install-apply-repeat", {"version": self.artifact["version"], "user_rules_preserved": True})
        super()._launch()

    def setup(self, action, *, preview=False, apply=False, installed=False):
        assert not (preview and apply), "A preview must never request an apply"
        source = self.install_root if installed else self.args.bundle
        command = [str(self.args.kitty), "+launch", str(source / "setup.py"), action,
                   "--kitty-config-dir", str(self.root), "--config-dir", str(self.rules_root),
                   "--json", "--no-launch"]
        if preview:
            command.append("--preview")
        if apply:
            command.append("--apply")
        process = subprocess.run(command, capture_output=True, text=True, timeout=30)
        assert process.returncode == 0, process.stdout + process.stderr
        result = json.loads(process.stdout)
        assert "fresh_window" not in result, "Harness setup must not launch a daily-use kitty window"
        if preview:
            assert result["status"] == "preview", result
        if action == "install" and result["status"] in ("installed", "already-installed"):
            expected = self.rules_root / "kittyscape.json"
            location = json.loads((self.install_root / "kittyscape/location.json").read_text())
            assert Path(location["config"]) == expected, location
        self.setup_calls.append({"action": action, "preview": preview, "apply": apply,
                                 "helper": str(source / "setup.py"), "command": command, "result": result})
        return result

    def action(self, name, *, pane=1):
        action = self.install_root / "kittyscape/action.py"
        return json.loads(self.rc("kitten", "--match", f"id:{pane}", str(action), name, "--json"))

    def attest_installation(self):
        snapshot = self.inspect()
        expected = self.install_root / "kittyscape"
        assert Path(snapshot["engine_file"]).resolve() == expected / "engine.py", snapshot
        assert Path(snapshot["config_path"]).resolve() == self.config_file, snapshot
        assert str(expected / "watcher.py") in snapshot["watchers"], snapshot
        assert str(self.args.bundle / "kittyscape/watcher.py") not in snapshot["watchers"], snapshot
        record = {key: snapshot[key] for key in ("engine_file", "config_path", "watchers")}
        (self.root / "installed-load.json").write_text(json.dumps(record, indent=2))
        self.record("artifact-installed-runtime-origin", record)

    def restore_and_uninstall(self):
        self.action("resume")
        self.cd(self.dirs["A"])
        self.settle(self.dirs["A"])
        self.wait(lambda: self.status()["windows"]["1"]["owned"], "ownership before final restore")
        self.action("restore")
        restored = self.status()
        assert "1" in restored["windows"], restored
        assert all(not window["owned"] for window in restored["windows"].values()), restored
        self.wait(lambda: _is_color(self.pixel(), True), "restored externally selected baseline B")
        self.screenshot("restored-before-uninstall")
        self.record("T08-installed-explicit-restore", {"owned": False, "baseline": "external image B"})
        self.uninstall_files()
        after = self.inspect()
        assert "1" in after["runtime"]["windows"], after
        assert all(not window["owned"] for window in after["runtime"]["windows"].values()), after
        assert _is_color(self.pixel(), True), "Uninstall changed the restored background"
        self.screenshot("restored-after-uninstall")

    def uninstall_files(self):
        rules = file_record(self.config_file, self.installer)
        before = tree_record(self.root, self.installer)
        assert self.setup("uninstall", preview=True, installed=True)["status"] == "preview"
        assert tree_record(self.root, self.installer) == before, "Uninstall preview wrote fixture files"
        result = self.setup("uninstall", apply=True, installed=True)
        assert result["status"] == "removed" and not result["retained"], result
        removed = tree_record(self.root, self.installer)
        assert self.setup("uninstall", apply=True)["status"] == "already-removed"
        assert tree_record(self.root, self.installer) == removed, "Repeated uninstall changed files"
        assert self.conf.read_bytes() == self.preinstall_conf
        assert file_record(self.conf, self.installer) == self.preinstall_conf_record, "Original config metadata changed"
        assert file_record(self.config_file, self.installer) == rules, "Uninstall changed current user rules"
        assert not (self.root / "kittyscape").exists(), "Owned installation files remain"
        assert not (self.root / "kittyscape.conf").exists(), "Generated include remains"
        self.record("T09-artifact-uninstall-preview-apply-repeat", {"config_restored": True, "user_rules_preserved": True})


def save_result(session, error):
    args = session.args
    result = {"created_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
              "backend": args.backend, "platform": os.uname().sysname, "architecture": os.uname().machine,
              "kitty": session.runtime, "shell": subprocess.check_output([str(args.shell), "--version"], text=True).splitlines()[0],
              "baseline": args.baseline, "startup": "login" if args.login else "interactive",
              "artifact": session.artifact, "installation": "generated-include-only",
              "setup_calls": session.setup_calls, "scenarios": session.results, "error": error}
    (session.root / "result.json").write_text(json.dumps(result, indent=2))
    print("Evidence: " + str(session.root), flush=True)


def failure_evidence(session, error):
    try:
        (session.root / "failure-state.json").write_text(json.dumps(session.inspect(), indent=2))
        session.screenshot("failure")
    except Exception as failure:
        (session.root / "failure-capture.json").write_text(json.dumps({"error": repr(error), "capture_error": repr(failure)}, indent=2))


def qualify_installed(args):
    if args.backend == "x11":
        assert args.display.startswith(":") and args.display.split(".")[0] != ":0", "Use a dedicated local Xvfb display"
        assert Path(args.framebuffer).is_file(), "The dedicated Xvfb framebuffer must already exist"
    session = InstalledSession(args)
    error = None
    try:
        session.attest_installation()
        core_scenarios(session)
        focus_scenarios(session)
        lifecycle_scenarios(session)
        if args.performance:
            performance_scenario(session)
        session.restore_and_uninstall()
    except Exception as caught:
        error = repr(caught)
        failure_evidence(session, caught)
        raise
    finally:
        try:
            save_result(session, error)
        finally:
            session.close()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--bundle", type=Path, required=True, help="Extracted source artifact")
    parser.add_argument("--archive", type=Path, required=True, help="Original source .tar.gz whose manifest must match")
    parser.add_argument("--kitty", type=Path, default=Path("/usr/bin/kitty"))
    parser.add_argument("--shell", type=Path, default=Path("/usr/bin/bash"))
    parser.add_argument("--backend", choices=("wayland", "x11"), default="x11")
    parser.add_argument("--display", default=":101")
    parser.add_argument("--framebuffer", default="/tmp/kittyscape-x11-experiment/frames/Xvfb_screen0")
    parser.add_argument("--baseline", choices=("none", "single", "list"), default="none")
    parser.add_argument("--performance", action="store_true")
    parser.add_argument("--login", action="store_true")
    parser.add_argument("--zsh-modules", type=Path)
    parser.add_argument("--shell-lib-dirs")
    qualify_installed(parser.parse_args())


if __name__ == "__main__":
    main()
