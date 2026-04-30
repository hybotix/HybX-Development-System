#!/usr/bin/env python3

"""
stop-v2.0.0.py
Hybrid RobotiX — HybX Development System

Stop a running app via HybXRunner (docker rm -f).
Replaces arduino-app-cli app stop.

Usage:
  stop <app_name>
  stop              (uses last app)
"""

import os
import sys
sys.path.insert(0, os.path.dirname(os.path.realpath(__file__)))
sys.path.insert(0, os.path.expanduser("~/lib"))

from hybx_config import get_active_board  # noqa: E402
from hybx_runner import HybXRunner             # noqa: E402

LAST_APP_FILE = os.path.expanduser("~/.hybx/last_app")


def load_last_app() -> str | None:
    if os.path.exists(LAST_APP_FILE):
        with open(LAST_APP_FILE, "r") as f:
            return f.read().strip()
    return None


def main():
    print("=== stop ===")

    board = get_active_board()
    print(f"Board: {board['name']} ({board['host']})")

    if len(sys.argv) < 2:
        app_name = load_last_app()
        if not app_name:
            print("Usage: stop <app_name>")
            sys.exit(1)
        print(f"Using last app: {app_name}")
    else:
        app_name = sys.argv[1]

    app_path = os.path.join(board["apps_path"], app_name)
    runner   = HybXRunner(board["name"], app_path)
    result   = runner.stop()
    print(f"Stopped: {app_name}")


if __name__ == "__main__":
    main()
