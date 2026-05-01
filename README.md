# HybX Development System v2.0
## Hybrid RobotiX

> *Hybrid RobotiX designs and creates intelligent technologies that empower people facing physical and accessibility challenges to live more independently and achieve more on their own terms.*

*"I. WILL. NEVER. GIVE. UP. OR. SURRENDER."*

*— Dale Weber, Founder, Hybrid RobotiX*

---

The HybX Development System is a complete, professional-grade development
environment for the **Arduino UNO Q**. It provides a clean Python and CLI
workflow for building, managing, and deploying Arduino apps entirely from the
command line. All commands run **natively on the UNO Q** over SSH, living
directly on the board's Debian Linux filesystem.

Built entirely in Python with versioned commands, a shared library system,
a board configuration manager, and direct Docker container control, HybX is
designed around one guiding philosophy: **clean architecture, zero vendor
lock-in, everything versioned, single source of truth.**

Hybrid RobotiX empowers developers to go beyond what standard development
systems allow — taking full control of the build pipeline, the hardware
interface, and the deployment lifecycle without being constrained by vendor
tools that cannot, will not, or refuse to provide what professional
development demands.

HybX exists because Arduino's build system stopped a developer who has never
liked limitations and never will. When a system tries to impose limits, Hybrid
RobotiX does not look for workarounds or back doors — if a way can be found to
exceed standard limitations, that is exactly what will happen, even if it means
being forced to create something better and replace the limiting system entirely.
`HybXCompiler`, `HybXFlasher`, and `HybXRunner` are the direct result of
that refusal to settle — and the VL53L5CX 8x8 ToF sensor is ranging today
because of it.

---

## What Was Replaced and Why

### arduino-cli → HybXCompiler + HybXFlasher

`arduino-cli` is used by Arduino's build pipeline to compile sketches and
flash binaries. It was replaced because:

- No way to force a truly clean rebuild from the command line
- Library changes were invisible — cached binaries reused silently
- Opaque caching layers spread across multiple locations

`HybXCompiler` always compiles fresh. `HybXFlasher` always flashes.
No caching. No surprises.

### arduino-app-cli → HybXRunner + docker logs

`arduino-app-cli` manages the Docker containers that run the Python side
of UNO Q apps. It was replaced because:

- `arduino-app-cli app start` cached compiled binaries by sketch hash —
  library changes were completely invisible, silently reusing old binaries
- No `--force-rebuild` or `--force-flash` flag
- `arduino-app-cli app logs` added unnecessary indirection
- Container startup failed silently when the build failed

`HybXRunner` manages Docker containers directly via the Python Docker API,
deriving its container configuration from `docker inspect` of known-good
containers. `mon` uses `docker logs -f` directly.

### logs → mon

The `logs` command was renamed to `mon` (monitor) in v2.0 — a shorter,
more descriptive name that doesn't conflict with the Unix `log` command.

---

## Commands

All commands run on the UNO Q itself over SSH.

| Command | Description |
|---------|-------------|
| `board` | Manage board configurations — add, use, remove, list, show, pat |
| `build` | Compile and flash a sketch via HybXCompiler + HybXFlasher |
| `clean` | Stop container, wipe cache, compile fresh, flash, start container |
| `libs` | Library manager — install, remove, upgrade, search, use |
| `list` | List all available apps for the active board |
| `mon` | Monitor live app output via `docker logs -f` |
| `project` | Manage projects — new, clone, list, show, use, rename, remove, push, pull |
| `restart` | Stop and restart the active app |
| `setup` | One-time system setup |
| `start` | Start an app container via HybXRunner |
| `stop` | Stop an app container |
| `update` | Pull latest repos, deploy lib/bin updates, invalidate stale caches |

`--log` flag available on `clean`, `start`, and `update` — writes all
output to `~/start.log` or `~/update.log` respectively. Ctrl+C traps
cleanly close the log and stop the app.

`FINALIZE` lives in `scripts/` only and must always be invoked by its
full path — it is intentionally never on PATH.

### board subcommands

| Subcommand | Description |
|------------|-------------|
| `board add <name>` | Add a new board configuration |
| `board use <name>` | Set the active board |
| `board show` | Show active board details |
| `board list` | List all configured boards |
| `board remove <name>` | Remove a board configuration |
| `board pat <token>` | Store GitHub PAT for push operations |
| `board pull` | Pull latest apps from GitHub to the board |
| `board pull <name>` | Pull a specific app from GitHub to the board |
| `board pull --force` | Pull and overwrite existing apps |
| `board pull --dry-run` | Preview what would be pulled without making changes |

### project subcommands

| Subcommand | Description |
|------------|-------------|
| `project new <type> <name>` | Create a new project scaffold |
| `project clone <source> <new>` | Clone an existing project to a new name |
| `project list` | List all projects for the active board |
| `project show` | Show the active project |
| `project use <name>` | Set the active project |
| `project rename <old> <new>` | Rename a project locally and in GitHub |
| `project remove <name>` | Remove a project from disk and GitHub |
| `project push` | Push active project edits to GitHub |
| `project push <name>` | Push a named project to GitHub |
| `project pull` | Pull active project from GitHub to the board |
| `project pull <name>` | Pull a named project from GitHub to the board |

### Command abbreviation

All commands and subcommands support prefix abbreviation — minimum 3 characters,
every character must be correct, and the prefix must be unambiguous:

```bash
project clo src dst      # project clone src dst
project ren old new      # project rename old new
project pus              # project push
project pul              # project pull
board pul --force        # board pull --force
```

The minimum prefix length is controlled by `HYBX_MIN_PREFIX` in `hybx_config.py`.
All current HybX commands are unambiguous at 3 characters.

For the full command reference see [`docs/COMMANDS.md`](docs/COMMANDS.md).

---

## Quick Start

On a new board, run the installer:

```bash
python3 scripts/install-v0.0.3.py
```

After installation, configure your board and pull apps from GitHub:

```bash
board add UNO-Q
board pull
```

Build and start an app:

```bash
build matrix-bno055
start matrix-bno055
mon
```

Or use `clean` for a guaranteed fresh compile + flash + start:

```bash
clean matrix-bno055
mon
```

---

## How It Works

Apps consist of two parts: an **Arduino sketch** (MCU side) and a **Python
controller** (Linux side). The two communicate over the
[Arduino RouterBridge](https://github.com/arduino/ArduinoCore-zephyr),
which lets the Python side call functions registered on the MCU and receive
data back. HybX manages the full lifecycle of both sides.

```
Your Mac / PC
    │
    │  SSH
    ▼
Arduino UNO Q  ──────────────────────────────────────────
    │                                                    │
    │  Debian Linux (ARM64)          STM32U5 MCU         │
    │  ~/bin/  — HybX commands       Arduino sketch      │
    │  ~/lib/  — shared modules      RouterBridge        │
    │  Python controller  ◄────────────────────────────► │
    │  HybXRunner (Docker)                               │
─────────────────────────────────────────────────────────
```

### Typical workflow

```bash
# Update system and pull latest app files from GitHub
update
board pull <app> --force

# Clean build — always compiles fresh, always flashes
clean <app>

# Monitor output
mon

# Push local edits back to GitHub
project push
```

---

## Shared Library Modules (~/lib/)

| Module | Description |
|--------|-------------|
| `hybx_config` | Board config, pull helpers, HybXTee, HybXTimer |
| `hybx_runner` | Docker container management (replaces arduino-app-cli) |
| `hybx_helpers` | App and library utilities |
| `compiler` | HybXCompiler — direct compilation pipeline, always fresh, no caching |
| `flasher` | HybXFlasher — direct OpenOCD flash, always flashes, no skip logic |

All modules are versioned (`module-vX.Y.Z.py`) with bare-name symlinks
(`module.py → module-vX.Y.Z.py`). `update` deploys the latest version
and relinks automatically.

---

## Library Management

`libs` is the single source of truth for all Arduino libraries on the board.

```bash
libs install "Adafruit BNO055"    # Install globally
libs use my-app "Adafruit BNO055" # Assign to project
libs list                          # List all libraries
libs upgrade                       # Upgrade all libraries
```

Removing a library that any project depends on is a hard block — no
`--force` flag. This keeps projects from silently breaking.

---

## Project Scaffolding

```bash
project new arduino my-sensor-app

# Clone an existing project to a new name
project clone monitor-vl53l5cx robot

# Push local edits back to GitHub
project push

# Pull latest version from GitHub
project pull

# Generated structure:
# my-sensor-app/
#   app.yaml          — name, icon, description
#   sketch/
#     sketch.ino      — MCU code (Arduino Bridge template)
#     sketch.yaml     — library dependencies
#   python/
#     main.py         — Python controller
```

---

## System Requirements

- Python 3.x
- git
- docker + docker compose
- arduino-cli (for `build` compile step)
- ssh / ssh-keygen

---

## VSCode Extension

The `hybx-dev` VSCode extension exposes all HybX commands in the Command
Palette under the `HybX:` prefix — no Remote-SSH extension required.

The extension `.vsix` is included in `vscode-extension/`.

| Setting | Default | Description |
|---------|---------|-------------|
| `hybxDev.sshHost` | `arduino@uno-q.local` | SSH connection string |
| `hybxDev.appsPath` | `~/Arduino/UNO-Q` | Apps directory on board |
| `hybxDev.sshKeyPath` | *(empty)* | SSH private key path |

---

## Repository Structure

```
HybX-Development-System/
  bin/                  — Versioned Python commands (symlinked into ~/bin)
  config/               — nano syntax highlighting configs
  docs/                 — COMMANDS.md, DESIGN.md, KNOWN_ISSUES.md
  lib/                  — Shared Python modules (hybx_config, hybx_runner, etc.)
  scripts/              — Installer, FINALIZE, and other one-time scripts
  vscode-extension/     — hybx-dev VSCode extension (.vsix)
  README.md             — This file
```

---

## Related Repositories

- **[UNO-Q](https://github.com/hybotix/UNO-Q)** — Arduino apps for the UNO Q
- **[hybx_vl53l5cx](https://github.com/hybotix/hybx_vl53l5cx)** — Minimal heap-free VL53L5CX library

---

## License

See [LICENSE](LICENSE).

---

*Hybrid RobotiX — San Diego*
