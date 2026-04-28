#!/usr/bin/env python3
"""
flash-v2.0.0.py
Hybrid RobotiX — HybX Development System v2.0
Dale Weber <hybotix@hybridrobotix.io>

Flash a compiled binary to the MCU without rebuilding or restarting
the Python app side. Uses HybXFlasher — always writes to flash,
always uses the correct binary, no RAM/flash confusion.

Useful when:
  - You want to flash without triggering a full rebuild
  - You need to re-flash after a power cycle
  - You are debugging and iterating on flash only

Usage:
  flash [<project_name_or_binary_path>]

  No args    — flash the last built binary for the active project
  project    — flash the cached binary for <project>
  /path/to/binary.elf-zsk.bin — flash a specific binary
"""

import os
import sys
import json
sys.path.insert(0, os.path.dirname(os.path.realpath(__file__)))
sys.path.insert(0, os.path.expanduser("~/lib"))

from hybx_config import get_active_board, load_config, HybXTimer  # noqa: E402
from flasher import HybXFlasher  # noqa: E402


# ── Board definition loader ────────────────────────────────────────────────────


def load_board_definition(board_id: str) -> dict:
    config      = load_config()
    github_user = config.get("github_user", "")
    boards_dir  = os.path.expanduser(
        f"~/Repos/GitHub/{github_user}/HybX-Development-System/boards"
    )
    board_file  = os.path.join(boards_dir, f"{board_id}.json")

    if not os.path.exists(board_file):
        print(f"ERROR: Board definition not found: {board_file}")
        sys.exit(1)

    with open(board_file) as f:
        return json.load(f)


# ── Binary resolution ──────────────────────────────────────────────────────────


def resolve_binary(apps_path: str, board_def: dict) -> tuple[str, str]:
    """
    Resolve binary path and display name from sys.argv or active project.
    Returns (binary_path, display_name).
    """
    binary_key = board_def["flash"]["binary_key"]

    if len(sys.argv) < 2:
        # Use active project
        config       = load_config()
        active_board = config.get("active_board", "")
        project      = config.get("board_projects", {}).get(
                           active_board, {}).get("active")
        if not project:
            print("Usage: flash [<project_or_binary_path>]")
            print("No active project set. Use: project use <n>")
            sys.exit(1)
        binary = os.path.join(apps_path, project, ".cache", "sketch", binary_key)
        return binary, project

    arg = sys.argv[1]

    # Direct binary path
    if arg.endswith(".bin") or arg.endswith(".elf"):
        return os.path.expanduser(arg), os.path.basename(arg)

    # Project name
    if os.path.isabs(arg) or arg.startswith("~") or arg.startswith("."):
        app_path = os.path.expanduser(arg)
        if app_path.endswith("/sketch"):
            app_path = app_path[:-7]
        project  = os.path.basename(app_path)
        binary   = os.path.join(app_path, ".cache", "sketch", binary_key)
        return binary, project

    # Bare project name
    app_path = os.path.join(apps_path, arg)
    if os.path.isdir(app_path):
        binary = os.path.join(app_path, ".cache", "sketch", binary_key)
        return binary, arg

    print(f"ERROR: Cannot resolve '{arg}' to a project or binary.")
    sys.exit(1)


# ── Main ───────────────────────────────────────────────────────────────────────


def main():
    print("=== flash ===")

    board     = get_active_board()
    apps_path = board["apps_path"]
    board_def = load_board_definition(board.get("board_id", "uno-q"))

    binary, display_name = resolve_binary(apps_path, board_def)

    print("Board:   " + board["name"] + " (" + board["host"] + ")")
    print("Project: " + display_name)
    print()

    flasher = HybXFlasher(board_def, binary_path=binary, verbose=False)

    with HybXTimer("flash", print_start=True):
        result = flasher.flash()

    if not result.success:
        print(f"ERROR: Flash failed — {result.error}")
        sys.exit(2)

    print()
    print("Done.")


if __name__ == "__main__":
    with HybXTimer("flash", print_start=True):
        main()
