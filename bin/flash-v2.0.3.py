#!/usr/bin/env python3
"""
flash-v2.0.1.py
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

from hybx_config import get_active_board, load_config, HybXTimer, mask_host  # noqa: E402
from flasher import HybXFlasher  # noqa: E402

LAST_APP_FILE = os.path.expanduser("~/.hybx/last_app")


def save_last_app(app_name: str):
    with open(LAST_APP_FILE, "w") as f:
        f.write(app_name + "\n")


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
    # binary_key is the project-named binary: <project>.elf-zsk.bin
    # Fall back to board def key if project name not found

    if len(sys.argv) < 2:
        # First: check last_app (most recent build)
        LAST_APP_FILE = os.path.expanduser("~/.hybx/last_app")
        if os.path.isfile(LAST_APP_FILE):
            with open(LAST_APP_FILE) as f:
                project = f.read().strip()
            if project:
                binary = os.path.join(apps_path, "build", f"{project}.elf-zsk.bin")
                if os.path.isfile(binary):
                    return binary, project

        # Fallback: use active project
        config       = load_config()
        active_board = config.get("active_board", "")
        project      = config.get("board_projects", {}).get(
                           active_board, {}).get("active")
        if not project:
            print("Usage: flash [<project_or_binary_path>]")
            print("No active project set. Use: project use <n>")
            sys.exit(1)
        binary = os.path.join(apps_path, "build", f"{project}.elf-zsk.bin")
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
        binary   = os.path.join(os.path.dirname(app_path), "build", f"{project}.elf-zsk.bin")
        return binary, project

    # Bare project name
    app_path = os.path.join(apps_path, arg)
    if os.path.isdir(app_path):
        binary = os.path.join(os.path.dirname(app_path), "build", f"{arg}.elf-zsk.bin")
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
    is_file = len(sys.argv) > 1 and (
        sys.argv[1].endswith(".bin") or sys.argv[1].endswith(".elf")
    )

    print("Board:   " + board["name"])
    if is_file:
        print("File:    " + display_name)
    else:
        print("Project: " + display_name)
    print()

    flasher = HybXFlasher(board_def, binary_path=binary, verbose=False)

    with HybXTimer("flash", print_start=True):
        result = flasher.flash()

    if not result.success:
        print(f"ERROR: Flash failed — {result.error}")
        sys.exit(2)

    if not is_file:
        save_last_app(display_name)

    print()
    print("Done.")


if __name__ == "__main__":
    with HybXTimer("flash", print_start=True):
        main()
