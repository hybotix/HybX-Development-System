# Contributing to HybX Development System
## Hybrid RobotiX

First — thank you. Every contribution, bug report, idea, and piece of
constructive feedback makes this system better for everyone who uses it.

*"I. WILL. NEVER. GIVE. UP. OR. SURRENDER."*

---

## The Philosophy

The HybX Development System exists to replace App Lab entirely and give
developers full, clean, reproducible control over the Arduino UNO Q
platform. Every contribution should move the system further in that
direction — cleaner, more reliable, more capable, zero vendor lock-in.

We are not at a 1.x release yet. This is the time to get things right.
Technical debt is not welcome. If something is wrong, fix it properly.

---

## What We Welcome

- **Bug fixes** — if something is broken, tell us or fix it
- **New commands** — if you need a capability that does not exist, build it
- **Improvements to existing commands** — better output, better error
  handling, better reliability
- **Documentation improvements** — if something is unclear, fix it
- **New entries in KNOWN_ISSUES.md** — discovered vendor bugs belong there
- **GUI-readiness improvements** — better --json output, structured data
- **Ideas and discussion** — open an issue, start a conversation

No contribution is too small. A typo fix is welcome. A one-line improvement
is welcome. A completely new command is welcome.

---

## What We Do Not Accept

- Code that bypasses `libs` for library management
- Modifications to `scripts/update.bash`
- Quoted strings outside of description fields
- Duplicated code that belongs in a shared module
- Workarounds for vendor bugs instead of proper bug reports
- Breaking changes without a major version bump
- Code that does not pass `pycodestyle --config=.pycodestyle`
- A `--force` flag on any destructive operation — ever

---

## Design Standards

All contributions must adhere to the following. These are not suggestions —
they are the standards that keep the system coherent and maintainable.

### Python Style

- All code must be Python 3 and pass `pycodestyle --config=.pycodestyle`
  with zero violations before submission
- Column-aligned assignments are the intentional project style — keep them
- Two blank lines between all top-level functions and classes
- All imports at the top of the file — `sys.path.insert` before other
  imports, local imports tagged with `# noqa: E402`
- Type hints on all function signatures
- Docstrings on all non-trivial functions
- String concatenation preferred over f-strings for consistency

### Strings

- **Only description fields may contain quoted strings**
- Identifiers, names, keys, subcommands, and paths are always bare
- This rule applies everywhere: Python code, JSON config, YAML files

### Shared Modules

- Any logic used by two or more commands **must** live in a shared
  importable module in `bin/`
- Never duplicate code across command files — ever
- Current shared modules: `hybx_config.py`, `libs_helpers.py`
- If your contribution needs a new shared module, create it and document
  it in `docs/DESIGN.md` section 3

### Versioning

- Every bin command is a versioned file: `command-vX.Y.Z.py`
- **Patch (Z):** bug fixes only, no behavior change
- **Minor (Y):** new features, backward compatible
- **Major (X):** breaking changes
- Never modify an existing versioned file — create a new version
- Never delete old versions — they are the historical record
- Shared modules (`hybx_config.py`, `libs_helpers.py`) are unversioned
  and updated in place

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

### Confirmation Prompts

- All confirmation prompts must use `confirm_prompt()` from `hybx_config.py`
- Users must type exactly `yes` or `no` — no abbreviations, no other input,
  re-prompts until one of the two is given
- Truly irreversible operations require a typed confirmation phrase in
  addition to the standard yes/no prompt

### The Untouchable File

- `scripts/update.bash` is **never** modified — ever, under any circumstances
- Its content is frozen; it must exist before the repo can be cloned

### Destructive Operations

- Any command that destroys data must have a `dryrun` subcommand that
  shows exactly what will happen and touches nothing
- Destructive operations always re-verify before acting, even if dryrun
  was already run
- There is no `--force` flag on any destructive operation — ever

---

## How to Contribute

1. Fork the repo
2. Create a branch: `git checkout -b my-feature`
3. Make your changes following all standards above
4. Run `pycodestyle --config=.pycodestyle bin/<your-file>.py`
5. Run `python3 -c "import ast; ast.parse(open('bin/<your-file>.py').read())"`
6. Test on a real UNO Q if possible
7. Open a pull request with a clear description of what changed and why

Pull requests are welcome against any part of the project. All pull
requests will be reviewed and merged at the sole discretion of the
project maintainer.

Both checks in steps 4 and 5 must pass clean before a pull request
will be reviewed.

---

## Reporting Issues

Open a GitHub issue. Include:

- What you were trying to do
- What command you ran
- What output you got
- What you expected instead

The more specific, the faster it gets fixed. Vendor bugs belong in
`docs/KNOWN_ISSUES.md` with a link to the upstream issue.

---

## Conduct

Be constructive. Be direct. Be respectful. We are all here to build
something good. Criticism of code is welcome and expected — criticism
of people is not.

---

## Questions

Open an issue tagged `question`. No question is too basic.

---

*Hybrid RobotiX — San Diego*
