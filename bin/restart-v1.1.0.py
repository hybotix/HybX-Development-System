#!/usr/bin/env python3

"""
restart-v1.1.0.py
Hybrid RobotiX — HybX Development System
"""

import os
import sys
sys.path.insert(0, os.path.dirname(os.path.realpath(__file__)))
sys.path.insert(0, os.path.expanduser("~/lib"))

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


def main():
    os.system("clear")
    print("=== restart ===")

    board = get_active_board()
    print(f"Board: {board['name']} ({board['host']})")

    if len(sys.argv) < 2:
        app_name = load_last_app()
        if not app_name:
            print("Usage: restart <app_name>")
            sys.exit(1)
        print(f"Using last app: {app_name}")
    else:
        app_name = sys.argv[1]

    save_last_app(app_name)

    # Delegate to start
    subprocess.run(["start", app_name])


if __name__ == "__main__":
    main()
