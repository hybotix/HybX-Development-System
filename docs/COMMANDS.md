# HybX Development System — Command Reference
## Hybrid RobotiX

All commands are versioned Python scripts in `~/bin/`, symlinked to the latest version by `newrepo`. Commands that operate on apps use the last active app if no app name is provided.

---

## Bootstrap

### `newrepo`
Re-clones both repos, reinstalls all bin commands, and relinks symlinks. Run after any repo changes or on a fresh UNO Q.

```
newrepo
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
Nukes Docker, clears cache, mounts `$HOME`, installs `~/bin/newrepo`, and starts the app.

```
start <app_name>
start
```

If no app name is given, uses the last active app.

**Example:**
```
start matrix-lis3dh
start
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
Compiles and uploads a sketch, and auto-generates `sketch.yaml` with detected libraries.

```
build <sketch_path>
```

**Example:**
```
build ~/Arduino/UNO-Q/matrix-lis3dh/sketch/
```

---

## Library Management

### `addlib`
Searches, installs, lists, and upgrades Arduino libraries via `arduino-cli`.

```
addlib search <name>
addlib install <name>
addlib list
addlib upgrade
```

| Subcommand | Description |
|------------|-------------|
| `search <name>` | Search Arduino Library Manager for a library |
| `install <name>` | Install a library |
| `list` | List all installed libraries |
| `upgrade` | Upgrade all installed libraries |

**Examples:**
```
addlib search "Adafruit LIS3DH"
addlib install "Adafruit LIS3DH"
addlib list
addlib upgrade
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

All configuration is stored in `~/.hybx/config.json`. This file is local to the device and never committed to any repo.

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
