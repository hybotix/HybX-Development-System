#!/usr/bin/env python3

"""
start-v2.1.3.py
Hybrid RobotiX — HybX Development System

Start an app on the active board.
Runs main.py directly in the foreground using the HybX venv.
Apps are interactive by design — stdin/stdout/stderr are live.

No Docker. No containers. No log files. No PID files.
The terminal is the interface.

v2.1:   Docker removed. All apps run interactively in the foreground.
v2.1.2: Updates both last_app and board_projects active project on start.
v2.1.3: Auto-creates versioned symlinks if main.py is missing.

Usage:
  start <app_name>
  start              (uses last app)
  start --compile    (force recompile even if sketch unchanged)
"""

import os
import sys
sys.path.insert(0, os.path.dirname(os.path.realpath(__file__)))
sys.path.insert(0, os.path.expanduser("~/lib"))

import json        # noqa: E402
import shutil      # noqa: E402
import subprocess  # noqa: E402
from hybx_config import get_active_board, load_config, save_config, install_sigint_handler  # noqa: E402

LAST_APP_FILE = os.path.expanduser("~/.hybx/last_app")
CONFIG_FILE   = os.path.expanduser("~/.hybx/config.json")
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
    install_sigint_handler()
    print("=== start ===")

    board = get_active_board()
    print(f"Board: {board['name']}")

    # Parse flags and args
    force_compile = "--compile" in sys.argv
    args = [a for a in sys.argv[1:] if not a.startswith("--")]

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

    # Also update board_projects so project rename can find the active app
    config = load_config()
    board_name = board["name"]
    if "board_projects" not in config:
        config["board_projects"] = {}
    if board_name not in config["board_projects"]:
        config["board_projects"][board_name] = {}
    config["board_projects"][board_name]["active"] = app_name
    save_config(config)

    app_path = get_app_path(app_name, board["apps_path"])
    app_id   = os.path.basename(app_path)
    main_py  = os.path.join(app_path, "python", "main.py")

    # If main.py doesn't exist, try to create symlinks from versioned files
    if not os.path.exists(main_py):
        from hybx_config import symlink_versioned_files
        symlink_versioned_files(app_path)

    if not os.path.exists(main_py):
        print(f"ERROR: main.py not found: {main_py}")
        print(f"       No versioned main-vX.Y.Z.py found either.")
        print(f"       Run: project pull {app_name}")
        sys.exit(1)

    if not os.path.exists(VENV_PYTHON):
        print(f"ERROR: HybX venv not found: {VENV_PYTHON}")
        print("       Run: update")
        sys.exit(1)

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
