#!/usr/bin/env python3

"""
mon-v2.1.0.py
Hybrid RobotiX — HybX Development System

Monitor a running app's output by tailing its log file.

v2.1: Docker removed. Tails ~/logs/<app>.log directly.

Usage:
  mon <app_name>
  mon              (uses last app)
"""

import os
import sys
sys.path.insert(0, os.path.dirname(os.path.realpath(__file__)))
sys.path.insert(0, os.path.expanduser("~/lib"))

import subprocess  # noqa: E402
from hybx_config import get_active_board, install_sigint_handler  # noqa: E402

LAST_APP_FILE = os.path.expanduser("~/.hybx/last_app")
LOG_DIR       = os.path.expanduser("~/logs")


def main():
    install_sigint_handler()
    print("=== mon ===")

    board = get_active_board()
    print(f"Board: {board['name']}")

    if len(sys.argv) < 2:
        if not os.path.exists(LAST_APP_FILE):
            print("Usage: mon <app_name>")
            sys.exit(1)
        with open(LAST_APP_FILE) as f:
            app_name = f.read().strip()
        print(f"Using last app: {app_name}")
    else:
        app_name = sys.argv[1]

    app_id  = os.path.basename(app_name)
    log_file = os.path.join(LOG_DIR, app_id + ".log")

    if not os.path.exists(log_file):
        print(f"ERROR: No log file found: {log_file}")
        print(f"       Has '{app_id}' been started yet?")
        sys.exit(1)

    print(f"Log: {log_file}")
    print()

    subprocess.run(["tail", "-f", log_file])


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nInterrupted.")
        sys.exit(1)
