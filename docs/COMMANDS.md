# HybX Development System — Command Reference
## Hybrid RobotiX

> *Hybrid RobotiX designs and creates intelligent technologies that empower people facing physical and accessibility challenges to live more independently and achieve more on their own terms.*

All commands are versioned Python scripts installed as symlinks in `~/bin/` on the active board. Symlinks always point to the latest version and are refreshed by `update`. Commands that operate on apps use the last active app if no app name is provided.

---

## Table of Contents

- [update](#update)
- [board](#board)
- [project](#project)
- [libs](#libs)
- [start](#start)
- [stop](#stop)
- [restart](#restart)
- [logs](#logs)
- [list](#list)
- [build](#build)
- [clean](#clean)
- [setup](#setup)
- [migrate](#migrate)
- [FINALIZE](#finalize)
- [Config File Reference](#config-file-reference)

---

## update

Pulls the latest HybX Development System and app repos, refreshes all versioned symlinks in `~/bin/`, and purges FINALIZE from `~/bin/` as a safety measure.

```
update
```

- Stashes any local uncommitted changes before pulling, pops them after
- Always sets executable permissions (755) on all copied bin files
- FINALIZE is purged from `~/bin/` on every update — it must never be on PATH

---

## board

Manages board configurations stored in `~/.hybx/config.json`. All other commands read the active board from this config.

```
board list
board show
board add <n>
board use <n>
board remove <n>
board sync
board sync --dry-run
```

| Subcommand | Description |
|------------|-------------|
| `list` | List all configured boards — active board marked with `*` |
| `show` | Show full details of the active board |
| `add <n>` | Add and configure a new board — shows pre-flight summary before making any changes |
| `use <n>` | Set the active board |
| `remove <n>` | Remove a board configuration |
| `sync` | Pull the board's app repo and copy any new apps into the apps directory |
| `sync --dry-run` | Preview what sync would add without making any changes |

**Notes:**
- `board add` prompts for all inputs first, then shows a complete pre-flight summary of every change to be made, then requires `YES` to proceed
- `board add` automatically clones or pulls the app repo after confirmation
- `board sync` only adds new apps — existing apps are never overwritten or modified
- `board sync --dry-run` only suggests running `board sync` when there are actually apps to add
- Board names are always stored in lowercase
- All confirmation prompts require uppercase `YES` or `NO` — deliberate intent required

**Example:**
```
board add UNO-Q
board use UNO-Q
board show
board sync --dry-run
board sync
```

---

## project

Manages projects for the active board. Projects live directly in the board's `apps_path`.

```
project list
project list --names
project show
project new <type> <n>
project set <n>
project remove <n>
```

| Subcommand | Description |
|------------|-------------|
| `list` | List all projects for the active board |
| `list --names` | List project names only, one per line |
| `show` | Show the active project name and board |
| `new <type> <n>` | Create a new project scaffold |
| `set <n>` | Set the active project |
| `remove <n>` | Remove a project from local disk — requires `YES` confirmation |

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
```

**Notes:**
- `project set` and `project remove` search the flat `apps_path` layout first, then type subdirectories — compatible with both layouts
- `project remove` requires uppercase `YES` confirmation — this deletes files from disk

**Examples:**
```
project new arduino matrix-bno055
project set matrix-bno055
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

Pulls latest repos, nukes Docker, syncs Arduino apps, installs `~/bin/update`, and starts the app. Skips recompile if the sketch is unchanged — use `--compile` to force a recompile.

```
start <app_name>
start
start <app_name> --compile
start --compile
```

If no app name is given, uses the last active app stored in `~/.hybx/last_app`. `--compile` forces a full recompile even if the sketch has not changed.

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

## logs

Shows live app logs. Clears the screen first.

```
logs <app_name>
logs
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
build <sketch_path>
```

**Example:**
```
build ~/Arduino/UNO-Q/matrix-bno055/sketch/
```

---

## clean

Full reset — stops the app, nukes the Docker container and image, clears the cache, then restarts.

```
clean <app_name>
clean
```

If no app name is given, uses the last active app.

---

## setup

One-time system setup. Installs nano syntax highlighting for `.ino` files.

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

Plain text file containing the name of the last app used by `start`, `stop`, `restart`, `logs`, or `clean`. Written automatically — never edit by hand.

---

*Hybrid RobotiX — San Diego*
