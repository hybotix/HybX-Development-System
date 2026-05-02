#!/usr/bin/env python3

"""
start-v2.1.2.py
Hybrid RobotiX — HybX Development System

Start an app on the active board.
Runs main.py directly in the foreground using the HybX venv.
Apps are interactive by design — stdin/stdout/stderr are live.

No Docker. No containers. No log files. No PID files.
The terminal is the interface.

v2.1:   Docker removed. All apps run interactively in the foreground.
v2.1.2: Optional script argument — defaults to main.py.

Usage:
  start <app_name>                  (runs main.py)
  start <app_name> <script.py>      (runs named script in python/)
  start                             (uses last app, runs main.py)
  start --compile                   (force recompile)
"""

import os
import sys
sys.path.insert(0, os.path.dirname(os.path.realpath(__file__)))
sys.path.insert(0, os.path.expanduser("~/lib"))

import json        # noqa: E402
import shutil      # noqa: E402
import subprocess  # noqa: E402
from hybx_config import get_active_board  # noqa: E402

LAST_APP_FILE = os.path.expanduser("~/.hybx/last_app")
VENV_PYTHON   = os.path.expanduser("~/.hybx/venv/bin/python3")


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
    force_compile = "--compile" in sys.argv
    args = [a for a in sys.argv[1:] if not a.startswith("--")]

    # Resolve app name and optional script
    if args:
        app_name = args[0]
        # Second arg is optional script name — defaults to main.py
        script   = args[1] if len(args) > 1 and args[1].endswith(".py") else "main.py"
        app_args = args[2:] if len(args) > 1 and args[1].endswith(".py") else args[1:]
    else:
        app_name = load_last_app()
        script   = "main.py"
        app_args = []
        if not app_name:
            print("Usage: start <app_name>")
            print("       start <app_name> <script.py>")
            print("       start <app_name> --compile")
            sys.exit(1)
        print(f"Using last app: {app_name}")

    save_last_app(app_name)

    app_path = get_app_path(app_name, board["apps_path"])
    app_id   = os.path.basename(app_path)
    main_py  = os.path.join(app_path, "python", script)

    if not os.path.exists(main_py):
        print(f"ERROR: {script} not found: {main_py}")
        sys.exit(1)

    if not os.path.exists(VENV_PYTHON):
        print(f"ERROR: HybX venv not found: {VENV_PYTHON}")
        print("       Run: update")
        sys.exit(1)

    # Sketch change detection — only relevant for main.py
    if script == "main.py":
        if force_compile:
            print("Forced recompile — clearing cache")
            clear_cache(app_path)
            save_sketch_hash(app_id, get_sketch_hash(app_path))
        elif sketch_changed(app_path, app_id):
            print("Sketch changed — clearing cache for recompile")
            clear_cache(app_path)
        else:
            print("Sketch unchanged — skipping recompile")

    # Build environment — ~/lib on PYTHONPATH so hybx_app.py is importable
    env = os.environ.copy()
    lib_dir = os.path.expanduser("~/lib")
    existing = env.get("PYTHONPATH", "")
    env["PYTHONPATH"] = lib_dir + (":" + existing if existing else "")

    cmd = [VENV_PYTHON, main_py] + app_args
    cwd = os.path.join(app_path, "python")

    print()
    proc = subprocess.run(cmd, cwd=cwd, env=env)
    sys.exit(proc.returncode)


if __name__ == "__main__":
    main()
