#!/usr/bin/env python3
"""
hybx-test-v1.1.0.py
Hybrid RobotiX — HybX Development System Test Command

Runs a comprehensive test of all HybX commands and subcommands.
Designed to run natively ON the Arduino UNO Q. Docker, arduino-app-cli,
arduino-cli, and all board hardware are assumed to be present.

All output is written to both the terminal and ~/hybx-test.log.
The log file is deleted and recreated on every run.
A lock file ~/hybx-test.lock prevents concurrent runs.

Usage:
  test              — Run all tests (read-only + hardware)
  test --all        — Include sandboxed tests
  test --verbose    — Show full command output

Only migrate is skipped — one-time destructive operation covered
by proxy through libs and build tests.
"""

import os
import sys
import subprocess
import json
import shutil
import time
import signal

# ── Config ─────────────────────────────────────────────────────────────────────

VERBOSE  = "--verbose" in sys.argv
RUN_ALL  = "--all"     in sys.argv

BIN_DIR   = os.path.expanduser("~/bin")
LIB_DIR   = os.path.expanduser("~/lib")
LOG_FILE  = os.path.expanduser("~/hybx-test.log")
LOCK_FILE = os.path.expanduser("~/hybx-test.lock")

CONFIG_FILE = os.path.expanduser("~/.hybx/config.json")
LAST_APP_FILE = os.path.expanduser("~/.hybx/last_app")

# Safe test app — used for start/stop/restart/logs/clean/build tests.
TEST_APP = "scd30"

# ── Logging ────────────────────────────────────────────────────────────────────

_log_file = None


def log_open():
    global _log_file
    if os.path.exists(LOG_FILE):
        os.remove(LOG_FILE)
    _log_file = open(LOG_FILE, "w")


def log_close():
    global _log_file
    if _log_file:
        _log_file.close()
        _log_file = None


def log(msg: str = ""):
    """Print to terminal and write to log file."""
    print(msg)
    if _log_file:
        _log_file.write(msg + "\n")
        _log_file.flush()


# ── Lock file ──────────────────────────────────────────────────────────────────

def acquire_lock():
    """
    Acquire the test lock file. Exits if another instance is already running.
    Uses PID-based stale lock detection.
    """
    if os.path.exists(LOCK_FILE):
        with open(LOCK_FILE, "r") as f:
            try:
                pid = int(f.read().strip())
            except ValueError:
                pid = None

        # Check if the PID is still running
        if pid:
            try:
                os.kill(pid, 0)  # Signal 0 — just checks if process exists
                print("ERROR: test is already running (PID " + str(pid) + ")")
                print("If this is wrong, delete ~/hybx-test.lock and try again.")
                sys.exit(1)
            except OSError:
                # Stale lock — process no longer running
                print("Removing stale lock file (PID " + str(pid) + " no longer running)")
                os.remove(LOCK_FILE)

    with open(LOCK_FILE, "w") as f:
        f.write(str(os.getpid()))


def release_lock():
    if os.path.exists(LOCK_FILE):
        os.remove(LOCK_FILE)


# ── State preservation ─────────────────────────────────────────────────────────

def save_state() -> dict:
    """Save active project and last app before sandboxed tests."""
    state = {"active_project": None, "last_app": None}
    try:
        with open(CONFIG_FILE) as f:
            config = json.load(f)
        active_board = config.get("active_board", "")
        state["active_project"] = config.get("board_projects", {}).get(
            active_board, {}).get("active")
    except Exception:
        pass
    try:
        with open(LAST_APP_FILE) as f:
            state["last_app"] = f.read().strip()
    except Exception:
        pass
    return state


def restore_state(state: dict):
    """Restore active project and last app after sandboxed tests."""
    try:
        with open(CONFIG_FILE) as f:
            config = json.load(f)
        active_board = config.get("active_board", "")
        if state["active_project"]:
            config.setdefault("board_projects", {}).setdefault(
                active_board, {})["active"] = state["active_project"]
        else:
            config.setdefault("board_projects", {}).setdefault(
                active_board, {}).pop("active", None)
        with open(CONFIG_FILE, "w") as f:
            json.dump(config, f, indent=2)
    except Exception:
        pass
    try:
        if state["last_app"]:
            with open(LAST_APP_FILE, "w") as f:
                f.write(state["last_app"])
    except Exception:
        pass


# ── Test Infrastructure ────────────────────────────────────────────────────────

passed  = []
failed  = []
skipped = []


def header(msg: str):
    log()
    log("=" * 60)
    log("  " + msg)
    log("=" * 60)
    log()


def run_cmd(args: list, input_text: str = None,
            timeout: int = 60) -> tuple[int, str, str]:
    """Run a HybX command. Returns (returncode, stdout, stderr)."""
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
        log("  $ " + " ".join(args))
        if result.stdout.strip():
            for line in result.stdout.strip().splitlines():
                log("    " + line)
        if result.stderr.strip():
            for line in result.stderr.strip().splitlines():
                log("    ERR: " + line)
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
        log("  FAIL  " + name)
        for r in reasons:
            log("        → " + r)
        if not VERBOSE:
            for line in combined.strip().splitlines()[:5]:
                log("        " + line)
    else:
        passed.append(name)
        log("  PASS  " + name)


def skip(name: str, reason: str):
    skipped.append(name)
    log("  SKIP  " + name + "  (" + reason + ")")


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

    test("board use nonexistent — fails cleanly",
         ["board", "use", "this-board-does-not-exist-xyz"],
         expect_exit=1,
         expect_in=["not found"])

    test("board remove nonexistent — fails cleanly",
         ["board", "remove", "this-board-does-not-exist-xyz"],
         expect_exit=1,
         expect_in=["not found"])


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

    test("project use (no name — shows usage)",
         ["project", "use"],
         expect_exit=1,
         expect_in=["usage"])

    test("project new (no args — shows usage)",
         ["project", "new"],
         expect_exit=1,
         expect_in=["usage"])

    test("project use nonexistent — fails cleanly",
         ["project", "use", "this-project-does-not-exist-xyz"],
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


def test_setup():
    header("setup")
    test("setup",
         ["setup"])


def test_list():
    header("list")
    test("list",
         ["list"])


def test_update():
    header("update")
    test("update",
         ["update"],
         expect_in=["update"],
         timeout=120)


# ── lib/ Deployment Tests ──────────────────────────────────────────────────────


def test_lib_deployment():
    header("lib/ deployment")

    for module in ["hybx_config.py", "libs_helpers.py"]:
        path = os.path.join(LIB_DIR, module)
        if os.path.isfile(path):
            passed.append("~/lib/" + module + " deployed")
            log("  PASS  ~/lib/" + module + " deployed")
        else:
            failed.append("~/lib/" + module + " deployed")
            log("  FAIL  ~/lib/" + module + " not found in ~/lib/")

    # Verify old shared modules are gone from ~/bin/
    for module in ["hybx_config.py", "libs_helpers.py"]:
        path = os.path.join(BIN_DIR, module)
        if not os.path.isfile(path):
            passed.append("~/bin/" + module + " removed")
            log("  PASS  ~/bin/" + module + " correctly removed")
        else:
            failed.append("~/bin/" + module + " still in ~/bin/")
            log("  FAIL  ~/bin/" + module + " should not be in ~/bin/")

    # Verify retired commands are gone from ~/bin/
    for cmd in ["cache", "boardsync"]:
        path = os.path.join(BIN_DIR, cmd)
        if not os.path.exists(path):
            passed.append("retired command '" + cmd + "' removed")
            log("  PASS  retired command '" + cmd + "' correctly removed from ~/bin/")
        else:
            failed.append("retired command '" + cmd + "' still in ~/bin/")
            log("  FAIL  retired command '" + cmd + "' should not be in ~/bin/")


# ── Hardware Tests ─────────────────────────────────────────────────────────────


def test_build():
    header("build")

    app_path    = get_test_app_path()
    sketch_path = os.path.join(app_path, "sketch")

    if not os.path.isdir(app_path):
        skip("build tests", TEST_APP + " not found at " + app_path)
        return

    # Test 1 — full sketch path
    test("build with full sketch path",
         ["build", sketch_path],
         expect_in=["build"],
         timeout=300)

    # Test 2 — project name only
    test("build with project name",
         ["build", TEST_APP],
         expect_in=["build"],
         timeout=300)

    # Test 3 — no args (uses active project)
    # First set scd30 as active project
    run_cmd(["project", "use", TEST_APP])
    test("build with no args — uses active project",
         ["build"],
         expect_in=["build"],
         timeout=300)


def test_app_lifecycle():
    header("start / stop / restart / logs / clean")

    app_path = get_test_app_path()

    if not os.path.isdir(app_path):
        skip("app lifecycle", TEST_APP + " not found at " + app_path)
        return

    # Stop anything already running — ignore exit code
    run_cmd(["stop", TEST_APP])
    time.sleep(3)

    # ── start with app name ────────────────────────────────────────────────────
    test("start with app name",
         ["start", TEST_APP],
         expect_in=["start"],
         timeout=120)
    time.sleep(5)

    # ── logs with app name ─────────────────────────────────────────────────────
    test("logs with app name",
         ["logs", TEST_APP],
         timeout=10)

    # ── stop with app name ─────────────────────────────────────────────────────
    test("stop with app name",
         ["stop", TEST_APP],
         expect_in=["stop"],
         timeout=30)
    time.sleep(3)

    # ── start with no args — uses last app ────────────────────────────────────
    test("start with no args — uses last app",
         ["start"],
         expect_in=["start"],
         timeout=120)
    time.sleep(5)

    # ── logs with no args — uses last app ─────────────────────────────────────
    test("logs with no args — uses last app",
         ["logs"],
         timeout=10)

    # ── stop with no args — uses last app ─────────────────────────────────────
    test("stop with no args — uses last app",
         ["stop"],
         expect_in=["stop"],
         timeout=30)
    time.sleep(3)

    # ── restart ────────────────────────────────────────────────────────────────
    test("restart with app name",
         ["restart", TEST_APP],
         expect_in=["start"],
         timeout=120)
    time.sleep(5)

    # ── restart with no args ───────────────────────────────────────────────────
    test("restart with no args — uses last app",
         ["restart"],
         expect_in=["start"],
         timeout=120)
    time.sleep(5)

    # Stop before clean
    run_cmd(["stop", TEST_APP])
    time.sleep(3)

    # ── clean ──────────────────────────────────────────────────────────────────
    test("clean with app name",
         ["clean", TEST_APP],
         expect_in=["clean"],
         timeout=120)


# ── Skipped Tests ──────────────────────────────────────────────────────────────


def test_skipped():
    header("Skipped")
    skip("migrate",
         "one-time destructive operation — covered by proxy through libs and build tests")


# ── Sandboxed Tests ────────────────────────────────────────────────────────────


def test_sandboxed_board():
    header("board (sandboxed)")

    test_board_name = "hybx-test-board-xyz"

    test("board add — cancels on NO",
         ["board", "add", test_board_name],
         expect_in=["cancelled", "nothing was changed"],
         input_text="NO\n")

    config_after = load_config()
    if test_board_name not in config_after.get("boards", {}):
        passed.append("board add cancelled — config unchanged")
        log("  PASS  board add cancelled — config unchanged")
    else:
        failed.append("board add cancelled — config unchanged")
        log("  FAIL  board add cancelled — config was modified!")

    test("board use nonexistent — fails cleanly",
         ["board", "use", test_board_name],
         expect_exit=1,
         expect_in=["not found"])

    test("board remove nonexistent — fails cleanly",
         ["board", "remove", test_board_name],
         expect_exit=1,
         expect_in=["not found"])


def test_sandboxed_project():
    header("project (sandboxed)")

    apps_path = get_apps_path()

    if not apps_path or not os.path.isdir(apps_path):
        skip("project sandboxed", "no active board apps_path found")
        return

    test_project_name = "hybx-test-project-xyz"
    test_project_path = os.path.join(apps_path, test_project_name)

    # Clean state
    if os.path.isdir(test_project_path):
        shutil.rmtree(test_project_path)

    # project new arduino
    test("project new arduino hybx-test-project-xyz",
         ["project", "new", "arduino", test_project_name],
         expect_in=["created"])

    if os.path.isdir(test_project_path):
        passed.append("project new — directory created")
        log("  PASS  project new — directory created")
    else:
        failed.append("project new — directory not created")
        log("  FAIL  project new — directory not created")

    # Verify scaffold files
    for f in ["app.yaml", "sketch/sketch.ino", "sketch/sketch.yaml",
              "python/main.py", "python/requirements.txt"]:
        full = os.path.join(test_project_path, f)
        if os.path.exists(full):
            passed.append("scaffold: " + f)
            log("  PASS  scaffold: " + f)
        else:
            failed.append("scaffold missing: " + f)
            log("  FAIL  scaffold missing: " + f)

    # project use
    test("project use hybx-test-project-xyz",
         ["project", "use", test_project_name],
         expect_in=["active project set to"])

    # project show
    test("project show — shows test project",
         ["project", "show"],
         expect_in=[test_project_name])

    # project remove — cancel
    test("project remove — cancels on NO",
         ["project", "remove", test_project_name],
         expect_in=["cancelled"],
         input_text="NO\n")

    if os.path.isdir(test_project_path):
        passed.append("project remove cancelled — directory still exists")
        log("  PASS  project remove cancelled — directory still exists")
    else:
        failed.append("project remove cancelled — directory was removed!")
        log("  FAIL  project remove cancelled — directory was removed!")

    # project remove — confirm
    test("project remove — confirms on YES",
         ["project", "remove", test_project_name],
         expect_in=["removed"],
         input_text="YES\n")

    if not os.path.isdir(test_project_path):
        passed.append("project remove — directory removed")
        log("  PASS  project remove — directory removed")
    else:
        failed.append("project remove — directory still exists")
        log("  FAIL  project remove — directory still exists")
        shutil.rmtree(test_project_path)


def test_sandboxed_libs():
    header("libs (sandboxed)")

    test_lib = "ArduinoJson"
    code, out, _ = run_cmd(["libs", "show", test_lib])
    already_installed = (code == 0)

    if already_installed:
        test("libs show " + test_lib,
             ["libs", "show", test_lib],
             expect_in=[test_lib])
        skip("libs install/remove " + test_lib,
             "already installed — skipping to avoid removing a real library")
        return

    test("libs install " + test_lib,
         ["libs", "install", test_lib],
         expect_in=["install"],
         timeout=60)

    test("libs list — shows " + test_lib,
         ["libs", "list"],
         expect_in=[test_lib])

    test("libs show " + test_lib,
         ["libs", "show", test_lib],
         expect_in=[test_lib])

    test("libs remove " + test_lib + " — cancels on NO",
         ["libs", "remove", test_lib],
         expect_in=["cancelled"],
         input_text="NO\n")

    test("libs remove " + test_lib + " — confirms on YES",
         ["libs", "remove", test_lib],
         expect_in=["removed"],
         input_text="YES\n")

    test("libs list — " + test_lib + " no longer present",
         ["libs", "list"],
         expect_not_in=[test_lib])


# ── Main ───────────────────────────────────────────────────────────────────────


def main():
    acquire_lock()
    log_open()

    try:
        log()
        log("Hybrid RobotiX — HybX Development System Test Suite")
        log("=====================================================")
        if RUN_ALL:
            log("Mode: ALL (read-only + hardware + sandboxed)")
        else:
            log("Mode: DEFAULT (read-only + hardware)")
        log("Log:  " + LOG_FILE)
        log()

        # Check all commands are available
        all_commands = ["board", "build", "clean", "libs", "list", "logs",
                        "project", "restart", "setup", "start", "stop",
                        "hybx-test", "update"]
        missing = [cmd for cmd in all_commands
                   if not os.path.exists(os.path.join(BIN_DIR, cmd))]
        if missing:
            log("ERROR: Missing commands in ~/bin: " + ", ".join(missing))
            log("Run 'update' first to install all commands.")
            sys.exit(1)

        # ── Read-only tests ────────────────────────────────────────────────────
        test_board()
        test_project()
        test_libs()
        test_setup()
        test_list()
        test_update()
        test_lib_deployment()

        # ── Hardware tests ─────────────────────────────────────────────────────
        test_build()
        test_app_lifecycle()

        # ── Sandboxed tests ────────────────────────────────────────────────────
        if RUN_ALL:
            state = save_state()
            try:
                test_sandboxed_board()
                test_sandboxed_project()
                test_sandboxed_libs()
            finally:
                restore_state(state)

        # ── Skipped ───────────────────────────────────────────────────────────
        test_skipped()

        # ── Summary ───────────────────────────────────────────────────────────
        log()
        log("=" * 60)
        log("  RESULTS")
        log("=" * 60)
        log()
        log("  Passed:  " + str(len(passed)))
        log("  Failed:  " + str(len(failed)))
        log("  Skipped: " + str(len(skipped)))
        log()

        if failed:
            log("  Failed tests:")
            for f in failed:
                log("    ✗ " + f)
            log()

        if len(failed) == 0:
            log("  All tests passed! 🎉")
        else:
            log("  " + str(len(failed)) + " test(s) failed.")
            log("  See " + LOG_FILE + " for full details.")

        log()

    finally:
        log_close()
        release_lock()

    sys.exit(0 if not failed else 1)


if __name__ == "__main__":
    main()
