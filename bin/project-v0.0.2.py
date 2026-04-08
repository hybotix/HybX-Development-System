#!/usr/bin/env python3
"""
project-v0.0.2.py
Hybrid RobotiX — HybX Development System

Manages projects for the active board.
Projects live under a project type directory within the board's apps directory.

Usage:
  project list                       - List projects for the active board
  project new <type> <name>          - Create a new project scaffold
  project set <name>                 - Set the active project
  project show                       - Show the active project
  project remove <name>              - Remove a project (local only)

Project types (case insensitive):
  arduino     → Arduino/
  micropython → MicroPython/
  ros2        → ROS2/

Examples:
  project new arduino    lis3dh
  project new micropython sensor-display
  project new ros2       navigation
"""

import sys
import os
import json
import shutil
import subprocess

sys.path.insert(0, os.path.dirname(os.path.realpath(__file__)))
from hybx_config import get_active_board

CONFIG_DIR    = os.path.expanduser("~/.hybx")
CONFIG_FILE   = os.path.join(CONFIG_DIR, "config.json")
LAST_APP_FILE = os.path.join(CONFIG_DIR, "last_app")

# ── Project type normalization ─────────────────────────────────────────────────
PROJECT_TYPES = {
    "arduino":     "Arduino",
    "micropython": "MicroPython",
    "ros2":        "ROS2",
}

def normalize_project_type(raw: str) -> str | None:
    """Normalize project type string to canonical form. Returns None if unknown."""
    return PROJECT_TYPES.get(raw.lower())

# ── Config helpers ─────────────────────────────────────────────────────────────

def load_config() -> dict:
    if not os.path.exists(CONFIG_FILE):
        return {"boards": {}, "active_board": None}
    with open(CONFIG_FILE, "r") as f:
        return json.load(f)

def save_config(config: dict):
    os.makedirs(CONFIG_DIR, exist_ok=True)
    with open(CONFIG_FILE, "w") as f:
        json.dump(config, f, indent=2)

def save_last_app(app_name: str):
    os.makedirs(CONFIG_DIR, exist_ok=True)
    with open(LAST_APP_FILE, "w") as f:
        f.write(app_name)

def get_active_project(config: dict, board_name: str) -> str | None:
    return config.get("board_projects", {}).get(board_name, {}).get("active")

def set_active_project(config: dict, board_name: str, project_name: str | None):
    if "board_projects" not in config:
        config["board_projects"] = {}
    if board_name not in config["board_projects"]:
        config["board_projects"][board_name] = {}
    config["board_projects"][board_name]["active"] = project_name

# ── Scaffold templates ─────────────────────────────────────────────────────────

SKETCH_INO = """\
/**
 * {name}
 * Hybrid RobotiX
 *
 * Arduino sketch for {name}.
 */

#include <Arduino_RouterBridge.h>

// ── Bridge functions ──────────────────────────────────────────────────────────

// Add Bridge.provide() calls here before setup()

// ── Setup ─────────────────────────────────────────────────────────────────────

void setup() {{
    Bridge.begin();
    // Initialize sensors and hardware here
}}

// ── Loop ──────────────────────────────────────────────────────────────────────

void loop() {{
    // Main loop — keep empty when using Bridge
}}
"""

SKETCH_YAML = """\
profiles:
  default:
    platforms:
      - platform: arduino:zephyr
    libraries:
      - Arduino_RouterBridge (0.3.0)
      - dependency: Arduino_RPClite (0.2.1)
      - dependency: ArxContainer (0.7.0)
      - dependency: ArxTypeTraits (0.3.2)
      - dependency: DebugLog (0.8.4)
      - dependency: MsgPack (0.4.2)
default_profile: default
"""

MAIN_PY = """\
from arduino.app_utils import App, Bridge
import time

def loop():
    \"\"\"Main loop — called repeatedly by App.run().\"\"\"
    pass  # TODO: Add Bridge.call() reads and processing here

App.run(user_loop=loop)
"""

REQUIREMENTS_TXT = """\
# Python dependencies for {name}
# Add pip packages here, one per line
"""

APP_YAML = """\
name: {name}
icon: 🤖
description: {name} app for Hybrid RobotiX
"""

# ── Commands ───────────────────────────────────────────────────────────────────

def cmd_list():
    board     = get_active_board()
    apps_path = board["apps_path"]
    config    = load_config()
    active    = get_active_project(config, board["name"])

    print(f"Board: {board['name']} ({board['host']})")
    print(f"Apps path: {apps_path}")
    print()

    if not os.path.exists(apps_path):
        print("Apps directory does not exist on this machine.")
        print("Run 'newrepo' to set up the board environment.")
        return

    # Walk all project type subdirectories
    found = False
    for type_dir in sorted(os.listdir(apps_path)):
        type_path = os.path.join(apps_path, type_dir)

        if not os.path.isdir(type_path):
            continue

        projects = [d for d in os.listdir(type_path)
                    if os.path.isdir(os.path.join(type_path, d))]

        if not projects:
            continue

        found = True
        print(f"{type_dir}/")

        for p in sorted(projects):
            marker = " *" if p == active else "  "
            print(f"{marker} {p}")

        print()

    if not found:
        print("No projects found. Use: project new <type> <name>")
        return

    if active:
        print(f"Active project: {active}")
    else:
        print("No active project. Use: project set <name>")

def cmd_new(project_type_raw: str, name: str):
    project_type = normalize_project_type(project_type_raw)

    if not project_type:
        print(f"ERROR: Unknown project type '{project_type_raw}'")
        print(f"Valid types: {', '.join(PROJECT_TYPES.keys())}")
        sys.exit(1)

    board     = get_active_board()
    apps_path = board["apps_path"]

    # Local project path: ~/Arduino/UNO-Q/<type>/<name>
    type_path    = os.path.join(apps_path, project_type)
    project_path = os.path.join(type_path, name)

    # Repo path: ~/Repos/GitHub/hybotix/UNO-Q/<type>/<board>/<name>
    repo_root = os.path.expanduser(
        f"~/Repos/GitHub/{board['repo'].split('github.com/')[-1].replace('.git', '')}"
    )
    repo_project_path = os.path.join(repo_root, project_type, board["name"], name)

    print(f"=== project new ===")
    print(f"Type:  {project_type}")
    print(f"Name:  {name}")
    print(f"Board: {board['name']} ({board['host']})")
    print()

    if os.path.exists(project_path):
        print(f"ERROR: Project '{name}' already exists at {project_path}")
        sys.exit(1)

    # Create directory structure
    sketch_dir = os.path.join(project_path, "sketch")
    python_dir = os.path.join(project_path, "python")
    os.makedirs(sketch_dir, exist_ok=True)
    os.makedirs(python_dir, exist_ok=True)
    print(f"Created: {project_path}/")

    # Write scaffold files
    files = {
        os.path.join(sketch_dir, "sketch.ino"):       SKETCH_INO.format(name=name),
        os.path.join(sketch_dir, "sketch.yaml"):      SKETCH_YAML,
        os.path.join(python_dir, "main.py"):          MAIN_PY.format(name=name),
        os.path.join(python_dir, "requirements.txt"): REQUIREMENTS_TXT.format(name=name),
        os.path.join(project_path, "app.yaml"):       APP_YAML.format(name=name),
    }

    for path, content in files.items():
        with open(path, "w") as f:
            f.write(content)
        print(f"Created: {os.path.relpath(path, apps_path)}")

    # Set as active project
    config = load_config()
    set_active_project(config, board["name"], name)
    save_config(config)
    save_last_app(name)
    print(f"\nActive project set to: {name}")

    # Commit and push to repo if repo exists
    if os.path.exists(repo_root):
        if not os.path.exists(repo_project_path):
            shutil.copytree(project_path, repo_project_path)
            rel = os.path.relpath(repo_project_path, repo_root)
            print(f"\nAdded to repo: {rel}/")

            subprocess.run(
                ["git", "-C", repo_root, "add", rel],
                capture_output=True
            )
            result = subprocess.run(
                ["git", "-C", repo_root, "commit", "-m",
                 f"Add {project_type} project scaffold: {name}"],
                capture_output=True, text=True
            )

            if result.returncode == 0:
                print(f"Committed: Add {project_type} project scaffold: {name}")
                result = subprocess.run(
                    ["git", "-C", repo_root, "push"],
                    capture_output=True, text=True
                )

                if result.returncode == 0:
                    print(f"Pushed to: {board['repo']}")
                else:
                    print(f"Push failed — commit local, push manually.")
                    print(result.stderr)
            else:
                print(f"Commit failed: {result.stderr}")
    else:
        print(f"\nNote: Repo not found at {repo_root} — project created locally only.")
        print(f"Run 'newrepo' to set up the full environment.")

    print(f"\nProject '{name}' ready.")

def cmd_set(name: str):
    board     = get_active_board()
    apps_path = board["apps_path"]

    # Search across all type directories
    found_path = None
    for type_dir in os.listdir(apps_path):
        candidate = os.path.join(apps_path, type_dir, name)

        if os.path.isdir(candidate):
            found_path = candidate
            break

    if not found_path:
        print(f"ERROR: Project '{name}' not found in {apps_path}")
        sys.exit(1)

    config = load_config()
    set_active_project(config, board["name"], name)
    save_config(config)
    save_last_app(name)
    print(f"Active project set to: {name}")

def cmd_show():
    board  = get_active_board()
    config = load_config()
    active = get_active_project(config, board["name"])

    print(f"Board: {board['name']} ({board['host']})")

    if active:
        print(f"Active project: {active}")
    else:
        print("No active project. Use: project set <name>")

def cmd_remove(name: str):
    board     = get_active_board()
    apps_path = board["apps_path"]

    # Search across all type directories
    found_path = None
    for type_dir in os.listdir(apps_path):
        candidate = os.path.join(apps_path, type_dir, name)

        if os.path.isdir(candidate):
            found_path = candidate
            break

    if not found_path:
        print(f"ERROR: Project '{name}' not found in {apps_path}")
        sys.exit(1)

    confirm = input(f"Remove project '{name}' from local disk? (yes/no): ").strip().lower()

    if confirm != "yes":
        print("Cancelled.")
        return

    shutil.rmtree(found_path)
    print(f"Removed: {found_path}")

    config = load_config()

    if get_active_project(config, board["name"]) == name:
        set_active_project(config, board["name"], None)
        save_config(config)
        print(f"Note: Active project cleared. Use: project set <name>")

def usage():
    print("Usage:")
    print("  project list                  - List projects for the active board")
    print("  project new <type> <name>     - Create a new project scaffold")
    print("  project set <name>            - Set the active project")
    print("  project show                  - Show the active project")
    print("  project remove <name>         - Remove a project (local only)")
    print()
    print("Project types: arduino, micropython, ros2")

# ── Main ───────────────────────────────────────────────────────────────────────

def main():
    os.system("clear")
    print("=== project ===")

    if len(sys.argv) < 2:
        usage()
        sys.exit(1)

    command = sys.argv[1]

    if command == "list":
        cmd_list()
    elif command == "show":
        cmd_show()
    elif command == "new":
        if len(sys.argv) < 4:
            print("Usage: project new <type> <name>")
            print("Example: project new arduino lis3dh")
            sys.exit(1)
        cmd_new(sys.argv[2], sys.argv[3])
    elif command == "set":
        if len(sys.argv) < 3:
            print("Usage: project set <name>")
            sys.exit(1)
        cmd_set(sys.argv[2])
    elif command == "remove":
        if len(sys.argv) < 3:
            print("Usage: project remove <name>")
            sys.exit(1)
        cmd_remove(sys.argv[2])
    else:
        print(f"ERROR: Unknown command '{command}'")
        usage()
        sys.exit(1)

if __name__ == "__main__":
    main()
