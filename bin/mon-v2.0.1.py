#!/usr/bin/env python3

"""
mon-v2.0.1.py
Hybrid RobotiX — HybX Development System

Monitor a running app's output via docker logs.
Replaces arduino-app-cli app logs entirely.

Usage:
  mon <app_name>
  mon              (uses last app)
"""

import os
import sys
sys.path.insert(0, os.path.dirname(os.path.realpath(__file__)))
sys.path.insert(0, os.path.expanduser("~/lib"))

import subprocess  # noqa: E402
from hybx_config import get_active_board  # noqa: E402

LAST_APP_FILE = os.path.expanduser("~/.hybx/last_app")


def load_last_app() -> str | None:
    if os.path.exists(LAST_APP_FILE):
        with open(LAST_APP_FILE, "r") as f:
            return f.read().strip()
    return None


def main():
    print("=== mon ===")

    board = get_active_board()
    print(f"Board: {board['name']} ({board['host']})")

    if len(sys.argv) < 2:
        app_name = load_last_app()
        if not app_name:
            print("Usage: mon <app_name>")
            sys.exit(1)
        print(f"Using last app: {app_name}")
    else:
        app_name = sys.argv[1]

    board_name     = board["name"].lower().replace("_", "-")
    container_name = f"arduino-{board_name}-{app_name}-main-1"

    subprocess.run(["docker", "logs", "-f", container_name])


if __name__ == "__main__":
    main()
