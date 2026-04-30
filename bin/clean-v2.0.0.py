#!/usr/bin/env python3

"""
clean-v2.0.0.py
Hybrid RobotiX — HybX Development System

Usage:
  clean <app_name>
  clean
  clean <app_name> --log   (pass --log through to start)
"""

import os
import sys
sys.path.insert(0, os.path.dirname(os.path.realpath(__file__)))
sys.path.insert(0, os.path.expanduser("~/lib"))

import json    # noqa: E402
import shutil  # noqa: E402
import subprocess  # noqa: E402
from hybx_config import get_active_board  # noqa: E402
from hybx_config import HybXTimer  # noqa: E402

SKETCH_HASHES_FILE = os.path.expanduser("~/.hybx/sketch_hashes.json")
LAST_APP_FILE = os.path.expanduser("~/.hybx/last_app")


def get_app_path(app_name: str, apps_path: str) -> str:
    if app_name.startswith("/") or app_name.startswith("~") or app_name.startswith("."):
        return app_name
    return os.path.expanduser(f"{apps_path}/{app_name}")


def load_last_app() -> str | None:
    if os.path.exists(LAST_APP_FILE):
        with open(LAST_APP_FILE, "r") as f:
            return f.read().strip()
    return None


def clear_sketch_hash(app_id: str):
    """Remove the stored sketch hash so start forces a recompile."""
    if not os.path.exists(SKETCH_HASHES_FILE):
        return
    with open(SKETCH_HASHES_FILE, "r") as f:
        hashes = json.load(f)
    if app_id in hashes:
        del hashes[app_id]
        with open(SKETCH_HASHES_FILE, "w") as f:
            json.dump(hashes, f, indent=2)


def main():
    print("=== clean ===")

    board = get_active_board()
    print(f"Board: {board['name']} ({board['host']})")

    log_mode = "--log" in sys.argv
    args = [a for a in sys.argv[1:] if not a.startswith("--")]

    if not args:
        app_name = load_last_app()
        if not app_name:
            print("Usage: clean <app_name>")
            sys.exit(1)
        print(f"Using last app: {app_name}")
    else:
        app_name = args[0]

    app_path = get_app_path(app_name, board["apps_path"])
    cache_path = os.path.join(app_path, ".cache")

    # Stop ALL running apps first — only one app can run at a time
    subprocess.run("docker rm -f $(docker ps -aq)", shell=True, capture_output=True)
    subprocess.run(["arduino-app-cli", "app", "stop", app_path])

    app_id = os.path.basename(app_path)
    container_name = f"arduino-{app_id}-main-1"
    subprocess.run(["docker", "rm", "-f", container_name], capture_output=True)
    subprocess.run(["docker", "rmi", "-f", f"arduino-{app_id}-main"], capture_output=True)
    print(f"Removed Docker container and image for: {app_id}")

    if os.path.exists(cache_path):
        shutil.rmtree(cache_path)
        print(f"Cleared cache: {cache_path}")

    clear_sketch_hash(app_id)

    # Compile and flash via HybX Build System
    build_cmd = ["build", app_name]
    if log_mode:
        build_cmd.append("--log")
    subprocess.run(build_cmd)

    # Start the Python container via HybXRunner
    sys.path.insert(0, os.path.expanduser("~/lib"))
    from runner import HybXRunner
    from hybx_config import load_config
    config   = load_config()
    boards   = config.get("boards", {})
    active   = config.get("active_board", "")
    board    = boards.get(active, {})
    runner   = HybXRunner(active, app_path)
    result   = runner.start()
    if result.success:
        print(f"Container started: {runner.container}")
    else:
        print(f"ERROR starting container: {result.message}")


if __name__ == "__main__":
    with HybXTimer("clean", print_start=True):
        main()
