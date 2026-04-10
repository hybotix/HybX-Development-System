# HybX Development System — Command Reference
## Hybrid RobotiX

All commands are versioned Python scripts in `~/bin/`, symlinked to the latest version by `update`. Commands that operate on apps use the last active app if no app name is provided.

---

## Bootstrap

### `update`
Re-clones both repos, reinstalls all bin commands, and relinks symlinks. Run after any repo changes or on a fresh UNO Q.

```
update
```

---

## Board Management

### `board`
Manages board configurations stored in `~/.hybx/config.json`. All other commands read the active board from this config.

```
board list
board show
board add <name>
board set <name>
board remove <name>
```

| Subcommand | Description |
|------------|-------------|
| `list` | List all configured boards, showing active board with `*` |
| `show` | Show full details of the active board |
| `add <name>` | Add a new board — prompts for host, apps path, and repo |
| `set <name>` | Set the active board |
| `remove <name>` | Remove a board configuration |

**Notes:**
- `board add` prompts for GitHub username (stored once in config), SSH host, apps path, and repo name
- PAT is **never** stored — git operations use the system keychain
- Board name should match the physical board name (e.g. `UNO-Q`)

**Example:**
```
board add UNO-Q
board set UNO-Q
board show
```

---

## Project Management

### `project`
Manages projects for the active board. Projects live under the board's apps directory.

```
project list
project show
project new <type> <name>
project set <name>
project remove <name>
```

| Subcommand | Description |
|------------|-------------|
| `list` | List all projects for the active board, grouped by type |
| `list --names` | List project names only, one per line |
| `show` | Show the active project name and board |
| `new <type> <name>` | Create a new project scaffold |
| `set <name>` | Set the active project |
| `remove <name>` | Remove a project from local disk |

**Project types** (case insensitive):

| Type | Normalized | Directory |
|------|-----------|-----------|
| `arduino` | `Arduino` | `~/Arduino/UNO-Q/<name>/` |
| `micropython` | `MicroPython` | `~/MicroPython/<board>/<name>/` |
| `ros2` | `ROS2` | `~/ROS2/<name>/` |

**Scaffold created by `project new`:**
```
<name>/
  app.yaml          — App metadata
  sketch/
    sketch.ino      — MCU code (Arduino Bridge template)
    sketch.yaml     — Library dependencies
  python/
    main.py         — Python controller
    requirements.txt — Python dependencies
```

**Examples:**
```
project new arduino    lis3dh
project new arduino    matrix-lis3dh
project new micropython sensor-display
project show
project list
```

---

## App Lifecycle

### `start`
Pulls latest repos, nukes Docker, syncs Arduino apps to `$HOME`, installs `~/bin/update`, and starts the app. Skips recompile if sketch is unchanged — use `--compile` to force a recompile.

```
start <app_name>
start
start <app_name> --compile
start --compile
```

If no app name is given, uses the last active app. `--compile` forces a recompile even if the sketch has not changed.

**Examples:**
```
start matrix-lis3dh
start
start matrix-lis3dh --compile
```

---

### `stop`
Stops the running app.

```
stop <app_name>
stop
```

If no app name is given, uses the last active app.

---

### `restart`
Stops and restarts the app. Delegates to `start`.

```
restart <app_name>
restart
```

If no app name is given, uses the last active app.

---

### `logs`
Shows live app logs. Clears the screen first.

```
logs <app_name>
logs
```

If no app name is given, uses the last active app.

---

### `clean`
Full reset — stops the app, nukes Docker container and image, clears cache, then restarts.

```
clean <app_name>
clean
```

If no app name is given, uses the last active app.

---

### `list`
Lists all apps available for the active board using `arduino-app-cli`.

```
list
```

---

### `build`
Verifies all project libraries are installed, then compiles and uploads the sketch.
Library detection and sketch.yaml generation are handled entirely by `libs` --
`build` is compile-and-flash only.

```
build <sketch_path>
```

**Example:**
```
build ~/Arduino/UNO-Q/matrix-lis3dh/sketch/
```

---

## Library Management

### `libs`
The single source of truth for all Arduino libraries. Libraries are global to
the board. Projects declare which global libraries they use. A library cannot
be removed while any project still uses it.

`libs` owns `~/.hybx/libraries.json` and is the only command that writes
`sketch.yaml` library sections. Never bypass `libs` for library operations.

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
| `list` | List all installed libraries with versions and project usage |
| `search <n>` | Search Arduino Library Manager |
| `install <n>` | Install a library globally and record it in the registry |
| `remove <n>` | Remove a library -- hard blocked if any project still uses it |
| `upgrade` | Upgrade all installed libraries and refresh registry versions |
| `upgrade <n>` | Upgrade one library |
| `show <n>` | Show library details, dependencies, and which projects use it |
| `use <project> <n>` | Declare that a project uses a library; rewrites sketch.yaml |
| `unuse <project> <n>` | Remove a project's use of a library; rewrites sketch.yaml |
| `update <project>` | Rewrite one project's sketch.yaml from registry |
| `update --all` | Rewrite all projects' sketch.yaml files from registry |
| `sync` | Rebuild installed registry from arduino-cli (preserves project assignments) |
| `check <project>` | Verify all project libraries are installed -- used by build |

**Flags:**

| Flag | Description |
|------|-------------|
| `--json` | Machine-readable JSON output on stdout |
| `--confirm` | Skip interactive confirmation prompts |

**Workflow -- new library:**
```
libs install Adafruit LIS3DH
libs use matrix-lis3dh Adafruit LIS3DH
```

**Workflow -- remove a library:**
```
libs unuse matrix-lis3dh Adafruit LIS3DH
libs remove Adafruit LIS3DH
```

**Workflow -- fresh board setup:**
```
libs sync
libs use <project> <n>    (repeat for each project/library pair)
```

**Protection rules:**
- `libs remove` is a hard abort (exit 3) if any project uses the library
- `libs remove` is also blocked if the library is a dependency of another
  library that is itself in use by any project
- There is no --force flag -- protection cannot be bypassed

---


---

---

## Finalization

### `FINALIZE`
Permanently severs all ties with App Lab. Removes the `migrate` command
and destroys the App Lab library store entirely. This action is
**permanent and irreversible**.

Only run this after `migrate run` has completed, `libs list` confirms
all libraries are present, and all projects have been tested and verified.

**Hybrid RobotiX and the HybX Development System are NOT responsible
for any data loss, broken sketches, or missing libraries that result
from running this command.**

```
FINALIZE dryrun
FINALIZE run
```

| Subcommand | Description |
|------------|-------------|
| `dryrun` | Show exactly what will be removed. Touches nothing. |
| `run` | Permanently remove App Lab and migrate. IRREVERSIBLE. |

**Flags:**

| Flag | Description |
|------|-------------|
| `--json` | Machine-readable JSON output |
| `--confirm` | Skip non-critical prompts only |

**Confirmation phrase** (must be typed exactly):
```
I am ready to cut ties with AppLab
```

The confirmation phrase is **always** required regardless of `--confirm`.
There is no bypass.

**Readiness checks** (both must pass before `FINALIZE run` proceeds):
- `libraries.json` must exist and contain registered libraries
- `~/.arduino15/internal/` must exist (something to actually remove)

**What gets removed:**
- `~/bin/migrate` symlink
- All `migrate-v*.py` versioned files
- `~/.arduino15/internal/` — the App Lab library store entirely

**What is preserved:**
- `libraries.json` and all registry data
- All libraries reinstalled via `arduino-cli`
- Everything else in `~/.arduino15/`

---

## Migration

### `migrate`
One-time migration from App Lab library storage to arduino-cli management.
Always run `migrate dryrun` before `migrate run`. This command is intentionally
separate from `libs` because it is destructive and should only ever be run once.

```
migrate dryrun
migrate run
```

| Subcommand | Description |
|------------|-------------|
| `dryrun` | Scan libraries, verify each is findable via arduino-cli, show exactly what will happen. Touches nothing. |
| `run` | Re-verify, wipe ~/.arduino15/internal/, reinstall all libraries via arduino-cli, sync registry. |

**Flags:**

| Flag | Description |
|------|-------------|
| `--json` | Machine-readable JSON output |
| `--confirm` | Skip interactive confirmation prompts |

**Rules:**
- `migrate run` always re-runs verification internally before wiping anything
- If any libraries cannot be found in the Arduino Library Manager, explicit
  confirmation is required before proceeding — those libraries will be lost
- Project assignments in libraries.json are preserved throughout
- After migration, all library operations go through `libs` exclusively

**Workflow:**
```
migrate dryrun      -- review what will happen, check for unfindable libraries
migrate run         -- wipe and reinstall once satisfied with dryrun output
libs list           -- verify all libraries came back correctly
libs use <project> <n>   -- wire up project assignments
```

---

## System Setup

### `setup`
One-time system setup — installs nano syntax highlighting for `.ino` files.

```
setup
```

---

## Config File Reference

All configuration lives in `~/.hybx/` on the device. These files are local
and never committed to any repo.

### `~/.hybx/config.json`

Board and project configuration.

```json
{
  "boards": {
    "UNO-Q": {
      "host":      "arduino@uno-q.local",
      "apps_path": "/home/arduino/Arduino/UNO-Q",
      "repo":      "https://github.com/hybotix/UNO-Q.git"
    }
  },
  "active_board": "UNO-Q",
  "github_user": "hybotix",
  "board_projects": {
    "UNO-Q": {
      "active": "matrix-lis3dh"
    }
  }
}
```

**Important:** PAT is **never** stored in this file or anywhere else.

### `~/.hybx/libraries.json`

Library registry. Owned exclusively by `libs`. Never edit by hand.

```json
{
  "installed": {
    "Adafruit SCD30": {
      "version":      "1.0.5",
      "installed_at": "2026-04-10T07:45:00",
      "description":  "Adafruit SCD30 CO2 sensor library"
    },
    "Adafruit BusIO": {
      "version":      "1.16.1",
      "installed_at": "2026-04-10T07:45:00",
      "description":  "Adafruit BusIO I2C/SPI abstraction library"
    }
  },
  "dependencies": {
    "Adafruit SCD30": ["Adafruit BusIO", "Adafruit Unified Sensor"]
  },
  "projects": {
    "securesmars":   ["Adafruit Motor Shield V2", "Adafruit SCD30"],
    "matrix-bno055": ["Adafruit BNO055", "Adafruit BusIO"]
  }
}
```

**Structure:**
- `installed` -- global truth: every library on the board with version and install timestamp
- `dependencies` -- what each library pulled in transitively (used by remove protection)
- `projects` -- which libraries each project directly uses (drives sketch.yaml rewrites)

**Rules:**
- All keys are bare identifiers; only `description` values are quoted strings
- A library in `projects` cannot be removed until all references are cleared with `libs unuse`
- Run `libs sync` to rebuild `installed` from arduino-cli after any out-of-band changes
