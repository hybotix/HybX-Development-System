#!/usr/bin/env python3
"""
build-v2.0.0.py
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

from hybx_config import get_active_board, load_libraries, load_config, HybXTimer  # noqa: E402
from compiler import HybXCompiler  # noqa: E402
from flasher  import HybXFlasher   # noqa: E402


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


def resolve_app_path(apps_path: str) -> tuple[str, str]:
    if len(sys.argv) < 2:
        config       = load_config()
        active_board = config.get("active_board", "")
        project      = config.get("board_projects", {}).get(
                           active_board, {}).get("active")
        if not project:
            print("Usage: build <project>")
            sys.exit(1)
        return os.path.join(apps_path, project), project
    arg = sys.argv[1]
    if os.path.isabs(arg) or arg.startswith("~") or arg.startswith("."):
        app_path = os.path.expanduser(arg)
        if app_path.endswith("/sketch"):
            app_path = app_path[:-7]
        return app_path, os.path.basename(app_path)
    candidate = os.path.join(apps_path, arg)
    if os.path.isdir(candidate):
        return candidate, arg
    print(f"ERROR: Project '{arg}' not found.")
    sys.exit(1)


def main():
    board     = get_active_board()
    apps_path = board["apps_path"]
    app_path, project = resolve_app_path(apps_path)

    print("=== build ===")
    print()
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

    flasher = HybXFlasher(board_def, binary_path=build_result.binary,
                          verbose=False)
    with HybXTimer("flash"):
        flash_result = flasher.flash()

    if not flash_result.success:
        print(f"ERROR: {flash_result.error}")
        sys.exit(2)


if __name__ == "__main__":
    main()
