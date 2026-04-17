#!/usr/bin/env python3
"""
test-v0.0.2.py
Hybrid RobotiX — HybX Development System Test Suite

Runs a comprehensive test of all HybX commands and subcommands.

This test suite runs natively ON the UNO Q. The UNO Q is the target
environment — Docker, arduino-app-cli, arduino-cli, and all board
hardware are assumed to be present and available.

Tests are organized into three categories:

  READ-ONLY   — No state changes. Runs as part of default test run.
  SANDBOXED   — Creates and destroys temporary test fixtures.
                Run with --all flag.
  HARDWARE    — Uses Docker and arduino-app-cli with scd30 as a
                safe test fixture. Runs as part of default test run.

Only migrate is skipped — it is a one-time destructive operation
that is covered by proxy through libs and build tests.

Usage:
  python3 test-v0.0.2.py           — Run all tests (read-only + hardware)
  python3 test-v0.0.2.py --all     — Include sandboxed tests
  python3 test-v0.0.2.py --verbose — Show full command output

Run this on the UNO Q directly.
"""

import os
import sys
import subprocess
import json
import shutil
import time

# ── Config ─────────────────────────────────────────────────────────────────────

VERBOSE  = "--verbose" in sys.argv
RUN_ALL  = "--all"     in sys.argv

BIN_DIR     = os.path.expanduser("~/bin")
CONFIG_FILE = os.path.expanduser("~/.hybx/config.json")

# Safe test app — used for start/stop/restart/logs/clean/build tests.
# scd30 is a simple, well-tested app with no destructive side effects.
TEST_APP = "scd30"

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


def run_cmd(args: list, input_text: str = None, timeout: int = 60) -> tuple[int, str, str]:
    """
    Run a HybX command. Returns (returncode, stdout, stderr).
    Feeds input_text to stdin if provided (for YES/NO prompts).
    """
    cmd = [os.path.join(BIN_DIR, args[0])] + args[1:]
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            input=input_text,
            timeout=timeout,
        )
    except subprocess.TimeoutExpired:
        return 1, "", "TIMEOUT after " + str(timeout) + "s"

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
         input_text: str = None,
         timeout: int = 60):
    """Run a single test. Records pass/fail."""
    code, out, err = run_cmd(args, input_text=input_text, timeout=timeout)
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


def get_apps_path() -> str:
    config    = load_config()
    board     = config.get("boards", {}).get(config.get("active_board", ""), {})
    apps_path = os.path.expanduser(board.get("apps_path", ""))
    return apps_path


def get_test_app_path() -> str:
    return os.path.join(get_apps_path(), TEST_APP)


# ── Read-Only Tests ────────────────────────────────────────────────────────────


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

    test("libs check (no name — shows usage)",
         ["libs", "check"],
         expect_exit=1,
         expect_in=["usage"])

    test("libs check scd30 — all libraries installed",
         ["libs", "check", TEST_APP])


def test_update():
    header("update")

    test("update",
         ["update"],
         expect_in=["update"],
         timeout=120)


def test_setup():
    header("setup")

    # setup installs nano syntax highlighting — safe to re-run
    test("setup",
         ["setup"])


def test_list():
    header("list")

    # list calls arduino-app-cli app list — safe read-only
    test("list",
         ["list"])


# ── Hardware Tests ─────────────────────────────────────────────────────────────


def test_build():
    header("build")

    sketch_path = os.path.join(get_test_app_path(), "sketch")

    if not os.path.isdir(sketch_path):
        skip("build scd30 sketch", TEST_APP + " sketch not found at " + sketch_path)
        return

    test("build scd30 sketch",
         ["build", sketch_path],
         expect_in=["build"],
         timeout=300)


def test_app_lifecycle():
    header("start / stop / restart / logs / clean")

    app_path = get_test_app_path()

    if not os.path.isdir(app_path):
        skip("app lifecycle", TEST_APP + " not found at " + app_path)
        return

    # stop first in case anything is already running — ignore exit code
    run_cmd(["stop", TEST_APP])
    time.sleep(2)

    # start
    test("start scd30",
         ["start", TEST_APP],
         expect_in=["start"],
         timeout=120)

    time.sleep(5)

    # logs — should show output without error
    test("logs scd30",
         ["logs", TEST_APP],
         timeout=10)

    # stop
    test("stop scd30",
         ["stop", TEST_APP],
         expect_in=["stop"],
         timeout=30)

    time.sleep(2)

    # restart
    test("restart scd30",
         ["restart", TEST_APP],
         expect_in=["start"],
         timeout=120)

    time.sleep(5)

    # stop before clean
    run_cmd(["stop", TEST_APP])
    time.sleep(2)

    # clean
    test("clean scd30",
         ["clean", TEST_APP],
         expect_in=["clean"],
         timeout=120)


# ── Skipped Tests ──────────────────────────────────────────────────────────────


def test_skipped():
    header("Skipped")

    skip("migrate", "one-time destructive operation — covered by proxy through libs and build tests")


# ── Sandboxed Tests ────────────────────────────────────────────────────────────


def test_sandboxed_board():
    header("board (sandboxed)")

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
    header("project (sandboxed)")

    apps_path = get_apps_path()

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

    # Verify scaffold files exist
    for f in ["app.yaml", "sketch/sketch.ino", "sketch/sketch.yaml", "python/main.py"]:
        full = os.path.join(test_project_path, f)
        if os.path.exists(full):
            passed.append("project new — scaffold: " + f)
            print("  PASS  project new — scaffold: " + f)
        else:
            failed.append("project new — scaffold missing: " + f)
            print("  FAIL  project new — scaffold missing: " + f)

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

    # Verify directory still exists after cancel
    if os.path.isdir(test_project_path):
        passed.append("project remove cancelled — directory still exists")
        print("  PASS  project remove cancelled — directory still exists")
    else:
        failed.append("project remove cancelled — directory was removed!")
        print("  FAIL  project remove cancelled — directory was removed!")

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
        shutil.rmtree(test_project_path)


def test_sandboxed_libs():
    header("libs (sandboxed)")

    # Use a small, safe library for install/remove testing
    test_lib = "ArduinoJson"

    # Check if already installed — skip install/remove if so
    code, out, _ = run_cmd(["libs", "show", test_lib])
    already_installed = (code == 0)

    if already_installed:
        # Already installed — just test show
        test("libs show " + test_lib,
             ["libs", "show", test_lib],
             expect_in=[test_lib])
        skip("libs install/remove " + test_lib,
             "already installed — skipping to avoid removing a real library")
        return

    # Install
    test("libs install " + test_lib,
         ["libs", "install", test_lib],
         expect_in=["install"],
         timeout=60)

    # Verify it appears in list
    test("libs list — shows " + test_lib,
         ["libs", "list"],
         expect_in=[test_lib])

    # Show
    test("libs show " + test_lib,
         ["libs", "show", test_lib],
         expect_in=[test_lib])

    # Remove — feed NO first (cancel)
    test("libs remove " + test_lib + " — cancels on NO",
         ["libs", "remove", test_lib],
         expect_in=["cancelled"],
         input_text="NO\n")

    # Remove — feed YES (confirm)
    test("libs remove " + test_lib + " — confirms on YES",
         ["libs", "remove", test_lib],
         expect_in=["removed"],
         input_text="YES\n")

    # Verify gone from list
    test("libs list — " + test_lib + " no longer present",
         ["libs", "list"],
         expect_not_in=[test_lib])


# ── Main ───────────────────────────────────────────────────────────────────────


def main():
    print()
    print("Hybrid RobotiX — HybX Development System Test Suite")
    print("=====================================================")
    if RUN_ALL:
        print("Mode: ALL (read-only + hardware + sandboxed)")
    else:
        print("Mode: DEFAULT (read-only + hardware)")
    print()

    # Check all commands are available
    all_commands = ["board", "build", "clean", "libs", "list", "logs",
                    "project", "restart", "setup", "start", "stop", "update"]
    missing = [cmd for cmd in all_commands
               if not os.path.exists(os.path.join(BIN_DIR, cmd))]
    if missing:
        print("ERROR: Missing commands in ~/bin: " + ", ".join(missing))
        print("Run 'update' first to install all commands.")
        sys.exit(1)

    # ── Read-only tests — always run ──────────────────────────────────────────
    test_board()
    test_project()
    test_libs()
    test_update()
    test_setup()
    test_list()

    # ── Hardware tests ────────────────────────────────────────────────────────
    test_build()
    test_app_lifecycle()

    # ── Sandboxed tests — only with --all ─────────────────────────────────────
    if RUN_ALL:
        test_sandboxed_board()
        test_sandboxed_project()
        test_sandboxed_libs()

    # ── Skipped ───────────────────────────────────────────────────────────────
    test_skipped()

    # ── Summary ───────────────────────────────────────────────────────────────
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
