#!/usr/bin/env python3
"""
start-v0.0.8.py
Hybrid RobotiX — HybX Development System

Start an app on the active board.
Reads board config from ~/.hybx/config.json.

Usage:
  start <app_name>
  start              (uses last app)
"""

import sys
import os
import shutil
import time
import subprocess
sys.path.insert(0, os.path.dirname(os.path.realpath(__file__)))
from hybx_config import get_active_board

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

def get_app_path(app_name: str, apps_path: str) -> str:
    if app_name.startswith("/") or app_name.startswith("~") or app_name.startswith("."):
        return app_name
    return f"{apps_path}/{app_name}"

def nuke_docker(app_id: str):
    container_name = f"arduino-{app_id}-main-1"
    subprocess.run(["docker", "rm", "-f", container_name], capture_output=True)
    subprocess.run(["docker", "rmi", "-f", f"arduino-{app_id}-main"], capture_output=True)
    print(f"Removed Docker container and image for: {app_id}")

def clear_cache(app_path: str):
    cache_path = os.path.join(app_path, ".cache")
    if os.path.exists(cache_path):
        shutil.rmtree(cache_path)
        print(f"Cleared cache: {cache_path}")

def patch_compose(app_path: str):
    """
    Patch the generated app-compose.yaml to mount $HOME into the container.
    """
    home = os.path.expanduser("~")
    compose_file = os.path.join(app_path, ".cache", "app-compose.yaml")

    print("Waiting for compose file...")
    for _ in range(120):
        if os.path.exists(compose_file):
            break
        time.sleep(0.5)

    if not os.path.exists(compose_file):
        print("WARNING: compose file not found — skipping $HOME mount patch")
        return

    home_mount = (
        f"    - type: bind\n"
        f"      source: {home}\n"
        f"      target: {home}\n"
    )

    with open(compose_file, "r") as f:
        content = f.read()

    if f"source: {home}" in content:
        print(f"$HOME already mounted in compose file")
        return

    content = content.replace("    volumes:\n", f"    volumes:\n{home_mount}", 1)

    with open(compose_file, "w") as f:
        f.write(content)

    print(f"Patched compose file: mounted {home} into container")

    subprocess.run([
        "docker", "compose",
        "-f", compose_file,
        "up", "-d", "--force-recreate"
    ], capture_output=True)

def install_newrepo():
    dev_repo = os.path.expanduser("~/Repos/GitHub/hybotix/HybX-Development-System")
    newrepo_src = os.path.join(dev_repo, "scripts", "newrepo.bash")
    newrepo_dst = os.path.expanduser("~/bin/newrepo")
    if os.path.exists(newrepo_src):
        shutil.copy2(newrepo_src, newrepo_dst)
        os.chmod(newrepo_dst, 0o755)
        print(f"Installed: newrepo -> ~/bin/newrepo")

def main():
    os.system("clear")
    print("=== start ===")

    board = get_active_board()
    print(f"Board: {board['name']} ({board['host']})")

    if len(sys.argv) < 2:
        app_name = load_last_app()
        if not app_name:
            print("Usage: start <app_name>")
            print("Example: start matrix-bno")
            sys.exit(1)
        print(f"Using last app: {app_name}")
    else:
        app_name = sys.argv[1]

    save_last_app(app_name)
    app_path = get_app_path(app_name, board["apps_path"])
    app_id = os.path.basename(app_path)

    nuke_docker(app_id)
    clear_cache(app_path)
    install_newrepo()

    subprocess.run(["arduino-app-cli", "app", "start", app_path])
    patch_compose(app_path)

if __name__ == "__main__":
    main()
