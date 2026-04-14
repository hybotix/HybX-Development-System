# HybX Development System
## Hybrid RobotiX

> *Hybrid RobotiX designs and creates intelligent technologies that empower people facing physical and accessibility challenges to live more independently and achieve more on their own terms.*

The HybX Development System is a portable, board-aware development environment for the Arduino UNO Q and compatible boards. It replaces Arduino App Lab with a clean, SSH-based workflow built entirely in Python, with versioned commands, a library manager, and a VSCode extension.

---

## Quick Start

On a new board, run the installer:

```bash
python3 scripts/install-v0.0.3.py
```

The installer detects your platform and shell, shows a full pre-flight summary of every change it will make, and requires your confirmation before touching anything.

After installation, configure your first board:

```bash
board add UNO-Q
```

---

## Commands

| Command | Description |
|---------|-------------|
| `board` | Manage board configurations — add, use, remove, list, show, sync |
| `build` | Verify libraries, compile and flash a sketch |
| `clean` | Full Docker nuke, cache clear, and restart |
| `libs` | Library manager — install, remove, upgrade, search, sync |
| `list` | List available apps for the active board |
| `logs` | Show live app logs |
| `migrate` | One-time migration from App Lab to arduino-cli library management |
| `project` | Manage projects — new, list, show, set, remove |
| `restart` | Stop and restart the active app |
| `setup` | One-time system setup (nano syntax highlighting, etc.) |
| `start` | Pull repos, sync apps, and start an app |
| `stop` | Stop the running app |
| `update` | Pull the latest HybX Development System and refresh ~/bin |

`FINALIZE` lives in `scripts/` only and must always be invoked by its full path — it is intentionally never on PATH.

For full command reference see `docs/COMMANDS.md`.

---

## Repository Structure

```
HybX-Development-System/
  bin/                  — Versioned Python commands (symlinked into ~/bin)
  config/               — nano syntax highlighting configs
  docs/                 — COMMANDS.md, DESIGN.md, BOARDS.md, KNOWN_ISSUES.md
  lib/                  — Shared Python modules (hybx_config, libs_helpers)
  scripts/              — Installer, FINALIZE, and other one-time scripts
  vscode-extension/     — HybX VSCode extension (.vsix)
  README.md             — This file
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

## Related Repositories

- **[UNO-Q](https://github.com/hybotix/UNO-Q)** — Arduino apps for the UNO Q board

---

## License

See LICENSE file.
