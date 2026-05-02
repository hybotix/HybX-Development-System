# HybX Development System — Change Log
## Hybrid RobotiX

> *Hybrid RobotiX designs and creates intelligent technologies that empower people facing physical and accessibility challenges to live more independently and achieve more on their own terms.*

---

## v2.1 (dev/v2.1 — in progress)

### Breaking Changes

- **Docker removed entirely.** Apps no longer run in containers. All apps run as plain Python processes in the foreground. `arduino.app_utils` is no longer used or required.
- **`main.py` is no longer stored in the repo.** Versioned files (`main-vX.Y.Z.py`) are stored in the repo. `main.py` is a symlink created on the board by `project pull`.
- **`start` is interactive by design.** Apps run in the foreground with live stdin/stdout/stderr. `mon` and `stop` are retained but background mode is gone.

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

- HybX Build System: `HybXCompiler` + `HybXFlasher` replace `arduino-cli`
- Board definitions in JSON (`boards/uno-q.json`)
- `flash` standalone command
- Named binaries in `<board>/build/`
- Minimal output — only what the developer must see
- Per-project `hybx.json` with `kconfig_overrides`
- DMA-enabled i2c4 via `setup-dma` script
- `mon` command for monitoring app output
- `project pull --all` replaces `board sync --force`
- VL53L5CX 8x8 ranging with confidence values

---

*Hybrid RobotiX — San Diego, CA*
