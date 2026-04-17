# HybX Development System — Testing Guide
## Hybrid RobotiX

> *Hybrid RobotiX designs and creates intelligent technologies that empower people facing physical and accessibility challenges to live more independently and achieve more on their own terms.*

---

## Overview

The HybX Development System test suite lives in `tests/test-v0.0.2.py`. It exercises all commands and subcommands systematically, reporting pass/fail for each test.

---

## Running the Tests

### Safe tests (read-only, no state changes)

```bash
python3 tests/test-v0.0.2.py
```

Runs all tests that do not modify system state. Safe to run at any time on any board.

### All tests including sandboxed

```bash
python3 tests/test-v0.0.2.py --all
```

Also runs sandboxed tests that create and destroy temporary test fixtures:
- Creates a temporary test board, verifies cancellation behavior, verifies error handling
- Creates a temporary test project, verifies set/show/remove behavior

### Verbose output

```bash
python3 tests/test-v0.0.2.py --verbose
```

Shows full command output for each test. Useful for debugging failures.

### Combined flags

```bash
python3 tests/test-v0.0.2.py --all --verbose
```

---

## Test Categories

### READ-ONLY

Tests that only read system state — safe to run any time.

| Command | Tests |
|---------|-------|
| `board` | list, show, sync --dry-run, usage errors |
| `project` | list, list --names, show, usage errors, nonexistent project error |
| `libs` | list, search, show, usage errors, nonexistent library error |
| `update` | full run |

### SANDBOXED

Tests that create and destroy temporary state. Only run with `--all`.

| Command | Tests |
|---------|-------|
| `board add` | Cancellation on `NO`, config unchanged after cancel, nonexistent board errors |
| `project new` | Scaffold creation, directory verification |
| `project use` | Set the temp project, verify show output |
| `project remove` | Cancellation on `NO`, confirmation on `YES`, directory removal verification |

### SKIPPED

Commands that require hardware, Docker, or are destructive one-time operations. Skipped in automated testing with a reason printed for each.

| Command | Reason |
|---------|--------|
| `build` | Requires Arduino board connected via SSH |
| `start` | Requires Docker and a running app |
| `stop` | Requires a running app |
| `restart` | Requires Docker and a running app |
| `logs` | Requires a running app |
| `list` | Requires arduino-app-cli on board |
| `clean` | Destructive — nukes Docker |
| `migrate` | One-time migration — destructive if re-run |
| `setup` | One-time setup |

These must be tested manually.

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

### State Verification

Sandboxed tests verify actual filesystem and config changes:
- Directory creation after `project new`
- Config unchanged after cancellation
- Directory removal after `project remove`

---

## Output Format

```
=== board ===

  PASS  board list
  PASS  board show
  PASS  board sync --dry-run
  FAIL  board use nonexistent — fails cleanly
        → missing: 'not found'
        ERROR: Board 'xyz' not found
  SKIP  build  (requires Arduino board)

============================================================
  RESULTS
============================================================

  Passed:  14
  Failed:  1
  Skipped: 9

  Failed tests:
    ✗ board use nonexistent — fails cleanly
```

---

## Adding New Tests

When adding a new command or subcommand, add corresponding tests to `tests/test-v0.0.2.py`:

1. Add read-only tests to the appropriate `test_<command>()` function
2. Add sandboxed tests to `test_sandboxed_<command>()` if state changes are needed
3. Add to the skipped list with a reason if hardware or Docker is required

Follow the existing pattern — use the `test()` helper for assertions and `skip()` for skipped tests.

---

*Hybrid RobotiX — San Diego*
