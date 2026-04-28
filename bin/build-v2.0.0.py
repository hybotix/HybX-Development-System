#!/usr/bin/env python3
"""
build-v2.0.0.py
Hybrid RobotiX — HybX Development System v2.0
Dale Weber <hybotix@hybridrobotix.io>

Compile and flash a sketch to the active board using the HybX Build
System. Replaces arduino-cli compile + arduino-cli upload entirely.

Same interface as v1.x — project name, full path, or no args (active
project). Library pre-flight check unchanged.

Changes from v1.2.0:
  - HybXCompiler replaces arduino-cli compile
  - HybXFlasher replaces arduino-cli upload + OpenOCD dance
  - Board definition loaded from boards/uno-q.json
  - HybXTimer applied automatically

Usage:
  build [<project_name_or_path>]
"""

import os
import sys
import json
sys.path.insert(0, os.path.dirname(os.path.realpath(__file__)))
sys.path.insert(0, os.path.expanduser("~/lib"))

from hybx_config import get_active_board, load_libraries, load_config, HybXTimer, mask_host, safe_path, mask_username  # noqa: E402
from compiler import HybXCompiler   # noqa: E402
from flasher  import HybXFlasher    # noqa: E402

# ── Board definition loader ────────────────────────────────────────────────────


def load_board_definition(board_id: str) -> dict:
    """
    Load the board definition JSON from boards/<board_id>.json.
    Looks in the HybX Development System repo.
    """
    config      = load_config()
    github_user = config.get("github_user", "")
    boards_dir  = os.path.expanduser(
        f"~/Repos/GitHub/{github_user}/HybX-Development-System/boards"
    )
    board_file  = os.path.join(boards_dir, f"{board_id}.json")

    if not os.path.exists(board_file):
        print(f"ERROR: Board definition not found: {board_file}")
        print(f"       Expected: boards/{board_id}.json in HybX-Development-System")
        sys.exit(1)

    with open(board_file) as f:
        return json.load(f)


# ── Library pre-flight ─────────────────────────────────────────────────────────


def check_libraries(project: str) -> bool:
    """
    Verify every library assigned to the project is installed.
    Returns True if all clear.
    """
    libs         = load_libraries()
    project_libs = libs["projects"].get(project, [])

    if not project_libs:
        print("Note: no library assignments found for " + project +
              " in registry.")
        print("      Use: libs use " + project + " <n>   to register libraries.")
        return True

    missing = [n for n in project_libs if n not in libs["installed"]]

    if missing:
        print("ERROR: " + project + " requires libraries that are not installed:")
        for m in missing:
            print("  " + m)
        print()
        print("Run: libs install <n>   for each missing library.")
        return False

    print("Libraries OK: " + str(len(project_libs)) + " assigned, all installed.")
    return True


# ── Path resolution ────────────────────────────────────────────────────────────


def resolve_app_path(apps_path: str) -> tuple[str, str]:
    """
    Resolve app path and project name from sys.argv or active project.
    Returns (app_path, project_name).
    """
    if len(sys.argv) < 2:
        config       = load_config()
        active_board = config.get("active_board", "")
        project      = config.get("board_projects", {}).get(
                           active_board, {}).get("active")
        if not project:
            print("Usage: build <project_or_app_path>")
            print("No active project set. Use: project use <n>")
            sys.exit(1)
        return os.path.join(apps_path, project), project

    arg = sys.argv[1]
    if os.path.isabs(arg) or arg.startswith("~") or arg.startswith("."):
        app_path = os.path.expanduser(arg)
        # Remove trailing /sketch if present
        if app_path.endswith("/sketch"):
            app_path = app_path[:-7]
        project  = os.path.basename(app_path)
        return app_path, project

    # Project name
    candidate = os.path.join(apps_path, arg)
    if os.path.isdir(candidate):
        return candidate, arg

    print(f"ERROR: Project '{arg}' not found in {safe_path(apps_path)}")
    sys.exit(1)


# ── Main ───────────────────────────────────────────────────────────────────────


def main():
    print("=== build ===")

    board     = get_active_board()
    apps_path = board["apps_path"]

    app_path, project = resolve_app_path(apps_path)

    print("Board:   " + board["name"])
    print("Project: " + project)
    print()

    # ── Pre-flight ─────────────────────────────────────────────────────────────
    if not check_libraries(project):
        sys.exit(1)
    print()

    # ── Load board definition ──────────────────────────────────────────────────
    board_def = load_board_definition(board.get("board_id", "uno-q"))

    # ── Compile ────────────────────────────────────────────────────────────────
    compiler = HybXCompiler(board_def, app_path, verbose=False)
    with HybXTimer("compile", print_start=True):
        build_result = compiler.build()

    if not build_result.success:
        print(f"ERROR: Compile failed — {build_result.error}")
        sys.exit(2)

    print(f"Binary: {os.path.basename(build_result.binary)}")
    print()

    # ── Flash ──────────────────────────────────────────────────────────────────
    flasher = HybXFlasher(board_def, binary_path=build_result.binary,
                          verbose=False)
    with HybXTimer("flash", print_start=True):
        flash_result = flasher.flash()

    if not flash_result.success:
        print(f"ERROR: Flash failed — {flash_result.error}")
        sys.exit(2)

    print()
    print("Done.")


if __name__ == "__main__":
    with HybXTimer("build", print_start=True):
        main()
