# HybX Development System — Command Reference
## Hybrid RobotiX

> *Hybrid RobotiX designs and creates intelligent technologies that empower people facing physical and accessibility challenges to live more independently and achieve more on their own terms.*

All commands are versioned Python scripts that run **natively on the Arduino UNO Q** — installed as symlinks in `~/bin/` on the board's Debian Linux filesystem. They are not tools that run on a connected Mac or PC; they execute directly on the board, invoked over SSH from your development machine. Symlinks always point to the latest version and are refreshed by `update`. Commands that operate on apps use the last active app if no app name is provided.

---

## Table of Contents

- [update](#update)
- [board](#board)
- [project](#project)
- [libs](#libs)
- [start](#start)
- [stop](#stop)
- [restart](#restart)
- [mon](#mon)
- [list](#list)
- [build](#build)
- [clean](#clean)
- [setup](#setup)
- [hybx-test](#hybx-test)
- [migrate](#migrate)
- [FINALIZE](#finalize)
- [Config File Reference](#config-file-reference)

---

## update

Pulls the latest HybX Development System and app repos, refreshes all versioned symlinks in `~/bin/`, deploys shared modules to `~/lib/`, purges retired commands, and removes old versioned files from `~/bin/`.

```
update
```

- Stashes any local uncommitted changes before pulling, pops them after
- Copies all commands from repo `bin/` to `~/bin/`
- Copies all shared modules from repo `lib/` to `~/lib/`
- Removes old versioned files from `~/bin/` — only the currently linked version is kept
- Removes retired commands (`cache`, `boardsync`) from `~/bin/`
- Removes old shared module copies from `~/bin/` — they now live in `~/lib/`
- FINALIZE is purged from `~/bin/` on every update — it must never be on PATH

---

## board

Manages board configurations stored in `~/.hybx/config.json`. All other commands read the active board from this config. Board is configuration-only — all GitHub sync is handled by `project push` and `project pull`.

```
board list
board show
board add <n>
board use <n>
board remove <n>
board pat <token>
```

| Subcommand | Description |
|------------|-------------|
| `list` | List all configured boards — active board marked with `*` |
| `show` | Show full details of the active board |
| `add <n>` | Add and configure a new board — shows pre-flight summary before making any changes |
| `use <n>` | Set the active board |
| `remove <n>` | Remove a board configuration |
| `pat <token>` | Store a GitHub PAT for push operations |

**Notes:**
- `board add` prompts for all inputs first, then shows a complete pre-flight summary of every change to be made, then requires `YES` to proceed
- `board add` automatically clones or pulls the app repo after confirmation
- Board names are always stored in lowercase
- All confirmation prompts require uppercase `YES` or `NO` — deliberate intent required
- PAT is stored in `~/.hybx/config.json` and used automatically by `project push`

**Example:**
```
board add UNO-Q
board use UNO-Q
board pat ghp_yourpersonalaccesstoken
board show
```

---

## project

Manages projects for the active board. Projects live directly in the board's `apps_path`. Handles all GitHub sync via `push` and `pull`.

```
project list
project list --names
project show
project new <type> <n>
project use <n>
project clone <source> <new>
project rename <old> <new>
project remove <n>
project push
project push <n>
project pull
project pull <n>
project pull --all
```

| Subcommand | Description |
|------------|-------------|
| `list` | List all projects for the active board |
| `list --names` | List project names only, one per line |
| `show` | Show the active project name and board |
| `new <type> <n>` | Create a new project scaffold |
| `use <n>` | Set the active project |
| `clone <source> <new>` | Clone an existing project to a new name |
| `rename <old> <new>` | Rename a project locally and in the GitHub repo |
| `remove <n>` | Remove a project from local disk and GitHub repo — requires `YES` confirmation |
| `push` | Push active project edits to GitHub |
| `push <n>` | Push a named project to GitHub |
| `pull` | Pull active project from GitHub to the board |
| `pull <n>` | Pull a named project from GitHub to the board |
| `pull --all` | Pull ALL projects from GitHub to the board — replaces `board sync --force` |

**Project types** (case insensitive):

| Type | Description |
|------|-------------|
| `arduino` | Arduino sketch + Python Bridge controller |
| `micropython` | MicroPython application |
| `ros2` | ROS 2 node |

**Scaffold created by `project new arduino`:**
```
<n>/
  app.yaml              — App name, icon, description
  sketch/
    sketch.ino          — MCU code (Arduino Bridge template)
    sketch.yaml         — Library dependencies (managed by libs)
  python/
    main.py             — Python controller
    requirements.txt    — Python dependencies
  docs/
    README.md           — Hardware, Wiring, Calibration, Orientation, Notes
```

**Notes:**
- Every new project gets a `docs/README.md` stub automatically
- `project clone` adds `docs/README.md` if the source project didn't have one
- `project pull --all` pulls the entire repo and overwrites all local projects — use when setting up a new board or after major changes
- `project push` prompts for a commit message before pushing — default: `sync: update <name>`
- `project remove` requires uppercase `YES` confirmation — this deletes files from disk and GitHub
- `project rename` updates the project directory, git history, and active project config

**Examples:**
```
project new arduino robot
project use robot
project push
project pull --all
project clone monitor robot-v2
project rename old-name new-name
project list
project show
```

---

## libs

The single source of truth for all Arduino libraries. Libraries are global to the board. Projects declare which global libraries they use. A library cannot be removed while any project still uses it.

`libs` owns `~/.hybx/libraries.json` and is the **only** command that writes `sketch.yaml` library sections. Never bypass `libs` for library operations.

```
libs list
libs search <n>
libs install <n>
libs remove <n>
libs upgrade
libs upgrade <n>
libs show <n>
libs use <project> <n>
libs unuse <project> <n>
libs update <project>
libs update --all
libs sync
libs check <project>
```

| Subcommand | Description |
|------------|-------------|
| `list` | List all installed libraries — name, version, column-aligned, with projects that use each |
| `search <n>` | Search Arduino Library Manager |
| `install <n>` | Install a library globally and record it in the registry |
| `remove <n>` | Remove a library — hard blocked (exit 3) if any project still uses it |
| `upgrade` | Upgrade all installed libraries and refresh registry versions |
| `upgrade <n>` | Upgrade one specific library |
| `show <n>` | Show library details, dependencies, and which projects use it |
| `use <project> <n>` | Declare that a project uses a library — rewrites sketch.yaml |
| `unuse <project> <n>` | Remove a project's use of a library — rewrites sketch.yaml |
| `update <project>` | Rewrite one project's sketch.yaml from the registry |
| `update --all` | Rewrite all projects' sketch.yaml files from the registry |
| `sync` | Rebuild the installed registry from arduino-cli (preserves project assignments) |
| `check <project>` | Verify all project libraries are installed — called by build as a pre-flight check |

**Flags (all subcommands):**

| Flag | Description |
|------|-------------|
| `--json` | Machine-readable JSON output on stdout |
| `--confirm` | Skip interactive confirmation prompts |

**Protection rules:**
- `libs remove` is a hard abort (exit code 3) if any project uses the library
- `libs remove` is also blocked if the library is a dependency of another library that is itself in use
- There is no `--force` flag — protection cannot be bypassed

**Workflow — install and assign a new library:**
```
libs install "Adafruit BNO055"
libs use matrix-bno055 "Adafruit BNO055"
```

**Workflow — remove a library:**
```
libs unuse matrix-bno055 "Adafruit BNO055"
libs remove "Adafruit BNO055"
```

**Workflow — fresh board setup:**
```
libs sync
libs use <project> <n>    (repeat for each project/library pair)
```

---

## start

Pulls latest repos, syncs new Arduino apps, installs `~/bin/update`, and starts the app. Skips recompile if the sketch is unchanged — use `--compile` to force a recompile.

```
start <app_name>
start
start <app_name> --compile
start --compile
```

If no app name is given, uses the last active app stored in `~/.hybx/last_app`. `--compile` forces a full recompile even if the sketch has not changed.

**Notes:**
- App sync only copies new apps — existing apps are never overwritten or deleted, preserving local changes
- This matches `project pull` behavior

**Examples:**
```
start matrix-bno055
start
start matrix-bno055 --compile
```

---

## stop

Stops the running app.

```
stop <app_name>
stop
```

If no app name is given, uses the last active app.

---

## restart

Stops and restarts the app. Delegates to `start`.

```
restart <app_name>
restart
```

If no app name is given, uses the last active app.

---

## mon

Monitor a running app's output.

```
mon <app_name>
mon
```

If no app name is given, uses the last active app.

---

## list

Lists all apps available for the active board using `arduino-app-cli`.

```
list
```

---

## build

Verifies all project libraries are installed, then compiles and flashes the sketch. Library detection and `sketch.yaml` generation are handled entirely by `libs` — `build` is compile-and-flash only.

```
build
build <project_name>
build <sketch_path>
```

| Form | Description |
|------|-------------|
| `build` | Uses the active project |
| `build <project_name>` | Resolves to `<apps_path>/<project>/sketch/` automatically |
| `build <sketch_path>` | Full or relative path to sketch directory |

**Examples:**
```
build
build matrix-bno055
build ~/Arduino/UNO-Q/matrix-bno055/sketch/
```

---

## clean

Full reset — nukes ALL running Docker containers, stops the app, removes its Docker container and image, clears the cache, then restarts.

```
clean <app_name>
clean
```

If no app name is given, uses the last active app.

**Notes:**
- Runs `docker rm -f $(docker ps -aq)` first to clear any stuck containers from any app
- Use `clean` whenever an app gets stuck in a running state that `stop` cannot clear

---

## setup

One-time system setup. Installs nano syntax highlighting for `.ino` files to `~/.local/share/nano/`. No sudo required.

```
setup
```

---

## migrate

One-time migration from App Lab library storage to `arduino-cli` management. Always run `migrate dryrun` before `migrate run`. This command is intentionally separate from `libs` because it is destructive and should only ever be run once.

```
migrate dryrun
migrate run
```

| Subcommand | Description |
|------------|-------------|
| `dryrun` | Scan libraries, verify each is findable via arduino-cli, show exactly what will happen — touches nothing |
| `run` | Re-verify, wipe `~/.arduino15/internal/`, reinstall all libraries via arduino-cli, sync registry |

**Flags:**

| Flag | Description |
|------|-------------|
| `--json` | Machine-readable JSON output |
| `--confirm` | Skip interactive confirmation prompts |

**Workflow:**
```
migrate dryrun      — review output, check for unfindable libraries
migrate run         — wipe and reinstall once satisfied
libs list           — verify all libraries came back correctly
libs use <project> <n>   — wire up project assignments
```

---

## FINALIZE

> ⚠️ **FINALIZE is intentionally NOT on PATH and never installed to `~/bin/`.**
> It lives exclusively in `scripts/` and must be invoked by its full path.
> This is a deliberate safety design — FINALIZE must never be run accidentally,
> by tab-completion, or by any automated process.
> The inconvenience of typing the full path is the point.

Permanently severs all ties with App Lab. Removes the `migrate` command and destroys the App Lab library store entirely. **This action is permanent and irreversible.**

Only run this after `migrate run` has completed, `libs list` confirms all libraries are present, and all projects have been tested and verified.

```
python3 ~/Repos/GitHub/hybotix/HybX-Development-System/scripts/FINALIZE-v0.0.1.py dryrun
python3 ~/Repos/GitHub/hybotix/HybX-Development-System/scripts/FINALIZE-v0.0.1.py run
```

| Subcommand | Description |
|------------|-------------|
| `dryrun` | Show exactly what will be removed — touches nothing |
| `run` | Permanently remove App Lab and migrate — **IRREVERSIBLE** |

**Confirmation phrase** (must be typed exactly):
```
I am ready to cut ties with AppLab
```

The confirmation phrase is **always** required. There is no bypass, even with `--confirm`.

**Readiness checks** (both must pass before `FINALIZE run` proceeds):
- `libraries.json` must exist and contain registered libraries
- `~/.arduino15/internal/` must exist

**What gets removed:**
- All `migrate-v*.py` versioned files and the `~/bin/migrate` symlink
- `~/.arduino15/internal/` — the App Lab library store — entirely

**What is preserved:**
- `libraries.json` and all registry data
- All libraries reinstalled via `arduino-cli`
- Everything else in `~/.arduino15/`

---

---

## libs install-git

Install a HybX library (not in the Arduino Library Manager) from a git URL.

```
libs install-git <url>
```

Clones the repo into `~/Arduino/hybx_libraries/<lib_name>/`. If already cloned, runs `git pull` instead. Reads `library.properties` and registers the library in `~/.hybx/libraries.json` under the `"hybx"` section.

Does **not** add the library to `sketch.yaml` — `arduino-app-cli` cannot resolve HybX libraries from the Library Manager. Use `libs embed` to embed the library source into a project.

**Example:**
```
libs install-git https://github.com/hybotix/hybx_vl53l5cx.git
```

---

## libs embed

Link an installed HybX library into a project by adding a `dir:` entry to `sketch.yaml`.

```
libs embed <project> <lib_name>
```

arduino-cli sketch profiles support `dir: /path/to/library` references (`LocalLibrary` RPC type). arduino-cli compiles these using `RecursiveLayout` — `src/` subdirectories are compiled recursively. This is the correct, supported mechanism for local libraries not in the Arduino Library Manager.

`libs embed` does three things:
1. Verifies the library is installed in `~/Arduino/libraries/`
2. Records the project in `libraries.json` under `hybx[lib][embedded_in]`
3. Rewrites `sketch.yaml` to add a `dir:` entry pointing to the install path

The sketch uses `#include <lib_name.h>` (angle brackets — it is a proper installed library).

**Example:**
```
libs embed monitor-vl53l5cx hybx_vl53l5cx
```

Result in `sketch.yaml`:
```yaml
libraries:
  - dir: /home/arduino/Arduino/libraries/hybx_vl53l5cx
```

**Workflow — adding a new HybX library to a project:**
```
libs install-git https://github.com/hybotix/hybx_vl53l5cx.git
libs embed monitor-vl53l5cx hybx_vl53l5cx
# sketch.ino already has: #include <hybx_vl53l5cx.h>
start monitor-vl53l5cx
```

**Workflow — updating after upstream changes:**
```
# update pulls all HybX library repos automatically — no manual step needed
update
restart monitor-vl53l5cx
```

---

## hybx-test

Runs the complete HybX test suite. Tests every command and subcommand natively on the board. All output is written to `~/hybx-test.log`. A lock file `~/hybx-test.lock` prevents concurrent runs.

```
hybx-test
hybx-test --all
hybx-test --verbose
hybx-test --all --verbose
```

| Flag | Description |
|------|-------------|
| *(none)* | Run all read-only and hardware tests |
| `--all` | Also run sandboxed tests (creates/destroys temporary fixtures) |
| `--verbose` | Show full command output for each test |

**Notes:**
- Log file `~/hybx-test.log` is deleted and recreated on every run
- Only `migrate` is skipped — one-time destructive operation
- All commands tested in every supported calling mode — full pathing coverage
- Sandboxed tests save and restore active project and last app

---

## Config File Reference

All configuration lives in `~/.hybx/` on the device. These files are local to each board and are never committed to any repo.

### `~/.hybx/config.json`

Board and project configuration. Written by `board` and `project` commands.

```json
{
  "boards": {
    "uno-q": {
      "host":      "arduino@uno-q.local",
      "apps_path": "/home/arduino/Arduino/UNO-Q",
      "repo":      "https://github.com/hybotix/UNO-Q.git"
    }
  },
  "active_board": "uno-q",
  "github_user":  "hybotix",
  "board_projects": {
    "uno-q": {
      "active": "matrix-bno055"
    }
  }
}
```

**Notes:**
- Board names are always lowercase in the config
- PAT is **never** stored here or anywhere on disk
- `board_projects` tracks the active project per board independently

### `~/.hybx/libraries.json`

Library registry. Owned exclusively by `libs`. **Never edit by hand.**

```json
{
  "installed": {
    "Adafruit SCD30": {
      "version":      "1.0.5",
      "installed_at": "2026-04-10T07:45:00",
      "description":  "Adafruit SCD30 CO2 sensor library"
    }
  },
  "dependencies": {
    "Adafruit SCD30": ["Adafruit BusIO", "Adafruit Unified Sensor"]
  },
  "projects": {
    "matrix-bno055": ["Adafruit BNO055", "Adafruit BusIO"]
  }
}
```

**Structure:**
- `installed` — global truth: every library on the board with version and install timestamp
- `dependencies` — transitive dependencies (used by remove protection)
- `projects` — which libraries each project directly uses (drives `sketch.yaml` rewrites)

### `~/.hybx/last_app`

Plain text file containing the name of the last app used by `start`, `stop`, `restart`, `mon`, or `clean`. Written automatically — never edit by hand.

---

*Hybrid RobotiX — San Diego*

---

## Command Abbreviation

HybX supports abbreviated command and subcommand names. Any prefix of a
command or subcommand is accepted, as long as:

1. The prefix is at least `HYBX_MIN_PREFIX` characters long (default: 3)
2. Every character typed is correct
3. The prefix is unambiguous — only one command starts with it

The minimum prefix length is defined in `hybx_config.py` as `HYBX_MIN_PREFIX`.
To change it, update that constant and run `update`.

### Top-level command abbreviation (via `hybx` dispatcher)

```bash
hybx cle vl53-diag       # → clean vl53-diag
hybx upd                 # → update
hybx mon                 # → mon (exact match)
hybx bui monitor-vl53l5cx  # → build monitor-vl53l5cx
```

### Subcommand abbreviation (direct command usage)

Subcommands within `board`, `project`, and `libs` also support prefix matching:

```bash
board lis                # → board list
board sho                # → board show
board pat                # → board pat

project lis              # → project list
project pus              # → project push
project pul              # → project pull
project pul --all        # → project pull --all
project pul robot        # → project pull robot
project clo monitor robot  # → project clone monitor robot
project ren old-name new-name  # → project rename
project rem myapp        # → project remove
```

### Rules

- Minimum 3 characters (configurable via `HYBX_MIN_PREFIX`)
- Every character must be correct — partial matches must be a true prefix
- Exact matches always take priority over prefix matches
- If ambiguous, all matching commands are shown and the command exits

### Why this feature exists

Abbreviated commands are standard in professional developer tools (git,
kubectl, docker, etc.). HybX follows the same convention — you type less,
the tool figures out what you mean, and you stay in flow. All current HybX
commands are unambiguous at 3 characters.
