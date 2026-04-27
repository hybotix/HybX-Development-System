#!/usr/bin/env python3

"""
migrate-v1.2.0.py
Hybrid RobotiX — HybX Development System

One-time migration from App Lab library storage to arduino-cli management.
Moves all libraries from ~/.arduino15/internal/ into arduino-cli's control
so that libs is the sole authority going forward.

THIS COMMAND IS DESTRUCTIVE. migrate run will permanently wipe
~/.arduino15/internal/. Always run migrate dryrun first.

Usage:
  migrate dryrun    - Scan libraries, verify all findable via arduino-cli,
                      show exactly what will happen. Touches nothing.
  migrate run       - Re-verify, then wipe and reinstall. Requires dryrun
                      to have been run with no unresolvable libraries, OR
                      explicit acknowledgement that some libraries will be lost.

Flags:
  --json            Machine-readable JSON output
  --confirm         Skip interactive confirmation prompts (for GUI)

Exit codes:
  0  success
  1  user error or unresolvable libraries found
  2  system error
"""

import os
import sys
sys.path.insert(0, os.path.dirname(os.path.realpath(__file__)))
sys.path.insert(0, os.path.expanduser("~/lib"))

import subprocess  # noqa: E402
import shutil  # noqa: E402
from datetime import datetime, timezone  # noqa: E402

from hybx_config import load_libraries, save_libraries  # noqa: E402
from libs_helpers import (  # noqa: E402
    cli_lib_list,
    cli_lib_install,
    cmd_sync_inner,
    ARDUINO_LIBS_DIR,
)

CONFIRMATION_PHRASE  = "I am ready to cut ties with AppLab"
APPLAB_INTERNAL_DIR  = os.path.expanduser("~/.arduino15/internal")


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

# ── arduino-cli search check ───────────────────────────────────────────────────


def check_findable(lib_name: str) -> bool:
    """
    Return True if arduino-cli can find lib_name in the Library Manager index.
    Uses search and checks for an exact name match in results.
    """
    result = subprocess.run(
        ["arduino-cli", "lib", "search", lib_name],
        capture_output=True,
        text=True,
    )
    for line in result.stdout.splitlines():
        if line.strip().startswith("Name:"):
            found = line.split("Name:", 1)[1].strip().strip('"')
            if found.lower() == lib_name.lower():
                return True
    return False

# ── Core logic ─────────────────────────────────────────────────────────────────


def scan_installed() -> list[dict]:
    """
    Return the list of libraries currently in APPLAB_INTERNAL_DIR.
    Each entry: {"name": ..., "version": ..., "description": ...}
    """
    return cli_lib_list()


def verify_libraries(libs: list[dict], json_mode: bool) -> tuple[list[str], list[str]]:
    """
    For each library, check whether arduino-cli can find it in the index.
    Returns (findable_names, unfindable_names).
    Prints progress when not in json_mode.
    """
    findable   = []
    unfindable = []

    for entry in libs:
        name = entry["name"]
        if not json_mode:
            print("  Checking: " + name + "...", end="", flush=True)
        ok = check_findable(name)
        if ok:
            findable.append(name)
            if not json_mode:
                print(" OK")
        else:
            unfindable.append(name)
            if not json_mode:
                print(" NOT FOUND in Library Manager")

    return findable, unfindable

# ── Commands ───────────────────────────────────────────────────────────────────


def cmd_dryrun(json_mode: bool):
    """
    Scan installed libraries, verify each is findable via arduino-cli,
    and report exactly what migrate run will do. Touches nothing.
    """
    if not json_mode:
        print("Scanning " + APPLAB_INTERNAL_DIR + "...")
        print()

    installed = scan_installed()

    if not installed:
        if json_mode:
            out_json({"ok": True, "status": "nothing_to_migrate", "libraries": []})
        else:
            print("No libraries found in " + APPLAB_INTERNAL_DIR)
            print("Nothing to migrate.")
        return

    if not json_mode:
        print("Found " + str(len(installed)) + " libraries:")
        for e in installed:
            print("  " + e["name"] + " (" + e["version"] + ")")
        print()
        print("Verifying each library is available in Arduino Library Manager...")
        print()

    findable, unfindable = verify_libraries(installed, json_mode)

    if json_mode:
        out_json({
            "ok":          True,
            "status":      "dryrun",
            "total":       len(installed),
            "findable":    findable,
            "unfindable":  unfindable,
            "will_wipe":   ARDUINO_LIBS_DIR,
            "will_install": findable,
            "will_lose":   unfindable,
        })
        return

    print()
    print("=" * 60)
    print("Dry run results:")
    print()
    print("  Will wipe:     " + ARDUINO_LIBS_DIR)
    print("  Will install:  " + str(len(findable)) + " libraries via arduino-cli")

    if unfindable:
        print("  CANNOT find:   " + str(len(unfindable)) + " libraries")
        print()
        print("Libraries NOT findable in Arduino Library Manager:")
        for n in unfindable:
            print("  " + n)
        print()
        print("These libraries will be LOST if you run migrate run.")
        print("Resolve these manually before proceeding, or acknowledge")
        print("they will not be reinstalled.")
    else:
        print()
        print("All libraries verified. Safe to run: migrate run")


def cmd_run(json_mode: bool, confirm_mode: bool):
    """
    Re-verify, then wipe ~/.arduino15/internal/ and reinstall everything
    via arduino-cli. Project assignments in libraries.json are preserved.
    """
    if not json_mode:
        print("Scanning " + APPLAB_INTERNAL_DIR + "...")
        print()

    installed = scan_installed()

    if not installed:
        if json_mode:
            out_json({"ok": True, "status": "nothing_to_migrate"})
        else:
            print("No libraries found in " + APPLAB_INTERNAL_DIR)
            print("Nothing to migrate.")
        return

    if not json_mode:
        print("Found " + str(len(installed)) + " libraries.")
        print()
        print("Re-verifying availability in Arduino Library Manager...")
        print()

    findable, unfindable = verify_libraries(installed, json_mode)

    # If any are unfindable, require explicit acknowledgement
    if unfindable and not confirm_mode and not json_mode:
        print()
        print("WARNING: The following libraries cannot be found in the")
        print("Arduino Library Manager and will NOT be reinstalled:")
        for n in unfindable:
            print("  " + n)
        print()
        if not confirm_prompt("Proceed anyway and lose these libraries"):
            print("Cancelled. Resolve unfindable libraries first.")
            print("Run: migrate dryrun   to see the full report.")
            sys.exit(1)
    elif unfindable and json_mode:
        # In JSON/GUI mode, unfindable libraries are reported but do not
        # block — the GUI is responsible for gating on this.
        pass

    # Final confirmation — phrase required, always
    if not json_mode:
        print()
        print("=" * 60)
        print("  WARNING: THIS ACTION IS DESTRUCTIVE AND IRREVERSIBLE")
        print("=" * 60)
        print()
        print("This will permanently wipe " + APPLAB_INTERNAL_DIR)
        print("and reinstall " + str(len(findable)) + " libraries via arduino-cli.")
        print()
        print("Hybrid RobotiX and the HybX Development System are NOT")
        print("responsible for any data loss or missing libraries that")
        print("result from running this command.")
        print()
        print("To proceed, type EXACTLY:")
        print()
        print("  " + CONFIRMATION_PHRASE)
        print()
        phrase = input("> ").strip()
        if phrase != CONFIRMATION_PHRASE:
            print()
            print("Confirmation phrase did not match. Aborted. Nothing was changed.")
            sys.exit(1)
    elif json_mode:
        try:
            phrase = input()
        except EOFError:
            phrase = ""
        if phrase != CONFIRMATION_PHRASE:
            out_json({"ok": False,
                      "error": "Confirmation phrase did not match. Aborted."})
            sys.exit(1)

    # ── Wipe ──────────────────────────────────────────────────────────────────
    if not json_mode:
        print()
        print("Wiping " + APPLAB_INTERNAL_DIR + "...")

    if os.path.isdir(APPLAB_INTERNAL_DIR):
        shutil.rmtree(APPLAB_INTERNAL_DIR)
    os.makedirs(APPLAB_INTERNAL_DIR, exist_ok=True)

    if not json_mode:
        print("Wiped.")
        print()

    # ── Reinstall ──────────────────────────────────────────────────────────────
    installed_ok  = []
    installed_err = []

    for name in findable:
        if not json_mode:
            print("Installing: " + name + "...", end="", flush=True)
        result = subprocess.run(
            ["arduino-cli", "lib", "install", name],
            capture_output=True,
            text=True,
        )
        if result.returncode == 0:
            installed_ok.append(name)
            if not json_mode:
                print(" OK")
        else:
            err = result.stderr.strip()
            installed_err.append({"name": name, "error": err})
            if not json_mode:
                print(" FAILED: " + err)

    # ── Sync registry ──────────────────────────────────────────────────────────
    if not json_mode:
        print()
        print("Syncing library registry...")

    cmd_sync_inner(json_mode=False)

    # ── Report ─────────────────────────────────────────────────────────────────
    if json_mode:
        out_json({
            "ok":             len(installed_err) == 0 and len(unfindable) == 0,
            "installed_ok":   installed_ok,
            "installed_err":  installed_err,
            "lost":           unfindable,
        })
    else:
        print()
        print("=" * 60)
        print("Migration complete.")
        print("  Installed OK:  " + str(len(installed_ok)))
        if installed_err:
            print("  Install failed: " + str(len(installed_err)))
            for e in installed_err:
                print("    " + e["name"] + ": " + e["error"])
        if unfindable:
            print("  Lost (not in Library Manager): " + str(len(unfindable)))
            for n in unfindable:
                print("    " + n)
        print()
        print("Run: libs list   to verify the registry.")

# ── Usage ──────────────────────────────────────────────────────────────────────


def usage():
    print("Usage:")
    print("  migrate dryrun    - Scan, verify, report. Touches nothing.")
    print("  migrate run       - Wipe App Lab store, reinstall via arduino-cli.")
    print()
    print("Always run migrate dryrun before migrate run.")
    print()
    print("Flags:")
    print("  --json      Machine-readable JSON output")
    print("  --confirm   Skip interactive confirmation prompts")

# ── Main ───────────────────────────────────────────────────────────────────────


def main():
    args, json_mode, confirm_mode = parse_args()

    if not json_mode:
        os.system("clear")
        print("=== migrate ===")
        print()

    if not args:
        usage()
        sys.exit(1)

    subcommand = args[0]

    if subcommand == "dryrun":
        cmd_dryrun(json_mode)
    elif subcommand == "run":
        cmd_run(json_mode, confirm_mode)
    else:
        out_error("Unknown subcommand: " + subcommand +
                  "  (use: migrate dryrun  or  migrate run)", json_mode, 1)


if __name__ == "__main__":
    main()
