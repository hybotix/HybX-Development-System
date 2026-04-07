#!/usr/bin/env python3
"""
board-v0.0.1.py
Hybrid RobotiX — HybX Development System

Manages board configurations for the HybX Development System.
All other commands read the active board from ~/.hybx/config.json.

Usage:
  board list              - List all configured boards
  board set <name>        - Set the active board
  board add <name>        - Add a new board configuration
  board remove <name>     - Remove a board configuration
  board show              - Show active board details
"""

import sys
import os
import json

CONFIG_DIR  = os.path.expanduser("~/.hybx")
CONFIG_FILE = os.path.join(CONFIG_DIR, "config.json")

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
    print(f"Config saved: {CONFIG_FILE}")

# ---------------------------------------------------------------------------
# Commands
# ---------------------------------------------------------------------------

def cmd_list():
    config = load_config()
    boards = config.get("boards", {})
    active = config.get("active_board")

    if not boards:
        print("No boards configured. Use: board add <name>")
        return

    print("Configured boards:")
    for name, info in boards.items():
        marker = " *" if name == active else "  "
        print(f"{marker} {name}")
        print(f"      host:      {info.get('host', '(not set)')}")
        print(f"      apps_path: {info.get('apps_path', '(not set)')}")
        print(f"      repo:      {info.get('repo', '(not set)')}")

    if active:
        print(f"\nActive board: {active}")
    else:
        print("\nNo active board set. Use: board set <name>")

def cmd_set(name: str):
    config = load_config()
    if name not in config.get("boards", {}):
        print(f"ERROR: Board '{name}' not found. Use: board list")
        sys.exit(1)
    config["active_board"] = name
    save_config(config)
    print(f"Active board set to: {name}")

def cmd_add(name: str):
    config = load_config()
    boards = config.setdefault("boards", {})

    if name in boards:
        print(f"Board '{name}' already exists. Use: board remove {name} first.")
        sys.exit(1)

    print(f"Adding board: {name}")
    print()

    default_host = f"arduino@{name}.local"
    default_apps_path = f"~/Arduino/{name}"

    host_input = input(f"  SSH host [{default_host}]: ").strip()
    host = host_input if host_input else default_host

    apps_path_input = input(f"  Apps path on board [{default_apps_path}]: ").strip()
    apps_path = os.path.expanduser(apps_path_input if apps_path_input else default_apps_path)

    default_repo = f"https://github.com/hybotix/{name}.git"
    repo_input = input(f"  App repo URL [{default_repo}]: ").strip()
    repo = repo_input if repo_input else default_repo

    boards[name] = {
        "host": host,
        "apps_path": apps_path,
        "repo": repo
    }

    # Set as active if it's the first board
    if config.get("active_board") is None:
        config["active_board"] = name
        print(f"\nFirst board added — setting as active board.")

    save_config(config)
    print(f"\nBoard '{name}' added successfully.")

def cmd_remove(name: str):
    config = load_config()
    boards = config.get("boards", {})

    if name not in boards:
        print(f"ERROR: Board '{name}' not found. Use: board list")
        sys.exit(1)

    confirm = input(f"Remove board '{name}'? (yes/no): ").strip().lower()
    if confirm != "yes":
        print("Cancelled.")
        return

    del boards[name]

    if config.get("active_board") == name:
        config["active_board"] = None
        print(f"WARNING: '{name}' was the active board. Use: board set <name>")

    save_config(config)
    print(f"Board '{name}' removed.")

def cmd_show():
    config = load_config()
    active = config.get("active_board")

    if not active:
        print("No active board set. Use: board set <name>")
        sys.exit(1)

    info = config.get("boards", {}).get(active, {})
    print(f"Active board: {active}")
    print(f"  host:      {info.get('host', '(not set)')}")
    print(f"  apps_path: {info.get('apps_path', '(not set)')}")
    print(f"  repo:      {info.get('repo', '(not set)')}")

def usage():
    print("Usage:")
    print("  board list              - List all configured boards")
    print("  board set <name>        - Set the active board")
    print("  board add <name>        - Add a new board configuration")
    print("  board remove <name>     - Remove a board configuration")
    print("  board show              - Show active board details")

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
    elif command == "set":
        if len(sys.argv) < 3:
            print("Usage: board set <name>")
            sys.exit(1)
        cmd_set(sys.argv[2])
    elif command == "add":
        if len(sys.argv) < 3:
            print("Usage: board add <name>")
            sys.exit(1)
        cmd_add(sys.argv[2])
    elif command == "remove":
        if len(sys.argv) < 3:
            print("Usage: board remove <name>")
            sys.exit(1)
        cmd_remove(sys.argv[2])
    else:
        print(f"ERROR: Unknown command '{command}'")
        usage()
        sys.exit(1)

if __name__ == "__main__":
    main()
