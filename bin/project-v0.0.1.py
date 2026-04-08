#!/usr/bin/env python3
"""
project-v0.0.1.py
Hybrid RobotiX — HybX Development System

Manages projects for the active board.
Projects live in the board's apps directory and repo.

Usage:
  project list              - List projects for the active board
  project new <name>        - Create a new project scaffold
  project set <name>        - Set the active project
  project show              - Show the active project
  project remove <name>     - Remove a project (local only)
"""

import sys
import os
import json
import subprocess

sys.path.insert(0, os.path.dirname(os.path.realpath(__file__)))
from hybx_config import get_active_board

CONFIG_DIR    = os.path.expanduser("~/.hybx")
CONFIG_FILE   = os.path.join(CONFIG_DIR, "config.json")
LAST_APP_FILE = os.path.join(CONFIG_DIR, "last_app")

# ---------------------------------------------------------------------------
# Config helpers
# ---------------------------------------------------------------------------

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

def get_board_projects(config: dict, board_name: str) -> dict:
    return config.get("board_projects", {}).get(board_name, {})

def set_active_project(config: dict, board_name: str, project_name: str):
    if "board_projects" not in config:
        config["board_projects"] = {}
    if board_name not in config["board_projects"]:
        config["board_projects"][board_name] = {}
    config["board_projects"][board_name]["active"] = project_name

def get_active_project(config: dict, board_name: str) -> str | None:
    return config.get("board_projects", {}).get(board_name, {}).get("active")

# ---------------------------------------------------------------------------
# Scaffold templates
# ---------------------------------------------------------------------------

SKETCH_INO = """\
/**
 * {name}
 * Hybrid RobotiX
 *
 * Arduino sketch for {name}.
 */

#include <Arduino_RouterBridge.h>

// ---------------------------------------------------------------------------
// Bridge functions
// ---------------------------------------------------------------------------

// Add Bridge.provide() calls here before setup()

// ---------------------------------------------------------------------------
// Setup
// ---------------------------------------------------------------------------

void setup() {{
    Bridge.begin();
    // Initialize sensors and hardware here
}}

// ---------------------------------------------------------------------------
// Loop
// ---------------------------------------------------------------------------

void loop() {{
    // Main loop — keep empty when using Bridge
}}
"""

SKETCH_YAML = """\
profiles:
  default:
    platforms:
      - platform: arduino:zephyr
    libraries: []
default_profile: default
"""

MAIN_PY = """\
#!/usr/bin/env python3
\"\"\"
{name}
Hybrid RobotiX

Python controller for {name}.
Reads data from the MCU via the Bridge and processes it.
\"\"\"

from arduino.app_utils import App, Bridge

def loop():
    \"\"\"Main loop — called repeatedly by App.run()\"\"\"
    pass  # TODO: Add Bridge.call() reads and processing here

App.run(user_loop=loop)
"""

REQUIREMENTS_TXT = """\
# Python dependencies for {name}
# Add pip packages here, one per line
"""

APP_YAML = """\
name: {name}
version: 1.0.0
description: {name} app for Hybrid RobotiX
sketch: sketch/
python: python/
"""

# ---------------------------------------------------------------------------
# Commands
# ---------------------------------------------------------------------------

def cmd_list():
    board = get_active_board()
    apps_path = board["apps_path"]

    print(f"Board: {board['name']} ({board['host']})")
    print(f"Apps path: {apps_path}")
    print()

    config = load_config()
    active = get_active_project(config, board["name"])

    # List directories in apps_path
    if not os.path.exists(apps_path):
        print("Apps directory does not exist on this machine.")
        print(f"Run 'newrepo' to set up the board environment.")
        return

    projects = [d for d in os.listdir(apps_path)
                if os.path.isdir(os.path.join(apps_path, d))]

    if not projects:
        print("No projects found. Use: project new <name>")
        return

    print("Projects:")
    for p in sorted(projects):
        marker = " *" if p == active else "  "
        print(f"{marker} {p}")

    if active:
        print(f"\nActive project: {active}")
    else:
        print("\nNo active project. Use: project set <name>")

def cmd_new(name: str):
    board = get_active_board()
    apps_path = board["apps_path"]
    repo_path = os.path.expanduser(
        f"~/Repos/GitHub/{board['repo'].split('github.com/')[-1].replace('.git', '')}"
    )

    project_path = os.path.join(apps_path, name)
    repo_project_path = os.path.join(repo_path, "Arduino", name)

    print(f"Creating project: {name}")
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
        os.path.join(sketch_dir, "sketch.ino"):      SKETCH_INO.format(name=name),
        os.path.join(sketch_dir, "sketch.yaml"):     SKETCH_YAML,
        os.path.join(python_dir, "main.py"):         MAIN_PY.format(name=name),
        os.path.join(python_dir, "requirements.txt"): REQUIREMENTS_TXT.format(name=name),
        os.path.join(project_path, "app.yaml"):      APP_YAML.format(name=name),
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
    if os.path.exists(repo_path):
        repo_project_path = os.path.join(repo_path, "Arduino", name)
        if not os.path.exists(repo_project_path):
            # Copy scaffold to repo
            import shutil
            shutil.copytree(project_path, repo_project_path)
            print(f"\nAdded to repo: Arduino/{name}/")

            result = subprocess.run(
                ["git", "-C", repo_path, "add", f"Arduino/{name}"],
                capture_output=True
            )
            result = subprocess.run(
                ["git", "-C", repo_path, "commit", "-m", f"Add project scaffold: {name}"],
                capture_output=True, text=True
            )
            if result.returncode == 0:
                print(f"Committed: Add project scaffold: {name}")
                result = subprocess.run(
                    ["git", "-C", repo_path, "push"],
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
        print(f"\nNote: Repo not found at {repo_path} — project created locally only.")
        print(f"Run 'newrepo' to set up the full environment.")

    print(f"\nProject '{name}' ready.")

def cmd_set(name: str):
    board = get_active_board()
    apps_path = board["apps_path"]
    project_path = os.path.join(apps_path, name)

    if not os.path.exists(project_path):
        print(f"ERROR: Project '{name}' not found at {project_path}")
        sys.exit(1)

    config = load_config()
    set_active_project(config, board["name"], name)
    save_config(config)
    save_last_app(name)
    print(f"Active project set to: {name}")

def cmd_show():
    board = get_active_board()
    config = load_config()
    active = get_active_project(config, board["name"])

    print(f"Board: {board['name']} ({board['host']})")
    if active:
        print(f"Active project: {active}")
        print(f"Path: {board['apps_path']}/{active}")
    else:
        print("No active project. Use: project set <name>")

def cmd_remove(name: str):
    board = get_active_board()
    apps_path = board["apps_path"]
    project_path = os.path.join(apps_path, name)

    if not os.path.exists(project_path):
        print(f"ERROR: Project '{name}' not found at {project_path}")
        sys.exit(1)

    confirm = input(f"Remove project '{name}' from local disk? (yes/no): ").strip().lower()
    if confirm != "yes":
        print("Cancelled.")
        return

    import shutil
    shutil.rmtree(project_path)
    print(f"Removed: {project_path}")

    # Clear active project if it was this one
    config = load_config()
    if get_active_project(config, board["name"]) == name:
        set_active_project(config, board["name"], None)
        save_config(config)
        print(f"Note: Active project cleared. Use: project set <name>")

def usage():
    print("Usage:")
    print("  project list              - List projects for the active board")
    print("  project new <name>        - Create a new project scaffold")
    print("  project set <name>        - Set the active project")
    print("  project show              - Show the active project")
    print("  project remove <name>     - Remove a project (local only)")

# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    if len(sys.argv) < 2:
        usage()
        sys.exit(1)

    command = sys.argv[1]

    if command == "list":
        cmd_list()
    elif command == "show":
        cmd_show()
    elif command == "new":
        if len(sys.argv) < 3:
            print("Usage: project new <name>")
            sys.exit(1)
        cmd_new(sys.argv[2])
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
