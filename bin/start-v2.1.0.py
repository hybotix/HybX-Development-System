#!/usr/bin/env python3

"""
start-v2.1.0.py
Hybrid RobotiX — HybX Development System

Start an app on the active board.
Runs main.py directly using the HybX venv — no Docker, no containers.

v2.1: Docker removed. Apps run as plain Python processes.
      Output goes to ~/logs/<app>.log and stdout simultaneously.
      PID stored in ~/.hybx/run/<app>.pid for stop/mon.

Usage:
  start <app_name>
  start              (uses last app)
  start --compile    (force recompile even if sketch unchanged)
  start --log        (also write all output to ~/start.log)
  start -i           (interactive — run in foreground with live stdin/stdout)
  start --interactive (same as -i)
"""

import os
import signal
import sys
import time
sys.path.insert(0, os.path.dirname(os.path.realpath(__file__)))
sys.path.insert(0, os.path.expanduser("~/lib"))

import json        # noqa: E402
import shutil      # noqa: E402
import subprocess  # noqa: E402
from hybx_config import get_active_board, mask_host, HybXTimer, HybXTee  # noqa: E402

LAST_APP_FILE = os.path.expanduser("~/.hybx/last_app")
RUN_DIR       = os.path.expanduser("~/.hybx/run")
LOG_DIR       = os.path.expanduser("~/logs")
VENV_PYTHON   = os.path.expanduser("~/.hybx/venv/bin/python3")


# ── PID management ─────────────────────────────────────────────────────────────

def pid_path(app_id: str) -> str:
    return os.path.join(RUN_DIR, app_id + ".pid")


def save_pid(app_id: str, pid: int):
    os.makedirs(RUN_DIR, exist_ok=True)
    with open(pid_path(app_id), "w") as f:
        f.write(str(pid))


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


# ── App management ─────────────────────────────────────────────────────────────

def stop_app(app_id: str):
    """Stop a running app by PID."""
    pid = load_pid(app_id)
    if pid is None:
        return
    try:
        os.kill(pid, signal.SIGTERM)
        # Wait up to 3 seconds for clean exit
        for _ in range(30):
            time.sleep(0.1)
            try:
                os.kill(pid, 0)   # check if still alive
            except ProcessLookupError:
                break
        else:
            # Still alive — force kill
            try:
                os.kill(pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
        print(f"Stopped: {app_id} (pid {pid})")
    except ProcessLookupError:
        pass   # already gone
    finally:
        clear_pid(app_id)


def app_is_running(app_id: str) -> bool:
    pid = load_pid(app_id)
    if pid is None:
        return False
    try:
        os.kill(pid, 0)
        return True
    except ProcessLookupError:
        clear_pid(app_id)
        return False


# ── Last app ───────────────────────────────────────────────────────────────────

def save_last_app(app_name: str):
    os.makedirs(os.path.dirname(LAST_APP_FILE), exist_ok=True)
    with open(LAST_APP_FILE, "w") as f:
        f.write(app_name)


def load_last_app() -> str | None:
    if os.path.exists(LAST_APP_FILE):
        with open(LAST_APP_FILE) as f:
            return f.read().strip()
    return None


# ── App path ───────────────────────────────────────────────────────────────────

def get_app_path(app_name: str, apps_path: str) -> str:
    if app_name.startswith("/") or app_name.startswith("~") or app_name.startswith("."):
        return os.path.expanduser(app_name)
    return os.path.expanduser(f"{apps_path}/{app_name}")


# ── Sketch change detection ────────────────────────────────────────────────────

SKETCH_HASHES_FILE = os.path.expanduser("~/.hybx/sketch_hashes.json")


def get_sketch_hash(app_path: str) -> str:
    import hashlib
    sketch_dir = os.path.join(app_path, "sketch")
    h = hashlib.md5()
    for root, _, files in os.walk(sketch_dir):
        for fname in sorted(files):
            fpath = os.path.join(root, fname)
            try:
                with open(fpath, "rb") as f:
                    h.update(f.read())
            except Exception:
                pass
    return h.hexdigest()


def load_sketch_hashes() -> dict:
    if os.path.exists(SKETCH_HASHES_FILE):
        with open(SKETCH_HASHES_FILE) as f:
            return json.load(f)
    return {}


def save_sketch_hash(app_id: str, hash_val: str):
    hashes = load_sketch_hashes()
    hashes[app_id] = hash_val
    os.makedirs(os.path.dirname(SKETCH_HASHES_FILE), exist_ok=True)
    with open(SKETCH_HASHES_FILE, "w") as f:
        json.dump(hashes, f, indent=2)


def sketch_changed(app_path: str, app_id: str) -> bool:
    current = get_sketch_hash(app_path)
    stored  = load_sketch_hashes().get(app_id)
    if current != stored:
        save_sketch_hash(app_id, current)
        return True
    return False


def clear_cache(app_path: str):
    cache_path = os.path.join(app_path, ".cache")
    if os.path.exists(cache_path):
        shutil.rmtree(cache_path)
        print(f"Cleared cache: {cache_path}")


# ── Main ───────────────────────────────────────────────────────────────────────

def main():
    print("=== start ===")

    board = get_active_board()
    print(f"Board: {board['name']}")

    # Parse flags and args
    force_compile = "--compile"     in sys.argv
    log_mode      = "--log"         in sys.argv
    interactive   = "--interactive" in sys.argv or "-i" in sys.argv
    args = [a for a in sys.argv[1:] if not a.startswith("--") and a != "-i"]

    log_path = os.path.expanduser("~/start.log")
    tee = HybXTee(log_path) if log_mode else None

    # Resolve app name
    if args:
        app_name = args[0]
        app_args = args[1:]
    else:
        app_name = load_last_app()
        app_args = []
        if not app_name:
            print("Usage: start <app_name>")
            print("       start <app_name> --compile")
            sys.exit(1)
        print(f"Using last app: {app_name}")

    save_last_app(app_name)

    if app_args:
        print(f"App args: {' '.join(app_args)}")

    app_path = get_app_path(app_name, board["apps_path"])
    app_id   = os.path.basename(app_path)
    main_py  = os.path.join(app_path, "python", "main.py")

    if not os.path.exists(main_py):
        print(f"ERROR: main.py not found: {main_py}")
        sys.exit(1)

    if not os.path.exists(VENV_PYTHON):
        print(f"ERROR: HybX venv not found: {VENV_PYTHON}")
        print("       Run: update")
        sys.exit(1)

    # Stop any running instance
    if app_is_running(app_id):
        print(f"Stopping: {app_id}")
        stop_app(app_id)

    # Sketch change detection / cache clear
    if force_compile:
        print("Forced recompile — clearing cache")
        clear_cache(app_path)
        save_sketch_hash(app_id, get_sketch_hash(app_path))
    elif sketch_changed(app_path, app_id):
        print("Sketch changed — clearing cache for recompile")
        clear_cache(app_path)
    else:
        print("Sketch unchanged — skipping recompile")

    # Set up log file for this app
    os.makedirs(LOG_DIR, exist_ok=True)
    app_log = os.path.join(LOG_DIR, app_id + ".log")

    # Build environment — ~/lib on PYTHONPATH so hybx_app.py is importable
    env = os.environ.copy()
    lib_dir = os.path.expanduser("~/lib")
    existing = env.get("PYTHONPATH", "")
    env["PYTHONPATH"] = lib_dir + (":" + existing if existing else "")

    cmd = [VENV_PYTHON, main_py] + app_args
    cwd = os.path.join(app_path, "python")

    if interactive:
        # Interactive mode — run in foreground with live stdin/stdout/stderr
        # No PID file, no log file — the terminal is the interface
        print(f"Running interactively: {app_id}")
        print()
        proc = subprocess.run(cmd, cwd=cwd, env=env)
        sys.exit(proc.returncode)

    else:
        # Background mode — stdout/stderr go to the app log file
        with HybXTimer("start", print_start=True):
            with open(app_log, "a") as log_f:
                proc = subprocess.Popen(
                    cmd,
                    stdout=log_f,
                    stderr=log_f,
                    cwd=cwd,
                    env=env,
                )

            save_pid(app_id, proc.pid)
            print(f"App started: {app_id} (pid {proc.pid})")
            print(f"Log: {app_log}")

    if tee:
        tee.close()


if __name__ == "__main__":
    main()
