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
All navigation and application logic runs on Linux (Python). The
Arduino sketch handles hardware access only and exposes it via Bridge
functions. This separation must be preserved and formalized in v3.0.

### State machines over monolithic loops
Robot navigation is implemented as an explicit state machine
(INIT → FORWARD → OBSTACLE → SCANNING → RECOVERING → FULL_BLOCK).
All complex behaviors in v3.0 should follow this pattern — explicit
states, explicit transitions, no hidden control flow.

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

## Future Hardware Notes

### Pan/Tilt Platform (VL53L5CX)
The VL53L5CX will eventually mount on a pan/tilt servo platform driven
by an Adafruit PCA9685 PWM Servo Driver (Wire1, 0x40). When added:
- Scanning will pan the sensor instead of rotating the whole robot
- Absolute look direction = pan_angle + BNO055_heading
- Bridge functions to add: set_pan(deg), set_tilt(deg), get_pan(), get_tilt()

### Motor Encoders
Motors have encoders. When integrated:
- Replace time-based backup (BACKUP_MS) with distance-based odometry
- Replace time-based rotation with encoder-counted turns
- Hookup point in code: handle_obstacle() in robot/python/main.py
