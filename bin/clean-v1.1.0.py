#!/usr/bin/env python3

"""
clean-v1.1.0.py
Hybrid RobotiX — HybX Development System
"""

import os
import sys
sys.path.insert(0, os.path.dirname(os.path.realpath(__file__)))
sys.path.insert(0, os.path.expanduser("~/lib"))

import shutil  # noqa: E402
import subprocess  # noqa: E402
from hybx_config import get_active_board  # noqa: E402

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


def main():
    os.system("clear")
    print("=== clean ===")

    board = get_active_board()
    print(f"Board: {board['name']} ({board['host']})")

    if len(sys.argv) < 2:
        app_name = load_last_app()
        if not app_name:
            print("Usage: clean <app_name>")
            sys.exit(1)
        print(f"Using last app: {app_name}")
    else:
        app_name = sys.argv[1]

    app_path = get_app_path(app_name, board["apps_path"])
    cache_path = os.path.join(app_path, ".cache")

    subprocess.run(["arduino-app-cli", "app", "stop", app_path])

    app_id = os.path.basename(app_path)
    container_name = f"arduino-{app_id}-main-1"
    subprocess.run(["docker", "rm", "-f", container_name], capture_output=True)
    subprocess.run(["docker", "rmi", "-f", f"arduino-{app_id}-main"], capture_output=True)
    print(f"Removed Docker container and image for: {app_id}")

    if os.path.exists(cache_path):
        shutil.rmtree(cache_path)
        print(f"Cleared cache: {cache_path}")

    subprocess.run(["start", app_name])


if __name__ == "__main__":
    main()
