#!/usr/bin/env python3

"""
stop-v2.1.0.py
Hybrid RobotiX — HybX Development System

Stop a running app by sending SIGTERM to its Python process.

v2.1: Docker removed. Uses PID file at ~/.hybx/run/<app>.pid.

Usage:
  stop <app_name>
  stop              (uses last app)
"""

import os
import signal
import sys
import time
sys.path.insert(0, os.path.dirname(os.path.realpath(__file__)))
sys.path.insert(0, os.path.expanduser("~/lib"))

from hybx_config import get_active_board, install_sigint_handler  # noqa: E402

LAST_APP_FILE = os.path.expanduser("~/.hybx/last_app")
RUN_DIR       = os.path.expanduser("~/.hybx/run")


# ── PID management ─────────────────────────────────────────────────────────────

def pid_path(app_id: str) -> str:
    return os.path.join(RUN_DIR, app_id + ".pid")


def load_pid(app_id: str) -> int | None:
    p = pid_path(app_id)
    if os.path.exists(p):
        with open(p) as f:
            try:
                return int(f.read().strip())
            except ValueError:
                return None
    return None


def clear_pid(app_id: str):
    p = pid_path(app_id)
    if os.path.exists(p):
        os.remove(p)


# ── Stop ───────────────────────────────────────────────────────────────────────

def stop_app(app_id: str) -> bool:
    """
    Stop a running app by PID.
    Returns True if stopped, False if not running.
    """
    pid = load_pid(app_id)
    if pid is None:
        return False

    try:
        os.kill(pid, 0)   # check alive
    except ProcessLookupError:
        clear_pid(app_id)
        return False

    try:
        os.kill(pid, signal.SIGTERM)
        for _ in range(30):
            time.sleep(0.1)
            try:
                os.kill(pid, 0)
            except ProcessLookupError:
                break
        else:
            os.kill(pid, signal.SIGKILL)
    except ProcessLookupError:
        pass
    finally:
        clear_pid(app_id)

    return True


# ── Main ───────────────────────────────────────────────────────────────────────

def main():
    install_sigint_handler()
    print("=== stop ===")

    board = get_active_board()
    print(f"Board: {board['name']}")

    if len(sys.argv) < 2:
        if not os.path.exists(LAST_APP_FILE):
            print("Usage: stop <app_name>")
            sys.exit(1)
        with open(LAST_APP_FILE) as f:
            app_name = f.read().strip()
        print(f"Using last app: {app_name}")
    else:
        app_name = sys.argv[1]

    app_id = os.path.basename(app_name)

    if stop_app(app_id):
        print(f"Stopped: {app_id}")
    else:
        print(f"Not running: {app_id}")


if __name__ == "__main__":
    main()
