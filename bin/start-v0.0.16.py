#!/usr/bin/env python3

"""
start-v0.0.16.py
Hybrid RobotiX — HybX Development System

Start an app on the active board.
Reads board config from ~/.hybx/config.json.

Usage:
  start <app_name>
  start              (uses last app)
  start --compile    (force recompile even if sketch unchanged)
"""

import os
import sys
import time
sys.path.insert(0, os.path.dirname(os.path.realpath(__file__)))

import shutil  # noqa: E402
import time  # noqa: E402
import subprocess  # noqa: E402
from hybx_config import get_active_board  # noqa: E402

LAST_APP_FILE = os.path.expanduser("~/.hybx/last_app")


def save_last_app(app_name: str):
    os.makedirs(os.path.dirname(LAST_APP_FILE), exist_ok=True)
    with open(LAST_APP_FILE, "w") as f:
        f.write(app_name)


def load_last_app() -> str | None:
    if os.path.exists(LAST_APP_FILE):
        with open(LAST_APP_FILE, "r") as f:
            return f.read().strip()
    return None


def get_app_path(app_name: str, apps_path: str) -> str:
    if app_name.startswith("/") or app_name.startswith("~") or app_name.startswith("."):
        return app_name
    return os.path.expanduser(f"{apps_path}/{app_name}")


SKETCH_HASHES_FILE = os.path.expanduser("~/.hybx/sketch_hashes.json")


def get_sketch_hash(app_path: str) -> str:
    """Compute a hash of all sketch source files to detect changes."""
    import hashlib
    sketch_dir = os.path.join(app_path, "sketch")
    h = hashlib.md5()
    for root, _, files in os.walk(sketch_dir):
        for fname in sorted(files):
            fpath = os.path.join(root, fname)
            try:
                with open(fpath, "rb") as f:
                    h.update(f.read())
            except Exception:
                pass
    return h.hexdigest()


def load_sketch_hashes() -> dict:
    if os.path.exists(SKETCH_HASHES_FILE):
        with open(SKETCH_HASHES_FILE, "r") as f:
            import json
            return json.load(f)
    return {}


def save_sketch_hash(app_id: str, hash_val: str):
    import json
    hashes = load_sketch_hashes()
    hashes[app_id] = hash_val
    os.makedirs(os.path.dirname(SKETCH_HASHES_FILE), exist_ok=True)
    with open(SKETCH_HASHES_FILE, "w") as f:
        json.dump(hashes, f, indent=2)


def sketch_changed(app_path: str, app_id: str) -> bool:
    """Return True if sketch has changed since last successful compile."""
    current_hash = get_sketch_hash(app_path)
    stored_hashes = load_sketch_hashes()
    stored_hash = stored_hashes.get(app_id)
    if current_hash != stored_hash:
        save_sketch_hash(app_id, current_hash)
        return True
    return False


# App states reported by arduino-app-cli app list that mean
# the app is not running and safe to restart.
APP_STOPPED_STATES = {"stopped", "failed", "uninitialized"}


def get_app_status(app_id: str) -> str | None:
    """
    Return the current status of app_id from arduino-app-cli app list,
    or None if the app is not found in the list.
    Parses the STATUS column from the text output.
    """
    result = subprocess.run(
        ["arduino-app-cli", "app", "list"],
        capture_output=True,
        text=True,
    )
    for line in result.stdout.splitlines():
        # Match lines that contain the app id or name
        if app_id.lower() in line.lower():
            parts = line.split()
            # STATUS is the 4th column (0-indexed: ID NAME ICON STATUS)
            if len(parts) >= 4:
                return parts[3].lower()
    return None


def stop_app(app_path: str, app_id: str):
    """
    Stop the running app via arduino-app-cli and wait until
    arduino-app-cli app list reports a non-running state before
    returning. Also waits for the Docker container to be gone.
    """
    container_name = "arduino-" + app_id + "-main-1"
    print("Stopping app: " + app_id)
    subprocess.run(["arduino-app-cli", "app", "stop", app_path])

    # Poll Docker until container is gone
    print("Waiting for container to stop", end="", flush=True)
    while True:
        result = subprocess.run(
            ["docker", "ps", "-a",
             "--filter", "name=" + container_name,
             "--format", "{{.Names}}"],
            capture_output=True,
            text=True,
        )
        if container_name not in result.stdout:
            break
        print(".", end="", flush=True)
        time.sleep(1)
    print()

    # Poll arduino-app-cli app list until status is not running
    print("Waiting for app state to clear", end="", flush=True)
    for _ in range(60):
        status = get_app_status(app_id)
        if status is None or status in APP_STOPPED_STATES:
            break
        print(".", end="", flush=True)
        time.sleep(1)
    print()
    print("App stopped.")


def nuke_docker(app_id: str):
    container_name = "arduino-" + app_id + "-main-1"
    subprocess.run(["docker", "rm", "-f", container_name], capture_output=True)
    subprocess.run(["docker", "rmi", "-f", "arduino-" + app_id + "-main"], capture_output=True)
    print("Removed Docker container and image for: " + app_id)


def clear_cache(app_path: str):
    cache_path = os.path.join(app_path, ".cache")
    if os.path.exists(cache_path):
        shutil.rmtree(cache_path)
        print(f"Cleared cache: {cache_path}")


def patch_compose(app_path: str):
    """
    Patch the generated app-compose.yaml to mount $HOME into the container.
    """
    home = os.path.expanduser("~")
    compose_file = os.path.join(app_path, ".cache", "app-compose.yaml")

    print("Waiting for compose file...")
    for _ in range(120):
        if os.path.exists(compose_file):
            break
        time.sleep(0.5)

    if not os.path.exists(compose_file):
        print("WARNING: compose file not found — skipping $HOME mount patch")
        return

    home_mount = (
        f"    - type: bind\n"
        f"      source: {home}\n"
        f"      target: {home}\n"
    )

    with open(compose_file, "r") as f:
        content = f.read()

    if f"source: {home}" in content:
        print(f"$HOME already mounted in compose file")
        return

    content = content.replace("    volumes:\n", f"    volumes:\n{home_mount}", 1)

    with open(compose_file, "w") as f:
        f.write(content)

    print(f"Patched compose file: mounted {home} into container")

    subprocess.run([
        "docker", "compose",
        "-f", compose_file,
        "up", "-d", "--force-recreate"
    ], capture_output=True)


def install_update():
    home     = os.path.expanduser("~")
    dev_repo = os.path.expanduser("~/Repos/GitHub/hybotix/HybX-Development-System")
    uno_repo = os.path.expanduser("~/Repos/GitHub/hybotix/UNO-Q")
    update_src = os.path.join(dev_repo, "scripts", "update.bash")
    update_dst  = os.path.expanduser("~/bin/update")

    # Pull latest Dev System
    subprocess.run(["git", "-C", dev_repo, "pull"], capture_output=True)

    # Pull latest UNO-Q and sync Arduino apps to $HOME
    if os.path.exists(uno_repo):
        subprocess.run(["git", "-C", uno_repo, "pull"], capture_output=True)
        arduino_src = os.path.join(uno_repo, "Arduino")
        arduino_dst = os.path.join(home, "Arduino")
        if os.path.exists(arduino_src):
            import shutil as _shutil
            if os.path.exists(arduino_dst):
                _shutil.rmtree(arduino_dst)
            _shutil.copytree(arduino_src, arduino_dst)

    if os.path.exists(update_src):
        # Deploy update.bash to ~/bin/ like every other command file
        update_bash_dst = os.path.join(home, "bin", "update.bash")
        shutil.copy2(update_src, update_bash_dst)
        os.chmod(update_bash_dst, 0o755)
        print("Installed: update.bash -> ~/bin/update.bash")

    # Remove the old command symlink from before it was renamed to 'update'
    old_cmd_name = "".join(["n", "e", "w", "r", "e", "p", "o"])
    old_cmd = os.path.join(home, "bin", old_cmd_name)
    if os.path.exists(old_cmd) or os.path.islink(old_cmd):
        os.remove(old_cmd)
        print("Removed old command symlink from ~/bin")

    # Sync all bin commands from dev repo to ~/bin/
    bin_src = os.path.join(dev_repo, "bin")
    bin_dst = os.path.join(home, "bin")
    if os.path.exists(bin_src) and os.path.exists(bin_dst):
        for fname in os.listdir(bin_src):
            src = os.path.join(bin_src, fname)
            dst = os.path.join(bin_dst, fname)
            if os.path.isfile(src):
                shutil.copy2(src, dst)
        # Relink symlinks to latest versions
        commands = ["board", "build", "clean", "FINALIZE", "libs", "list", "logs",
                    "migrate", "project", "restart", "setup", "start", "stop",
                    "update"]
        for cmd in commands:
            import glob
            versions = sorted(glob.glob(os.path.join(bin_dst, f"{cmd}-v*.py")))
            if versions:
                latest = versions[-1]
                link = os.path.join(bin_dst, cmd)
                if os.path.islink(link):
                    os.remove(link)
                os.symlink(latest, link)
                os.chmod(latest, 0o755)


def main():
    os.system("clear")
    print("=== start ===")

    board = get_active_board()
    print(f"Board: {board['name']} ({board['host']})")

    # Pull and sync latest bin commands FIRST so next run is always current
    install_update()

    # Step 1: Strip all flags from argv
    force_compile = "--compile" in sys.argv
    args = [a for a in sys.argv[1:] if not a.startswith("--")]

    # Step 2: Determine app name from args or persistent file
    if args:
        app_name = args[0]
    else:
        app_name = load_last_app()
        if not app_name:
            print("Usage: start <app_name>")
            print("       start <app_name> --compile")
            sys.exit(1)
        print(f"Using last app: {app_name}")

    # Step 3: Now that we have a confirmed valid app name, save it
    save_last_app(app_name)

    app_path = get_app_path(app_name, board["apps_path"])
    app_id   = os.path.basename(app_path)

    stop_app(app_path, app_id)
    nuke_docker(app_id)

    if force_compile:
        print(f"Forced recompile — clearing cache")
        clear_cache(app_path)
        save_sketch_hash(app_id, get_sketch_hash(app_path))
    elif sketch_changed(app_path, app_id):
        print(f"Sketch changed — clearing cache for recompile")
        clear_cache(app_path)
    else:
        print(f"Sketch unchanged — skipping recompile")

    subprocess.run(["arduino-app-cli", "app", "start", app_path], cwd=os.path.expanduser("~"))
    patch_compose(app_path)


if __name__ == "__main__":
    main()
