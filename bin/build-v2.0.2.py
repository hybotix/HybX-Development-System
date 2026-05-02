#!/usr/bin/env python3
"""
build-v2.0.1.py
Hybrid RobotiX — HybX Development System v2.0
Dale Weber <hybotix@hybridrobotix.io>

Compile and flash a sketch. On success: lists user libraries only.
On failure: clear error message. Nothing else.

Usage:
  build [<project_name_or_path>]
"""

import os
import sys
import json
sys.path.insert(0, os.path.dirname(os.path.realpath(__file__)))
sys.path.insert(0, os.path.expanduser("~/lib"))

from hybx_config import get_active_board, load_libraries, load_config, HybXTimer, resolve_project, save_config  # noqa: E402
from compiler import HybXCompiler  # noqa: E402
from flasher  import HybXFlasher   # noqa: E402

LAST_APP_FILE = os.path.expanduser("~/.hybx/last_app")


def save_last_app(app_name: str):
    with open(LAST_APP_FILE, "w") as f:
        f.write(app_name + "\n")
    # Also update config active project
    config = load_config()
    board = get_active_board()
    board_name = board.get("name", "")
    config.setdefault("board_projects", {}).setdefault(board_name, {})["active"] = app_name
    save_config(config)


def load_board_definition(board_id: str) -> dict:
    config      = load_config()
    github_user = config.get("github_user", "")
    boards_dir  = os.path.expanduser(
        f"~/Repos/GitHub/{github_user}/HybX-Development-System/boards"
    )
    board_file  = os.path.join(boards_dir, f"{board_id}.json")
    if not os.path.exists(board_file):
        print(f"ERROR: Board definition not found: boards/{board_id}.json")
        sys.exit(1)
    with open(board_file) as f:
        return json.load(f)


def check_libraries(project: str) -> bool:
    libs         = load_libraries()
    project_libs = libs["projects"].get(project, [])
    if not project_libs:
        return True
    missing = [n for n in project_libs if n not in libs["installed"]]
    if missing:
        print("ERROR: Missing libraries:")
        for m in missing:
            print(f"  {m}")
        return False
    return True





def main():
    board     = get_active_board()
    apps_path = board["apps_path"]
    arg = sys.argv[1] if len(sys.argv) > 1 else None
    app_path, project = resolve_project(apps_path, arg)

    print("=== build ===")
    print("Board:   " + board["name"])
    print("Project: " + project)
    print()

    if not check_libraries(project):
        sys.exit(1)

    board_def = load_board_definition(board.get("board_id", "uno-q"))

    compiler = HybXCompiler(board_def, app_path, verbose=False)
    with HybXTimer("build"):
        build_result = compiler.build()

    if not build_result.success:
        print(f"ERROR: {build_result.error}")
        sys.exit(2)

    save_last_app(project)

    flasher = HybXFlasher(board_def, binary_path=build_result.binary,
                          verbose=False)
    with HybXTimer("flash"):
        flash_result = flasher.flash()

    if not flash_result.success:
        print(f"ERROR: {flash_result.error}")
        sys.exit(2)


if __name__ == "__main__":
    main()
