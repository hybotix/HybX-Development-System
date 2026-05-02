# HybX Development System — Change Log
## Hybrid RobotiX

> *Hybrid RobotiX designs and creates intelligent technologies that empower people facing physical and accessibility challenges to live more independently and achieve more on their own terms.*

---

## v2.1 (dev/v2.1 — in progress)

### Breaking Changes

- **Docker removed entirely.** Apps no longer run in containers. All apps run as plain Python processes in the foreground. `arduino.app_utils` is no longer used or required.
- **`main.py` is no longer stored in the repo.** Versioned files (`main-vX.Y.Z.py`) are stored in the repo. `main.py` is a symlink created on the board by `project pull`.
- **`start` is interactive by design.** Apps run in the foreground with live stdin/stdout/stderr. Background mode is gone.

### New Features

#### hybx_app (v1.0.0)
Native replacement for `arduino.app_utils`. Provides `Bridge` and `App` — the complete UNO Q Python runtime. Speaks msgpack-RPC directly to `/var/run/arduino-router.sock`. No Docker image required. Deployed to `~/lib/hybx_app.py` by `update`.

#### board branch
New subcommand: `board branch <name>`. Switches all repos (HybX-Development-System, UNO-Q, all HybX libraries) to the named branch and runs `update`. Stores `dev_branch` in `~/.hybx/config.json` as the single source of truth for the active branch.

#### Versioned file pattern for app scripts
App Python scripts follow the same versioning pattern as bin commands:
- Repo stores: `main-vX.Y.Z.py`, `visualizer-vX.Y.Z.py`, etc.
- Board has: `main.py` → symlink to latest versioned file
- `project pull` creates bare-name symlinks after copying from repo
- `project push` skips symlinks — only real versioned files go to repo
- `symlink_versioned_files()` added to `hybx_config` library

#### pcd shell function
`setup` now adds a `pcd` shell function to `~/.bashrc`:
- `pcd` — cd to the active project directory
- `pcd <name>` — cd to a named project directory

Required because Unix shells cannot have their working directory changed by an external command — only a shell function can do this. Added once by `setup`, never touched by `update`.

#### HybX venv
`update` now manages `~/.hybx/venv` — a Python virtual environment for running apps. Contains `msgpack` and any future runtime dependencies. Apps run with `~/.hybx/venv/bin/python3`.

#### get-vl53 app (formerly monitor)
Complete VL53L5CX data collection and labeling system:
- **`main-v1.0.1.py`** — Interactive data collector. Prompts for orientation label (`center`, `left`, `right`, `up`, `down`) and frame count before collection. Writes Edge Impulse-compatible CSV with label in filename: `<label>_<YYYYMMDD_HHMMSS>.csv`.
- **`visualizer-v1.0.2.py`** — Frame-by-frame data labeler. Centroid-based direction suggestion. Controls: A)ccept, S)kip, B)ack, Q)uit, Enter=advance, or type to override. Resumes from first unlabeled frame. Atomic save (temp file → rename).

### Changes to Existing Commands

#### start (v2.1.3)
- Runs `main.py` directly in the foreground — no Docker, no background process
- Updates both `last_app` and `board_projects` on every start
- Auto-creates versioned symlinks if `main.py` is missing

#### stop (v2.1.0)
- Sends SIGTERM to process by name — no Docker

#### mon (v2.1.0)
- Tails `~/logs/<app>.log` — no Docker logs

#### update (v2.1.0)
- Manages `~/.hybx/venv` — creates and installs dependencies
- Deploys `hybx_app` to `~/lib/`
- Never switches branches — always pulls currently checked-out branch

#### project (v2.1.4)
- `push` — skips symlinks, only real versioned files go to repo. Pushes to current branch.
- `pull` — calls `symlink_versioned_files()` after copy. Pulls from current branch.
- `pull --all` — calls `symlink_versioned_files()` for every project
- `rename` — calls `symlink_versioned_files()` after local rename. Updates `last_app` and `board_projects` if renamed project was active.
- `new` — scaffold updated to use `hybx_app` instead of `arduino.app_utils`

#### board (v2.1.0)
- `show` — displays active branch
- `branch <name>` — new subcommand (see above)

#### setup (v1.3.0)
- Adds `pcd` shell function to `~/.bashrc`

### Bug Fixes

- **pull_repo branch switching** (hybx_config v1.3.1, released as v2.0.1) — `pull_repo()` was hardcoded to switch to `dev/v2.0` on every pull. Fixed: always pulls currently checked-out branch, never switches.
- **project rename duplicate load_config** (v2.1.4) — `load_config()` was called twice.
- **project rename last_app not updated** (v2.1.3) — `start` saves `last_app` but not `board_projects`, so rename couldn't find the active project. Fixed: `start` now updates both.
- **start missing symlinks** (v2.1.3) — if `main.py` symlink was missing after a rename, `start` failed. Fixed: auto-creates symlinks from versioned files before failing.

### Library Changes

#### hybx_config (v1.3.4)
- `pull_repo()` — branch parameter removed. Always pulls current branch.
- `symlink_versioned_files(project_path)` — new public function. Scans project dirs for versioned `.py` files, creates bare-name symlinks to latest version. Only makes files in app root executable.

---

## v2.0.1 (patch — released)

### Bug Fixes

- **pull_repo branch switching** (hybx_config v1.3.1) — `pull_all_repos()` hardcoded `branch="dev/v2.0"` causing every `update` run to switch HybX-Development-System back to `dev/v2.0`. Fixed: branch parameter removed entirely. Always pulls current branch.

---

## v2.0 (released)

### Breaking Changes

- `arduino-cli` replaced by `HybXCompiler` and `HybXFlasher` for compile and flash
- `board sync` removed — replaced by `project push` and `project pull`
- `hybx` dispatcher removed — prefix matching built directly into each command
- `runner.py` renamed to `hybx_runner.py` for consistent `hybx_` naming
- `libs_helpers.py` renamed to `hybx_helpers.py`

### New Features

#### HybX Build System
- `HybXCompiler` — full 8-step build pipeline for Arduino UNO Q / Zephyr sketches. No `arduino-cli`.
- `HybXFlasher` — clean OpenOCD flash via SWD. Always writes to flash, never RAM.
- Board definitions in `boards/uno-q.json` — toolchain paths, compile flags, linker scripts, OpenOCD config.
- `flash` — new standalone flash command. Flashes last built binary without rebuilding.
- Per-project `hybx.json` with `kconfig_overrides` for DMA and other Kconfig settings.
- `setup-dma` script — patches Arduino board package for DMA-enabled I2C (required for VL53L5CX).
- Named binaries in `<board>/build/<project>.elf-zsk.bin`.

#### project push / project pull
- `project push` — commit and push project from board to GitHub
- `project pull` — pull project from GitHub to board
- `project pull --all` — pull all projects from GitHub to board (replaces `board sync --force`)
- `project clone <source> <new>` — clone an existing project to a new name
- `project rename <old> <new>` — rename a project locally and in git repo
- `project remove <name>` — remove project from local disk and GitHub (requires `YES`)

#### Command prefix matching
All commands support abbreviated subcommands (minimum 3 characters, unambiguous):
- `board lis` → `board list`
- `project pus` → `project push`
- `libs ins` → `libs install`

`HYBX_MIN_PREFIX` in `hybx_config` controls minimum prefix length.

#### board pat
- `board pat <token>` — store GitHub PAT in board config for `project push`

#### HybXRunner (v2.0 — superseded in v2.1)
Replaced `arduino-app-cli` for Docker container management. Managed containers directly without arduino-app-cli. Superseded entirely in v2.1 when Docker was removed.

#### VL53L5CX support
- Full 8x8 depth map via `monitor` app
- Confidence value calculation per zone
- DMA-enabled I2C for firmware upload

### Changes to Existing Commands

#### update (v2.0.0)
- Completely silent when everything is current
- Purges rogue versioned files not present in repo
- Removes retired commands from `~/bin/`
- Prefix symlinks for all commands

#### clean (v2.0.0)
- Calls `build` directly instead of `start --compile`
- Wipes `~/.cache/arduino/sketches/` to force full recompile

#### libs (v2.0.0)
- Prefix matching for all subcommands
- `libs embed` — `dir:` entry in `sketch.yaml` for HybX libraries
- HybX libraries install to `~/Arduino/libraries/` (not `hybx_libraries/`)

### Bug Fixes

- `project remove` — now shows unmistakable destructive operation warning
- `project clone` — lost in v2.0.5, restored in v2.0.6
- `clean` — does not start container if build failed
- `hybx_runner` — use `--mount` for LED/socket paths containing colons

---

## v1.2.2 (released)

### Changes

- **Privacy:** `update` masks `github_user` and SSH host in output — `***` instead of real values
- `HybXTimer` timing utility added to `hybx_config` — silent by default, enabled with `HYBX_TIMING=1`
- `build` — fix missing `HybXTimer` import
- Shared library modules versioned: `hybx_config-vX.Y.Z.py` pattern introduced

---

## v1.2.1 (released)

### Changes

- `HybXTimer` timing utility added to `hybx_config`
- Versioned shared modules — `update` handles versioned lib files

---

## v1.2 (released)

### New Features

- **VL53L5CX documentation** — ST ToF sensor compatibility table for v1.x vs v2.0. Full documentation of I2C firmware upload hang and DMA resolution path.
- `start-v1.2.0` — syncs tracked files for existing apps on every pull (sketch, python, app.yaml). Previously only new apps were copied; existing apps were never updated.
- `clean-v1.2.0` — clears sketch hash before calling `start --compile`, ensuring clean forces full recompile.
- `libs-v1.2.0` — HybX libraries use `dir:` sketch.yaml entries. Install to `~/Arduino/libraries/`.
- `update-v1.2.0` — purges rogue versioned files and retired `sync` command.
- Removed `os.system("clear")` from all commands — was wiping terminal context.

### Bug Fixes

- `libs embed` — `dir:` entry correctly written to `sketch.yaml`, no source copying
- `libs_helpers` — scans `~/Arduino/libraries/` as second lib root after `arduino-cli` install + `libs sync`

---

## v1.1.1 (released)

### New Features

- `board sync --force` — overwrite existing apps from repo (full board sync)
- `start-v1.1.0` — trust Docker container gone as stop signal; 60s timeout on app state clear
- `clean-v1.1.1` — nuke all Docker containers at start of clean

### Bug Fixes

- `start` — replace wipe-and-recreate with safe copy-only-new-apps to preserve local changes
- `hybx-test` — add `libs use/unuse/update/sync` tests, `--json` tests, `board sync`, `project new` types

---

## v1.0.1 (released)

### Bug Fixes

- `update` — add debug output to lib copy, show exact source path

---

## v1.0.0 (released)

### Initial Release

First stable release of the HybX Development System. Complete replacement for Arduino App Lab on the UNO Q.

#### Commands

- `board` — board configuration (add, use, remove, list, show)
- `build` — compile and flash via arduino-cli
- `clean` — full Docker reset + cache clear + restart
- `hybx-test` — self-contained test suite
- `libs` — library manager (install, remove, use, unuse, search, show, sync, upgrade)
- `list` — list available apps
- `migrate` — one-time migration from App Lab library storage to arduino-cli
- `project` — project management (new, use, show, list, clone, remove)
- `restart` — stop and restart active app
- `setup` — one-time system setup (nano syntax highlighting)
- `start` — pull repos, sync apps, start app
- `stop` — stop running app
- `update` — pull repos, deploy commands, refresh symlinks

#### Architecture

- All Python, no bash — every command is a versioned Python script
- Commands deployed to `~/bin/` as symlinks to versioned files
- Shared config in `~/.hybx/config.json` and `~/.hybx/libraries.json`
- `FINALIZE` — permanent App Lab severance tool (not on PATH, invoked by full path only)
- Installer: `scripts/install-v0.0.3.py` — full pre-flight summary, requires `YES`

---

*Hybrid RobotiX — San Diego, CA*
