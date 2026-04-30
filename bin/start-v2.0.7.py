#!/usr/bin/env python3

"""
start-v2.0.7.py
Hybrid RobotiX — HybX Development System

Start an app on the active board.
Reads board config from ~/.hybx/config.json.

Usage:
  start <app_name>
  start              (uses last app)
  start --compile    (force recompile even if sketch unchanged)
  start --log        (also write all output to ~/start.log)
"""

import os
import signal
import sys
import time
sys.path.insert(0, os.path.dirname(os.path.realpath(__file__)))
sys.path.insert(0, os.path.expanduser("~/lib"))

import shutil  # noqa: E402
import subprocess  # noqa: E402
from hybx_config import get_active_board, mask_host, HybXTimer, HybXTee  # noqa: E402

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

    # Poll arduino-app-cli app list until status is not running.
    # If Docker container is already gone, trust that over arduino-app-cli's
    # internal state — app-cli can get stuck in "stopping" even after the
    # container is fully removed.
    print("Waiting for app state to clear", end="", flush=True)
    timed_out = True
    for _ in range(60):
        # Check Docker first — if container is gone, we're done regardless
        docker_result = subprocess.run(
            ["docker", "ps", "-a", "--filter", "name=" + container_name,
             "--format", "{{.Names}}"],
            capture_output=True, text=True,
        )
        if container_name not in docker_result.stdout:
            timed_out = False
            break
        status = get_app_status(app_id)
        if status is None or status in APP_STOPPED_STATES:
            timed_out = False
            break
        print(".", end="", flush=True)
        time.sleep(1)
    print()
    if timed_out:
        print("Warning: app state did not clear after 60s — continuing anyway.")
    else:
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


def main():
    print("=== start ===")

    board = get_active_board()
    print(f"Board: {board['name']} ({board['host']})")

    # Step 1: Strip all flags from argv
    force_compile = "--compile" in sys.argv
    log_mode      = "--log"     in sys.argv
    args = [a for a in sys.argv[1:] if not a.startswith("--")]

    # Start logging if --log was passed
    log_path = os.path.expanduser("~/start.log")
    tee = HybXTee(log_path) if log_mode else None

    # Ctrl+C handler — close log and stop app cleanly.
    # Uses a list so the closure can reference app_path/app_id after they
    # are assigned later in main().
    _state = {"app_path": None, "app_id": None}

    def _sigint_handler(sig, frame):
        print("\nInterrupted — stopping app...")
        if _state["app_path"] and _state["app_id"]:
            try:
                stop_app(_state["app_path"], _state["app_id"])
            except Exception:
                pass
        if tee:
            tee.close()
        sys.exit(0)

    signal.signal(signal.SIGINT, _sigint_handler)

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
    _state["app_path"] = app_path
    _state["app_id"]   = app_id

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

    with HybXTimer("start", print_start=True):
        if log_mode:
            # Capture arduino-app-cli output and tee it to the log
            result = subprocess.run(
                ["arduino-app-cli", "app", "start", app_path],
                cwd=os.path.expanduser("~"),
                capture_output=True, text=True
            )
            if result.stdout:
                print(result.stdout, end="")
            if result.stderr:
                print(result.stderr, end="")
        else:
            subprocess.run(["arduino-app-cli", "app", "start", app_path], cwd=os.path.expanduser("~"))
    patch_compose(app_path)

    if tee:
        tee.close()


if __name__ == "__main__":
    main()
