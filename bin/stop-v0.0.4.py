#!/usr/bin/env python3
"""
stop-v0.0.4.py
Hybrid RobotiX — HybX Development System
"""

import sys
import os
import subprocess
sys.path.insert(0, os.path.dirname(os.path.realpath(__file__)))
from hybx_config import get_active_board

LAST_APP_FILE = os.path.expanduser("~/.hybx/last_app")

def get_app_path(app_name: str, apps_path: str) -> str:
    if app_name.startswith("/") or app_name.startswith("~") or app_name.startswith("."):
        return app_name
    return f"{apps_path}/{app_name}"

def load_last_app() -> str | None:
    if os.path.exists(LAST_APP_FILE):
        with open(LAST_APP_FILE, "r") as f:
            return f.read().strip()
    return None

def main():
    board = get_active_board()

    if len(sys.argv) < 2:
        app_name = load_last_app()
        if not app_name:
            print("Usage: stop <app_name>")
            sys.exit(1)
        print(f"Using last app: {app_name}")
    else:
        app_name = sys.argv[1]

    app_path = get_app_path(app_name, board["apps_path"])
    subprocess.run(["arduino-app-cli", "app", "stop", app_path])

if __name__ == "__main__":
    main()
