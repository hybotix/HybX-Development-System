# Contributing to HybX Development System
## Hybrid RobotiX

First — thank you. Every contribution, bug report, idea, and piece of
constructive feedback makes this system better for everyone who uses it.

*"I. WILL. NEVER. GIVE. UP. OR. SURRENDER."*

---

## Philosophy

The HybX Development System exists to replace App Lab entirely and give
developers full, clean, reproducible control over the Arduino UNO Q
platform. Every contribution should move the system further in that
direction — cleaner, more reliable, more capable, zero vendor lock-in.

---

## What We Welcome

- **Bug fixes** — if something is broken, tell us or fix it
- **New commands** — if you need a capability that doesn't exist, build it
- **Improvements to existing commands** — better output, better error handling,
  better reliability
- **Documentation improvements** — if something is unclear, fix it
- **Test coverage** — we have none yet; help us build it
- **Ideas and discussion** — open an issue, start a conversation

No contribution is too small. A typo fix is welcome. A one-line improvement
is welcome. A completely new command is welcome.

---

## Design Standards

All contributions must adhere to the following. These are not suggestions —
they are the standards that keep the system coherent and maintainable.

### Python Style

- All code must be Python 3 and pass `pycodestyle --config=.pycodestyle`
- Column-aligned assignments are the intentional project style — keep them
- f-strings are acceptable but string concatenation is preferred for
  consistency across the codebase
- All new functions must have docstrings

### Versioning

- Every bin command is a versioned file: `command-vX.Y.Z.py`
- **Patch (Z):** bug fixes only, no behavior change
- **Minor (Y):** new features, backward compatible
- **Major (X):** breaking changes
- Never modify an existing versioned file — create a new version
- Old versions are never deleted — they are the rollback path

### Shared Modules

- Any logic used by two or more commands **must** live in a shared
  importable module in `bin/`
- Never duplicate code across command files
- Current shared modules: `hybx_config.py`, `libs_helpers.py`
- If your contribution needs a new shared module, create one

### Library Management

- `libs` is the sole authority over Arduino libraries
- Never bypass `libs` for library operations
- Never write to `sketch.yaml` library sections from outside `libs`
- `libraries.json` is owned by `libs` — never edit it by hand in code

### Configuration

- All configuration lives in `~/.hybx/` — never hardcode paths
- PATs are **never** stored in any config file or committed to any repo
- Board and project config lives in `~/.hybx/config.json`
- Library registry lives in `~/.hybx/libraries.json`

### Output and GUI Readiness

- All commands must support `--json` for machine-readable output
- All commands must support `--confirm` to skip interactive prompts
- Exit codes must be meaningful: 0 success, 1 user error, 2 system error,
  3 conflict
- Never parse command output to determine success — use exit codes

### The Untouchable File

- `scripts/update.bash` is **never** modified — ever
- Its content is frozen; only the referenced repos and variables at the
  top may change via a new copy, never an in-place edit

### Destructive Operations

- Any command that destroys data must have a `dryrun` subcommand
- Destructive operations require explicit user confirmation
- Confirmation prompts must use `confirm_prompt()` from `hybx_config.py`
- Operations that are truly irreversible require a typed confirmation phrase
- There is no `--force` flag on destructive operations — ever

---

## How to Contribute

1. Fork the repo
2. Create a branch: `git checkout -b my-feature`
3. Make your changes following the standards above
4. Run `pycodestyle --config=.pycodestyle bin/<your-file>.py`
5. Test on a real UNO Q if possible
6. Open a pull request with a clear description of what changed and why

---

## Reporting Issues

Open a GitHub issue. Include:

- What you were trying to do
- What command you ran
- What output you got
- What you expected instead

The more specific, the faster it gets fixed.

---

## Conduct

Be constructive. Be direct. Be respectful. We are all here to build
something good. Criticism of code is welcome and expected — criticism
of people is not.

---

## Questions

Open an issue tagged `question`. No question is too basic.
