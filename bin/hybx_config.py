"""
hybx_config.py
Hybrid RobotiX — HybX Development System

Shared config helper. All bin commands import this to get the active board settings.

Usage in bin commands:
    from hybx_config import get_active_board

    board = get_active_board()   # exits with error if none configured
    host      = board["host"]
    apps_path = board["apps_path"]
    repo      = board["repo"]
    name      = board["name"]
"""

import os
import json
import sys

CONFIG_DIR  = os.path.expanduser("~/.hybx")
CONFIG_FILE = os.path.join(CONFIG_DIR, "config.json")

def load_config() -> dict:
    if not os.path.exists(CONFIG_FILE):
        return {"boards": {}, "active_board": None}
    with open(CONFIG_FILE, "r") as f:
        return json.load(f)

def get_active_board() -> dict:
    """
    Returns the active board config dict with an added 'name' key.
    Exits with an error message if no board is configured or active.
    """
    config = load_config()
    active = config.get("active_board")

    if not active:
        print("ERROR: No active board set.")
        print("Use: board add <n>   to add a board")
        print("     board set <n>   to set the active board")
        sys.exit(1)

    boards = config.get("boards", {})
    if active not in boards:
        print(f"ERROR: Active board '{active}' not found in config.")
        print("Use: board list")
        sys.exit(1)

    board = dict(boards[active])
    board["name"] = active
    return board
