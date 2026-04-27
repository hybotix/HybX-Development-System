#!/usr/bin/env python3

"""
build-v1.2.0.py
Hybrid RobotiX — HybX Development System

Compile and upload a sketch to the active board.
Library management is handled entirely by libs — this command
only verifies that all project libraries are installed before
compiling, then delegates the compile and upload to arduino-cli.

Usage:
  build <sketch_path>

Changes from v0.0.1:
  - Removed parse_libraries() and generate_sketch_yaml() — libs is King
  - Added libs check pre-flight before compile
  - sketch.yaml is now owned and written exclusively by libs
"""

import os
import sys
sys.path.insert(0, os.path.dirname(os.path.realpath(__file__)))
sys.path.insert(0, os.path.expanduser("~/lib"))

import subprocess  # noqa: E402

from hybx_config import get_active_board, load_libraries, load_config  # noqa: E402

FQBN = "arduino:zephyr:unoq"

# ── Pre-flight: verify libraries ───────────────────────────────────────────────


def check_libraries(project: str) -> bool:
    """
    Verify every library assigned to the project in libraries.json is
    actually present in the installed section. Returns True if all clear.
    Prints a clear error and returns False if any are missing.
    """
    libs         = load_libraries()
    project_libs = libs["projects"].get(project, [])

    if not project_libs:
        # No assignments recorded — warn but do not block
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
        print("Then: libs use " + project + " <n>   if not already assigned.")
        return False

    print("Libraries OK: " + str(len(project_libs)) + " assigned, all installed.")
    return True

# ── Compile ────────────────────────────────────────────────────────────────────


def compile_sketch(sketch_path: str) -> tuple[int, str]:
    print("Compiling " + sketch_path + "...")
    result = subprocess.run(
        ["arduino-cli", "compile", "--fqbn", FQBN, sketch_path, "-v"],
        capture_output=True,
        text=True,
    )
    print(result.stdout)
    if result.stderr:
        print(result.stderr)
    return result.returncode, result.stdout

# ── Upload ─────────────────────────────────────────────────────────────────────


def upload_sketch(sketch_path: str) -> int:
    print("Uploading " + sketch_path + "...")
    result = subprocess.run(
        ["arduino-cli", "upload", "--profile", "default",
         "--fqbn", FQBN, sketch_path],
        capture_output=False,
    )
    return result.returncode

# ── Main ───────────────────────────────────────────────────────────────────────


def main():
    print("=== build ===")

    board     = get_active_board()
    apps_path = board["apps_path"]

    # Resolve sketch path:
    # If given a full path — use it directly
    # If given a project name — resolve to <apps_path>/<project>/sketch/
    # If given nothing — use the active project
    if len(sys.argv) < 2:
        # No argument — use active project from config
        config       = load_config()
        active_board = config.get("active_board", "")
        project      = config.get("board_projects", {}).get(
                           active_board, {}).get("active")
        if not project:
            print("Usage: build <project_or_sketch_path>")
            print("No active project set. Use: project use <n>")
            sys.exit(1)
        sketch_path = os.path.join(apps_path, project, "sketch")
    else:
        arg = sys.argv[1]
        if os.path.isabs(arg) or arg.startswith("~") or arg.startswith("."):
            # Full or relative path — use as-is
            sketch_path = os.path.expanduser(arg)
        elif os.path.isdir(os.path.join(apps_path, arg, "sketch")):
            # Project name — resolve to sketch directory
            sketch_path = os.path.join(apps_path, arg, "sketch")
        elif os.path.isdir(os.path.join(apps_path, arg)):
            # Project name but no sketch subdir — use project dir directly
            sketch_path = os.path.join(apps_path, arg)
        else:
            # Try as-is
            sketch_path = arg

    # Derive project name from resolved sketch path
    parts   = os.path.normpath(sketch_path).split(os.sep)
    project = None
    for i, part in enumerate(parts):
        if part == "sketch" and i > 0:
            project = parts[i - 1]
            break
    if not project:
        project = parts[-1]

    print("Board:   " + board["name"] + " (" + board["host"] + ")")
    print("Project: " + project)
    print("Sketch:  " + sketch_path)
    print()

    # ── Pre-flight ─────────────────────────────────────────────────────────────
    if not check_libraries(project):
        sys.exit(1)

    print()

    # ── Compile ────────────────────────────────────────────────────────────────
    returncode, _ = compile_sketch(sketch_path)
    if returncode != 0:
        print("Compile failed. Aborting upload.")
        sys.exit(2)

    # ── Upload ─────────────────────────────────────────────────────────────────
    if upload_sketch(sketch_path) != 0:
        print("Upload failed.")
        sys.exit(2)

    print("Done.")


if __name__ == "__main__":
    main()