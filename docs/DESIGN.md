# HybX Development System — Design Document
## Hybrid RobotiX

> *Hybrid RobotiX designs and creates intelligent technologies that empower people facing physical and accessibility challenges to live more independently and achieve more on their own terms.*

*"I. WILL. NEVER. GIVE. UP. OR. SURRENDER."*

---

## Table of Contents

1. [Overview](#1-overview)
2. [Repository Structure](#2-repository-structure)
3. [Design Principles](#3-design-principles)
4. [Bin Commands](#4-bin-commands)
5. [Shared Library](#5-shared-library)
6. [Installer](#6-installer)
7. [Versioning Conventions](#7-versioning-conventions)
8. [Configuration Architecture](#8-configuration-architecture)
9. [Safety Design](#9-safety-design)
10. [User Interaction Design](#10-user-interaction-design)
11. [VSCode Extension](#11-vscode-extension)
12. [Testing](#12-testing)
13. [Key Technical Discoveries](#13-key-technical-discoveries)
14. [Known Issues](#14-known-issues)
15. [Roadmap](#15-roadmap)

---

## 1. Overview

The HybX Development System is a complete App Lab replacement that runs **natively on the Arduino UNO Q**. All commands execute directly on the board — installed in `~/bin/` on the UNO Q's Debian Linux filesystem and invoked over SSH from a development machine. It is not a remote control tool running on a Mac or PC; it is a native Linux toolchain that lives on the board itself.

The system includes versioned Python bin commands, a library manager, a board configuration manager, a project manager, and a VSCode extension that integrates all commands into the editor.

The system is designed to be clean, reproducible, and fully independent of Arduino's managed infrastructure. Every board can be completely reproduced from the repos in a single `update` run.

**Guiding philosophy:** clean architecture, zero vendor lock-in, everything versioned, single source of truth.

---

## 2. Repository Structure

```
HybX-Development-System/
  bin/                  — Versioned Python bin commands
  config/               — nano syntax highlighting configs
  docs/                 — Design documents, command reference, known issues
  lib/                  — Shared Python modules (single source of truth)
  scripts/              — Installer, FINALIZE, and other one-time scripts
  vscode-extension/     — HybX VSCode extension (.vsix)
  README.md             — Quick start and reference
```

### bin/

Contains all versioned command files. Commands are copied to `~/bin/` by `update`. No shared modules live here — they live exclusively in `lib/`.

### lib/

The single source of truth for all shared Python modules:
- `hybx_config.py` — board config, library registry, shared path constants
- `libs_helpers.py` — library filesystem scanning, arduino-cli wrappers

Shared modules are deployed to `~/lib/` on the board by `update`. Commands import from `~/lib/` at runtime via `sys.path.insert(0, os.path.expanduser("~/lib"))`. Nothing in `lib/` is duplicated in `bin/`.

### scripts/

Contains one-time scripts that are intentionally NOT on PATH:
- `install-v0.0.3.py` — new board installer
- `FINALIZE-v0.0.1.py` — permanent App Lab severance (irreversible)

### tests/

Contains the test suite:
- `test-v0.0.2.py` — comprehensive test of all commands and subcommands

---

## 3. Design Principles

- **All Python, no bash** — every command is a versioned Python script. Bash is only permitted for one-time bootstrap scripts that must exist before the repo is cloned.
- **Versioned filenames** — `command-vX.Y.Z.py` with unversioned symlinks pointing to the latest version
- **Single source of truth** — the repo is authoritative; the board environment is always fully reproducible from it
- **Shared code lives in shared modules** — any logic used by two or more commands must be extracted into `lib/`. Never duplicate code across command files.
- **Configuration in JSON** — all state stored in `~/.hybx/config.json` and `~/.hybx/libraries.json`
- **No PATs on disk** — PATs are never stored anywhere in the system. SSH keys + keychain only.
- **Executable permissions always set** — all `.py` files in `bin/` are always `chmod 755` after copy. Never inherit repo permissions.
- **Pre-flight before action** — any command that makes significant changes shows a complete summary of what will happen and requires explicit confirmation before touching anything
- **Deliberate confirmation** — all YES/NO prompts require uppercase `YES` or `NO` to show intentionality
- **GUI-ready** — all commands support `--json` for machine-readable output and `--confirm` for non-interactive operation, enabling future GUI integration without code changes

---

## 4. Bin Commands

| Command | Latest | Description |
|---------|--------|-------------|
| `board` | v1.1.0 | Board configuration — add, use, remove, list, show, sync |
| `build` | v1.1.0 | Verify libraries, compile and flash — accepts project name, full path, or no args |
| `clean` | v1.1.0 | Full Docker nuke + cache clear + restart |
| `hybx-test` | v1.1.0 | Self-contained test suite — log file, lock file, full pathing coverage |
| `libs` | v1.1.0 | Library manager — global registry, project assignments, sketch.yaml authority |
| `list` | v1.1.0 | List available apps via arduino-app-cli |
| `logs` | v1.1.0 | Show live app logs |
| `migrate` | v1.1.0 | One-time migration from App Lab to arduino-cli library management |
| `project` | v1.1.0 | Project management — new, list, show, use, remove |
| `restart` | v1.1.0 | Stop and restart the active app |
| `setup` | v1.1.0 | One-time system setup — no sudo, installs to ~/.local/share/nano/ |
| `start` | v1.1.0 | Pull repos, sync apps, start app |
| `stop` | v1.1.0 | Stop the running app |
| `update` | v1.1.0 | Pull repos, deploy ~/lib/, clean ~/bin/, refresh symlinks |

See `docs/COMMANDS.md` for the full subcommand reference.

### 4.1 start (v1.1.1)

The primary command. Every `restart` delegates to `start`.

Sequence:
1. Clear screen, print `=== start ===`
2. Save app name to `~/.hybx/last_app`
3. Remove Docker container: `docker rm -f arduino-<app>-main-1`
4. Remove Docker image: `docker rmi -f arduino-<app>-main`
5. Remove `.cache/` directory from app folder
6. Pull latest repos
7. Sync apps to board's apps_path — **only new apps, never overwrites existing**
8. Run `arduino-app-cli app start <app_path>`
9. Wait for `.cache/app-compose.yaml` to be generated (up to 60 seconds)
10. Patch the compose file to mount `$HOME` into the container
11. Restart the container with the patched compose file

**Why the `$HOME` mount patch:** The Docker container generated by `arduino-app-cli` does not mount `$HOME` by default. Python apps that need to persist state (e.g. `~/.scd30-calibrated`) require this mount. The patch inserts a bind mount into the generated compose file and force-recreates the container.

**v1.1.1 fix:** Previous versions wiped `~/Arduino` entirely on every `start` run via `shutil.rmtree`, then recreated it from the repo. This caused `[ERROR] App Is Running` when starting a new app while another was running, because `arduino-app-cli` detected the previous app's path had been destroyed and recreated. Fixed to use safe copy-only-new-apps behavior, matching `board sync`.

### 4.2 build (v0.0.2)

Compiles and flashes MCU sketches without App Lab.

Sequence:
1. Derive project name from sketch path
2. Run `libs check <project>` pre-flight — abort if any assigned library is not installed
3. Run `arduino-cli compile --fqbn arduino:zephyr:unoq <sketch_path> -v`
4. Run `arduino-cli upload --profile default --fqbn arduino:zephyr:unoq <sketch_path>`

Upload uses OpenOCD via SWD under the hood — the same mechanism App Lab uses, but invoked directly through Arduino CLI. `sketch.yaml` is owned exclusively by `libs` and is never written or modified by `build`.

### 4.3 board (v0.0.7)

Manages board configurations in `~/.hybx/config.json`.

Key behaviors:
- `board add` collects ALL inputs first, shows a full pre-flight summary, then requires `YES` before making any changes
- `board add` automatically clones or pulls the app repo after confirmation
- `board sync` only adds new apps — never overwrites or modifies existing apps
- `board sync --dry-run` only suggests running `board sync` when there are actually apps to add
- Board names are always normalized to lowercase in config

### 4.4 libs (v0.0.1)

The library manager and single source of truth for all Arduino libraries.

Key behaviors:
- All library operations go through `libs` — never bypass it
- `libs remove` is hard-blocked (exit code 3) if any project uses the library
- `libs remove` is also blocked if the library is a dependency of another in-use library
- There is no `--force` flag — protection cannot be bypassed
- `libs` is the only command that writes `sketch.yaml` library sections
- All subcommands support `--json` and `--confirm` for GUI integration

### 4.4a clean (v1.1.1)

**v1.1.1 fix:** `clean` now runs `docker rm -f $(docker ps -aq)` as its first action, nuking all running Docker containers before stopping the target app. This ensures stuck containers from any app are cleared, preventing `[ERROR] App Is Running` from blocking the clean operation.

---

### 4.5 update (v1.1.0)

Pulls the latest repos and refreshes the board environment.

Key behaviors:
- Stashes local uncommitted changes before pulling, pops them after
- FINALIZE safety purge runs BEFORE copy/link loop — purges both symlink and versioned FINALIZE files from `~/bin/`
- Always sets `chmod 755` on all `.py` files after copying — never inherits repo permissions
- `sync` is NOT in the COMMANDS list — it is a subcommand of `board`, not a standalone command

### 4.6 project (v0.0.2)

Manages projects for the active board.

Key behaviors:
- `project use` and `project remove` search the flat `apps_path` layout first, then type subdirectories — compatible with both UNO-Q's flat layout and potential future structured layouts
- `project remove` requires `YES` confirmation before deleting files from disk

---

## 5. Shared Library

All shared code lives in `lib/`. Commands import from there via `sys.path.insert`.

### Deployment

`update` deploys all `lib/*.py` files to `~/lib/` on the board. All commands add `~/lib` to `sys.path` at startup:

```python
sys.path.insert(0, os.path.expanduser("~/lib"))
```

No shared modules exist in `bin/` in the repo — `lib/` is the single and only source.

### lib/hybx_config.py

Central shared configuration module. Contains:

| Function | Description |
|----------|-------------|
| `load_config()` | Load `~/.hybx/config.json` |
| `save_config(config)` | Save config to `~/.hybx/config.json` |
| `get_active_board()` | Return active board dict — exits with error if none set |
| `get_push_url(board)` | Return authenticated push URL for board's repo |
| `load_libraries()` | Load `~/.hybx/libraries.json` |
| `save_libraries(libs)` | Save libraries registry |
| `get_library_users(libs, lib_name)` | Return list of projects using a library |
| `get_dependent_libraries(libs, lib_name)` | Return libraries that depend on a library |
| `confirm_prompt(question)` | YES/NO prompt — requires uppercase, re-prompts until valid |
| `mask_username(value)` | Replace github_user with *** in display strings |
| `mask_host(host)` | Replace user@ with ***@ in host strings |
| `safe_path(path)` | Replace /home/<user> with ~ in displayed paths |
| `HybXTimer(label)` | Timing utility — silent by default, set `HYBX_TIMING=1` to enable |

**`HybXTimer`** measures elapsed time for any operation. Silent by default.
To enable timing output: `export HYBX_TIMING=1` in `~/.bashrc`.
Usage: `with HybXTimer("label"): ...` or `@HybXTimer.timed("label")`.

**`confirm_prompt()`** is the single centralized prompting routine for the entire system. All YES/NO prompts call this function. Fixes to prompting behavior are made here once and apply everywhere.

### lib/libs_helpers.py

Library filesystem scanning and arduino-cli wrapper functions used by `libs`.

---

## 6. Installer

`scripts/install-v0.0.3.py` installs the HybX Development System on a new board or machine.

### Installation Flow

1. Collect all inputs first: `github_user`, `apps_repo_name` (ARM64 only)
2. Detect platform from `platform.system()` and `platform.machine()`
3. Detect shell from `$SHELL` environment variable — never assumed from platform
4. Build and display a complete pre-flight summary of every change to be made
5. Require `YES` confirmation before touching anything
6. Execute: save config → setup ~/bin → setup SSH → clone repos → install symlinks

### Shell Support

Shell is detected from `$SHELL` — not assumed from platform. Any shell can be used on any platform.

| Shell | RC File | PATH syntax | Keychain syntax |
|-------|---------|-------------|-----------------|
| bash | `~/.bashrc` | `export PATH="$HOME/bin:$PATH"` | `eval $(keychain ...)` |
| zsh | `~/.zshrc` | `export PATH="$HOME/bin:$PATH"` | `eval $(keychain ...)` |
| fish | `~/.config/fish/config.fish` | `fish_add_path $HOME/bin` | `keychain ... \| source` |

### Pre-Flight Summary

The installer shows exactly what will happen before doing anything, organized by section:

- **CONFIG** — github_user to be saved to config.json
- **~/bin** — whether the directory will be created, what PATH line will be added to the rc file
- **SSH** — whether a new key will be generated or an existing one will be used
- **KEYCHAIN** — (Linux only) whether keychain needs installing, what line will be added
- **REPOSITORIES** — which repos will be cloned or pulled
- **HybX COMMANDS** — every command symlink that will be created

Cancellation prints "Nothing was changed." and exits cleanly.

---

## 7. Versioning Conventions

All bin commands follow strict versioning:

- **Filename format:** `command-vX.Y.Z.py`
- **Version reflects release** — the version number in the filename matches the HybX release it was introduced in:
  - `command-v0.0.x.py` — pre-v1.0 development history
  - `command-v1.1.0.py` — introduced or updated in v1.1
  - `command-v1.5.0.py` — introduced or updated in v1.5
  - `command-v2.0.0.py` — introduced or updated in v2.0
- **Symlinks** always point to the latest version, updated by `update`
- **Old versions stay in the repo** — for history and rollback reference
- **Only the linked version lives on the board** — `update` removes old versioned files from `~/bin/`

When a command is updated:
1. Create the new versioned file named for the current release (e.g. `board-v1.1.0.py`)
2. Push to the repo
3. Run `update` on the board to update the symlink

Shared modules (`hybx_config.py`, `libs_helpers.py`) are unversioned — they evolve in place. Changes to shared modules are always backward compatible.

---

## 8. Configuration Architecture

All configuration lives in `~/.hybx/` on the board. These files are local to each board and are never committed to any repo.

### `~/.hybx/config.json`

Written by `board`, `project`, and `install`. Contains board definitions, active board, github_user, and active project per board.

### `~/.hybx/libraries.json`

Written exclusively by `libs`. Contains the global library registry with versions, dependencies, and project assignments. Never edit by hand.

### `~/.hybx/last_app`

Written by `start`, `stop`, `restart`, `logs`, `clean`. Plain text, contains the name of the last used app.

### Separation of Concerns

| Config | Owner | Never written by |
|--------|-------|-----------------|
| `config.json` | `board`, `project`, `install` | `libs`, `build`, `start` |
| `libraries.json` | `libs` | Everything else |
| `last_app` | `start`, `stop`, `restart`, `logs`, `clean` | Everything else |

---

## 9. Safety Design

Several safety mechanisms are built into the system to prevent accidental data loss or irreversible actions.

### FINALIZE Safety

FINALIZE is the most destructive command in the system — it permanently severs App Lab and deletes `~/.arduino15/internal/`. Three layers of protection:

1. **Not on PATH** — lives in `scripts/` only, must be invoked by full path
2. **Never installed** — `install` and `update` explicitly exclude it from the COMMANDS list
3. **Actively purged** — `update` runs a FINALIZE safety purge BEFORE the copy/link loop, removing any FINALIZE symlink or versioned file that might exist in `~/bin/`

### Library Removal Protection

`libs remove` is a hard abort (exit code 3) if any project uses the library, or if any library that depends on it is itself in use by any project. There is no `--force` flag — this protection cannot be bypassed.

### Pre-Flight Summaries

`board add` and `install` both collect all inputs first, then show a complete pre-flight summary of every change to be made, then require `YES` before touching anything. Cancellation always prints "Nothing was changed."

### Confirmation Prompts

All YES/NO prompts across the entire system are routed through `confirm_prompt()` in `lib/hybx_config.py`. Uppercase `YES` or `NO` is required — deliberate intent is the design goal. Fixes to confirmation behavior are made once and apply everywhere.

---

## 10. User Interaction Design

### Pre-Flight Pattern

Any command that makes significant or irreversible changes follows this pattern:

1. Collect ALL inputs first — no prompting interleaved with side effects
2. Inspect current system state
3. Build a complete human-readable summary of everything that will happen
4. Display the summary
5. Prompt for `YES` or `NO`
6. If `YES`: execute. If `NO`: print "Nothing was changed." and exit

### Confirmation Prompts

All confirmation prompts:
- Are routed through `confirm_prompt()` in `lib/hybx_config.py`
- Require uppercase `YES` or `NO`
- Re-prompt until a valid response is given
- Never accept `y`, `yes`, `n`, `no` — only `YES` and `NO`

### Dry-Run Pattern

Commands that sync or modify state support `--dry-run` to preview without acting:
- `board sync --dry-run` — shows what apps would be added
- `migrate dryrun` — shows what libraries would be migrated
- `FINALIZE dryrun` — shows what would be removed

Dry-run output is always clearly labeled. `board sync --dry-run` only suggests running `board sync` when there are actually changes to make.

### JSON Output

All commands that produce structured output support `--json` for machine-readable output on stdout. This enables future GUI integration without modifying the commands — the GUI calls the same commands with `--json` and parses the output.

---

## 11. VSCode Extension

The `hybx-dev` VSCode extension provides a graphical front-end for all HybX Development System commands. It runs on the local machine and executes commands via SSH — no Node.js SSH library, no Remote-SSH dependency.

### Architecture

The extension communicates with the board entirely over SSH. Any machine that can `ssh arduino@uno-q.local` from a terminal can use the extension.

All commands are invoked with `--json` where supported for machine-readable output, and `--confirm` to suppress interactive prompts.

### Commands

All commands are available in the VSCode Command Palette under the `HybX:` prefix.

### Configuration

| Setting | Default | Description |
|---------|---------|-------------|
| `hybxDev.sshHost` | `arduino@uno-q.local` | SSH connection string |
| `hybxDev.appsPath` | `~/Arduino/UNO-Q` | Apps directory on board |
| `hybxDev.sshKeyPath` | *(empty)* | SSH private key path |

---

## 12. Testing

The test suite is `hybx-test` — a first-class HybX command deployed to `~/bin/` by `update`. It runs natively on the board. No repo access is required.

### Running Tests

```bash
# Default — read-only + hardware tests
hybx-test

# All tests including sandboxed (creates/destroys temporary fixtures)
hybx-test --all

# Verbose output (shows full command output for each test)
hybx-test --verbose
```

All output is written to both the terminal and `~/hybx-test.log`. The log is deleted and recreated on every run. A lock file `~/hybx-test.lock` prevents concurrent runs.

### Test Categories

| Category | Description |
|----------|-------------|
| **READ-ONLY** | Safe to run any time — no state changes |
| **HARDWARE** | Requires Docker and arduino-app-cli — included in default run |
| **SANDBOXED** | Creates and destroys temporary test fixtures — `--all` only |
| **SKIPPED** | `migrate` only — one-time destructive operation |

### Skipped Commands

Only `migrate` is skipped — it is a one-time destructive operation covered by proxy through `libs` and `build` tests.

---

## 13. Key Technical Discoveries

These are undocumented behaviors of the UNO Q platform discovered through reverse engineering:

- **QWIIC uses `Wire1`** — the QWIIC connector is on I2C bus 1, not the default bus 0. All QWIIC/Stemma QT sensors must be initialized with `&Wire1`
- **`Bridge.provide()` before `setup()`** — Bridge function registrations must be declared before `setup()` runs or they are not available to the Python side
- **`arduino-app-cli` without App Lab** — `arduino-app-cli app start` works directly from the command line without the App Lab GUI
- **OpenOCD via SWD** — `arduino-cli upload` uses OpenOCD over SWD internally; this is the same flash mechanism as App Lab
- **`arduino.app_utils` is Docker-injected** — the `arduino.app_utils` Python package is not installable from PyPI; it is injected into the Docker container at runtime by `arduino-app-cli`
- **Library storage location** — App Lab libraries are stored in `~/.arduino15/internal/` in a nested hash layout
- **Docker container naming** — containers are named `arduino-<app>-main-1`
- **GPIO voltage** — GPIO pins on the UNO Q operate at 3.3V. Shields designed for 5V Arduino Uno may need level shifting

---

## 14. Known Issues

See `docs/KNOWN_ISSUES.md` for full details on open vendor bugs:

- **Docker mDNS resolution** — apps cannot resolve `*.local` hostnames inside Docker containers (Arduino issue [#328](https://github.com/arduino/arduino-app-cli/issues/328))
- **Infineon optigatrust I2C bus** — `liboptigatrust` hardcodes `/dev/i2c-1` (Infineon issue [#26](https://github.com/Infineon/python-optiga-trust/issues/26))
- **update getcwd errors** — cosmetic errors when running `update` from inside `$REPO_DEST`

---

## 15. Roadmap

### Near Term
- Complete `hub5-bno055` HUB75 64×32 LED panel implementation
- Hover IP auto-update Python script for dynamic DNS
- Tag and release v1.1

### Medium Term
- `board sync --force` — overwrite existing apps from repo (default sync still protects local changes)

- VSCode extension: wire Library Manager UI to `libs --json` output
- VSCode extension: sidebar panel with app tree view
- VSCode extension: library manager UI with conflict warnings

### Long Term
- Support for additional boards (Portenta X8, ESP32 family)
- GUI wrapper for full HybX Development System
- My Chairiet Distributed Computing Platform integration

---

*Hybrid RobotiX — San Diego*

---

## 16. Branching Strategy

**RULE: ALL work MUST be done on a branch. No direct commits to `main`. Ever.**

`main` is always stable. It only receives merges from branches at release time.

### Branch Types

| Branch | Purpose |
|--------|---------|
| `main` | Latest stable release — only updated via merge, never direct commit |
| `dev/vX.Y` | Active development for the next major/minor version |
| `fix/description` | Bug fix branch for a specific issue |
| `feature/description` | Feature branch for a specific new capability |

### Release Workflow

1. All work happens on a branch (`dev/v2.0`, `fix/xxx`, `feature/xxx`)
2. When ready to release, open a PR from the branch to `main`
3. Merge the PR to `main`
4. Tag `main` at the merge commit: `git tag -a vX.Y.Z -m "..."`
5. Push the tag: `git push origin vX.Y.Z`
6. Create a GitHub Release from the tag

### What Never Happens

- No direct commits to `main`
- No cherry-picks to `main`
- No hotfixes directly on `main`
- No exceptions — every change, no matter how small, goes on a branch first

### Current Branches

| Branch | Status |
|--------|--------|
| `main` | Stable — v1.2.2 |
| `dev/v2.0` | Active — HybX Build System development |

---

*Hybrid RobotiX — San Diego*

---

## v2.0 Roadmap — HybX Build System

**Goal:** Replace `arduino-cli` and `arduino-app-cli` compile/flash pipeline with a
Python-based build system that gives HybX complete control over every build step.
Option 2 (native Zephyr/west) is the long-term destination; v2.0 is Option 1.

v2.0 is a major version because it is a complete replacement of the core build
pipeline — not a feature addition. v1.x remains the stable foundation.

### Motivation

Every problem encountered during `hybx_vl53l5cx` development traces back to
`arduino-app-cli` and `arduino-cli` being opaque, library-manager-locked, and
impossible to extend:

- Local libraries require `dir:` workarounds in `sketch.yaml`
- Library Manager lockdown prevents first-class HybX library support
- Sketch hash/cache/Docker state can get out of sync with no recovery path
- Silent build failures with no diagnostic output
- Developers fight the toolchain instead of building products

### Design Principles

1. **No silent failures** — every step reports success or failure explicitly
2. **First-class HybX libraries** — no Library Manager, no workarounds
3. **Board abstraction** — adding a new board is adding a JSON file
4. **Option 2 compatible** — architecture must not preclude native Zephyr migration
5. **Developer friendly** — `hybx-build`, `hybx-flash` just work

### Target Boards (v1.5)

| Board | MCU | RTOS | Toolchain | Flash |
|---|---|---|---|---|
| Arduino UNO Q | STM32U5 (Cortex-M33) | Zephyr | arm-zephyr-eabi | OpenOCD/SWD |
| Arduino Portenta X8 | STM32H747 (Cortex-M7) | bare/Zephyr | arm-none-eabi | OpenOCD/SWD |
| Arduino Ventuno Q | TBD | TBD | TBD | TBD |

### Repository Structure

```
hybx_build_system/          (new repo: hybotix/HybX-Build-System)
                            (developed in parallel with v1.x maintenance)
  boards/
    uno-q.json              board definition: toolchain, OpenOCD cfg, linker script
    portenta-x8.json
    ventuno-q.json
  bin/
    hybx-build-v1.5.0.py    compile sketch for active board
    hybx-flash-v1.5.0.py    flash compiled binary to MCU
    hybx-monitor-v1.5.0.py  Bridge/serial monitor
  lib/
    compiler.py             GCC invocation, include path resolution
    flasher.py              OpenOCD invocation
    board.py                board definition loader
    library.py              HybX library resolver (replaces Library Manager)
  docs/
    DESIGN.md
    COMMANDS.md
    KNOWN_ISSUES.md
```

### Board Definition Format

```json
{
  "name": "Arduino UNO Q",
  "id": "uno-q",
  "mcu": "STM32U5",
  "core": "cortex-m33",
  "rtos": "zephyr",
  "toolchain": "arm-zephyr-eabi",
  "toolchain_path": "/home/arduino/.arduino15/packages/zephyr/tools/arm-zephyr-eabi",
  "openocd_cfg": "target/stm32u5x.cfg",
  "openocd_interface": "interface/linuxgpiod.cfg",
  "flash_address": "0x08000000",
  "ram_size": 131072,
  "flash_size": 2097152
}
```

### Phase Plan

**Phase 1 (v2.0.0):** hybx-build + hybx-flash for UNO Q
- Call arm-zephyr-eabi GCC directly with correct flags
- Call OpenOCD directly for flash
- HybX library resolver: finds libraries in ~/Arduino/libraries/ without
  Library Manager — no sketch.yaml dir: entries needed
- Replaces: arduino-cli compile, arduino-cli upload, arduino-app-cli app start
  (sketch side only — Python/Docker side unchanged)

**Phase 2 (v2.0.x):** Portenta X8 + Ventuno Q board definitions

**Phase 3 (future):** Option 2 — native Zephyr/west integration
- Replace Arduino API shims with native Zephyr APIs
- west for dependency management
- Full Zephyr threading, device tree, subsystems

### What Does NOT Change in v2.0

- The Python app side (Docker, Bridge RPC) — arduino-app-cli still manages this
- The HybX Development System command structure
- Existing sketches — .h/.cpp file format is preserved
- The no-silent-failures policy

---

