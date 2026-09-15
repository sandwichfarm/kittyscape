"""Filesystem and extracted-artifact acceptance for the user-local installer."""

import hashlib
import importlib.util
import json
import os
from pathlib import Path
import shutil
import stat
import subprocess
import tarfile
import tempfile
import unittest
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[2]


def load_module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


installer = load_module("kittyscape_installer_tests", ROOT / "packaging/installer.py")
builder = load_module("kittyscape_builder_tests", ROOT / "packaging/builder.py")


def tree_state(root):
    result = {}
    if root.exists():
        for path in sorted(root.rglob("*")):
            info = path.lstat()
            content = os.readlink(path) if path.is_symlink() else path.read_bytes() if path.is_file() else None
            result[str(path.relative_to(root))] = (stat.S_IMODE(info.st_mode), content)
    return result


class InstallationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="kittyscape-install-")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.source = self.root / "source bundle"
        self.source.mkdir()
        (self.source / "kittyscape").mkdir()
        (self.source / "kittyscape/__init__.py").write_text("__version__ = '0.1.0.dev1'\n")
        (self.source / "kittyscape/watcher.py").write_text("def on_load(boss, data):\n    pass\n")
        (self.source / "kittyscape/action.py").write_text("def main(args):\n    pass\n")
        (self.source / "README.md").write_text("Fixture installation bundle.\n")
        shutil.copy2(ROOT / "setup.py", self.source / "setup.py")
        shutil.copytree(ROOT / "packaging", self.source / "packaging", ignore=shutil.ignore_patterns("__pycache__"))
        self.config = self.root / "configuration with spaces"
        self.config.mkdir()
        self.conf = self.config / "kitty.conf"
        self.original = b"font_size 13\ninclude theme.conf\n# no final newline"
        self.conf.write_bytes(self.original)
        self.conf.chmod(0o640)
        os.utime(self.conf, ns=(1_700_000_000_111_000_000, 1_700_000_000_222_000_000))
        (self.config / "theme.conf").write_bytes(b"background #112233\n")
        self.installed = self.config / "kittyscape/0.1.0.dev1"

    def install(self, apply=True):
        return installer.install(self.source, self.config, apply=apply)

    def test_preview_writes_nothing(self):
        before = tree_state(self.root)
        result = self.install(apply=False)
        self.assertEqual(result["status"], "preview")
        self.assertIn("watcher ", result["generated_config"])
        self.assertEqual(tree_state(self.root), before)

    def test_preview_missing_config_directory_writes_nothing(self):
        absent = self.root / "absent/config"
        installer.install(self.source, absent)
        self.assertFalse((self.root / "absent").exists())

    def test_install_repeat_and_remove_preserve_bytes_and_metadata(self):
        before = self.conf.stat()
        self.assertEqual(self.install()["status"], "installed")
        state = tree_state(self.config)
        self.assertEqual(self.install()["status"], "already-installed")
        self.assertEqual(tree_state(self.config), state)
        self.assertEqual(installer.uninstall(self.config, apply=True)["status"], "removed")
        self.assertEqual(self.conf.read_bytes(), self.original)
        after = self.conf.stat()
        self.assertEqual((after.st_mode, after.st_uid, after.st_gid, after.st_mtime_ns),
                         (before.st_mode, before.st_uid, before.st_gid, before.st_mtime_ns))
        self.assertFalse((self.config / "kittyscape").exists())
        self.assertEqual(installer.uninstall(self.config, apply=True)["status"], "already-removed")

    def test_symlink_config_and_includes_survive(self):
        target = self.root / "actual kitty.conf"
        self.conf.rename(target)
        self.conf.symlink_to(target)
        before = target.stat()
        include = (self.config / "theme.conf").read_bytes()
        self.install()
        self.assertTrue(self.conf.is_symlink())
        installer.uninstall(self.config, apply=True)
        self.assertEqual(os.readlink(self.conf), str(target))
        self.assertEqual(target.read_bytes(), self.original)
        self.assertEqual(target.stat().st_mtime_ns, before.st_mtime_ns)
        self.assertEqual((self.config / "theme.conf").read_bytes(), include)

    def test_location_metadata_and_user_configuration(self):
        user_config = self.config / "kittyscape.json"
        user_config.write_bytes(b'{"user-owned": true}\n')
        self.install()
        location = json.loads((self.installed / "kittyscape/location.json").read_text())
        self.assertEqual(location, {"config": str(user_config)})
        installer.uninstall(self.config, apply=True)
        self.assertEqual(user_config.read_bytes(), b'{"user-owned": true}\n')

    def test_separate_rules_configuration_is_created_and_preserved(self):
        rules = self.root / "user configuration" / "kittyscape"
        result = installer.install(self.source, self.config, rules_dir=rules, apply=True)
        config = rules / "kittyscape.json"
        self.assertTrue(result["config_created"])
        self.assertEqual(json.loads(config.read_text()), {"version": 1, "enabled": True, "rules": []})
        location = json.loads((self.installed / "kittyscape/location.json").read_text())
        self.assertEqual(location, {"config": str(config)})
        installer.uninstall(self.config, apply=True)
        self.assertTrue(config.exists(), "Rules are user-owned and remain after uninstall")

    def test_one_step_main_installs_and_opens_a_fresh_window(self):
        rules = self.root / "user configuration" / "kittyscape"
        output = []
        with patch.object(installer, "kitty_capabilities", return_value={"required_apis": "present"}), patch.object(
            installer, "launch_kitty", return_value={"status": "started", "pid": 42},
        ) as launch, patch("builtins.print", side_effect=output.append):
            code = installer.main(["install", "--json", "--kitty-config-dir", str(self.config), "--config-dir", str(rules)],
                                  bundle_root=self.source, default_config_dir=self.config,
                                  default_rules_dir=rules, kitty_executable="/fake/kitty")
        self.assertEqual(code, 0)
        result = json.loads(output[-1])
        self.assertEqual(result["status"], "installed")
        self.assertTrue((rules / "kittyscape.json").exists())
        launch.assert_called_once_with("/fake/kitty", self.config)

    def test_preview_does_not_create_the_separate_rules_configuration(self):
        rules = self.root / "user configuration" / "kittyscape"
        output = []
        with patch.object(installer, "kitty_capabilities", return_value={}), patch("builtins.print", side_effect=output.append):
            code = installer.main(["install", "--json", "--preview", "--kitty-config-dir", str(self.config), "--config-dir", str(rules)],
                                  bundle_root=self.source, default_config_dir=self.config,
                                  default_rules_dir=rules, kitty_executable="/fake/kitty")
        self.assertEqual(code, 0)
        self.assertEqual(json.loads(output[-1])["status"], "preview")
        self.assertFalse(rules.exists())

    def test_human_install_output_is_actionable_without_file_inventory(self):
        text = installer.display_result({
            "action": "install", "status": "installed", "config_file": "/home/user/.config/kittyscape/kittyscape.json",
            "config_created": True, "fresh_window": {"status": "started", "pid": 42},
            "files": ["a" * 100],
        })
        self.assertIn("Kittyscape is ready", text)
        self.assertIn("kittyscape.json", text)
        self.assertIn("Ctrl+Shift+F9", text)
        self.assertNotIn("a" * 100, text)

    def test_dangling_rules_configuration_symlink_is_rejected(self):
        rules = self.root / "user configuration" / "kittyscape"
        rules.mkdir(parents=True)
        (rules / "kittyscape.json").symlink_to(self.root / "missing.json")
        with self.assertRaises(installer.InstallError):
            installer.install(self.source, self.config, rules_dir=rules, apply=True)

    def test_uninstall_preserves_later_unrelated_edits(self):
        self.install()
        self.conf.write_bytes(self.conf.read_bytes() + b"\n# Added later\nfont_size 17\n")
        installer.uninstall(self.config, apply=True)
        self.assertEqual(self.conf.read_bytes(), self.original + b"\n# Added later\nfont_size 17\n")

    def test_uninstall_preview_has_no_changes(self):
        self.install()
        before = tree_state(self.config)
        installer.uninstall(self.config)
        self.assertEqual(tree_state(self.config), before)

    def test_conflicting_unowned_files_are_never_overwritten(self):
        for relative in ("kittyscape.conf", "kittyscape/0.1.0.dev1/kittyscape/watcher.py"):
            with self.subTest(relative=relative):
                path = self.config / relative
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(b"user content")
                before = tree_state(self.config)
                with self.assertRaises(installer.InstallError):
                    self.install()
                self.assertEqual(tree_state(self.config), before)
                path.unlink()

    def test_modified_owned_files_are_retained_and_reported(self):
        self.install()
        watcher = self.installed / "kittyscape/watcher.py"
        watcher.write_bytes(b"# User edit\n")
        result = installer.uninstall(self.config, apply=True)
        self.assertIn("kittyscape/0.1.0.dev1/kittyscape/watcher.py", result["retained"])
        self.assertEqual(watcher.read_bytes(), b"# User edit\n")
        self.assertEqual(self.conf.read_bytes(), self.original)
        self.assertEqual(installer.uninstall(self.config, apply=True)["retained"], result["retained"])

    def test_modified_installation_cannot_be_replaced_by_repeat(self):
        self.install()
        watcher = self.installed / "kittyscape/watcher.py"
        watcher.write_bytes(b"# User edit\n")
        before = tree_state(self.config)
        with self.assertRaises(installer.InstallError):
            self.install()
        self.assertEqual(tree_state(self.config), before)

    def test_corrupt_backup_blocks_uninstall_and_rollback(self):
        self.install()
        (self.config / "kittyscape/kitty.conf.backup").write_bytes(b"corrupted")
        before = tree_state(self.config)
        for action in (installer.uninstall, installer.rollback):
            with self.assertRaises(installer.InstallError):
                action(self.config, apply=True)
            self.assertEqual(tree_state(self.config), before)

    def test_rollback_restores_original_and_refuses_unrelated_edits(self):
        self.install()
        installer.rollback(self.config, apply=True)
        self.assertEqual(self.conf.read_bytes(), self.original)
        self.install()
        self.conf.write_bytes(self.conf.read_bytes() + b"# Later edit\n")
        before = tree_state(self.config)
        with self.assertRaises(installer.InstallError):
            installer.rollback(self.config, apply=True)
        self.assertEqual(tree_state(self.config), before)

    def test_missing_original_config_is_removed_without_losing_new_content(self):
        self.conf.unlink()
        self.install()
        installer.rollback(self.config, apply=True)
        self.assertFalse(self.conf.exists())
        self.install()
        self.conf.write_bytes(self.conf.read_bytes() + b"font_size 19\n")
        installer.uninstall(self.config, apply=True)
        self.assertEqual(self.conf.read_bytes(), b"font_size 19\n")

    def test_retargeted_config_symlink_is_refused(self):
        target = self.root / "original-target.conf"
        self.conf.rename(target)
        self.conf.symlink_to(target)
        self.install()
        other = self.root / "different.conf"
        other.write_bytes(b"untouched")
        self.conf.unlink()
        self.conf.symlink_to(other)
        with self.assertRaises(installer.InstallError):
            installer.uninstall(self.config, apply=True)
        self.assertEqual(other.read_bytes(), b"untouched")

    def test_changed_owned_file_symlink_never_deletes_external_target(self):
        self.install()
        external = self.root / "external.py"
        external.write_bytes(b"preserve me")
        watcher = self.installed / "kittyscape/watcher.py"
        watcher.unlink()
        watcher.symlink_to(external)
        result = installer.uninstall(self.config, apply=True)
        self.assertTrue(result["retained"])
        self.assertEqual(external.read_bytes(), b"preserve me")

    def test_failed_install_rolls_back_created_files(self):
        before = tree_state(self.config)
        write = installer.write_new

        def fail_on_action(path, data, **kwargs):
            if path.name == "action.py":
                raise OSError("injected copy failure")
            return write(path, data, **kwargs)

        with patch.object(installer, "write_new", side_effect=fail_on_action):
            with self.assertRaises(OSError):
                self.install()
        self.assertEqual(tree_state(self.config), before)

    def test_builder_is_deterministic_and_excludes_unrelated_files(self):
        (self.source / ".secret").write_text("never package")
        (self.source / "kittyscape/ignored.pyc").write_bytes(b"cache")
        theme = self.source / "docs/.vitepress/theme/index.js"
        theme.parent.mkdir(parents=True)
        theme.write_text("export default {}\n")
        evidence = self.source / "docs/public/evidence/release.json"
        evidence.parent.mkdir(parents=True)
        evidence.write_text('{"artifact": "prior build"}\n')
        first = builder.build_release(self.source, self.root / "release one")
        evidence.write_text('{"artifact": "new build"}\n')
        second = builder.build_release(self.source, self.root / "release two")
        self.assertEqual(first.read_bytes(), second.read_bytes())
        with tarfile.open(first) as archive:
            names = archive.getnames()
            self.assertIn("kittyscape-0.1.0.dev1/manifest.json", names)
            self.assertIn("kittyscape-0.1.0.dev1/docs/.vitepress/theme/index.js", names)
            record = json.load(archive.extractfile("kittyscape-0.1.0.dev1/docs/public/evidence/release.json"))
            self.assertEqual(record["status"], "source-build-unqualified")
            self.assertIsNone(record["artifact"])
            self.assertFalse(any(".secret" in item or item.endswith(".pyc") for item in names))
        checksum = hashlib.sha256(first.read_bytes()).hexdigest()
        self.assertIn(checksum, (first.parent / "SHA256SUMS").read_text())

    @unittest.skipUnless(shutil.which("kitty"), "kitty embedded runtime unavailable")
    def test_extracted_artifact_cli_preview_install_remove(self):
        archive = builder.build_release(self.source, self.root / "dist")
        extracted = self.root / "extracted artifact"
        extracted.mkdir()
        with tarfile.open(archive) as bundle:
            bundle.extractall(extracted, filter="data")
        setup = extracted / "kittyscape-0.1.0.dev1/setup.py"
        base = [shutil.which("kitty"), "+launch", str(setup)]
        rules = self.root / "user rules"
        before = tree_state(self.config)
        preview = subprocess.run(base + ["install", "--json", "--preview", "--no-launch", "--kitty-config-dir", str(self.config),
                                         "--config-dir", str(rules)], capture_output=True, text=True, check=True)
        self.assertEqual(json.loads(preview.stdout)["status"], "preview")
        self.assertEqual(tree_state(self.config), before)
        subprocess.run(base + ["install", "--json", "--no-launch", "--kitty-config-dir", str(self.config),
                               "--config-dir", str(rules)], capture_output=True, check=True)
        installed_setup = self.installed / "setup.py"
        subprocess.run([shutil.which("kitty"), "+launch", str(installed_setup), "uninstall", "--json",
                        "--kitty-config-dir", str(self.config), "--apply"], capture_output=True, check=True)
        self.assertEqual(tree_state(self.config), before)

    def test_untracked_user_file_is_retained_and_reported(self):
        self.install()
        note = self.installed / "my notes.txt"
        note.write_bytes(b"keep this")
        result = installer.uninstall(self.config, apply=True)
        self.assertIn("kittyscape/0.1.0.dev1/my notes.txt", result["retained"])
        self.assertEqual(note.read_bytes(), b"keep this")

    def test_manifest_rejects_changed_and_unlisted_code(self):
        archive = builder.build_release(self.source, self.root / "dist")
        extracted = self.root / "extracted"
        extracted.mkdir()
        with tarfile.open(archive) as bundle:
            bundle.extractall(extracted, filter="data")
        source = extracted / "kittyscape-0.1.0.dev1"
        extra = source / "kittyscape/unlisted.py"
        extra.write_bytes(b"# not in manifest\n")
        with self.assertRaises(installer.InstallError):
            installer.install(source, self.config, apply=True)
        extra.unlink()
        (source / "kittyscape/watcher.py").write_bytes(b"# changed after build\n")
        with self.assertRaises(installer.InstallError):
            installer.install(source, self.config, apply=True)

    def test_unreadable_backup_preserves_installation(self):
        self.install()
        backup = self.config / "kittyscape/kitty.conf.backup"
        backup.chmod(0)
        before = tree_state(self.config.parent) if os.geteuid() == 0 else self.conf.read_bytes()
        try:
            if os.geteuid() == 0:
                self.skipTest("root can read permission-zero files")
            with self.assertRaises(PermissionError):
                installer.rollback(self.config, apply=True)
            self.assertEqual(self.conf.read_bytes(), before)
        finally:
            backup.chmod(0o600)

    @unittest.skipUnless(hasattr(os, "setxattr"), "filesystem extended attributes unavailable")
    def test_config_extended_attributes_survive_roundtrip(self):
        try:
            os.setxattr(self.conf, "user.kittyscape_test", b"original metadata")
        except OSError as error:
            self.skipTest(str(error))
        self.install()
        installer.uninstall(self.config, apply=True)
        self.assertEqual(os.getxattr(self.conf, "user.kittyscape_test"), b"original metadata")

    def test_uninstall_retains_edited_config_and_package_permissions(self):
        self.install()
        self.conf.chmod(0o600)
        watcher = self.installed / "kittyscape/watcher.py"
        watcher.chmod(0o400)
        result = installer.uninstall(self.config, apply=True)
        self.assertEqual(stat.S_IMODE(self.conf.stat().st_mode), 0o600)
        self.assertIn("kittyscape/0.1.0.dev1/kittyscape/watcher.py", result["retained"])
        self.assertEqual(stat.S_IMODE(watcher.stat().st_mode), 0o400)

    def test_interrupted_removal_can_resume_without_losing_later_edits(self):
        self.install()
        self.conf.write_bytes(self.conf.read_bytes() + b"# later customization\n")
        unlink = Path.unlink

        def fail_on_watcher(path, *args, **kwargs):
            if path.name == "watcher.py":
                raise PermissionError("injected removal failure")
            return unlink(path, *args, **kwargs)

        with patch.object(Path, "unlink", fail_on_watcher):
            with self.assertRaises(PermissionError):
                installer.uninstall(self.config, apply=True)
        installer.uninstall(self.config, apply=True)
        self.assertEqual(self.conf.read_bytes(), self.original + b"# later customization\n")

    def test_uninstall_refuses_concurrent_config_save_and_can_retry(self):
        self.install()
        update = installer.update_receipt
        addition = b"\n# concurrent user change\nfont_size 27\n"

        def save_after_receipt(root, receipt):
            update(root, receipt)
            self.conf.write_bytes(self.conf.read_bytes() + addition)

        with patch.object(installer, "update_receipt", save_after_receipt):
            with self.assertRaises(installer.InstallError):
                installer.uninstall(self.config, apply=True)
        self.assertTrue(self.conf.read_bytes().endswith(addition))
        self.assertTrue((self.installed / "kittyscape/watcher.py").exists())
        self.assertTrue((self.config / installer.RECEIPT).exists())
        self.assertEqual((self.config / installer.BACKUP).read_bytes(), self.original)
        installer.uninstall(self.config, apply=True)
        self.assertEqual(self.conf.read_bytes(), self.original + addition)

    def test_rollback_refuses_concurrent_config_save(self):
        self.install()
        update = installer.update_receipt

        def save_after_receipt(root, receipt):
            update(root, receipt)
            self.conf.write_bytes(self.conf.read_bytes() + b"\nfont_size 27\n")

        with patch.object(installer, "update_receipt", save_after_receipt):
            with self.assertRaises(installer.InstallError):
                installer.rollback(self.config, apply=True)
        self.assertTrue(self.conf.read_bytes().endswith(b"\nfont_size 27\n"))
        self.assertTrue((self.config / installer.RECEIPT).exists())

    def test_config_deletion_refuses_concurrent_save(self):
        self.conf.unlink()
        self.install()
        update = installer.update_receipt

        def save_after_receipt(root, receipt):
            update(root, receipt)
            self.conf.write_bytes(self.conf.read_bytes() + b"font_size 27\n")

        with patch.object(installer, "update_receipt", save_after_receipt):
            with self.assertRaises(installer.InstallError):
                installer.uninstall(self.config, apply=True)
        self.assertTrue(self.conf.exists())
        self.assertTrue(self.conf.read_bytes().endswith(b"font_size 27\n"))
        self.assertTrue((self.installed / "kittyscape/watcher.py").exists())

    def test_removal_refuses_concurrent_config_symlink_retarget(self):
        target = self.root / "original-target.conf"
        self.conf.rename(target)
        self.conf.symlink_to(target)
        self.install()
        before = target.read_bytes()
        other = self.root / "new-target.conf"
        other.write_bytes(b"font_size 27\n")
        update = installer.update_receipt

        def retarget_after_receipt(root, receipt):
            update(root, receipt)
            self.conf.unlink()
            self.conf.symlink_to(other)

        with patch.object(installer, "update_receipt", retarget_after_receipt):
            with self.assertRaises(installer.InstallError):
                installer.uninstall(self.config, apply=True)
        self.assertEqual(target.read_bytes(), before)
        self.assertEqual(other.read_bytes(), b"font_size 27\n")
        self.assertEqual(self.conf.resolve(), other)
        self.assertTrue((self.config / installer.RECEIPT).exists())

    def test_uninstall_rechecks_after_staging_replacement(self):
        self.install()
        copy_metadata = installer.copy_metadata

        def save_during_staging(source, destination):
            copy_metadata(source, destination)
            if source == self.conf:
                saved = self.root / "editor-save.conf"
                saved.write_bytes(self.conf.read_bytes() + b"\nfont_size 27\n")
                saved.replace(self.conf)

        with patch.object(installer, "copy_metadata", save_during_staging):
            with self.assertRaises(installer.InstallError):
                installer.uninstall(self.config, apply=True)
        self.assertTrue(self.conf.read_bytes().endswith(b"\nfont_size 27\n"))
        self.assertTrue((self.installed / "kittyscape/watcher.py").exists())

    @unittest.skipUnless(hasattr(os, "setxattr"), "filesystem extended attributes unavailable")
    def test_uninstall_retains_xattr_only_package_edit(self):
        self.install()
        watcher = self.installed / "kittyscape/watcher.py"
        try:
            os.setxattr(watcher, "user.kittyscape_review", b"user metadata")
        except OSError as error:
            self.skipTest(str(error))
        result = installer.uninstall(self.config, apply=True)
        self.assertIn("kittyscape/0.1.0.dev1/kittyscape/watcher.py", result["retained"])
        self.assertEqual(os.getxattr(watcher, "user.kittyscape_review"), b"user metadata")

    @unittest.skipUnless(hasattr(os, "setxattr"), "filesystem extended attributes unavailable")
    def test_rollback_refuses_xattr_only_config_edit(self):
        try:
            os.setxattr(self.conf, "user.kittyscape_review", b"original metadata")
        except OSError as error:
            self.skipTest(str(error))
        self.install()
        os.setxattr(self.conf, "user.kittyscape_review", b"later metadata")
        before = self.conf.read_bytes()
        with self.assertRaises(installer.InstallError):
            installer.rollback(self.config, apply=True)
        self.assertEqual(self.conf.read_bytes(), before)
        self.assertEqual(os.getxattr(self.conf, "user.kittyscape_review"), b"later metadata")
        self.assertTrue((self.config / installer.RECEIPT).exists())

    @unittest.skipUnless(shutil.which("kitty"), "kitty runtime unavailable")
    def test_generated_config_parses_with_spaces_and_quoted_kitten_paths(self):
        self.install()
        code = (
            "import json,sys; from kitty.config import load_config; errors=[]; "
            "opts=load_config(sys.argv[1],accumulate_bad_lines=errors); "
            "assert not errors,errors; print(json.dumps(list(opts.watcher)))"
        )
        for executable in (shutil.which("kitty"), "/tmp/kittyscape-tools/kitty-0.38.1/bin/kitty"):
            if not Path(executable).exists():
                continue
            with self.subTest(kitty=executable):
                result = subprocess.run([executable, "+runpy", code, str(self.conf)], capture_output=True, text=True)
                self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
                self.assertEqual(json.loads(result.stdout), [str(self.installed / "kittyscape/watcher.py")])

    @unittest.skipUnless(Path("/tmp/kittyscape-tools/kitty-0.38.1/bin/kitty").exists(), "candidate portable kitty unavailable")
    def test_candidate_embedded_runtime_install_and_remove(self):
        executable = "/tmp/kittyscape-tools/kitty-0.38.1/bin/kitty"
        rules = self.root / "user rules"
        for action, extra in (("install", ["--preview", "--no-launch"]), ("install", ["--no-launch"]),
                              ("rollback", ["--apply"])):
            result = subprocess.run([executable, "+launch", str(self.source / "setup.py"), action,
                                     "--kitty-config-dir", str(self.config), "--config-dir", str(rules)] + extra,
                                    capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(self.conf.read_bytes(), self.original)

    def test_system_python_has_actionable_cli_diagnostic(self):
        result = subprocess.run([shutil.which("python"), str(self.source / "setup.py"), "install",
                                 "--kitty-config-dir", str(self.config), "--config-dir", str(self.config), "--apply"],
                                capture_output=True, text=True)
        self.assertEqual(result.returncode, 1)
        self.assertIn("kitty +launch", result.stdout)
        self.assertEqual(self.conf.read_bytes(), self.original)

    @unittest.skipUnless(shutil.which("kitty"), "kitty runtime unavailable")
    def test_missing_kitty_capability_prevents_installation(self):
        code = (
            "import runpy,sys; import kitty.fast_data_types as f; del f.add_timer; "
            "runpy.run_path(sys.argv[1])['main']([sys.argv[1], 'install', '--kitty-config-dir', sys.argv[2], '--apply'])"
        )
        before = tree_state(self.config)
        result = subprocess.run([shutil.which("kitty"), "+runpy", code, str(self.source / "setup.py"), str(self.config)],
                                capture_output=True, text=True)
        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        self.assertIn("add_timer", result.stdout)
        self.assertEqual(tree_state(self.config), before)


if __name__ == "__main__":
    unittest.main()
