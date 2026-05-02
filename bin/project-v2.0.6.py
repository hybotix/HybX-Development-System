#!/usr/bin/env python3

"""
project-v2.0.6.py
Hybrid RobotiX — HybX Development System

Manages projects for the active board.
Projects live under a project type directory within the board's apps directory.

Usage:
  project list                       - List projects for the active board
  project list --names               - List project names only
  project new <type> <name>          - Create a new project scaffold
  project use <name>                 - Set the active project
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

import os
import sys
sys.path.insert(0, os.path.dirname(os.path.realpath(__file__)))
sys.path.insert(0, os.path.expanduser("~/lib"))

import json  # noqa: E402
import shutil  # noqa: E402

from hybx_config import get_active_board, validate_name, get_push_url, confirm_prompt, resolve_subcommand  # noqa: E402

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


def cmd_list(names_only: bool = False):
    board     = get_active_board()
    apps_path = board["apps_path"]
    config    = load_config()
    active    = get_active_project(config, board["name"])

    if not os.path.exists(apps_path):
        print("Apps directory does not exist on this machine.")
        print("Run 'update' to set up the board environment.")
        return

    # Projects live directly in apps_path — identify them by presence of app.yaml
    all_projects = sorted([
        d for d in os.listdir(apps_path)
        if os.path.isdir(os.path.join(apps_path, d))
        and os.path.exists(os.path.join(apps_path, d, "app.yaml"))
    ])

    if not all_projects:
        print("No projects found. Use: project new <type> <n>")
        return

    if names_only:
        for p in all_projects:
            print(p)
        return

    print(f"Board: {board['name']} ({board['host']})")
    print(f"Apps path: {apps_path}")
    print()

    for p in all_projects:
        marker = " *" if p == active else "  "
        print(f"{marker} {p}")

    print()

    if active:
        print(f"Active project: {active}")
    else:
        print("No active project. Use: project use <n>")


def cmd_new(project_type_raw: str, name: str):
    project_type = normalize_project_type(project_type_raw)

    if not project_type:
        print(f"ERROR: Unknown project type '{project_type_raw}'")
        print(f"Valid types: {', '.join(PROJECT_TYPES.keys())}")
        sys.exit(1)

    board     = get_active_board()
    apps_path = board["apps_path"]

    # Local project path: <apps_path>/<n>
    # apps_path already includes the board name e.g. ~/Arduino/UNO-Q
    project_path = os.path.join(apps_path, name)

    # Repo path: ~/Repos/GitHub/hybotix/UNO-Q/Arduino/<board>/<n>
    repo_root = os.path.expanduser(
        f"~/Repos/GitHub/{board['repo'].split('github.com/')[-1].replace('.git', '')}"
    )
    repo_project_path = os.path.join(repo_root, "Arduino", board["name"], name)

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
    print(f"\nProject '{name}' ready.")
    print(f"Use 'start {name}' to build and run.")


def cmd_use(name: str):
    board     = get_active_board()
    apps_path = board["apps_path"]

    # Search directly in apps_path first (flat layout)
    found_path = None
    direct = os.path.join(apps_path, name)
    if os.path.isdir(direct):
        found_path = direct

    # Fall back to searching inside type subdirectories
    if not found_path:
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
        print("No active project. Use: project use <name>")


def cmd_remove(name: str):
    import subprocess
    board     = get_active_board()
    apps_path = board["apps_path"]

    # Search directly in apps_path first (flat layout)
    found_path = None
    direct = os.path.join(apps_path, name)
    if os.path.isdir(direct):
        found_path = direct

    # Fall back to searching inside type subdirectories
    if not found_path:
        for type_dir in os.listdir(apps_path):
            candidate = os.path.join(apps_path, type_dir, name)
            if os.path.isdir(candidate):
                found_path = candidate
                break

    if not found_path:
        print(f"ERROR: Project '{name}' not found in {apps_path}")
        sys.exit(1)

    # Check if it exists in the repo too
    repo_root = os.path.expanduser(
        f"~/Repos/GitHub/{board['repo'].split('github.com/')[-1].replace('.git', '')}"
    )
    repo_project_path = os.path.join(repo_root, "Arduino", board["name"].upper(), name)
    in_repo = os.path.isdir(repo_project_path)

    print(f"Project:  {name}")
    print(f"Local:    {found_path}")
    if in_repo:
        print(f"Repo:     {repo_project_path}")
    print()
    print("=" * 60)
    print("  ⚠️  DESTRUCTIVE OPERATION — CANNOT BE REVERSED  ⚠️")
    print("=" * 60)
    print(f"  This will PERMANENTLY DELETE '{name}' from:")
    print(f"    • Local disk:  {found_path}")
    if in_repo:
        print(f"    • Git repo:    {repo_project_path}")
        print(f"    • GitHub:      committed and pushed — gone forever")
    print()
    print("  There is NO undo. The project CANNOT be recovered.")
    print("=" * 60)
    print()

    if not confirm_prompt(f"Permanently remove '{name}' from ALL locations"):
        print("Cancelled.")
        return

    # Remove local
    shutil.rmtree(found_path)
    print(f"Removed local: {found_path}")

    # Remove from repo and push
    if in_repo:
        shutil.rmtree(repo_project_path)
        subprocess.run(["git", "rm", "-rf", repo_project_path], cwd=repo_root, capture_output=True)
        result = subprocess.run(
            ["git", "commit", "-m", f"remove: delete project {name}"],
            cwd=repo_root, capture_output=True, text=True
        )
        if result.returncode == 0:
            print(f"Committed removal to repo.")
            push_url = get_push_url(board)
            if push_url:
                push = subprocess.run(
                    ["git", "push", push_url, "main"],
                    cwd=repo_root, capture_output=True, text=True
                )
                if push.returncode == 0:
                    print(f"Pushed to GitHub.")
                else:
                    print(f"WARNING: Push failed — removal committed locally.")
                    print(f"  Run: cd {repo_root} && git push")
            else:
                print(f"NOTE: No push URL — removal committed locally.")
                print(f"  Run: cd {repo_root} && git push")
        else:
            print(f"WARNING: git commit failed: {result.stderr.strip()}")

    config = load_config()
    if get_active_project(config, board["name"]) == name:
        set_active_project(config, board["name"], None)
        save_config(config)
        print(f"Active project cleared. Use: project use <name>")


def usage():
    print("Usage:")
    print("  project list                  - List projects for the active board")
    print("  project list --names          - List project names only, one per line")
    print("  project new <type> <name>     - Create a new project scaffold")
    print("  project rename <old> <new>    - Rename a project locally and in git repo")
    print("  project clone <name1> <name2> - Clone an existing project to a new name")
    print("  project use <name>            - Set the active project")
    print("  project show                  - Show the active project")
    print("  project remove <name>         - Remove a project from local disk AND git repo")
    print()
    print("Project types: arduino, micropython, ros2")

# ── Main ───────────────────────────────────────────────────────────────────────


def cmd_clone(source_name: str, new_name: str):
    import re
    import shutil
    import subprocess

    board     = get_active_board()
    apps_path = board["apps_path"]

    source_path = os.path.join(apps_path, source_name)
    new_path    = os.path.join(apps_path, new_name)

    print(f"=== project clone ===")
    print(f"Source: {source_name}")
    print(f"New:    {new_name}")
    print(f"Board:  {board['name']} ({board['host']})")
    print()

    if not os.path.isdir(source_path):
        print(f"ERROR: Source project not found: {source_path}")
        sys.exit(1)

    if os.path.exists(new_path):
        print(f"ERROR: Project '{new_name}' already exists at {new_path}")
        sys.exit(1)

    def ignore_cache(src, names):
        return [n for n in names if n == ".cache"]

    shutil.copytree(source_path, new_path, ignore=ignore_cache)
    print(f"Copied: {source_name} → {new_name}")

    # Update app.yaml name field
    app_yaml = os.path.join(new_path, "app.yaml")
    if os.path.exists(app_yaml):
        with open(app_yaml, "r") as f:
            content = f.read()
        content = re.sub(r'^name:.*$', f'name: {new_name}', content, flags=re.MULTILINE)
        with open(app_yaml, "w") as f:
            f.write(content)
        print(f"Updated: app.yaml name → {new_name}")

    # Sync to repo and push
    repo_root = os.path.expanduser(
        f"~/Repos/GitHub/{board['repo'].split('github.com/')[-1].replace('.git', '')}"
    )
    repo_project_path = os.path.join(repo_root, "Arduino", board["name"].upper(), new_name)

    if os.path.isdir(repo_root):
        if os.path.exists(repo_project_path):
            print(f"WARNING: Repo path already exists: {repo_project_path}")
        else:
            shutil.copytree(new_path, repo_project_path, ignore=ignore_cache)
            # Update app.yaml in repo
            repo_yaml = os.path.join(repo_project_path, "app.yaml")
            if os.path.exists(repo_yaml):
                with open(repo_yaml, "r") as f:
                    content = f.read()
                content = re.sub(r'^name:.*$', f'name: {new_name}', content, flags=re.MULTILINE)
                with open(repo_yaml, "w") as f:
                    f.write(content)
            print(f"Synced to repo: {repo_project_path}")
            subprocess.run(["git", "add", repo_project_path], cwd=repo_root)
            result = subprocess.run(
                ["git", "commit", "-m", f"feat: add {new_name} (cloned from {source_name})"],
                cwd=repo_root, capture_output=True, text=True
            )
            if result.returncode == 0:
                print(f"Committed to repo.")
                push_url = get_push_url(board)
                if push_url:
                    push = subprocess.run(
                        ["git", "push", push_url, "main"],
                        cwd=repo_root, capture_output=True, text=True
                    )
                    if push.returncode == 0:
                        print(f"Pushed to GitHub.")
                    else:
                        print(f"WARNING: Push failed — committed locally.")
                        print(f"  Run: cd {repo_root} && git push")
                else:
                    print(f"NOTE: No push URL — committed locally.")
    else:
        print(f"NOTE: Repo not found — skipping git sync.")

    config = load_config()
    set_active_project(config, board["name"], new_name)
    save_config(config)
    save_last_app(new_name)
    print(f"\nActive project set to: {new_name}")
    print(f"Project '{new_name}' ready. Run 'clean {new_name}' to build and start.")


def cmd_rename(old_name: str, new_name: str):
    import re
    import subprocess
    board     = get_active_board()
    apps_path = board["apps_path"]

    old_path = os.path.join(apps_path, old_name)
    new_path = os.path.join(apps_path, new_name)

    print(f"=== project rename ===")
    print(f"From: {old_name}")
    print(f"To:   {new_name}")
    print(f"Board: {board['name']} ({board['host']})")
    print()

    if not os.path.isdir(old_path):
        print(f"ERROR: Project '{old_name}' not found at {old_path}")
        sys.exit(1)

    if os.path.exists(new_path):
        print(f"ERROR: Project '{new_name}' already exists at {new_path}")
        sys.exit(1)

    if not confirm_prompt(f"Rename '{old_name}' to '{new_name}'"):
        print("Cancelled.")
        return

    # Rename locally
    os.rename(old_path, new_path)
    print(f"Renamed local: {old_name} → {new_name}")

    # Update app.yaml name field
    app_yaml = os.path.join(new_path, "app.yaml")
    if os.path.exists(app_yaml):
        with open(app_yaml, "r") as f:
            content = f.read()
        content = re.sub(r'^name:.*$', f'name: {new_name}', content, flags=re.MULTILINE)
        with open(app_yaml, "w") as f:
            f.write(content)
        print(f"Updated: app.yaml name → {new_name}")

    # Rename in repo
    repo_root = os.path.expanduser(
        f"~/Repos/GitHub/{board['repo'].split('github.com/')[-1].replace('.git', '')}"
    )
    repo_old = os.path.join(repo_root, "Arduino", board["name"].upper(), old_name)
    repo_new = os.path.join(repo_root, "Arduino", board["name"].upper(), new_name)

    if os.path.isdir(repo_root):
        if os.path.isdir(repo_old):
            os.rename(repo_old, repo_new)
            # Update app.yaml in repo too
            repo_yaml = os.path.join(repo_new, "app.yaml")
            if os.path.exists(repo_yaml):
                with open(repo_yaml, "r") as f:
                    content = f.read()
                content = re.sub(r'^name:.*$', f'name: {new_name}', content, flags=re.MULTILINE)
                with open(repo_yaml, "w") as f:
                    f.write(content)
            subprocess.run(["git", "add", "-A"], cwd=repo_root)
            result = subprocess.run(
                ["git", "commit", "-m", f"rename: {old_name} → {new_name}"],
                cwd=repo_root, capture_output=True, text=True
            )
            if result.returncode == 0:
                print(f"Committed rename to repo.")
                push_url = get_push_url(board)
                if push_url:
                    push = subprocess.run(
                        ["git", "push", push_url, "main"],
                        cwd=repo_root, capture_output=True, text=True
                    )
                    if push.returncode == 0:
                        print(f"Pushed to GitHub.")
                    else:
                        print(f"WARNING: Push failed — rename committed locally.")
                        print(f"  Run: cd {repo_root} && git push")
                else:
                    print(f"NOTE: No push URL — rename committed locally.")
                    print(f"  Run: cd {repo_root} && git push")
            else:
                print(f"WARNING: git commit failed: {result.stderr.strip()}")
        else:
            print(f"NOTE: Project not found in repo — skipping git sync.")
    else:
        print(f"NOTE: Repo not found at {repo_root} — skipping git sync.")

    # Update config if this was the active project
    config = load_config()
    if get_active_project(config, board["name"]) == old_name:
        set_active_project(config, board["name"], new_name)
        save_config(config)
        print(f"Active project updated to: {new_name}")

    save_last_app(new_name)
    print(f"\nProject renamed successfully. Run 'clean {new_name}' to rebuild.")
    import re
    import shutil

    board     = get_active_board()
    apps_path = board["apps_path"]

    source_path = os.path.join(apps_path, source_name)
    new_path    = os.path.join(apps_path, new_name)

    print(f"=== project clone ===")
    print(f"Source: {source_name}")
    print(f"New:    {new_name}")
    print(f"Board:  {board['name']} ({board['host']})")
    print()

    if not os.path.isdir(source_path):
        print(f"ERROR: Source project not found: {source_path}")
        sys.exit(1)

    if os.path.exists(new_path):
        print(f"ERROR: Project '{new_name}' already exists at {new_path}")
        sys.exit(1)

    # Copy all files excluding .cache
    def ignore_cache(src, names):
        return [n for n in names if n == ".cache"]

    shutil.copytree(source_path, new_path, ignore=ignore_cache)
    print(f"Copied: {source_name} → {new_name}")

    # Update app.yaml name field
    app_yaml = os.path.join(new_path, "app.yaml")
    if os.path.exists(app_yaml):
        with open(app_yaml, "r") as f:
            content = f.read()
        content = re.sub(r'^name:.*$', f'name: {new_name}', content, flags=re.MULTILINE)
        with open(app_yaml, "w") as f:
            f.write(content)
        print(f"Updated: app.yaml name → {new_name}")

    # Sync to UNO-Q repo and commit
    repo_root = os.path.expanduser(
        f"~/Repos/GitHub/{board['repo'].split('github.com/')[-1].replace('.git', '')}"
    )
    repo_project_path = os.path.join(repo_root, "Arduino", board["name"].upper(), new_name)

    if os.path.isdir(repo_root):
        if os.path.exists(repo_project_path):
            print(f"WARNING: Repo path already exists: {repo_project_path}")
        else:
            shutil.copytree(new_path, repo_project_path, ignore=ignore_cache)
            print(f"Synced to repo: {repo_project_path}")

            # git add + commit
            import subprocess
            subprocess.run(["git", "add", repo_project_path], cwd=repo_root)
            result = subprocess.run(
                ["git", "commit", "-m",
                 f"feat: add {new_name} (cloned from {source_name})"],
                cwd=repo_root,
                capture_output=True, text=True
            )
            if result.returncode == 0:
                print(f"Committed to repo: {new_name}")
                # Push using stored push URL if available
                push_url = get_push_url(board)
                if push_url:
                    push = subprocess.run(
                        ["git", "push", push_url, "main"],
                        cwd=repo_root, capture_output=True, text=True
                    )
                    if push.returncode == 0:
                        print(f"Pushed to GitHub.")
                    else:
                        print(f"WARNING: Push failed — commit saved locally.")
                        print(f"  Run: cd {repo_root} && git push")
                else:
                    print(f"NOTE: No push URL configured — commit saved locally.")
                    print(f"  Run: cd {repo_root} && git push")
            else:
                print(f"WARNING: git commit failed: {result.stderr.strip()}")
    else:
        print(f"NOTE: Repo not found at {repo_root} — skipping git sync.")

    # Register as active project in config
    config = load_config()
    set_active_project(config, board["name"], new_name)
    save_config(config)
    save_last_app(new_name)

    print(f"\nActive project set to: {new_name}")
    print(f"Project '{new_name}' ready. Run 'clean {new_name}' to build and start.")


def main():
    print("=== project ===")

    SUBCOMMANDS = ["list", "show", "new", "use", "clone", "rename", "remove"]

    if len(sys.argv) < 2:
        usage()
        sys.exit(1)

    command = resolve_subcommand(sys.argv[1], SUBCOMMANDS)

    if command == "list":
        names_only = "--names" in sys.argv
        cmd_list(names_only=names_only)
    elif command == "show":
        cmd_show()
    elif command == "new":
        if len(sys.argv) < 4:
            print("Usage: project new <type> <name>")
            print("Example: project new arduino lis3dh")
            sys.exit(1)
        cmd_new(sys.argv[2], " ".join(sys.argv[3:]))
    elif command == "use":
        if len(sys.argv) < 3:
            print("Usage: project use <name>")
            sys.exit(1)
        cmd_use(" ".join(sys.argv[2:]))
    elif command == "remove":
        if len(sys.argv) < 3:
            print("Usage: project remove <name>")
            sys.exit(1)
        cmd_remove(" ".join(sys.argv[2:]))
    elif command == "rename":
        if len(sys.argv) < 4:
            print("Usage: project rename <old_name> <new_name>")
            sys.exit(1)
        cmd_rename(sys.argv[2], sys.argv[3])
    elif command == "clone":
        if len(sys.argv) < 4:
            print("Usage: project clone <source_name> <new_name>")
            sys.exit(1)
        cmd_clone(sys.argv[2], sys.argv[3])
    else:
        print(f"ERROR: Unknown command '{command}'")
        usage()
        sys.exit(1)


if __name__ == "__main__":
    main()
