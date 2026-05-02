#!/usr/bin/env python3

"""
project-v2.0.8.py
Hybrid RobotiX — HybX Development System

Manages projects for the active board.
Projects live under a project type directory within the board's apps directory.

Usage:
  project list                       - List projects for the active board
  project list --names               - List project names only
  project new <type> <name>          - Create a new project scaffold
  project use <name>                 - Set the active project
  project show                       - Show the active project
  project clone <source> <new>       - Clone an existing project to a new name
  project rename <old> <new>         - Rename a project locally and in git repo
  project remove <name>              - Remove a project from local disk AND git repo

Project types (case insensitive):
  arduino     → Arduino/
  micropython → MicroPython/
  ros2        → ROS2/

Examples:
  project new arduino    lis3dh
  project new micropython sensor-display
  project new ros2       navigation
  project clone monitor-vl53l5cx robot-ranger

Changes in v2.0.7:
  - All git commit/push calls now stream output directly to the terminal.
    No more capture_output=True silencing failures. You will see exactly
    what git reports — errors, warnings, and all.
  - Removed duplicate cmd_clone body that was appended inside cmd_rename.
  - Extracted git_commit_and_push() helper used by clone, rename, remove.
  - ERROR prefix on all failure paths (was WARNING/NOTE — too easy to miss).
"""

import os
import re
import sys
import json
import shutil
import subprocess

sys.path.insert(0, os.path.dirname(os.path.realpath(__file__)))
sys.path.insert(0, os.path.expanduser("~/lib"))

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


def repo_root_for_board(board: dict) -> str:
    """Compute the local repo root path for the active board."""
    return os.path.expanduser(
        f"~/Repos/GitHub/{board['repo'].split('github.com/')[-1].replace('.git', '')}"
    )


def git_commit_and_push(repo_root: str, message: str, board: dict) -> bool:
    """
    Run git commit then git push, streaming all output directly to the terminal
    so nothing is silenced. Returns True if both succeeded, False otherwise.
    """
    print("--- git commit ---")
    result = subprocess.run(
        ["git", "commit", "-m", message],
        cwd=repo_root
    )
    if result.returncode != 0:
        print("ERROR: git commit failed.")
        return False

    push_url = get_push_url(board)
    if not push_url:
        print("ERROR: No push URL — changes committed locally but NOT pushed to GitHub.")
        print(f"  Fix: run 'board pat <your-pat>' then: cd {repo_root} && git push")
        return False

    print("--- git push ---")
    push = subprocess.run(
        ["git", "push", push_url, "main"],
        cwd=repo_root
    )
    if push.returncode != 0:
        print("ERROR: git push failed — changes committed locally but NOT on GitHub.")
        print(f"  Fix: cd {repo_root} && git push")
        return False

    return True


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

    all_projects = sorted([
        d for d in os.listdir(apps_path)
        if os.path.isdir(os.path.join(apps_path, d))
        and os.path.exists(os.path.join(apps_path, d, "app.yaml"))
    ])

    if not all_projects:
        print("No projects found. Use: project new <type> <name>")
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
        print("No active project. Use: project use <name>")


def cmd_new(project_type_raw: str, name: str):
    project_type = normalize_project_type(project_type_raw)

    if not project_type:
        print(f"ERROR: Unknown project type '{project_type_raw}'")
        print(f"Valid types: {', '.join(PROJECT_TYPES.keys())}")
        sys.exit(1)

    board     = get_active_board()
    apps_path = board["apps_path"]
    project_path = os.path.join(apps_path, name)

    print(f"=== project new ===")
    print(f"Type:  {project_type}")
    print(f"Name:  {name}")
    print(f"Board: {board['name']} ({board['host']})")
    print()

    if os.path.exists(project_path):
        print(f"ERROR: Project '{name}' already exists at {project_path}")
        sys.exit(1)

    sketch_dir = os.path.join(project_path, "sketch")
    python_dir = os.path.join(project_path, "python")
    os.makedirs(sketch_dir, exist_ok=True)
    os.makedirs(python_dir, exist_ok=True)
    print(f"Created: {project_path}/")

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

    found_path = None
    direct = os.path.join(apps_path, name)
    if os.path.isdir(direct):
        found_path = direct

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


def cmd_clone(source_name: str, new_name: str):
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
    repo_root         = repo_root_for_board(board)
    repo_project_path = os.path.join(repo_root, "Arduino", board["name"].upper(), new_name)

    if not os.path.isdir(repo_root):
        print(f"ERROR: Repo not found at {repo_root} — project created locally but NOT in git.")
        print(f"  Fix: run 'update' to clone the UNO-Q repo to the board.")
    elif os.path.exists(repo_project_path):
        print(f"ERROR: Repo path already exists: {repo_project_path}")
        print(f"  Fix: manually remove it from the repo and try again.")
    else:
        shutil.copytree(new_path, repo_project_path, ignore=ignore_cache)
        # Update app.yaml in repo copy
        repo_yaml = os.path.join(repo_project_path, "app.yaml")
        if os.path.exists(repo_yaml):
            with open(repo_yaml, "r") as f:
                content = f.read()
            content = re.sub(r'^name:.*$', f'name: {new_name}', content, flags=re.MULTILINE)
            with open(repo_yaml, "w") as f:
                f.write(content)
        print(f"Synced to repo: {repo_project_path}")
        subprocess.run(["git", "add", repo_project_path], cwd=repo_root)
        git_commit_and_push(repo_root, f"feat: add {new_name} (cloned from {source_name})", board)

    config = load_config()
    set_active_project(config, board["name"], new_name)
    save_config(config)
    save_last_app(new_name)
    print(f"\nActive project set to: {new_name}")
    print(f"Project '{new_name}' ready. Run 'clean {new_name}' to build and start.")


def cmd_rename(old_name: str, new_name: str):
    board     = get_active_board()
    apps_path = board["apps_path"]

    old_path = os.path.join(apps_path, old_name)
    new_path = os.path.join(apps_path, new_name)

    print(f"=== project rename ===")
    print(f"From:  {old_name}")
    print(f"To:    {new_name}")
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
    repo_root = repo_root_for_board(board)
    repo_old  = os.path.join(repo_root, "Arduino", board["name"].upper(), old_name)
    repo_new  = os.path.join(repo_root, "Arduino", board["name"].upper(), new_name)

    if not os.path.isdir(repo_root):
        print(f"ERROR: Repo not found at {repo_root} — renamed locally but NOT in git.")
        print(f"  Fix: run 'update' to clone the repo, then rename manually.")
    elif not os.path.isdir(repo_old):
        print(f"NOTE: '{old_name}' not found in repo — skipping git sync.")
        print(f"  (Local rename still applied.)")
    else:
        os.rename(repo_old, repo_new)
        repo_yaml = os.path.join(repo_new, "app.yaml")
        if os.path.exists(repo_yaml):
            with open(repo_yaml, "r") as f:
                content = f.read()
            content = re.sub(r'^name:.*$', f'name: {new_name}', content, flags=re.MULTILINE)
            with open(repo_yaml, "w") as f:
                f.write(content)
        subprocess.run(["git", "add", "-A"], cwd=repo_root)
        git_commit_and_push(repo_root, f"rename: {old_name} → {new_name}", board)

    config = load_config()
    if get_active_project(config, board["name"]) == old_name:
        set_active_project(config, board["name"], new_name)
        save_config(config)
        print(f"Active project updated to: {new_name}")

    save_last_app(new_name)
    print(f"\nProject renamed successfully. Run 'clean {new_name}' to rebuild.")


def cmd_remove(name: str):
    board     = get_active_board()
    apps_path = board["apps_path"]

    found_path = None
    direct = os.path.join(apps_path, name)
    if os.path.isdir(direct):
        found_path = direct

    if not found_path:
        for type_dir in os.listdir(apps_path):
            candidate = os.path.join(apps_path, type_dir, name)
            if os.path.isdir(candidate):
                found_path = candidate
                break

    if not found_path:
        print(f"ERROR: Project '{name}' not found in {apps_path}")
        sys.exit(1)

    repo_root         = repo_root_for_board(board)
    repo_project_path = os.path.join(repo_root, "Arduino", board["name"].upper(), name)
    in_repo           = os.path.isdir(repo_project_path)

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

    shutil.rmtree(found_path)
    print(f"Removed local: {found_path}")

    if in_repo:
        subprocess.run(["git", "rm", "-rf", repo_project_path], cwd=repo_root)
        subprocess.run(["git", "add", "-A"], cwd=repo_root)
        git_commit_and_push(repo_root, f"remove: delete project {name}", board)

    config = load_config()
    if get_active_project(config, board["name"]) == name:
        set_active_project(config, board["name"], None)
        save_config(config)
        print(f"Active project cleared. Use: project use <name>")


def cmd_push(project_name: str = None):
    """
    Push a project from the board's local apps directory to GitHub.

    If project_name is None, the active project is used.

    Steps:
      1. Resolve project name — active project or named project.
      2. Copy project files from apps_path into the local repo clone,
         overwriting the repo copy with the current local version.
      3. Prompt for a commit message (default: "sync: update <name>").
      4. git add, git commit, git push — all with full visible output.

    This is the correct way to sync local edits made on the board
    (via nano, VSCode, or any editor) back to GitHub.
    """
    board      = get_active_board()
    board_name = board["name"]
    apps_path  = board["apps_path"]
    repo_url   = board.get("repo", "")

    # ── Resolve project name ───────────────────────────────────────────────────
    if project_name is None:
        config       = load_config()
        project_name = config.get("board_projects", {}).get(board_name, {}).get("active")

    if not project_name:
        print("ERROR: No active project set and no project name given.")
        print("  Fix: run 'project use <name>' or 'project push <name>'")
        sys.exit(1)

    # ── Verify local project exists ────────────────────────────────────────────
    local_project_path = os.path.join(apps_path, project_name)

    if not os.path.isdir(local_project_path):
        print(f"ERROR: Project '{project_name}' not found at {local_project_path}")
        sys.exit(1)

    # ── Derive local repo path ─────────────────────────────────────────────────
    if not repo_url:
        print(f"ERROR: No repo configured for board '{board_name}'.")
        print(f"  Fix: re-add the board with: board add {board_name}")
        sys.exit(1)

    try:
        path_part = repo_url.replace("https://github.com/", "").rstrip("/")

        if path_part.endswith(".git"):
            path_part = path_part[:-4]

        github_user, repo_name = path_part.split("/", 1)
    except (ValueError, AttributeError):
        print(f"ERROR: Could not parse repo URL: {repo_url}")
        sys.exit(1)

    repo_path         = os.path.expanduser(f"~/Repos/GitHub/{github_user}/{repo_name}")
    repo_project_path = os.path.join(repo_path, "Arduino", board_name.upper(), project_name)

    if not os.path.isdir(repo_path):
        print(f"ERROR: Repo not found at {repo_path}")
        print(f"  Fix: run 'update' to clone the repo to this board.")
        sys.exit(1)

    # ── Get push URL with PAT ──────────────────────────────────────────────────
    push_url = get_push_url(board)

    if not push_url:
        print(f"ERROR: No PAT stored for board '{board_name}'.")
        print(f"  Fix: run 'board pat <your-pat>' then retry.")
        sys.exit(1)

    # ── Header ────────────────────────────────────────────────────────────────
    print(f"=== project push ===")
    print(f"Project: {project_name}")
    print(f"Board:   {board_name} ({board['host']})")
    print(f"Repo:    {repo_path}")
    print()

    # ── Prompt for commit message ──────────────────────────────────────────────
    try:
        message = input(f"Commit message [sync: update {project_name}]: ").strip()

        if not message:
            message = f"sync: update {project_name}"

    except KeyboardInterrupt:
        print("\nCancelled.")
        return

    # ── Copy local project into repo ───────────────────────────────────────────
    def ignore_cache(src, names):
        # Exclude build cache directories from the repo copy
        return [n for n in names if n == ".cache"]

    if os.path.isdir(repo_project_path):
        # Remove existing repo copy so we get a clean overwrite
        shutil.rmtree(repo_project_path)

    shutil.copytree(local_project_path, repo_project_path, ignore=ignore_cache)
    print(f"Copied: {local_project_path}")
    print(f"    to: {repo_project_path}")
    print()

    # ── git add ────────────────────────────────────────────────────────────────
    subprocess.run(["git", "add", repo_project_path], cwd=repo_path)

    # ── git commit ────────────────────────────────────────────────────────────
    print("--- git commit ---")
    result = subprocess.run(
        ["git", "commit", "-m", message],
        cwd=repo_path
    )

    if result.returncode != 0:
        print("ERROR: git commit failed.")
        print("  If there were no changes, the working tree was already clean.")
        return

    # ── git push ───────────────────────────────────────────────────────────────
    print("--- git push ---")
    push = subprocess.run(
        ["git", "push", push_url, "main"],
        cwd=repo_path
    )

    if push.returncode != 0:
        print(f"ERROR: git push failed — committed locally but NOT on GitHub.")
        print(f"  Fix: cd {repo_path} && git push")
        return

    print()
    print(f"Project '{project_name}' pushed to GitHub successfully.")


def cmd_pull(project_name: str = None):
    """
    Pull the latest version of a project from GitHub into the board's apps directory.

    If project_name is None, the active project is used.

    Steps:
      1. Resolve project name — active project or named project.
      2. Pull the latest repo with git pull (visible output).
      3. Copy the project from the repo into apps_path, overwriting
         the local version with what is on GitHub.

    Use this when another developer has pushed changes and you want
    to update your local copy on the board.
    """
    board      = get_active_board()
    board_name = board["name"]
    apps_path  = board["apps_path"]
    repo_url   = board.get("repo", "")

    # ── Resolve project name ───────────────────────────────────────────────────
    if project_name is None:
        config       = load_config()
        project_name = config.get("board_projects", {}).get(board_name, {}).get("active")

    if not project_name:
        print("ERROR: No active project set and no project name given.")
        print("  Fix: run 'project use <name>' or 'project pull <name>'")
        sys.exit(1)

    # ── Derive local repo path ─────────────────────────────────────────────────
    if not repo_url:
        print(f"ERROR: No repo configured for board '{board_name}'.")
        print(f"  Fix: re-add the board with: board add {board_name}")
        sys.exit(1)

    try:
        path_part = repo_url.replace("https://github.com/", "").rstrip("/")

        if path_part.endswith(".git"):
            path_part = path_part[:-4]

        github_user, repo_name = path_part.split("/", 1)
    except (ValueError, AttributeError):
        print(f"ERROR: Could not parse repo URL: {repo_url}")
        sys.exit(1)

    repo_path         = os.path.expanduser(f"~/Repos/GitHub/{github_user}/{repo_name}")
    repo_project_path = os.path.join(repo_path, "Arduino", board_name.upper(), project_name)

    if not os.path.isdir(repo_path):
        print(f"ERROR: Repo not found at {repo_path}")
        print(f"  Fix: run 'update' to clone the repo to this board.")
        sys.exit(1)

    # ── Header ────────────────────────────────────────────────────────────────
    print(f"=== project pull ===")
    print(f"Project: {project_name}")
    print(f"Board:   {board_name} ({board['host']})")
    print(f"Repo:    {repo_path}")
    print()

    # ── git pull ───────────────────────────────────────────────────────────────
    print("--- git pull ---")
    result = subprocess.run(
        ["git", "pull"],
        cwd=repo_path
    )

    if result.returncode != 0:
        print(f"ERROR: git pull failed.")
        print(f"  Fix: cd {repo_path} && git pull")
        sys.exit(1)

    print()

    # ── Verify project exists in repo after pull ───────────────────────────────
    if not os.path.isdir(repo_project_path):
        print(f"ERROR: Project '{project_name}' not found in repo at {repo_project_path}")
        print(f"  The project may not exist on GitHub yet.")
        sys.exit(1)

    # ── Copy project from repo into apps_path ─────────────────────────────────
    local_project_path = os.path.join(apps_path, project_name)

    def ignore_cache(src, names):
        # Exclude build cache directories from the copy
        return [n for n in names if n == ".cache"]

    if os.path.isdir(local_project_path):
        shutil.rmtree(local_project_path)

    shutil.copytree(repo_project_path, local_project_path, ignore=ignore_cache)
    print(f"Updated: {local_project_path}")
    print(f"   from: {repo_project_path}")
    print()
    print(f"Project '{project_name}' pulled from GitHub successfully.")


def usage():
    print("Usage:")
    print("  project list                       - List projects for the active board")
    print("  project list --names               - List project names only, one per line")
    print("  project new <type> <name>          - Create a new project scaffold")
    print("  project clone <source> <new>       - Clone an existing project to a new name")
    print("  project rename <old> <new>         - Rename a project locally and in git repo")
    print("  project use <name>                 - Set the active project")
    print("  project show                       - Show the active project")
    print("  project remove <name>              - Remove a project from local disk AND git repo")
    print("  project push                       - Push active project to GitHub")
    print("  project push <name>                - Push named project to GitHub")
    print("  project pull                       - Pull active project from GitHub")
    print("  project pull <name>                - Pull named project from GitHub")
    print()
    print("Project types: arduino, micropython, ros2")


# ── Main ───────────────────────────────────────────────────────────────────────

def main():
    print("=== project ===")

    SUBCOMMANDS = ["list", "show", "new", "use", "clone", "rename", "remove", "push", "pull"]

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
    elif command == "push":
        project_arg = next((a for a in sys.argv[2:] if not a.startswith("--")), None)
        cmd_push(project_arg)
    elif command == "pull":
        project_arg = next((a for a in sys.argv[2:] if not a.startswith("--")), None)
        cmd_pull(project_arg)
    else:
        print(f"ERROR: Unknown command '{command}'")
        usage()
        sys.exit(1)


if __name__ == "__main__":
    main()
