# HybX Development System
## Hybrid RobotiX

> *Hybrid RobotiX designs and creates intelligent technologies that empower people facing physical and accessibility challenges to live more independently and achieve more on their own terms.*

*"I. WILL. NEVER. GIVE. UP. OR. SURRENDER."*

---

The HybX Development System is a complete, professional-grade development environment for the Arduino UNO Q. For developers who love the command line, it is a natural alternative to AppLab — giving you a clean Python and CLI workflow for building, managing, and deploying Arduino apps. All commands run **natively on the UNO Q** over SSH, living directly on the board's Debian Linux filesystem.

Built entirely in Python with versioned commands, a library manager, a board configuration manager, a project manager, and a VSCode extension, the HybX Development System is designed around one guiding philosophy: **clean architecture, zero vendor lock-in, everything versioned, single source of truth.**

---

## What It Does

- **Build and flash** Arduino sketches directly from the command line via `arduino-cli` — no GUI required
- **Manage libraries** globally on the board with full dependency protection — no accidental removals, no broken projects
- **Manage projects** with scaffolding for Arduino, MicroPython, and ROS 2 app types
- **Start, stop, restart, and tail logs** for running apps in a single command
- **Sync apps** from GitHub repos to the board automatically
- **Integrate with VSCode** via the `hybx-dev` extension for a full graphical workflow

---

## Quick Start

On a new board, run the installer:

```bash
python3 scripts/install-v0.0.3.py
```

The installer detects your platform and shell, shows a complete pre-flight summary of every change it will make, and requires your explicit confirmation before touching anything.

After installation, configure your first board:

```bash
board add UNO-Q
board sync
```

Then build and start your first app:

```bash
build matrix-bno055
start matrix-bno055
logs matrix-bno055
```

---

## Commands

| Command | Description |
|---------|-------------|
| `board` | Manage board configurations — add, use, remove, list, show, sync |
| `build` | Verify libraries, compile and flash a sketch |
| `clean` | Full Docker reset, cache clear, and restart |
| `libs` | Library manager — install, remove, upgrade, search, use, sync |
| `list` | List all available apps for the active board |
| `logs` | Show live app logs |
| `migrate` | One-time migration from App Lab to arduino-cli library management |
| `project` | Manage projects — new, list, show, use, remove |
| `restart` | Stop and restart the active app |
| `setup` | One-time system setup (nano syntax highlighting, etc.) |
| `start` | Pull repos, sync apps, and start an app |
| `stop` | Stop the running app |
| `update` | Pull the latest HybX Development System and refresh `~/bin/` |

`FINALIZE` lives in `scripts/` only and must always be invoked by its full path — it is intentionally never on PATH.

For the full command reference see [`docs/COMMANDS.md`](docs/COMMANDS.md).

---

## How It Works

Apps consist of two parts: an **Arduino sketch** (MCU side) and a **Python controller** (Linux side). The two communicate over the [Arduino RouterBridge](https://github.com/arduino/ArduinoCore-zephyr), which lets the Python side call functions registered on the MCU and receive data back. The HybX Development System manages the full lifecycle of both sides.

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
    │                                                    │
─────────────────────────────────────────────────────────
```

---

## Library Management

`libs` is the single source of truth for all Arduino libraries on the board. It owns `~/.hybx/libraries.json` and is the **only** command that writes `sketch.yaml` library sections.

```bash
# Install a library globally
libs install "Adafruit BNO055"

# Assign it to a project (rewrites sketch.yaml automatically)
libs use my-app "Adafruit BNO055"

# List all installed libraries and their project assignments
libs list

# Upgrade all libraries
libs upgrade
```

Removing a library that any project depends on is a hard block — there is no `--force` flag. This keeps projects from silently breaking.

---

## Project Scaffolding

```bash
# Create a new Arduino Bridge app
project new arduino my-sensor-app

# Generated structure:
# my-sensor-app/
#   app.yaml          — name, icon, description
#   sketch/
#     sketch.ino      — MCU code (Arduino Bridge template)
#     sketch.yaml     — library dependencies (managed by libs)
#   python/
#     main.py         — Python controller
#     requirements.txt
```

---

## Supported Platforms

| Platform | Status |
|----------|--------|
| Linux ARM64 (UNO Q, Raspberry Pi 5, etc.) | ✅ Fully supported |
| Linux x86_64 | ✅ Fully supported |
| macOS (Apple Silicon) | ✅ Fully supported |
| macOS (Intel) | ✅ Fully supported |

## Supported Shells

| Shell | RC File |
|-------|---------|
| bash | `~/.bashrc` |
| zsh | `~/.zshrc` |
| fish | `~/.config/fish/config.fish` |

Shell is detected from `$SHELL` — never assumed from platform.

---

## System Requirements

- Python 3.x
- git
- ssh / ssh-keygen
- arduino-cli
- docker + docker compose
- keychain (Linux — installed automatically by the installer)

---

## VSCode Extension

The `hybx-dev` VSCode extension brings the full HybX Development System into your editor. It connects to the board over SSH and exposes all commands in the Command Palette under the `HybX:` prefix — no Remote-SSH extension required.

The extension `.vsix` is included in `vscode-extension/` and can be installed directly in VSCode via **Extensions → Install from VSIX**.

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
  docs/                 — COMMANDS.md, DESIGN.md, BOARDS.md, KNOWN_ISSUES.md
  lib/                  — Shared Python modules (hybx_config, libs_helpers)
  scripts/              — Installer, FINALIZE, and other one-time scripts
  vscode-extension/     — hybx-dev VSCode extension (.vsix)
  README.md             — This file
```

---

## Related Repositories

- **[UNO-Q](https://github.com/hybotix/UNO-Q)** — Arduino apps for the UNO Q board

---

## License

See [LICENSE](LICENSE).

---

*Hybrid RobotiX — San Diego*
