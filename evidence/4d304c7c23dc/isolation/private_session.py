"""Own a headless Wayfire parent and private nested Hyprland test session."""

import argparse
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import tempfile
import time


CONFIG = '''hl.monitor({output="",mode="1280x800@60",position="auto",scale=1})
hl.config({
    xwayland={enabled=false},
    general={layout="dwindle",gaps_in=0,gaps_out=0,border_size=0},
    decoration={rounding=0,blur={enabled=false},shadow={enabled=false}},
    animations={enabled=false},
    misc={disable_hyprland_logo=true,disable_splash_rendering=true},
    ecosystem={no_update_news=true,no_donation_nag=true,enforce_permissions=false},
    cursor={no_hardware_cursors=1}
})
hl.window_rule({name="kittyscape-private-fixtures",match={class="kittyscape-qualification"},
    workspace="15 silent",float=true,size={960,640},move={20,20}})
'''


def base_environment(root, runtime):
    environment = {key: os.environ[key] for key in ("LANG", "LC_ALL", "TZ", "USER", "LOGNAME") if key in os.environ}
    environment.update({
        "PATH": "/usr/bin:/bin", "HOME": str(root / "home"), "SHELL": "/bin/sh", "ZDOTDIR": str(root / "home"),
        "XDG_RUNTIME_DIR": str(runtime), "XDG_CONFIG_HOME": str(root / "config"),
        "XDG_CACHE_HOME": str(root / "cache"), "XDG_DATA_HOME": str(root / "data"), "XDG_STATE_HOME": str(root / "state"),
        "XDG_SESSION_TYPE": "wayland", "DBUS_SESSION_BUS_ADDRESS": "unix:path=" + str(runtime / "bus"),
        "MESA_SHADER_CACHE_DIR": str(root / "cache/mesa"), "HYPRLAND_NO_SD_VARS": "1", "HYPRLAND_NO_SD_NOTIFY": "1",
    })
    return environment


def isolated(command, render):
    return ["/usr/bin/bwrap", "--ro-bind", "/", "/", "--dev", "/dev", "--dir", "/dev/dri",
            "--dev-bind", render, render, "--bind", "/tmp", "/tmp", "--unshare-net", "--unshare-ipc",
            "--die-with-parent", *command]


def publish(root, name, data):
    temporary = root / (name + ".tmp")
    temporary.write_text(json.dumps(data, indent=2) + "\n")
    temporary.chmod(0o600)
    temporary.replace(root / name)


def spawn(command, environment, path):
    with path.open("w") as stream:
        return subprocess.Popen(command, env=environment, stdin=subprocess.DEVNULL, stdout=stream, stderr=stream)


def wait_for(predicate, processes, root, label, seconds=15):
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        try:
            value = predicate()
        except (subprocess.CalledProcessError, json.JSONDecodeError):
            value = None
        if value:
            return value
        if any(process.poll() is not None for process in processes):
            raise RuntimeError(label + " process exited; inspect " + str(root))
        time.sleep(0.05)
    raise RuntimeError(label + " timed out; inspect " + str(root))


def ctl(environment, *arguments):
    assert Path(environment["XDG_RUNTIME_DIR"]).resolve().is_relative_to("/tmp")
    signature = environment["HYPRLAND_INSTANCE_SIGNATURE"]
    result = subprocess.run(["/usr/bin/hyprctl", "-i", signature, *arguments], env=environment, capture_output=True, text=True, timeout=3)
    if result.returncode:
        path = Path(environment["HOME"]).parent / "ipc-error.log"
        path.write_text(result.stdout + result.stderr)
        raise subprocess.CalledProcessError(result.returncode, result.args, result.stdout, result.stderr)
    return result.stdout


def run(root):
    saved = json.loads((root / "prepared.json").read_text())
    runtime = Path(saved["runtime"])
    environment = base_environment(root, runtime)
    processes = []
    stopped = False

    def stop(signum, frame):
        nonlocal stopped
        stopped = True

    signal.signal(signal.SIGTERM, stop)
    signal.signal(signal.SIGINT, stop)
    try:
        bus = spawn(["/usr/bin/dbus-daemon", "--config-file=" + str(root / "dbus.conf"), "--nofork", "--nopidfile"],
                    environment, root / "dbus.log")
        processes.append(bus)
        wait_for(lambda: (runtime / "bus").is_socket(), processes, root, "private bus")
        parent_env = dict(environment, WLR_BACKENDS="headless", WLR_HEADLESS_OUTPUTS="1", WLR_RENDERER="gles2",
                          WLR_RENDER_DRM_DEVICE=saved["render_node"], XDG_CURRENT_DESKTOP="wayfire")
        parent = spawn(isolated(["/usr/bin/wayfire", "--config", str(root / "wayfire.ini")], saved["render_node"]),
                       parent_env, root / "wayfire.log")
        processes.append(parent)
        sockets = wait_for(lambda: [path for path in runtime.glob("wayland-*") if path.is_socket()], processes, root, "Wayfire")
        child_env = dict(environment, WAYLAND_DISPLAY=sockets[0].name, XDG_CURRENT_DESKTOP="Hyprland",
                         LIBSEAT_BACKEND="noop", AQ_DRM_DEVICES="/dev/null", AQ_NO_KMS_REQUIREMENT="1")
        verify = subprocess.run(isolated(["/usr/bin/Hyprland", "--verify-config", "--config", str(root / "hyprland.lua")],
                                          saved["render_node"]), env=child_env, capture_output=True, text=True)
        (root / "config-verify.log").write_text(verify.stdout + verify.stderr)
        if verify.returncode:
            raise RuntimeError("Private Hyprland config validation failed")
        child = spawn(isolated(["/usr/bin/Hyprland", "--config", str(root / "hyprland.lua")], saved["render_node"]),
                      child_env, root / "hyprland.log")
        processes.append(child)
        instance = wait_for(lambda: [path for path in (runtime / "hypr").glob("*") if (path / ".socket.sock").is_socket()],
                            processes, root, "Hyprland IPC")[0]
        displays = wait_for(lambda: [path.name for path in runtime.glob("wayland-*")
                                    if path.is_socket() and path.name != sockets[0].name], processes, root, "Hyprland display")
        client_env = dict(environment, WAYLAND_DISPLAY=displays[0], HYPRLAND_INSTANCE_SIGNATURE=instance.name,
                          XDG_CURRENT_DESKTOP="Hyprland", LIBGL_ALWAYS_SOFTWARE="1",
                          __EGL_VENDOR_LIBRARY_FILENAMES="/usr/share/glvnd/egl_vendor.d/50_mesa.json",
                          LD_PRELOAD="/usr/lib/libwayland-client.so.0")
        publish(root, "starting-environment.json", client_env)
        available = wait_for(lambda: ctl(client_env, "-j", "monitors"), processes, root, "private IPC")
        if not json.loads(available):
            ctl(client_env, "output", "create", "headless", "KITTYSCAPE-HEADLESS")
        wait_for(lambda: json.loads(ctl(client_env, "-j", "monitors")), processes, root, "private output", seconds=45)
        ctl(client_env, "dispatch", "hl.dsp.focus({workspace=15})")
        ctl(client_env, "eval", 'hl.env("LIBGL_ALWAYS_SOFTWARE", "1"); '
            'hl.env("__EGL_VENDOR_LIBRARY_FILENAMES", "/usr/share/glvnd/egl_vendor.d/50_mesa.json"); '
            'hl.env("LD_PRELOAD", "/usr/lib/libwayland-client.so.0")')
        assert json.loads(ctl(client_env, "activeworkspace", "-j"))["id"] == 15
        assert not ctl(client_env, "configerrors").strip(), "Private config has errors"
        instances = json.loads(subprocess.check_output(["/usr/bin/hyprctl", "instances", "-j"], env=client_env, text=True))
        active = next(item for item in instances if item["instance"] == instance.name)
        state = {**saved, "status": "running", "supervisor_pid": os.getpid(), "dbus_pid": bus.pid,
                 "wayfire_wrapper_pid": parent.pid, "hyprland_wrapper_pid": child.pid, "hyprland_instance": active,
                 "parent_display": sockets[0].name, "environment": client_env,
                 "version": json.loads(ctl(client_env, "version", "-j")), "monitors": json.loads(ctl(client_env, "monitors", "-j"))}
        publish(root, "environment.json", client_env)
        publish(root, "session.json", state)
        while not stopped:
            if any(process.poll() is not None for process in processes):
                raise RuntimeError("A private session process exited")
            time.sleep(0.2)
    except Exception as error:
        publish(root, "error.json", {"error": repr(error), "supervisor_pid": os.getpid()})
        raise
    finally:
        for process in reversed(processes):
            if process.poll() is None:
                process.terminate()
        for process in reversed(processes):
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                publish(root, "cleanup-pending.json", {"pid": process.pid})


def start(render):
    assert str(render).startswith("/dev/dri/renderD") and render.is_char_device()
    root = Path(tempfile.mkdtemp(prefix="kittyscape-private-wayland-"))
    runtime = Path(tempfile.mkdtemp(prefix="kswl-"))
    for name in ("home", "config", "cache", "data", "state"):
        (root / name).mkdir(mode=0o700)
    runtime.chmod(0o700)
    (root / "wayfire.ini").write_text("[core]\nplugins =\nxwayland = false\nvwidth = 1\nvheight = 1\n"
                                      "[output:HEADLESS-1]\nmode = 1280x800\n")
    (root / "hyprland.lua").write_text(CONFIG)
    (root / "dbus.conf").write_text('<busconfig><type>session</type><listen>unix:path=' + str(runtime / "bus") + '</listen>'
                                    '<auth>EXTERNAL</auth><policy context="default"><allow send_destination="*"/>'
                                    '<allow receive_sender="*"/><allow own="*"/></policy></busconfig>')
    publish(root, "prepared.json", {"root": str(root), "runtime": str(runtime), "render_node": str(render)})
    with (root / "supervisor.log").open("w") as stream:
        process = subprocess.Popen([sys.executable, __file__, "run", "--root", str(root)],
                                   env=base_environment(root, runtime), stdin=subprocess.DEVNULL,
                                   stdout=stream, stderr=stream, start_new_session=True)
    print(json.dumps({"root": str(root), "runtime": str(runtime), "supervisor_pid": process.pid}), flush=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("start", "run", "stop"))
    parser.add_argument("--root", type=Path)
    parser.add_argument("--render-node", type=Path, default=Path("/dev/dri/renderD129"))
    args = parser.parse_args()
    if args.action == "start":
        start(args.render_node)
    elif args.action == "run":
        run(args.root)
    else:
        state = json.loads((args.root / "session.json").read_text())
        pid = state["supervisor_pid"]
        assert str(args.root).encode() in Path(f"/proc/{pid}/cmdline").read_bytes(), "Supervisor PID no longer matches"
        os.kill(pid, signal.SIGTERM)
