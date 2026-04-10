# HybX Development System
## Hybrid RobotiX

A portable, repeatable development environment for the Arduino UNO Q, built around versioned bin commands, a single bootstrap script, and a clean separation of configuration from logic.

---

## Quick Start

For a new UNO Q, copy the bootstrap script to `$HOME` and run it once:

```bash
cp scripts/update-v0.0.1.bash ~/update-v0.0.1.bash
# Edit the top variables to match your setup
bash ~/update-v0.0.1.bash
```

After the first `start`, `~/bin/update` is installed automatically and you can use `update` directly from then on.

---

## Repository Structure

```
HybX-Development-System/
  bin/                  — Versioned Python bin commands
  docs/                 — Design documents, inventory, known issues
  scripts/              — Bootstrap script (update-v0.0.1.bash template)
  vscode-extension/     — HybX Development System VSCode extension
  README.md             — This file
```

---

## Configuration

Only the top variables in `scripts/update-v0.0.1.bash` need editing for a new user:

```bash
REPO_DEST="$HOME/Repos/GitHub/hybotix"
REPO="https://github.com/hybotix/UNO-Q.git"
DEV_REPO="https://github.com/hybotix/HybX-Development-System.git"
SECRETS_DEST="securesmars"
COMMANDS="addlib build clean list logs restart start stop"
```

Everything below the variables is generic infrastructure — no changes needed.

---

## Bin Commands

| Command | Description |
|---------|-------------|
| `start <app>` | Nuke Docker, clear cache, install update, mount $HOME, start app |
| `restart <app>` | Delegates to start |
| `stop` | Stop the running app |
| `logs` | Show live app logs |
| `list` | List available apps |
| `build <app>` | Compile and flash sketch |
| `clean` | Full Docker nuke + cache clear + restart |
| `addlib` | Search, install, list, or upgrade Arduino libraries |

---

## VSCode Extension

The `vscode-extension/` directory contains the **HybX Development System** VSCode extension — a graphical front-end for all bin commands.

### Install

```bash
"/Applications/Visual Studio Code.app/Contents/Resources/app/bin/code" \
    --install-extension vscode-extension/hybx-dev-0.1.0.vsix
```

Or on Linux/Windows:

```bash
code --install-extension vscode-extension/hybx-dev-0.1.0.vsix
```

After installing, restart VSCode. All commands appear in the Command Palette under `HybX:`.

See `vscode-extension/README.md` for full documentation.

---

## Conventions

- All Python, no bash/shell scripts (except the one-time bootstrap)
- Versioned filenames: `command-vX.Y.Z.py`
- Configuration in variables at top of each script
- `update-v0.0.1.bash` lives in `$HOME` only — never in the repo root
- `start` installs `~/bin/update` on every run

---

## Related Repositories

- **[UNO-Q](https://github.com/hybotix/UNO-Q)** — Robot apps (Arduino sketches + Python controllers)

---

## License

See LICENSE file.
