# HybX Development System — Testing Guide
## Hybrid RobotiX

> *Hybrid RobotiX designs and creates intelligent technologies that empower people facing physical and accessibility challenges to live more independently and achieve more on their own terms.*

---

## Overview

The HybX Development System includes `hybx-test` — a first-class command that runs a comprehensive test of every HybX command and subcommand. It is designed to run **natively on the Arduino UNO Q**. arduino-cli and all board hardware are assumed to be present.

`hybx-test` is a self-contained command deployed to `~/bin/` by `update`. No repo access is required to run it — it works on any HybX installation.

All output is written to both the terminal and `~/hybx-test.log`. The log file is deleted and recreated on every run. A lock file `~/hybx-test.lock` prevents concurrent runs.

---

## Running the Tests

### Default — read-only + hardware

```bash
hybx-test
```

Runs all read-only and hardware tests. Safe to run at any time.

### All tests including sandboxed

```bash
hybx-test --all
```

Also runs sandboxed tests that create and destroy temporary test fixtures:
- Creates a temporary test board — verifies cancellation, error handling
- Creates a temporary test project — verifies scaffold, set/show/remove
- Installs and removes a test library — verifies install/show/remove cycle

### Verbose output

```bash
hybx-test --verbose
```

Shows full command output for each test. Useful for debugging failures.

### Combined flags

```bash
hybx-test --all --verbose
```

---

## Log File

Every run writes a complete log to `~/hybx-test.log`:

- Previous log is deleted at the start of each run
- All test output — PASS, FAIL, SKIP — is written to the log
- Full command output is written to the log regardless of `--verbose`
- Start time, end time, and elapsed time are recorded
- Failed test summary at the end

To review after a run:

```bash
cat ~/hybx-test.log
```

---

## Lock File

`hybx-test` uses `~/hybx-test.lock` to prevent concurrent runs:

- If the lock file exists and the PID is still running — exits with an error
- If the lock file exists but the PID is gone (stale lock) — removes it and proceeds
- Lock is always released in a `finally` block — cleaned up even on crash or Ctrl+C

If you need to manually clear a stale lock:

```bash
rm ~/hybx-test.lock
```

---

## Test Categories

### READ-ONLY

Tests that only read system state — safe to run any time.

| Command | Tests |
|---------|-------|
| `board` | list, show, sync --dry-run, usage errors, nonexistent board errors |
| `project` | list, list --names, show, usage errors, nonexistent project error |
| `libs` | list, search, show, upgrade, usage errors, nonexistent library error, check |
| `setup` | full run — installs ino.nanorc to ~/.local/share/nano/ |
| `list` | full run — lists available apps |
| `update` | full run — pulls repos, refreshes ~/bin/, deploys ~/lib/ |
| `lib/ deployment` | verifies ~/lib/ modules present, old ~/bin/ copies removed, retired commands gone |

### HARDWARE

Tests that require board hardware and a running arduino-router. Uses `scd30` as a safe test fixture. Runs as part of the default test run.

| Command | Tests |
|---------|-------|
| `build` | full sketch path, project name only, no args (uses active project) |
| `start` | with app name, with no args (uses last app) |
| `stop` | with app name, with no args (uses last app) |
| `restart` | with app name, with no args (uses last app) |
| `mon` | with app name, with no args (uses last app) |
| `clean` | with app name |

### SANDBOXED

Tests that create and destroy temporary state. Only run with `--all`. Active project and last app are saved before sandboxed tests and restored after — even if tests fail.

| Command | Tests |
|---------|-------|
| `board add` | Cancellation on `NO`, config unchanged after cancel |
| `board use` | Nonexistent board error |
| `board remove` | Nonexistent board error |
| `project new` | Scaffold creation, all expected files verified |
| `project use` | Set temp project, verify show output |
| `project remove` | Cancellation on `NO`, confirmation on `YES`, directory removal |
| `libs install` | Install test library |
| `libs show` | Show installed library |
| `libs remove` | Cancellation on `NO`, confirmation on `YES` |

### SKIPPED

Only `migrate` is skipped — it is a one-time destructive operation covered by proxy through `libs` and `build` tests.

---

## What is Tested

### Exit Codes

Every test checks the exit code against the expected value:
- `0` for successful operations
- Non-zero for expected errors (usage errors, not found errors, etc.)

### Output Content

Tests verify that expected strings appear in the output:
- Usage instructions when required arguments are missing
- Error messages when operations fail expectedly
- Success messages when operations complete

### Pathing

All commands that accept a path or name argument are tested in every supported calling mode:
- `build` — full path, project name, no args (active project)
- `start`/`stop`/`restart`/`mon`/`clean` — app name, no args (last app)

### State Verification

Sandboxed tests verify actual filesystem and config changes:
- Directory creation and scaffold files after `project new`
- Config unchanged after cancellation
- Directory removal after `project remove`
- `~/lib/` modules deployed correctly
- Old shared module copies gone from `~/bin/`
- Retired commands gone from `~/bin/`

---

## Output Format

```
Hybrid RobotiX — HybX Development System Test Suite
=====================================================
Mode: ALL (read-only + hardware + sandboxed)
Log:  /home/arduino/hybx-test.log
Start: 2026-04-19 23:14:22

============================================================
  board
============================================================

  PASS  board list
  PASS  board show
  FAIL  board use nonexistent — fails cleanly
        → missing: 'not found'
        ERROR: Board 'xyz' not found

============================================================
  RESULTS
============================================================

  Start:   2026-04-19 23:14:22
  End:     2026-04-19 23:31:47
  Elapsed: 0:17:25

  Passed:  90
  Failed:  0
  Skipped: 1

  All tests passed! 🎉
```

---

*Hybrid RobotiX — San Diego, CA*
