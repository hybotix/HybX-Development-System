#!/usr/bin/env python3
"""
finalize-v0.0.1.py
Hybrid RobotiX — HybX Development System

Permanently severs all ties with App Lab. Removes the migrate command
and destroys the App Lab library store. This action is IRREVERSIBLE.

This command exists as a deliberate, ceremonial step. It should only
be run after:
  1. migrate run has been completed successfully
  2. libs list confirms all expected libraries are present
  3. All projects have been tested and verified working

Hybrid RobotiX and the HybX Development System are NOT responsible
for any data loss, broken sketches, or missing libraries that result
from running this command. You have been warned.

Usage:
  FINALIZE dryrun    - Show exactly what will be removed. Touches nothing.
  FINALIZE run       - Permanently remove App Lab. IRREVERSIBLE.

Flags:
  --json             Machine-readable JSON output
  --confirm          Skip interactive prompts (GUI only — confirmation
                     phrase is ALWAYS required regardless of this flag)

Exit codes:
  0  success
  1  user error, not ready, or cancelled
  2  system error
"""

import os
import sys
import shutil

sys.path.insert(0, os.path.dirname(os.path.realpath(__file__)))

from hybx_config import load_libraries, LIBRARIES_FILE  # noqa: E402
from libs_helpers import ARDUINO_LIBS_DIR               # noqa: E402

CONFIRMATION_PHRASE = "I am ready to cut ties with AppLab"

APPLAB_INTERNAL_DIR = os.path.expanduser("~/.arduino15/internal")

# Migrate files to remove — all versions
MIGRATE_SCRIPT_PATTERN = "migrate-v"
MIGRATE_SYMLINK        = "migrate"


# ── Argument parsing ───────────────────────────────────────────────────────────

def parse_args() -> tuple[list[str], bool, bool]:
    args         = sys.argv[1:]
    json_mode    = "--json" in args
    confirm_mode = "--confirm" in args
    positionals  = [a for a in args if not a.startswith("--")]
    return positionals, json_mode, confirm_mode


# ── Output helpers ─────────────────────────────────────────────────────────────

def out_json(data: dict):
    import json
    print(json.dumps(data, indent=2))


def out_error(msg: str, json_mode: bool, code: int = 1):
    if json_mode:
        out_json({"ok": False, "error": msg})
    else:
        print("ERROR: " + msg)
    sys.exit(code)


# ── Readiness check ────────────────────────────────────────────────────────────

def check_ready(json_mode: bool) -> tuple[bool, list[str]]:
    """
    Verify the system is ready for finalization.
    Returns (ready, list_of_problems).
    """
    problems = []

    # Check libraries.json exists and has entries
    if not os.path.exists(LIBRARIES_FILE):
        problems.append(
            "libraries.json does not exist — run 'migrate run' first"
        )
    else:
        libs = load_libraries()
        if not libs["installed"]:
            problems.append(
                "No libraries registered in libraries.json — "
                "run 'migrate run' first"
            )

    # Check App Lab internal dir exists (something to actually remove)
    if not os.path.isdir(APPLAB_INTERNAL_DIR):
        problems.append(
            APPLAB_INTERNAL_DIR + " does not exist — "
            "nothing to remove, may already be finalized"
        )

    return len(problems) == 0, problems


# ── Impact summary ─────────────────────────────────────────────────────────────

def build_impact(bin_dir: str) -> dict:
    """
    Build the full list of what FINALIZE run will remove.
    """
    migrate_files   = []
    migrate_symlink = None

    if os.path.isdir(bin_dir):
        for entry in os.scandir(bin_dir):
            if entry.name.startswith(MIGRATE_SCRIPT_PATTERN):
                migrate_files.append(entry.path)
            if entry.name == MIGRATE_SYMLINK:
                migrate_symlink = entry.path

    applab_size = 0
    applab_count = 0
    if os.path.isdir(APPLAB_INTERNAL_DIR):
        for dirpath, dirnames, filenames in os.walk(APPLAB_INTERNAL_DIR):
            for f in filenames:
                try:
                    applab_size += os.path.getsize(
                        os.path.join(dirpath, f)
                    )
                    applab_count += 1
                except OSError:
                    pass

    return {
        "migrate_symlink":  migrate_symlink,
        "migrate_files":    sorted(migrate_files),
        "applab_dir":       APPLAB_INTERNAL_DIR,
        "applab_files":     applab_count,
        "applab_size_mb":   round(applab_size / 1024 / 1024, 2),
    }


# ── Commands ───────────────────────────────────────────────────────────────────

def cmd_dryrun(json_mode: bool):
    """
    Show exactly what FINALIZE run will do. Touches nothing.
    """
    bin_dir = os.path.expanduser("~/bin")

    ready, problems = check_ready(json_mode)
    impact          = build_impact(bin_dir)

    if json_mode:
        out_json({
            "ok":      True,
            "status":  "dryrun",
            "ready":   ready,
            "problems": problems,
            "impact":  impact,
        })
        return

    print("=" * 60)
    print("FINALIZE dry run — nothing will be changed")
    print("=" * 60)
    print()

    if not ready:
        print("NOT READY — the following issues must be resolved first:")
        print()
        for p in problems:
            print("  ! " + p)
        print()
        print("Resolve these before running: FINALIZE run")
        return

    print("Readiness check: PASSED")
    print()
    print("The following will be PERMANENTLY removed:")
    print()

    if impact["migrate_symlink"]:
        print("  Symlink:  " + impact["migrate_symlink"])
    for f in impact["migrate_files"]:
        print("  File:     " + f)

    print()
    print("  Directory: " + impact["applab_dir"])
    print("    Files:   " + str(impact["applab_files"]))
    print("    Size:    " + str(impact["applab_size_mb"]) + " MB")
    print()
    print("This action is PERMANENT and IRREVERSIBLE.")
    print()
    print("If everything looks correct, run: FINALIZE run")


def cmd_run(json_mode: bool):
    """
    Permanently remove App Lab and the migrate command.
    Requires typing the confirmation phrase exactly.
    IRREVERSIBLE.
    """
    bin_dir = os.path.expanduser("~/bin")

    # ── Readiness check ────────────────────────────────────────────────────────
    ready, problems = check_ready(json_mode)

    if not ready:
        if json_mode:
            out_json({
                "ok":      False,
                "error":   "System is not ready for finalization.",
                "problems": problems,
            })
        else:
            print("ERROR: System is not ready for finalization.")
            print()
            for p in problems:
                print("  ! " + p)
            print()
            print("Resolve these issues then run: FINALIZE run")
        sys.exit(1)

    impact = build_impact(bin_dir)

    # ── Warning display ────────────────────────────────────────────────────────
    if not json_mode:
        print("=" * 60)
        print("  WARNING: THIS ACTION IS PERMANENT AND IRREVERSIBLE")
        print("=" * 60)
        print()
        print("Hybrid RobotiX and the HybX Development System are NOT")
        print("responsible for any data loss, broken sketches, or missing")
        print("libraries that result from running this command.")
        print()
        print("You are certifying that:")
        print("  - migrate run has been completed successfully")
        print("  - libs list shows all expected libraries")
        print("  - All projects have been tested and are working")
        print("  - You understand that App Lab library storage will be")
        print("    permanently destroyed and cannot be recovered")
        print()
        print("The following will be PERMANENTLY removed:")
        print()
        if impact["migrate_symlink"]:
            print("  Symlink:   " + impact["migrate_symlink"])
        for f in impact["migrate_files"]:
            print("  File:      " + f)
        print()
        print("  Directory: " + impact["applab_dir"])
        print("    Files:   " + str(impact["applab_files"]))
        print("    Size:    " + str(impact["applab_size_mb"]) + " MB")
        print()
        print("=" * 60)
        print()
        print("To proceed, type EXACTLY:")
        print()
        print("  " + CONFIRMATION_PHRASE)
        print()

    # ── Confirmation phrase — ALWAYS required, even with --confirm ─────────────
    if json_mode:
        # In JSON/GUI mode the GUI must collect and pass the phrase
        # via stdin. Read one line.
        try:
            phrase = input()
        except EOFError:
            phrase = ""
    else:
        phrase = input("> ").strip()

    if phrase != CONFIRMATION_PHRASE:
        if json_mode:
            out_json({
                "ok":    False,
                "error": "Confirmation phrase did not match. Aborted.",
            })
        else:
            print()
            print("Confirmation phrase did not match.")
            print("Aborted. Nothing was changed.")
        sys.exit(1)

    # ── Execute ────────────────────────────────────────────────────────────────
    removed  = []
    errors   = []

    # Remove migrate symlink
    if impact["migrate_symlink"]:
        try:
            os.remove(impact["migrate_symlink"])
            removed.append(impact["migrate_symlink"])
            if not json_mode:
                print("Removed: " + impact["migrate_symlink"])
        except OSError as e:
            errors.append(str(e))

    # Remove migrate versioned files
    for f in impact["migrate_files"]:
        try:
            os.remove(f)
            removed.append(f)
            if not json_mode:
                print("Removed: " + f)
        except OSError as e:
            errors.append(str(e))

    # Wipe App Lab internal directory
    if os.path.isdir(APPLAB_INTERNAL_DIR):
        try:
            shutil.rmtree(APPLAB_INTERNAL_DIR)
            removed.append(APPLAB_INTERNAL_DIR)
            if not json_mode:
                print("Removed: " + APPLAB_INTERNAL_DIR)
        except OSError as e:
            errors.append(str(e))

    # ── Report ─────────────────────────────────────────────────────────────────
    if json_mode:
        out_json({
            "ok":      len(errors) == 0,
            "removed": removed,
            "errors":  errors,
        })
    else:
        print()
        print("=" * 60)
        if errors:
            print("Finalization completed with errors:")
            for e in errors:
                print("  ! " + e)
        else:
            print("Finalization complete.")
            print()
            print("App Lab has been permanently removed.")
            print("The migrate command no longer exists.")
            print("HybX is now the sole authority over your libraries.")
            print()
            print("Welcome to the other side.")


# ── Usage ──────────────────────────────────────────────────────────────────────

def usage():
    print("Usage:")
    print("  FINALIZE dryrun    - Show what will be removed. Touches nothing.")
    print("  FINALIZE run       - Permanently remove App Lab. IRREVERSIBLE.")
    print()
    print("Always run FINALIZE dryrun before FINALIZE run.")
    print()
    print("Flags:")
    print("  --json      Machine-readable JSON output")
    print("  --confirm   Skip non-critical prompts (confirmation phrase")
    print("              is ALWAYS required regardless of this flag)")


# ── Main ───────────────────────────────────────────────────────────────────────

def main():
    args, json_mode, confirm_mode = parse_args()

    if not json_mode:
        os.system("clear")
        print("=== FINALIZE ===")
        print()

    if not args:
        usage()
        sys.exit(1)

    subcommand = args[0]

    if subcommand == "dryrun":
        cmd_dryrun(json_mode)
    elif subcommand == "run":
        cmd_run(json_mode)
    else:
        out_error(
            "Unknown subcommand: " + subcommand +
            "  (use: FINALIZE dryrun  or  FINALIZE run)",
            json_mode, 1
        )


if __name__ == "__main__":
    main()
