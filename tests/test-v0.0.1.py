#!/usr/bin/env python3
"""
test-v0.0.1.py
Hybrid RobotiX — HybX Development System Test Suite

Runs a comprehensive test of all HybX commands and subcommands.
Tests are organized into three categories:

  READ-ONLY   — Safe to run any time. No state changes.
  SANDBOXED   — Creates and destroys temporary test fixtures.
  SKIPPED     — Commands that require hardware or Docker (build, start, stop,
                restart, logs, list, clean, migrate, setup).

Usage:
  python3 test-v0.0.1.py              — Run all safe tests
  python3 test-v0.0.1.py --all        — Include sandboxed tests
  python3 test-v0.0.1.py --verbose    — Show full command output

Must be run on the active board (UNO Q or similar).
"""

import os
import sys
import subprocess
import json
import tempfile
import shutil

# ── Config ─────────────────────────────────────────────────────────────────────

VERBOSE     = "--verbose" in sys.argv
RUN_ALL     = "--all"     in sys.argv

BIN_DIR     = os.path.expanduser("~/bin")
CONFIG_FILE = os.path.expanduser("~/.hybx/config.json")

# ── Test Infrastructure ────────────────────────────────────────────────────────

passed  = []
failed  = []
skipped = []


def header(msg: str):
    print()
    print("=" * 60)
    print("  " + msg)
    print("=" * 60)
    print()


def run_cmd(args: list, input_text: str = None) -> tuple[int, str, str]:
    """
    Run a HybX command. Returns (returncode, stdout, stderr).
    Feeds input_text to stdin if provided (for YES/NO prompts).
    """
    cmd = [os.path.join(BIN_DIR, args[0])] + args[1:]
    result = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        input=input_text,
    )
    if VERBOSE:
        print("  $ " + " ".join(args))
        if result.stdout.strip():
            for line in result.stdout.strip().splitlines():
                print("    " + line)
        if result.stderr.strip():
            for line in result.stderr.strip().splitlines():
                print("    ERR: " + line)
    return result.returncode, result.stdout, result.stderr


def test(name: str, args: list,
         expect_exit: int = 0,
         expect_in: list = None,
         expect_not_in: list = None,
         input_text: str = None):
    """
    Run a single test. Records pass/fail.
    """
    code, out, err = run_cmd(args, input_text=input_text)
    combined = out + err
    reasons  = []

    if code != expect_exit:
        reasons.append("exit code " + str(code) + " (expected " + str(expect_exit) + ")")

    for phrase in (expect_in or []):
        if phrase.lower() not in combined.lower():
            reasons.append("missing: '" + phrase + "'")

    for phrase in (expect_not_in or []):
        if phrase.lower() in combined.lower():
            reasons.append("unexpected: '" + phrase + "'")

    if reasons:
        failed.append(name)
        print("  FAIL  " + name)
        for r in reasons:
            print("        → " + r)
        if not VERBOSE:
            for line in combined.strip().splitlines()[:5]:
                print("        " + line)
    else:
        passed.append(name)
        print("  PASS  " + name)


def skip(name: str, reason: str):
    skipped.append(name)
    print("  SKIP  " + name + "  (" + reason + ")")


def load_config() -> dict:
    with open(CONFIG_FILE) as f:
        return json.load(f)


# ── Tests ──────────────────────────────────────────────────────────────────────


def test_board():
    header("board")

    test("board (no args — shows usage)",
         ["board"],
         expect_exit=1,
         expect_in=["usage"])

    test("board list",
         ["board", "list"],
         expect_in=["boards"])

    test("board show",
         ["board", "show"],
         expect_in=["active board"])

    test("board show — has host",
         ["board", "show"],
         expect_in=["host"])

    test("board show — has apps_path",
         ["board", "show"],
         expect_in=["apps_path"])

    test("board show — has repo",
         ["board", "show"],
         expect_in=["repo"])

    test("board sync --dry-run",
         ["board", "sync", "--dry-run"],
         expect_in=["dry run"])

    test("board use (no name — shows usage)",
         ["board", "use"],
         expect_exit=1,
         expect_in=["usage"])

    test("board remove (no name — shows usage)",
         ["board", "remove"],
         expect_exit=1,
         expect_in=["usage"])

    test("board add (no name — shows usage)",
         ["board", "add"],
         expect_exit=1,
         expect_in=["usage"])


def test_project():
    header("project")

    test("project (no args — shows usage)",
         ["project"],
         expect_exit=1,
         expect_in=["usage"])

    test("project list",
         ["project", "list"],
         expect_in=["apps path"])

    test("project list --names",
         ["project", "list", "--names"])

    test("project show",
         ["project", "show"])

    test("project set (no name — shows usage)",
         ["project", "set"],
         expect_exit=1,
         expect_in=["usage"])

    test("project new (no args — shows usage)",
         ["project", "new"],
         expect_exit=1,
         expect_in=["usage"])

    test("project set nonexistent — fails cleanly",
         ["project", "set", "this-project-does-not-exist-xyz"],
         expect_exit=1,
         expect_in=["not found"])

    test("project remove (no name — shows usage)",
         ["project", "remove"],
         expect_exit=1,
         expect_in=["usage"])


def test_libs():
    header("libs")

    test("libs (no args — shows usage)",
         ["libs"],
         expect_exit=1,
         expect_in=["usage"])

    test("libs list",
         ["libs", "list"])

    test("libs search (no query — shows usage)",
         ["libs", "search"],
         expect_exit=1,
         expect_in=["usage"])

    test("libs search Adafruit",
         ["libs", "search", "Adafruit"])

    test("libs show (no name — shows usage)",
         ["libs", "show"],
         expect_exit=1,
         expect_in=["usage"])

    test("libs install (no name — shows usage)",
         ["libs", "install"],
         expect_exit=1,
         expect_in=["usage"])

    test("libs remove (no name — shows usage)",
         ["libs", "remove"],
         expect_exit=1,
         expect_in=["usage"])

    test("libs upgrade (no args — runs for all)",
         ["libs", "upgrade"])

    test("libs show nonexistent — fails cleanly",
         ["libs", "show", "this-library-does-not-exist-xyz"],
         expect_exit=1,
         expect_in=["not installed"])


def test_update():
    header("update")

    # update pulls repos and refreshes bin — safe to run
    test("update",
         ["update"],
         expect_in=["update"])


def test_skipped():
    header("Skipped (require hardware or Docker)")

    skip("build",   "requires Arduino board connected via SSH")
    skip("start",   "requires Docker and an app")
    skip("stop",    "requires a running app")
    skip("restart", "requires Docker and an app")
    skip("logs",    "requires a running app")
    skip("list",    "requires arduino-app-cli on board")
    skip("clean",   "destructive — nukes Docker")
    skip("migrate", "one-time migration — destructive if re-run")
    skip("setup",   "one-time setup — safe but no-op to test")


def test_sandboxed_board():
    """
    Sandboxed board tests — adds and removes a temporary test board.
    Only runs with --all flag.
    """
    header("board (sandboxed)")

    config_before = load_config()
    test_board_name = "hybx-test-board-xyz"

    # board add — feed NO to the confirmation prompt
    test("board add test-board — cancels on NO",
         ["board", "add", test_board_name],
         expect_in=["cancelled", "nothing was changed"],
         input_text="NO\n")

    # Verify board was NOT added
    config_after = load_config()
    if test_board_name not in config_after.get("boards", {}):
        passed.append("board add cancelled — config unchanged")
        print("  PASS  board add cancelled — config unchanged")
    else:
        failed.append("board add cancelled — config unchanged")
        print("  FAIL  board add cancelled — config was modified!")

    # board use nonexistent — should fail cleanly
    test("board use nonexistent — fails cleanly",
         ["board", "use", test_board_name],
         expect_exit=1,
         expect_in=["not found"])

    # board remove nonexistent — should fail cleanly
    test("board remove nonexistent — fails cleanly",
         ["board", "remove", test_board_name],
         expect_exit=1,
         expect_in=["not found"])


def test_sandboxed_project():
    """
    Sandboxed project tests — creates and removes a temporary test project.
    Only runs with --all flag.
    """
    header("project (sandboxed)")

    config   = load_config()
    board    = config.get("boards", {}).get(config.get("active_board", ""), {})
    apps_path = os.path.expanduser(board.get("apps_path", ""))

    if not apps_path or not os.path.isdir(apps_path):
        skip("project new/remove sandboxed", "no active board apps_path found")
        return

    test_project_name = "hybx-test-project-xyz"
    test_project_path = os.path.join(apps_path, test_project_name)

    # Ensure clean state
    if os.path.isdir(test_project_path):
        shutil.rmtree(test_project_path)

    # project new arduino
    test("project new arduino hybx-test-project-xyz",
         ["project", "new", "arduino", test_project_name],
         expect_in=["created"])

    # Verify directory was created
    if os.path.isdir(test_project_path):
        passed.append("project new — directory created")
        print("  PASS  project new — directory created")
    else:
        failed.append("project new — directory not created")
        print("  FAIL  project new — directory not created")

    # project set
    test("project set hybx-test-project-xyz",
         ["project", "set", test_project_name],
         expect_in=["active project set to"])

    # project show — should show our test project
    test("project show — shows test project",
         ["project", "show"],
         expect_in=[test_project_name])

    # project remove — feed NO first (cancel)
    test("project remove — cancels on NO",
         ["project", "remove", test_project_name],
         expect_in=["cancelled"],
         input_text="NO\n")

    # project remove — feed YES (confirm)
    test("project remove — confirms on YES",
         ["project", "remove", test_project_name],
         expect_in=["removed"],
         input_text="YES\n")

    # Verify directory was removed
    if not os.path.isdir(test_project_path):
        passed.append("project remove — directory removed")
        print("  PASS  project remove — directory removed")
    else:
        failed.append("project remove — directory still exists")
        print("  FAIL  project remove — directory still exists")
        # Clean up manually
        shutil.rmtree(test_project_path)


# ── Main ───────────────────────────────────────────────────────────────────────


def main():
    print()
    print("Hybrid RobotiX — HybX Development System Test Suite")
    print("=====================================================")
    print("Mode: " + ("ALL (including sandboxed)" if RUN_ALL else "Safe only"))
    print()

    # Check commands are available
    missing = []
    for cmd in ["board", "project", "libs", "update"]:
        if not os.path.exists(os.path.join(BIN_DIR, cmd)):
            missing.append(cmd)
    if missing:
        print("ERROR: Missing commands in ~/bin: " + ", ".join(missing))
        print("Run 'update' first to install all commands.")
        sys.exit(1)

    # Run tests
    test_board()
    test_project()
    test_libs()
    test_update()

    if RUN_ALL:
        test_sandboxed_board()
        test_sandboxed_project()

    test_skipped()

    # ── Summary ────────────────────────────────────────────────────────────────
    print()
    print("=" * 60)
    print("  RESULTS")
    print("=" * 60)
    print()
    print("  Passed:  " + str(len(passed)))
    print("  Failed:  " + str(len(failed)))
    print("  Skipped: " + str(len(skipped)))
    print()

    if failed:
        print("  Failed tests:")
        for f in failed:
            print("    ✗ " + f)
        print()

    if len(failed) == 0:
        print("  All tests passed! 🎉")
    else:
        print("  " + str(len(failed)) + " test(s) failed.")

    print()
    sys.exit(0 if not failed else 1)


if __name__ == "__main__":
    main()
