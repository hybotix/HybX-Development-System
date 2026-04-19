#!/usr/bin/env python3

"""
logs-v0.0.4.py
Hybrid RobotiX — HybX Development System
"""

import os
import sys
sys.path.insert(0, os.path.dirname(os.path.realpath(__file__)))
sys.path.insert(0, os.path.expanduser("~/lib"))

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
    print("=== logs ===")

    board = get_active_board()
    print(f"Board: {board['name']} ({board['host']})")

    if len(sys.argv) < 2:
        app_name = load_last_app()
        if not app_name:
            print("Usage: logs <app_name>")
            sys.exit(1)
        print(f"Using last app: {app_name}")
    else:
        app_name = sys.argv[1]

    app_path = get_app_path(app_name, board["apps_path"])
    subprocess.run(["arduino-app-cli", "app", "logs", app_path])


if __name__ == "__main__":
    main()
