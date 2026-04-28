#!/usr/bin/env python3

"""
stop-v1.2.0.py
Hybrid RobotiX — HybX Development System

Stops the running app and waits until the Docker container is fully gone
before returning. No timeout — polls until the container has actually stopped.

Changes from v0.0.4:
  - Added container polling after stop so callers (restart, clean, etc.)
    never proceed before the app is fully down.
"""

import os
import sys
sys.path.insert(0, os.path.dirname(os.path.realpath(__file__)))
sys.path.insert(0, os.path.expanduser("~/lib"))

import time  # noqa: E402
import subprocess  # noqa: E402
from hybx_config import get_active_board  # noqa: E402

LAST_APP_FILE = os.path.expanduser("~/.hybx/last_app")
POLL_INTERVAL = 1  # seconds between container existence checks


def get_app_path(app_name: str, apps_path: str) -> str:
    if app_name.startswith("/") or app_name.startswith("~") or app_name.startswith("."):
        return app_name
    return os.path.expanduser(apps_path + "/" + app_name)


def load_last_app() -> str | None:
    if os.path.exists(LAST_APP_FILE):
        with open(LAST_APP_FILE, "r") as f:
            return f.read().strip()
    return None


def container_running(container_name: str) -> bool:
    """Return True if the named Docker container exists (running or stopped)."""
    result = subprocess.run(
        ["docker", "ps", "-a", "--filter", "name=" + container_name,
         "--format", "{{.Names}}"],
        capture_output=True,
        text=True,
    )
    return container_name in result.stdout


def wait_for_stop(container_name: str):
    """Poll until the container is fully gone."""
    if not container_running(container_name):
        print("App already stopped.")
        return

    print("Waiting for app to stop", end="", flush=True)
    while container_running(container_name):
        print(".", end="", flush=True)
        time.sleep(POLL_INTERVAL)
    print()
    print("App stopped.")


def main():
    board = get_active_board()

    if len(sys.argv) < 2:
        app_name = load_last_app()
        if not app_name:
            print("Usage: stop <app_name>")
            sys.exit(1)
        print("Using last app: " + app_name)
    else:
        app_name = sys.argv[1]

    app_path       = get_app_path(app_name, board["apps_path"])
    app_id         = os.path.basename(app_path)
    container_name = "arduino-" + app_id + "-main-1"

    subprocess.run(["arduino-app-cli", "app", "stop", app_path])
    wait_for_stop(container_name)


if __name__ == "__main__":
    main()
