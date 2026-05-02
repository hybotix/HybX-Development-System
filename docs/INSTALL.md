# HybX Development System — Installation Guide
## Hybrid RobotiX

> *Hybrid RobotiX designs and creates intelligent technologies that empower people facing physical and accessibility challenges to live more independently and achieve more on their own terms.*

This guide covers installing the HybX Development System on a new board.

> **Important:** HybX runs **natively on the Arduino UNO Q**. All commands are installed in `~/bin/` on the board's Debian Linux filesystem and execute directly on the board. You SSH into the board to use them — they are not tools that run on your Mac or PC.

---

## Table of Contents

1. [Prerequisites](#1-prerequisites)
2. [Supported Platforms](#2-supported-platforms)
3. [Supported Shells](#3-supported-shells)
4. [Installation](#4-installation)
5. [First Board Setup](#5-first-board-setup)
6. [Verifying the Installation](#6-verifying-the-installation)
7. [Updating](#7-updating)
8. [Uninstalling](#8-uninstalling)

---

## 1. Prerequisites

### All Platforms

- Python 3.x
- git
- ssh / ssh-keygen
- wget

### Linux ARM64 (UNO Q, Raspberry Pi, etc.)

- arduino-cli (pre-installed on UNO Q)
- keychain (installed automatically by the installer if not present)

### macOS

- Xcode Command Line Tools: `xcode-select --install`

---

## 2. Supported Platforms

| Platform | Architecture | Status |
|----------|-------------|--------|
| Linux ARM64 | aarch64 | ✅ Fully supported (UNO Q, Raspberry Pi 4B/5, etc.) |
| Linux x86_64 | x86_64 | ✅ Fully supported |
| macOS Apple Silicon | arm64 | ✅ Fully supported |
| macOS Intel | x86_64 | ✅ Fully supported |

---

## 3. Supported Shells

Shell is detected from the `$SHELL` environment variable — never assumed from the platform. Any shell can run on any platform.

| Shell | RC File |
|-------|---------|
| bash | `~/.bashrc` |
| zsh | `~/.zshrc` |
| fish | `~/.config/fish/config.fish` |
| other | `~/.bashrc` (with a warning) |

---

## 4. Installation

### Step 1 — Clone the HybX Development System

```bash
mkdir -p ~/Repos/GitHub/hybotix
cd ~/Repos/GitHub/hybotix
git clone https://github.com/hybotix/HybX-Development-System.git
```

### Step 2 — Run the Installer

```bash
python3 ~/Repos/GitHub/hybotix/HybX-Development-System/scripts/install-v0.0.3.py
```

The installer will:

1. Ask for your GitHub username
2. Ask for your apps repo name (Linux ARM64 only — e.g. `UNO-Q`)
3. Show a **complete pre-flight summary** of every change it will make
4. Ask for `YES` or `NO` confirmation — **nothing happens until you type `YES`**
5. If confirmed: set up SSH, clone repos, install commands to `~/bin`

### Step 3 — Activate the Shell Environment

**bash:**
```bash
source ~/.bashrc
```

**zsh:**
```bash
source ~/.zshrc
```

**fish:**
```bash
source ~/.config/fish/config.fish
```

Or simply open a new terminal window.

### Step 4 — Verify

```bash
board --version
update --version
```

---

## 5. First Board Setup

After installation, configure your first board:

```bash
board add UNO-Q
```

The `board add` command will:
1. Ask for the SSH host (default: `arduino@uno-q.local`)
2. Ask for the apps path on the board (default: `~/Arduino/UNO-Q`)
3. Ask for the app repo name (default: the board name)
4. Show a full pre-flight summary of everything that will happen
5. Require `YES` confirmation before proceeding
6. Clone or pull the app repo automatically

After adding a board:

```bash
# Verify the board is configured correctly
board show

# Sync the latest apps from the repo
project pull

# Set your first project
project use matrix-bno055
```

### Run setup

After adding a board, run `setup` once:

```bash
setup
source ~/.bashrc
```

`setup` installs:

**Arduino syntax highlighting for nano** — `ino.nanorc` installed to `~/.local/share/nano/`.

**`pcd` — project directory shortcut** — a shell function added to `~/.bashrc`:

```bash
pcd           # cd to the active project directory
pcd monitor   # cd to a named project directory
```

`pcd` is necessary because Unix shells cannot have their working directory
changed by an external command or script — only a shell function running
inside the current shell can do this. `setup` adds `pcd` to `~/.bashrc`
once, and it is available in every shell session thereafter.

`source ~/.bashrc` (or open a new shell) to activate it immediately.

---

## 6. Verifying the Installation

### Check all commands are available

```bash
for cmd in board build clean hybx-test libs list mon migrate project restart setup start stop update; do
    which $cmd && echo "$cmd: OK" || echo "$cmd: MISSING"
done
```

### Check ~/lib/ is deployed

```bash
ls ~/lib/
```

Should show: `hybx_config.py`, `libs_helpers.py`, `__init__.py`

### Run the test suite

```bash
# Default — read-only + hardware tests
hybx-test

# All tests including sandboxed
hybx-test --all

# Verbose output
hybx-test --verbose
```

Results are written to `~/hybx-test.log`.

### Check the config

```bash
board show
project show
libs list
```

---

## 7. Updating

To pull the latest HybX Development System and refresh all commands:

```bash
update
```

`update` will:
- Stash any local uncommitted changes
- Pull the latest repo
- Copy all new versioned command files to `~/bin/`
- Set executable permissions (755) on all copied files
- Relink all symlinks to the latest versioned file for each command
- Purge FINALIZE from `~/bin/` as a safety measure
- Pop any stashed changes

Run `update` from `$HOME` to avoid getcwd errors:

```bash
cd ~
update
```

---

## 8. Uninstalling

To remove the HybX Development System:

```bash
# Remove all commands from ~/bin
for cmd in board build clean hybx-test libs list mon migrate project restart setup start stop update; do
    rm -f ~/bin/$cmd ~/bin/${cmd}-v*.py
done

# Remove shared modules
rm -rf ~/lib

# Remove configuration
rm -rf ~/.hybx

# Remove the repo (optional)
rm -rf ~/Repos/GitHub/hybotix/HybX-Development-System

# Remove PATH line from shell rc (manual — open the file and remove the HybX block)
```

---

*Hybrid RobotiX — San Diego, CA*
