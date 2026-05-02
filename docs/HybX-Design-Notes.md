# HybX v3.0 Design Notes
Hybrid RobotiX — Dale Weber <hybotix@hybridrobotix.io>

This document captures design insights, principles, and decisions made
during v2.0 development that should inform the architecture and UX of
HybX v3.0. Add to this document whenever a design insight surfaces.

---

## Core Philosophy

- **Keep developers in the flow.** No command or UI action should force
  a developer to context-switch or do something outside their normal
  workflow. Every friction point in v2.0 is a design requirement for v3.0.

- **Intuitive naming over descriptive naming.** Commands and UI elements
  should use vocabulary developers already know. If it needs explanation,
  the name is wrong.

- **Symmetry matters.** Paired operations should have paired names.
  `pull`/`push`, `start`/`stop`, `build`/`clean` — the relationship
  should be obvious without documentation.

---

## Command Design Principles

### pull / push symmetry (2026-05-01)
`board sync` was renamed to `board pull` because `sync` was ambiguous
about direction. `pull` and `push` are a natural pair every developer
already understands from git. The v3.0 GUI should reflect this same
symmetry — a Pull button and a Push button, not a Sync button.

### Git output must always be visible (2026-05-01)
Silent git failures caused `project clone` to appear to succeed while
never pushing to GitHub. In v2.0 this was fixed by removing
`capture_output=True` from all git calls. In v3.0, the GUI must display
git output in real time — never hide it behind a spinner with only a
success/failure indicator.

### Error messages must be actionable (2026-05-01)
Every error message in HybX must tell the developer exactly what went
wrong AND how to fix it. "ERROR: git push failed" is not acceptable.
"ERROR: git push failed — committed locally but NOT on GitHub.
Fix: cd <path> && git push" is acceptable.

---

## Architecture Principles

### Linux-side logic, hardware-side I/O
All application logic runs on Linux (Python). The Arduino sketch handles
hardware access only and exposes it via Bridge functions. This separation
must be preserved and formalized in v3.0.

---

## v3.0 Technology Decisions

### Language: Go
v3.0 GUI will be built in Go for the following reasons:
- Compiled to native binaries — fast and responsive on all platforms
- Built-in concurrency (goroutines) — handles SSH, MQTT, serial, and
  UI simultaneously without GIL limitations
- Single binary output — no installer complexity
- Cross-platform: Mac, Windows, Linux

### GUI Framework: Fyne
Fyne is a cross-platform GUI toolkit written in Go. It produces
native-feeling applications on all platforms and handles HiDPI/scaling
correctly — solving the display scaling issues encountered with VSCode.

### Must be cross-platform
The v3.0 GUI must run identically on Mac, Windows, and Linux.
No platform-specific code in the UI layer.

---

## Known Pain Points in v2.0 (to fix in v3.0)

- VSCode Remote SSH does not source ~/.bashrc for non-interactive shells,
  requiring `bash -ic` workarounds in the extension.
- VSCode UI does not scale correctly on high-DPI external monitors.
- Extension management in VSCode adds friction for developers.
- No native remote file editing without extensions.

---

## v2.1 Roadmap

### HybX Interactive Shell
A `hybx` command that launches a persistent shell understanding all
HybX commands with abbreviation support. Instead of typing full
commands repeatedly, the developer stays in one context:

```
$ hybx
HybX Development System v2.1
Board: uno-q (arduino@uno-q.local)
Project: robot

hybx> pr pu        ← abbreviates to: project push
hybx> b sh         ← abbreviates to: board show
```

Features:
- Command and subcommand abbreviation (reuses resolve_subcommand())
- Active board and project shown in prompt
- Command history (up arrow)
- Tab completion on commands and project names
- Built with Python prompt_toolkit library

This also finalizes the v3.0 GUI API — every command the shell
understands becomes a button or menu item in the GUI.

### Motor Encoders
When motor encoders are integrated, replace time-based behaviors with
encoder-counted odometry. See robot/docs/README.md for details.

---

## HybX Interactive Shell (2026-05-01)

### Concept
A `hybx` interactive shell that a developer invokes once and stays in,
rather than typing full commands each time. Understands all HybX commands
and supports abbreviation of both command and subcommand.

### Example usage
```
$ hybx
HybX Development System v2.0
Board: uno-q (arduino@uno-q.local)
Project: robot

hybx> project push
hybx> pr pu          <- abbreviation
hybx> p pu           <- shorter abbreviation
hybx> board show
hybx> b sh
hybx> exit
```

### Features
- All existing bin commands work natively inside the shell
- Abbreviation of both command and subcommand using the existing
  resolve_subcommand() logic already in hybx_config
- Active board and project shown in the prompt at all times
- Command history (up arrow)
- Tab completion on commands and project names
- Built with Python prompt_toolkit for history, completion, and
  syntax highlighting in the shell itself

### Why this matters for v3.0
The shell's command vocabulary becomes the API that the v3.0 GUI is
built on. Every command the shell understands, the GUI exposes as a
button or menu item. Building the shell first validates the command
API before committing it to a GUI.

### Implementation notes
- Python prompt_toolkit library is the right tool for this
- resolve_subcommand() in hybx_config already handles abbreviation —
  apply it at the top level for the shell command too
- The shell prompt should always show: board name, project name, and
  connection status

---

## HybX Command Interpreter — v2.1 Target (2026-05-01)

### Decision
The `hybx` interactive shell concept is confirmed for v2.1 — not v3.0.
v2.0 features are frozen at current state for release. v2.1 headline
feature is the `hybx` interpreter.

### Vision
A single `hybx` command starts an interpreter at the beginning of every
development session. The `hybx> ` prompt makes it clear the developer
is inside the HybX environment, not at the shell level.

```
$ hybx
HybX Development System v2.1
Board: uno-q (arduino@uno-q.local)  Project: robot

hybx> project push
hybx> clean robot
hybx> mon
hybx> exit
$
```

### Key insight
The interpreter IS HybX. The underlying bin scripts become implementation
details — the interpreter is the user-facing interface. This eliminates:
- PATH issues entirely
- Shell quoting headaches
- The need for the VSCode extension to manage PATH
- Inconsistency between how commands are invoked

### Long-term path
The interpreter could eventually grow into the entire HybX Development
System as a single cohesive program — no separate bin scripts, no
symlink management, no versioned files. Just `hybx`.

### Implementation plan for v2.1
- Single `hybx` entry point script installed to ~/bin
- Imports all existing cmd_* functions from bin scripts directly
- prompt_toolkit for history, tab completion, syntax highlighting
- resolve_subcommand() handles abbreviation at top level too
- Prompt shows: board name, project name, connection status
- `exit` or Ctrl+D returns to shell

### v2.0 freeze
All current features are frozen. No new commands or behavior changes
until v2.1. Outstanding items for v2.1 planning:
- hybx interpreter (above)
- Separate VSCode extension into its own repo
- Full audit of all docs for consistency

---

## Version Roadmap (2026-05-01)

### v2.0 — Current (Feature Frozen)
All current features as implemented. Ready for release.

### v2.1 — HybX Interpreter
The `hybx` interactive shell as the primary user interface.
Single entry point, built-in abbreviation, prompt_toolkit, full
session context in the prompt.

### v2.2 — Edge Impulse Integration
Complete Edge Impulse integration for on-device ML inferencing.
Blocked pending Edge Impulse account resolution.

Potential scope:
- `hybx ei` subcommands for model management
- Deploy Edge Impulse models to UNO Q via HybX workflow
- Integration with the VL53L5CX and BNO055 sensor data pipeline
- On-device inferencing via the Arduino sketch / Python Bridge pattern

### v3.0 — Native Cross-Platform GUI
Go + Fyne GUI application. Cross-platform: Mac, Windows, Linux.
Built on the command vocabulary established by the v2.1 interpreter.

---

## ML Inferencing

Edge Impulse (v2.2) and Google LiteRT are the primary ML platforms under
evaluation. See robot/docs/README.md in the UNO-Q repo for full details
on the inferencing strategy, data collection pipeline, and Hailo-10H
evaluation questions.

---

## v2.1 — Drop Docker for App Execution (2026-05-02)

### Decision
Drop Docker entirely for UNO Q app execution in v2.1. Every app runs
as a direct Python process with full TTY, stdin, stdout, and stderr
connected to the developer's SSH session.

### Why Docker was used originally
Arduino chose Docker for `arduino-app-cli` for dependency isolation,
reproducibility, and security sandboxing. HybX inherited this model
when HybXRunner replaced arduino-app-cli.

### Why Docker is no longer needed
- **Dependency isolation** — already handled by per-app Python venv
- **Security** — UNO Q is a single-developer board, not a multi-tenant server
- **Restart policy** — HybX manages restart explicitly via `restart` command
- **Resource limits** — never been a concern on the UNO Q

### What Docker actually does (from HybXRunner analysis)
The container mounts and wires up:
1. `/var/run/arduino-router.sock` — RouterBridge Unix socket (MCU ↔ Python)
2. `msgpack-rpc-router:host-gateway` — extra hosts entry for router hostname
3. `ghcr.io/arduino/app-bricks/python-apps-base:0.8.0` — Arduino base image
   with `arduino` Python package pre-installed
4. `/sys/class/leds/*` — LED control mounts
5. Group adds: 44, 29, 991, 20, 1001 — serial, GPIO, I2C access

### None of this requires Docker
- Router socket — direct filesystem access, no container needed
- `msgpack-rpc-router` hostname — add once to `/etc/hosts`, done forever
- `arduino` Python package — install directly into the app venv
- LED mounts — direct filesystem access
- Group memberships — set on the arduino user account, not per-container

### v2.1 Implementation Plan

**Replace HybXRunner with a direct process launcher:**
- Activate the app venv
- Run `python3 python/main.py` directly
- Full TTY attached — stdin/stdout/stderr all connected
- PID file written to `~/.hybx/<app>.pid` for stop/restart

**`start`** — activate venv, exec Python process, write PID file

**`stop`** — read PID file, send SIGTERM, wait for clean exit

**`restart`** — stop + start

**`mon`** — no longer needed for most apps since output goes directly
to the terminal. Keep as an alias for compatibility.

**`/etc/hosts`** — add `msgpack-rpc-router` entry once during `setup`

**`setup`** — install `arduino` package into each app venv directly

### Benefits
- Full interactivity — every app gets stdin automatically
- No Docker daemon dependency
- No container overhead or startup delay
- Simpler `start`, `stop`, `restart` implementation
- `input()`, menus, prompts all work natively
- No `mon` required — output is already in your terminal
- One less thing that can go wrong
