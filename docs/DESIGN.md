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
16. [Branching Strategy](#16-branching-strategy)
17. [HybX Build System v2.0](#17-hybx-build-system-v20)

---

## 1. Overview

The HybX Development System is a complete replacement for Arduino's toolchain that runs **natively on the Arduino UNO Q**. All commands execute directly on the board — installed in `~/bin/` on the UNO Q's Debian Linux filesystem and invoked over SSH from a development machine. It is not a remote control tool running on a Mac or PC; it is a native Linux toolchain that lives on the board itself.

The system includes versioned Python bin commands, a library manager, a board configuration manager, a project manager, and a VSCode extension that integrates all commands into the editor.

**v2.0** replaces `arduino-cli` compile and flash with `HybXCompiler` and `HybXFlasher` — a complete Python-based build pipeline that gives HybX full control over every build step.

**v2.1** removes Docker entirely. All apps run as plain Python processes in the foreground. `hybx_app` replaces `arduino.app_utils` as the native runtime. Apps are interactive by design — stdin/stdout/stderr are live. The terminal is the interface.

**Guiding philosophy:** clean architecture, zero vendor lock-in, everything versioned, single source of truth. Show the developer only what they must see — nothing more.

---

## 2. Repository Structure

```
HybX-Development-System/
  bin/                  — Versioned Python bin commands
  boards/               — Board definition JSON files (v2.0)
  config/               — nano syntax highlighting configs
  docs/                 — Design documents, command reference, known issues
  lib/                  — Shared Python modules (single source of truth)
  scripts/              — Installer, FINALIZE, and other one-time scripts
  vscode-extension/     — HybX VSCode extension (.vsix)
  README.md             — Quick start and reference
```

### boards/

Board definition JSON files for the HybX Build System. One file per board:

- `uno-q.json` — Arduino UNO Q (STM32U5, Cortex-M33, Zephyr)

Each board definition contains: toolchain paths, compile flags, linker scripts, OpenOCD flash config, library paths, and `system_libraries` list.

### bin/

Versioned command files. Commands are deployed to `~/bin/` by `update`. No shared modules live here.

### lib/

Single source of truth for all shared Python modules:

- `hybx_config-vX.Y.Z.py` → deployed as `hybx_config.py`
- `libs_helpers-vX.Y.Z.py` → deployed as `libs_helpers.py`
- `compiler-vX.Y.Z.py` → deployed as `compiler.py` (v2.0)
- `flasher-vX.Y.Z.py` → deployed as `flasher.py` (v2.0)
- `hybx_app-vX.Y.Z.py` → deployed as `hybx_app.py` (v2.1)

### Build Output

```
~/Arduino/UNO-Q/
  build/                    — All compiled binaries for the UNO Q board
    lsm6dsox.elf-zsk.bin    — Named after the project, ready to flash
  <app>/
    sketch/                 — Arduino sketch source
    python/                 — Python Bridge app (versioned: main-vX.Y.Z.py)
    data/                   — App data files (collected datasets, etc.)
    .cache/sketch/          — Intermediate build artifacts (auto-cleaned)
```

---

## 3. Design Principles

- **All Python, no bash** — every command is a versioned Python script
- **Versioned filenames** — `command-vX.Y.Z.py` with unversioned symlinks
- **Single source of truth** — repo is authoritative; board is always reproducible
- **Shared code lives in shared modules** — never duplicate across commands
- **Configuration in JSON** — all state in `~/.hybx/config.json` and `~/.hybx/libraries.json`
- **No silent failures** — every step reports success or failure explicitly
- **Show only what matters** — developer sees only what they must pay attention to
- **Silent when happy** — commands produce zero output when nothing changes
- **Branching discipline** — ALL work on branches, never direct to main
- **Apps are interactive by design** — stdin/stdout/stderr always live, terminal is the interface
- **No Docker** — apps run as plain Python processes, no containers

---

## 4. Bin Commands

| Command | Latest | Description |
|---------|--------|-------------|
| `board` | v2.1.0 | Board configuration — add, use, remove, list, show, branch |
| `build` | v2.0.0 | Compile and flash using HybX Build System |
| `clean` | v2.0.0 | Cache clear + restart |
| `flash` | v2.0.0 | Flash last built binary to MCU (standalone) |
| `hybx-test` | v1.2.0 | Self-contained test suite |
| `libs` | v1.2.0 | Library manager |
| `list` | v1.2.0 | List available apps |
| `mon` | v2.1.0 | Monitor running app output (tails log file) |
| `project` | v2.1.1 | Project management — push, pull, new, rename, clone, remove |
| `restart` | v1.2.0 | Stop and restart the active app |
| `setup` | v1.3.0 | One-time system setup |
| `start` | v2.1.1 | Start app in foreground — interactive by design |
| `stop` | v2.1.0 | Stop the running app |
| `update` | v2.1.0 | Pull repos, deploy libs, refresh commands — silent when current |

### 4.1 build (v2.0.0)

The primary compile+flash command. Uses `HybXCompiler` and `HybXFlasher` — no `arduino-cli`.

Output format:
```
=== build ===
Board:   UNO-Q
Project: lsm6dsox
  Libraries (3):
    Adafruit BusIO
    Adafruit LSM6DS
    Adafruit Unified Sensor
  Compiling...
  Linking
  Done
  Flashing lsm6dsox
  Done
```

On failure: `ERROR: <clear message>`. Nothing else.

Binary output: `~/Arduino/<BOARD>/build/<project>.elf-zsk.bin`
Intermediate artifacts: `<app>/.cache/sketch/` — auto-deleted after successful build.

### 4.2 flash (v2.0.0)

Standalone flash command. Flashes the last built binary without rebuilding or restarting the Python side.

```
flash [<project_name_or_binary_path>]
```

Always writes to flash (never RAM). Uses `HybXFlasher` directly.

### 4.3 start (v2.1.1)

Runs `main.py` directly in the foreground using the HybX venv. No Docker, no containers, no log files, no PID files. The terminal is the interface.

Apps are interactive by design — `input()` works, stdin/stdout/stderr are live.

Optional script argument:
```
start <app_name>              — runs main.py
start <app_name> <script.py>  — runs named script in python/
start --compile               — force recompile
```

### 4.4 update (v2.1.0)

Completely silent when everything is current. Pulls all repos on their current branch (never switches branches), deploys versioned lib modules as bare-name symlinks, refreshes command symlinks, manages HybX venv at `~/.hybx/venv`.

### 4.5 board branch (v2.1.0)

Switches all repos to a named branch and runs update:
```
board branch dev/v2.1
```

Stores `dev_branch` in `~/.hybx/config.json` as the single source of truth for the active branch.

---

## 5. Shared Library

### lib/hybx_config.py

| Function | Description |
|----------|-------------|
| `load_config()` | Load `~/.hybx/config.json` |
| `save_config(config)` | Save config |
| `get_active_board()` | Return active board dict |
| `load_libraries()` | Load `~/.hybx/libraries.json` |
| `save_libraries(libs)` | Save libraries registry |
| `confirm_prompt(question)` | YES/NO prompt — uppercase required |
| `mask_username(value)` | Replace github_user with *** |
| `mask_host(host)` | Replace user@ with ***@ |
| `safe_path(path)` | Replace /home/<user> with ~ |
| `HybXTimer(label)` | Timing utility — silent by default |
| `symlink_versioned_files(project_path)` | Create bare-name symlinks to latest versioned files |

**`HybXTimer`** is silent by default. Enable with `export HYBX_TIMING=1` in `~/.bashrc`.

### lib/hybx_app.py (v2.1)

Native replacement for `arduino.app_utils`. Provides `Bridge` and `App` — the complete UNO Q Python runtime. No Docker, no arduino-app-cli, no arduino.app_utils.

```python
from hybx_app import Bridge, App

def loop():
    result = Bridge.call("my_function", "arg1")
    print(result)

App.run(user_loop=loop)
```

Wire protocol: standard msgpack-RPC over `/var/run/arduino-router.sock`.
- Request: `[0, msgid, method, [args]]`
- Response: `[1, msgid, error, result]`

### lib/compiler.py (v2.0)

`HybXCompiler` — full 8-step build pipeline for Arduino UNO Q / Zephyr sketches.

### lib/flasher.py (v2.0)

`HybXFlasher` — clean OpenOCD flash via SWD. Always writes to flash. Completely silent on success.

### lib/libs_helpers.py

Library filesystem scanning and arduino-cli wrapper functions used by `libs`.

---

## 6. Installer

`scripts/install-v0.0.3.py` — installs the HybX Development System on a new board. Collects all inputs first, shows complete pre-flight summary, requires `YES` before touching anything.

---

## 7. Versioning Conventions

- **Filename format:** `command-vX.Y.Z.py`
- **MAJOR.MINOR** — locked to the release (e.g. `2.1` = v2.1 release)
- **PATCH** — increments on every change to that file (`2.1.0` → `2.1.1` → `2.1.2`)
- Every time a command or lib file is changed, bump the PATCH version and create a new file
- **Never modify an existing versioned file** — always create a new version
- **Lib files follow the same rule** — `hybx_config-v1.3.3.py` → `hybx_config-v1.3.4.py`
- **Symlinks** always point to latest version — `update` version-sorts and links highest
- **Only linked version lives on board** — `update` removes older versions, repo is the archive
- **App scripts follow the same pattern** — `main-vX.Y.Z.py` in repo, `main.py` symlink on board
- `project pull` creates bare-name symlinks for app scripts after copying from repo
- `project push` skips symlinks — only real versioned files go to the repo

---

## 8. Configuration Architecture

### `~/.hybx/config.json`

Contains board definitions, active board, github_user, active project per board, `board_id` for v2.0 board definition lookup, and `dev_branch` for the active development branch.

### `~/.hybx/libraries.json`

Written exclusively by `libs`. Global library registry with versions, dependencies, and project assignments.

### `~/.hybx/last_app`

Plain text — name of the last used app.

### `~/.hybx/venv/`

HybX Python virtual environment. Managed by `update`. Contains `msgpack` and any other runtime dependencies. Apps run with `~/.hybx/venv/bin/python3`.

---

## 9. Safety Design

- **FINALIZE** — not on PATH, never installed, actively purged by `update`
- **Library removal** — hard abort if any project uses the library
- **Pre-flight summaries** — `board add` and `install` show full summary before acting
- **Confirmation prompts** — uppercase `YES`/`NO` required, routed through `confirm_prompt()`

---

## 10. User Interaction Design

**Core philosophy:** Show the developer only what they MUST pay attention to. Nothing more.

- Silent when happy — zero output when nothing changes (`update` on current system)
- One line per phase — `Compiling...`, `Linking`, `Flashing lsm6dsox`
- Errors are clear and immediate — `ERROR: <message>`
- No paths in output — project names only
- No host exposure — `Board: UNO-Q` not `Board: UNO-Q (arduino@uno-q.local)`
- `HYBX_TIMING=1` env var enables timing output for those who want it
- Apps are interactive — prompts, input(), and live output work naturally

---

## 11. VSCode Extension

`hybx-dev` — graphical front-end for all HybX commands, runs on local machine, executes via SSH. All commands available under `HybX:` prefix in Command Palette.

---

## 12. Testing

`hybx-test` — first-class HybX command, runs natively on board. Categories: READ-ONLY, HARDWARE, SANDBOXED. Output to terminal and `~/hybx-test.log`.

---

## 13. Key Technical Discoveries

- **QWIIC uses `Wire1`** — I2C bus 1, not bus 0
- **`Wire1.begin()` before `Bridge.begin()`** — required; reversing this hangs the MCU
- **msgpack-RPC wire protocol** — `[0, msgid, method, [args]]` / `[1, msgid, error, result]` over `/var/run/arduino-router.sock`
- **arduino-router socket** — world-writable at `/var/run/arduino-router.sock`, always running
- **`Bridge.provide()` in setup()** — methods registered before Bridge.begin() are available immediately
- **OpenOCD via SWD** — flash mechanism, always writes to flash not RAM
- **Library storage** — `~/.arduino15/internal/` nested hash layout
- **GPIO voltage** — 3.3V on UNO Q
- **VL53L5CX firmware upload** — requires DMA on STM32U5; 500ms I2C kernel timeout blocks 32KB upload. See KNOWN_ISSUES.md.
- **Zephyr I2C timeout** — `CONFIG_I2C_STM32_TRANSFER_TIMEOUT_MSEC=500` default. DMA (`CONFIG_I2C_STM32_V2_DMA=y`) resolves in v2.0 build system.
- **precompiled core.a** — arduino-cli caches a precompiled core at `~/.cache/arduino/cores/arduino_zephyr_unoq_*/core.a` — reused by HybXCompiler

---

## 14. Known Issues

See `docs/KNOWN_ISSUES.md` for full details.

---

## 15. Roadmap

### v2.0.1 (patch)
- ✅ Fix pull_repo() branch switching bug — never switch branches on pull

### v2.0 (released)
- ✅ HybX Build System — HybXCompiler + HybXFlasher replace arduino-cli
- ✅ Board definitions in JSON (`boards/uno-q.json`)
- ✅ `flash` standalone command
- ✅ Named binaries in `<board>/build/`
- ✅ Minimal output — only what the developer must see
- ✅ Per-project `hybx.json` config with kconfig_overrides
- ✅ DMA-enabled i2c4 via `setup-dma` script
- ✅ `mon` command for monitoring app output
- ✅ `project pull <app> --force` for targeted app syncing
- ✅ `clean` calls `build` — no more stale cached binaries
- ✅ VL53L5CX ranging with confidence values on UNO Q

### v2.1 (active — dev/v2.1)
- ✅ Docker removed entirely — apps run as plain Python processes
- ✅ `hybx_app` — native replacement for `arduino.app_utils`
- ✅ `start` — interactive by design, foreground always
- ✅ `stop` — SIGTERM by process name
- ✅ `mon` — tails app log file
- ✅ `board branch` — switch all repos and deploy in one command
- ✅ Versioned file pattern for app scripts (main-vX.Y.Z.py)
- ✅ `project pull` creates bare-name symlinks for app scripts
- ✅ `project push` skips symlinks — only versioned files in repo
- ✅ `symlink_versioned_files()` in hybx_config library
- ✅ `pcd` shell function via `setup`
- ✅ VL53L5CX interactive data collector
- ✅ VL53L5CX data visualizer with centroid-based direction suggestion
- 🔲 Stash pop warning cleanup in pull_repo
- 🔲 Merge dev/v2.1 → main, tag v2.1

---

## 16. Branching Strategy

**RULE: ALL work MUST be done on a branch. No direct commits to `main`. Ever.**

`main` is always stable. It only receives merges from branches at release time.

| Branch | Purpose |
|--------|---------|
| `main` | Latest stable — only updated via merge, never direct commit |
| `dev/vX.Y` | Active development |
| `fix/description` | Bug fix branch |
| `feature/description` | Feature branch |

### Release Workflow
1. All work on a branch
2. PR from branch to `main`
3. Merge, tag, push tag
4. Create GitHub Release from tag

### What Never Happens
- No direct commits to `main`
- No cherry-picks to `main`
- No exceptions

### Current Branches
| Branch | Status |
|--------|--------|
| `main` | Stable — v2.0.1 |
| `dev/v2.0` | Maintenance |
| `dev/v2.1` | Active |

---

## 17. HybX Build System v2.0

### Architecture

```
boards/uno-q.json       — Complete board definition (toolchain, flags, linker, flash)
lib/compiler.py         — HybXCompiler: 8-step build pipeline
lib/flasher.py          — HybXFlasher: OpenOCD flash via SWD
bin/build-v2.0.0.py     — build command using HybXCompiler + HybXFlasher
bin/flash-v2.0.0.py     — standalone flash command
```

### Build Pipeline (HybXCompiler)

1. Preprocess .ino → .cpp (Arduino preamble injection)
2. Library discovery — #include scanning with visited-set recursion guard
3. Compile sketch + libraries + core (precompiled core.a reused)
4. Link pass 1: static check (memory-check.ld + syms-dynamic.ld)
5. Link pass 2: dynamic temp (build-dynamic.ld) → temp.elf
6. gen-rodata-ld: generate rodata_split.ld from temp ELF
7. Link pass 3: final (rodata_split.ld + build-dynamic.ld) → debug.elf
8. strip → objcopy (.bin, .hex) → zephyr-sketch-tool (.elf-zsk.bin)
9. Copy `<project>.elf-zsk.bin` to `<board>/build/`
10. Delete intermediate artifacts from `.cache/sketch/`

### Output Philosophy

System libraries (Wire, SPI, RouterBridge, RPClite, ArxContainer, etc.) are defined in `boards/uno-q.json` under `system_libraries`. They are compiled but never shown to the developer — they are infrastructure, not choices.

Only user-selected libraries appear in output.

### Per-Project Configuration — hybx.json

Each project can have an optional `hybx.json` in its root directory for
project-specific build configuration:

```json
{
  "kconfig_overrides": {
    "CONFIG_I2C_STM32_V2_DMA": "y",
    "CONFIG_I2C_STM32_TRANSFER_TIMEOUT_MSEC": "5000"
  },
  "dts_overlays": [
    "i2c4_dma.overlay"
  ]
}
```

When `kconfig_overrides` is present, the compiler patches `autoconf.h`
at build time. The core.a remains the same — only the config is modified.

### DMA for ST ToF Sensors

ST RAM-based ToF sensors (VL53L5CX, VL53L7CH, VL53L8CH) require ~86KB
firmware upload over I2C at boot. This requires DMA-enabled I2C transfer.

**Setup (run once after Arduino board package install/update):**
```bash
python3 scripts/setup-dma-v0.0.1.py
```

**Per-project (add hybx.json to project directory):**
```json
{
  "kconfig_overrides": {
    "CONFIG_I2C_STM32_V2_DMA": "y",
    "CONFIG_I2C_STM32_TRANSFER_TIMEOUT_MSEC": "5000"
  }
}
```

DMA configuration for i2c4 on STM32U585:
- TX: `GPDMA1_REQUEST_I2C4_TX = 22` (slot 22)
- RX: `GPDMA1_REQUEST_I2C4_RX = 21` (slot 21)
- DTS: `dmas = <&gpdma1 2 22 0x80440>, <&gpdma1 3 21 0x80480>;`
- Kconfig: `CONFIG_I2C_STM32_V2_DMA=y`

---

## VL53L5CX Integration — Key Lessons (v2.0)

Integrating the ST VL53L5CX 8x8 ToF sensor with the Arduino UNO Q and
RouterBridge required solving several non-obvious platform issues. These
are documented here as permanent reference.

### Wire1 + RouterBridge initialization order

```cpp
void setup() {
    Wire1.begin();    // MUST be before Bridge.begin()
    Bridge.begin();
    Bridge.provide("begin_sensor", begin_sensor);
    // ... more provides ...
}
```

`Wire1.begin()` after `Bridge.begin()` hangs the MCU permanently.
`#include <Wire.h>` must be in the sketch, not any library.

### Firmware upload must be Linux-triggered

The VL53L5CX requires a ~86KB firmware upload on every power-on (~30s).
Blocking `setup()` for this duration starves the Bridge UART transport.
Solution: expose `begin_sensor()` as a Bridge function. Python calls it,
which blocks on the Linux side while the MCU uploads firmware transparently.

---

*Hybrid RobotiX — San Diego, CA*
