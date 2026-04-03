# UNO Q Development System Design Document
## Hybrid RobotiX

---

## 1. Overview

The UNO Q Development System is a portable, repeatable development environment for the Arduino UNO Q. It replaces Arduino App Lab entirely with a clean, SSH-based workflow built around versioned Python bin commands, a single bootstrap script, and a strict separation of configuration from logic.

**Guiding philosophy:** maximum capability through clean architecture — every command has a single responsibility, every file is versioned, and nothing requires a GUI.

*"I. WILL. NEVER. GIVE. UP. OR. SURRENDER."*

---

## 2. Repository Structure

```
UNO-Q-Development-System/
  bin/          — Versioned Python bin commands
  docs/         — Design documents, known issues
  scripts/      — Bootstrap script (newrepo.bash template)
  README.md
```

The Development System is one of two repositories in the UNO Q ecosystem:

| Repository | Contents |
|------------|----------|
| [UNO-Q-Development-System](https://github.com/hybotix/UNO-Q-Development-System) | Bin commands, bootstrap, VSCode extension |
| [UNO-Q](https://github.com/hybotix/UNO-Q) | Arduino apps (sketches + Python controllers) |

---

## 3. Bootstrap

### 3.1 newrepo.bash

`scripts/newrepo.bash` is the single entry point for setting up a new UNO Q or rebuilding an existing one. It lives in `$HOME` on the UNO Q and is never stored in the repo itself — it must exist before the repos are cloned.

**First-time setup on a new UNO Q:**

```bash
cp ~/Repos/GitHub/hybotix/UNO-Q-Development-System/scripts/newrepo.bash ~/newrepo.bash
bash ~/newrepo.bash
```

**Subsequent resets** (after first `start` installs `~/bin/newrepo`):

```bash
newrepo
```

### 3.2 User-Configurable Variables

Only the top variables in `newrepo.bash` need editing for a new user or project:

```bash
REPO_DEST="$HOME/Repos/GitHub/hybotix"
REPO="https://github.com/hybotix/UNO-Q.git"
DEV_REPO="https://github.com/hybotix/UNO-Q-Development-System.git"
SECRETS_DEST="securesmars"
COMMANDS="addlib build clean list logs restart start stop"
```

Everything below the variables is generic infrastructure and never needs editing.

### 3.3 What newrepo.bash Does

1. Removes `~/Arduino`, `~/bin`, and `~/Repos`
2. Clones both repos into `~/Repos/GitHub/hybotix/`
3. Copies `Arduino/` from UNO-Q repo to `~/Arduino/`
4. Copies `bin/` from Development System repo to `~/bin/`
5. Copies `secrets.py.template` into each app listed in `SECRETS_DEST`
6. Creates versioned symlinks for all bin commands
7. On every `start`, also installs `~/bin/newrepo` from the repo

---

## 4. Bin Commands

All commands are versioned Python scripts in `~/bin/`, symlinked to the latest version by `newrepo.bash`.

### 4.1 Command Reference

| Command | Latest | Description |
|---------|--------|-------------|
| `start <app>` | v0.0.6 | Nuke Docker, clear cache, install newrepo, patch `$HOME` mount, launch app |
| `restart <app>` | v0.0.6 | Delegates entirely to `start` |
| `stop <app>` | v0.0.3 | Stop the running app |
| `logs <app>` | v0.0.3 | Show live app logs |
| `list` | v0.0.1 | List all available apps |
| `build <sketch>` | v0.0.1 | Compile sketch, auto-generate `sketch.yaml`, flash via OpenOCD |
| `addlib` | v0.0.1 | Search, install, list, or upgrade Arduino libraries |
| `clean <app>` | v0.0.1 | Full Docker nuke + cache clear + restart |
| `newrepo` | — | Re-bootstrap the UNO Q environment |

### 4.2 Last App Memory

All commands store the last used app name in `~/.last_app`. If no argument is provided, the last app is used automatically:

```bash
start matrix-bno    # starts matrix-bno, saves to ~/.last_app
restart             # restarts matrix-bno (from ~/.last_app)
logs                # shows logs for matrix-bno
stop                # stops matrix-bno
```

### 4.3 start — The Central Command

On every invocation `start`:

1. Saves the app name to `~/.last_app`
2. Removes the Docker container: `docker rm -f arduino-<app>-main-1`
3. Removes the Docker image: `docker rmi -f arduino-<app>-main`
4. Removes the `.cache/` directory inside the app folder
5. Installs `newrepo.bash` as `~/bin/newrepo`
6. Runs `arduino-app-cli app start <app_path>`
7. Waits for `.cache/app-compose.yaml` to be generated (up to 60 seconds)
8. Patches the compose file to mount `$HOME` into the container at the same path
9. Restarts the container with the patched compose file

The `$HOME` mount patch is critical — without it, Python apps cannot read or write files in `$HOME` (e.g. `~/.scd30-calibrated` calibration flags).

### 4.4 build — Sketch Compiler

1. Compiles with `arduino-cli compile --fqbn arduino:zephyr:unoq <path> -v`
2. Parses verbose output to extract library names and versions
3. Auto-generates `sketch.yaml` with the correct library profile
4. Flashes via `arduino-cli upload --profile default` (OpenOCD/SWD)

### 4.5 addlib — Library Management

```bash
addlib search "Adafruit SCD30"
addlib install "Adafruit SCD30"
addlib list
addlib upgrade
```

---

## 5. Versioning Conventions

- **Bin commands:** `command-vX.Y.Z.py` (e.g. `start-v0.0.6.py`)
- **Version bumps:** only files that changed get bumped
- **Symlinks:** always point to the latest version
- **No bash or shell scripts** — everything is Python
- **Configuration** at the top of each script in clearly named variables
- **JSON** for any structured configuration storage

---

## 6. Docker Management

### 6.1 Why Docker is Nuked on Every Start

The Docker image caches Python code at build time. Modifying `main.py` and simply restarting runs the old cached Python. Removing the container and image entirely forces a clean rebuild.

### 6.2 $HOME Mount Patch

The generated `app-compose.yaml` does not mount `$HOME` into the container. The `start` command patches it to add:

```yaml
volumes:
  - type: bind
    source: /home/arduino
    target: /home/arduino
```

The container is restarted with the patched file via `docker compose up -d --force-recreate`.

### 6.3 Known Docker Limitation

Apps cannot resolve local network hostnames (e.g. `pimqtt.local`) from inside Docker containers due to network isolation. See `docs/KNOWN_ISSUES.md` and Arduino issue #328.

---

## 7. VSCode Extension

The `uno-q-dev` extension brings all Development System commands into VSCode without requiring a terminal.

### 7.1 Architecture

Runs on the local machine and executes all commands via `ssh <host> <bin-command>` using the system `ssh` binary. No Remote-SSH extension or Node.js SSH library required.

### 7.2 Features

- **Command Palette** — all bin commands under `UNO Q:` prefix
- **Status bar** — current app name and running/stopped state; click to start
- **App picker** — queries `~/Arduino` over SSH, presents apps as quick-pick list
- **Live log streaming** — auto-streams logs into UNO Q output panel after start/restart
- **Library management** — addlib sub-menu for search, install, list, upgrade

### 7.3 Settings

| Setting | Default | Description |
|---------|---------|-------------|
| `unoQDev.sshHost` | `arduino@unoq.local` | SSH connection string |
| `unoQDev.appsPath` | `~/Arduino` | Apps directory on UNO Q |
| `unoQDev.sshKeyPath` | *(empty)* | SSH private key path |

### 7.4 Installation

```bash
"/Applications/Visual Studio Code.app/Contents/Resources/app/bin/code" \
  --install-extension uno-q-dev-0.1.0.vsix
```

---

## 8. Known Issues

See `docs/KNOWN_ISSUES.md` for current open issues:

- **Docker mDNS resolution** — `*.local` hostnames not resolvable inside containers (Arduino issue #328)
- **Infineon optigatrust I2C bus** — hardcoded to `/dev/i2c-1` (Infineon issue #26)

---

## 9. Roadmap

### Near Term
- Add `uno-q-dev` VSCode extension to this repo under `vscode/`
- Publish extension to VSCode Marketplace

### Medium Term
- Python replacement for `newrepo.bash` (eliminate last bash script)
- Extension: auto-detect apps without manual SSH query
- Extension: integrated sketch file picker for `build`

### Long Term
- Multi-board support
- Extension: MQTT topic monitor panel
- Extension: sensor data dashboard
