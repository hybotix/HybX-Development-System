# HybX Development System

**Hybrid RobotiX** — Arduino UNO Q development commands integrated directly into Visual Studio Code.

---

## Overview

The [Arduino UNO Q](https://store.arduino.cc/products/uno-q) is a dual-processor board combining a Qualcomm QRB2210 MPU running Debian Linux with an STM32U585 MCU for real-time control. The [HybX Development System](https://github.com/hybotix/HybX-Development-System) provides an App Lab-free development workflow using versioned Python bin commands over SSH.

This extension brings every Development System command into VSCode — no terminal required for routine operations.

---

## Features

### Command Palette Integration

All commands are available via `Cmd+Shift+P` (Mac) or `Ctrl+Shift+P` (Windows/Linux) under the `HybX:` prefix:

| Command | Description |
|---------|-------------|
| `HybX: Connect` | Test SSH connection to the UNO Q |
| `HybX: Start App` | Pick an app and start it (Docker nuke + cache clear + launch) |
| `HybX: Stop App` | Stop the currently running app |
| `HybX: Restart App` | Restart the current app |
| `HybX: Show Logs` | Stream live app logs into the UNO Q output panel |
| `HybX: Build Sketch` | Compile and flash a sketch to the STM32U585 MCU |
| `HybX: Add Library` | Search, install, list, or upgrade Arduino libraries |
| `HybX: List Apps` | List all available apps on the UNO Q |
| `HybX: Clean` | Full Docker nuke + cache clear + restart |
| `HybX: Run newrepo (Bootstrap)` | Re-clone repos and rebuild the UNO Q environment |

### Status Bar

A status bar item at the bottom of VSCode shows the current app state at a glance:

- `▶ HybX: matrix-bno` — app is running
- `■ HybX: matrix-bno (stopped)` — app is stopped
- `⬡ HybX` — no app selected

Click the status bar item to run **HybX: Start App**.

### App Picker

**Start App** and **Restart App** query the UNO Q over SSH and present your available apps as a quick-pick list. You can also type an app name manually.

### Live Log Streaming

After **Start App** or **Restart App**, logs stream automatically into the dedicated **UNO Q** output panel. Use **Show Logs** to re-attach at any time.

### Library Management

**Add Library** presents a sub-menu:

- `search` — search the Arduino library registry
- `install` — install a library by name
- `list` — list all installed libraries
- `upgrade` — upgrade all installed libraries

---

## Requirements

- Visual Studio Code 1.110.0 or later
- An Arduino UNO Q on the local network
- SSH access to the UNO Q (default: `arduino@unoq.local`)
- The [HybX Development System](https://github.com/hybotix/HybX-Development-System) installed on the UNO Q (`start`, `stop`, `restart`, `logs`, `build`, `addlib`, `list`, `clean`, `newrepo` in `~/bin`)
- `ssh` available in your system PATH (standard on macOS and Linux; use OpenSSH for Windows)

---

## Extension Settings

Configure via **File → Preferences → Settings** and search for `UNO Q`:

| Setting | Default | Description |
|---------|---------|-------------|
| `hybxDev.sshHost` | `arduino@unoq.local` | SSH connection string (`user@host`) |
| `hybxDev.appsPath` | `~/Arduino` | Path to the Arduino apps directory on the UNO Q |
| `hybxDev.sshKeyPath` | *(empty)* | Path to SSH private key. Leave empty to use your default SSH key (`~/.ssh/id_rsa` or `~/.ssh/id_ed25519`) |

### Example `settings.json`

```json
{
  "hybxDev.sshHost": "arduino@unoq.local",
  "hybxDev.appsPath": "~/Arduino",
  "hybxDev.sshKeyPath": ""
}
```

---

## Getting Started

### 1. Install the HybX Development System on the UNO Q

SSH into the UNO Q and clone the Development System repo:

```bash
ssh arduino@unoq.local
git clone https://github.com/hybotix/HybX-Development-System.git \
    ~/Repos/GitHub/hybotix/HybX-Development-System
```

Run the bootstrap script (first time only):

```bash
cp ~/Repos/GitHub/hybotix/HybX-Development-System/scripts/newrepo.bash ~/newrepo.bash
bash ~/newrepo.bash
```

### 2. Install this Extension

Install from the VSIX file:

```
Cmd+Shift+P → Extensions: Install from VSIX → select hybx-dev-0.1.0.vsix
```

Or search the marketplace for **HybX Development System**.

### 3. Verify the Connection

Open the Command Palette and run **HybX: Connect**. You should see:

```
─── connect ───────────────────────────
UNO Q connected — 6.6.47-yocto-standard
```

### 4. Start Your First App

Run **HybX: Start App**, pick an app from the list (e.g. `matrix-bno`), and watch the output panel stream live logs.

---

## How It Works

All commands run `ssh <host> <bin-command>` using the `ssh` binary on your local machine. No Node.js SSH library is involved — this is plain OpenSSH, the same connection you use in the terminal.

The extension does not require Remote-SSH or any other VSCode extension. It works from a plain local VSCode window as long as your machine can reach the UNO Q over SSH.

---

## The HybX Development System

This extension is the VSCode front-end for the [HybX Development System](https://github.com/hybotix/HybX-Development-System) — a set of versioned Python bin commands that replace Arduino App Lab entirely:

| Command | Version | What It Does |
|---------|---------|--------------|
| `start` | v0.0.6 | Stop, nuke Docker, clear cache, patch `$HOME` mount, launch app |
| `restart` | v0.0.6 | Delegates to `start` |
| `stop` | v0.0.3 | Stop the running app |
| `logs` | v0.0.3 | Show live app logs |
| `build` | v0.0.1 | Compile sketch, auto-generate `sketch.yaml`, flash via OpenOCD |
| `addlib` | v0.0.1 | Arduino library management via `arduino-cli` |
| `list` | v0.0.1 | List available apps |
| `clean` | v0.0.1 | Full Docker nuke + cache clear + restart |
| `newrepo` | — | Bootstrap: wipe and re-clone both repos, rebuild symlinks |

### Key Technical Details

- QWIIC connector on the UNO Q uses `Wire1`, not the default `Wire`
- `Bridge.provide()` calls must be declared before `setup()`
- Apps run inside Docker containers managed by `arduino-app-cli`
- The Development System patches the Docker compose file to mount `$HOME` inside the container
- All bin commands are versioned (`command-vX.Y.Z.py`) with unversioned symlinks

### Known Issues on the UNO Q

- **Docker mDNS resolution** — apps cannot resolve `*.local` hostnames inside Docker containers (Arduino issue [#328](https://github.com/arduino/arduino-app-cli/issues/328))
- **Infineon optigatrust I2C bus** — `liboptigatrust` hardcodes `/dev/i2c-1` (Infineon issue [#26](https://github.com/Infineon/python-optiga-trust/issues/26))

---

## Related Repositories

| Repository | Description |
|------------|-------------|
| [hybotix/HybX-Development-System](https://github.com/hybotix/HybX-Development-System) | The bin commands this extension wraps |
| [hybotix/UNO-Q](https://github.com/hybotix/UNOQ) | Arduino app examples and sketches |

---

## About

Built by **Dale Weber**, founder of [Hybrid RobotiX](https://github.com/hybotix) and The Accessibility Files. Licensed amateur radio operator **N7PKT**.

*"I. WILL. NEVER. GIVE. UP. OR. SURRENDER."*

---

## License

MIT License — see [LICENSE](LICENSE) for details.
