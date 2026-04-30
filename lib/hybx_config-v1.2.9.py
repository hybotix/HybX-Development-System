"""
hybx_config.py
Hybrid RobotiX — HybX Development System

Shared config helper. All bin commands import this to get the active board
settings and library registry.

Usage in bin commands:
    from hybx_config import get_active_board, get_push_url
    from hybx_config import load_libraries, save_libraries

    board     = get_active_board()   # exits with error if none configured
    host      = board["host"]
    apps_path = board["apps_path"]   # always fully expanded, no ~
    repo      = board["repo"]
    name      = board["name"]
    pat       = board["pat"]         # GitHub PAT for push (may be empty)

    push_url  = get_push_url(board)  # PAT-embedded URL for git push

    libs      = load_libraries()     # full libraries.json as dict
    save_libraries(libs)             # write libraries.json atomically
"""

import os
import json
import sys

CONFIG_DIR     = os.path.expanduser("~/.hybx")
CONFIG_FILE    = os.path.join(CONFIG_DIR, "config.json")
LIBRARIES_FILE = os.path.join(CONFIG_DIR, "libraries.json")

# ── Add lib/ to sys.path at import time ────────────────────────────────────────
# lib_path is written to config.json by update. If present, add it to sys.path
# so all shared modules in lib/ are importable from any command in ~/bin/.

def _add_lib_path():
    if not os.path.exists(CONFIG_FILE):
        return
    try:
        with open(CONFIG_FILE) as f:
            cfg = json.load(f)
        lib_path = cfg.get("lib_path", "")
        if lib_path and os.path.isdir(lib_path) and lib_path not in sys.path:
            sys.path.insert(0, lib_path)
    except Exception:
        pass

_add_lib_path()

# ── Board config ───────────────────────────────────────────────────────────────


def load_config() -> dict:
    os.makedirs(CONFIG_DIR, exist_ok=True)
    if not os.path.exists(CONFIG_FILE):
        return {"boards": {}, "active_board": None}
    with open(CONFIG_FILE, "r") as f:
        try:
            return json.load(f)
        except json.JSONDecodeError as e:
            # Handle malformed JSON (e.g., trailing commas)
            content = f.read()
            # Remove trailing commas before } or ]
            content = content.replace(',}', '}').replace(',]', ']')
            return json.loads(content)


def get_active_board() -> dict:
    """
    Returns the active board config dict with added 'name' key.
    Expands ~ in apps_path automatically.
    Exits with an error message if no board is configured or active.
    """
    config = load_config()
    active = config.get("active_board")

    if not active:
        print("ERROR: No active board set.")
        print("Use: board add <n>   to add a board")
        print("     board use <n>   to set the active board")
        sys.exit(1)

    boards = config.get("boards", {})

    if active not in boards:
        print("ERROR: Active board " + active + " not found in config.")
        print("Use: board list")
        sys.exit(1)

    board = dict(boards[active])
    board["name"] = active
    # Always expand ~ so subprocesses get a real path
    board["apps_path"] = os.path.expanduser(board.get("apps_path", "~/Arduino"))
    board.setdefault("pat", "")
    return board


def get_push_url(board: dict) -> str:
    """
    Returns a PAT-embedded HTTPS URL for git push.
    If no PAT is stored, returns the plain repo URL.
    """
    repo = board.get("repo", "")
    pat  = board.get("pat", "")

    if not pat or not repo.startswith("https://"):
        return repo

    # Embed PAT: https://<pat>@github.com/...
    return repo.replace("https://", "https://" + pat + "@")

# ── Library registry ───────────────────────────────────────────────────────────


LIBRARIES_TEMPLATE = {
    "installed":    {},
    "dependencies": {},
    "projects":     {},
}


def load_libraries() -> dict:
    """
    Load ~/.hybx/libraries.json.
    Returns a fully-structured dict even if the file does not exist yet.

    Structure:
      {
        "installed": {
          "Adafruit SCD30": {
            "version":      "1.0.5",
            "installed_at": "2026-04-10T07:45:00",
            "description":  "Adafruit SCD30 CO2 sensor library"
          },
          ...
        },
        "dependencies": {
          "Adafruit SCD30": ["Adafruit BusIO", "Adafruit Unified Sensor"],
          ...
        },
        "projects": {
          "securesmars":   ["Adafruit SCD30", "Adafruit Motor Shield V2"],
          "matrix-bno055": ["Adafruit BNO055", "Adafruit BusIO"],
          ...
        }
      }

    Keys are bare identifiers. Only description values are quoted strings.
    """
    os.makedirs(CONFIG_DIR, exist_ok=True)
    if not os.path.exists(LIBRARIES_FILE):
        import copy
        empty = copy.deepcopy(LIBRARIES_TEMPLATE)
        save_libraries(empty)
        return empty
    with open(LIBRARIES_FILE, "r") as f:
        data = json.load(f)
    # Ensure all top-level sections exist even in older files
    for key in LIBRARIES_TEMPLATE:
        data.setdefault(key, {})
    return data


def save_libraries(libs: dict):
    """
    Write libraries.json atomically via a temp file + rename.
    Ensures the config dir exists.
    """
    os.makedirs(CONFIG_DIR, exist_ok=True)
    tmp = LIBRARIES_FILE + ".tmp"
    with open(tmp, "w") as f:
        json.dump(libs, f, indent=2)
    os.replace(tmp, LIBRARIES_FILE)


def get_library_users(libs: dict, lib_name: str) -> list[str]:
    """
    Return a sorted list of project names that directly use lib_name.
    """
    return sorted(
        proj for proj, lib_list in libs["projects"].items()
        if lib_name in lib_list
    )


def get_dependent_libraries(libs: dict, lib_name: str) -> list[str]:
    """
    Return a sorted list of installed library names that list lib_name
    as one of their dependencies — i.e. libraries that would break if
    lib_name were removed.
    """
    return sorted(
        parent for parent, deps in libs["dependencies"].items()
        if lib_name in deps and parent in libs["installed"]
    )


# ── ML platform config ─────────────────────────────────────────────────────────


def get_ml_config(board: dict) -> dict:
    """
    Return the ML platform config for the given board.
    Returns a dict with ml_platform, ml_api_key, ml_project_id.
    All fields default to empty string if not set.
    """
    return {
        "ml_platform":   board.get("ml_platform", ""),
        "ml_api_key":    board.get("ml_api_key", ""),
        "ml_project_id": board.get("ml_project_id", ""),
    }


def has_ml_config(board: dict) -> bool:
    """Return True if the board has ML platform credentials configured."""
    return bool(board.get("ml_api_key", "").strip())


def save_config(config: dict):
    """Write config.json atomically via a temp file + rename."""
    # Remove deprecated board_projects key
    config.pop("board_projects", None)
    os.makedirs(CONFIG_DIR, exist_ok=True)
    tmp = CONFIG_FILE + ".tmp"
    with open(tmp, "w") as f:
        json.dump(config, f, indent=2)
    os.replace(tmp, CONFIG_FILE)


def confirm_prompt(question: str) -> bool:
    """
    Prompt the user with a YES/NO question.
    Requires exactly "YES" or "NO" in uppercase — re-prompts until one is given.
    Uppercase is required to show deliberate intent.
    Returns True for YES, False for NO.
    """
    while True:
        answer = input(question + " (YES/NO): ").strip()
        if answer == "YES":
            return True
        if answer == "NO":
            return False
        print("Please type exactly 'YES' or 'NO' in uppercase.")


# ── Privacy helpers ────────────────────────────────────────────────────────────

def mask_username(value: str, config: dict | None = None) -> str:
    """
    Replace the github_user in a string with *** for display purposes.
    Protects the username from shoulder-surfing.

    mask_username("hybotix")               -> "***"
    mask_username("~/Repos/GitHub/hybotix/HybX-Development-System")
                                           -> "~/Repos/GitHub/***/HybX-Development-System"
    """
    if not value:
        return value

    if config is None:
        try:
            config = load_config()
        except Exception:
            return value

    github_user = config.get("github_user", "")
    if github_user and github_user in value:
        return value.replace(github_user, "***")
    return value


def mask_host(host: str) -> str:
    """
    Mask the username portion of a host string for display.
    "arduino@uno-q.local" -> "***@uno-q.local"
    "uno-q.local"         -> "uno-q.local"
    """
    if "@" in host:
        _, hostname = host.split("@", 1)
        return f"***@{hostname}"
    return host


def safe_path(path: str) -> str:
    """
    Shorten a path for display by replacing $HOME with ~.
    Never exposes the actual home directory path.
    ~/Repos/GitHub/hybotix/X -> ~/Repos/GitHub/***/X  (via mask_username)
    /home/arduino/bin/foo    -> ~/bin/foo
    """
    home = os.path.expanduser("~")
    if path.startswith(home):
        path = "~" + path[len(home):]
    return path

# ── Timing utility ─────────────────────────────────────────────────────────────

import time
import functools


class HybXTimer:
    """Timing utility for HybX operations.

    Measures elapsed wall-clock time and prints results in a consistent
    format: [timer] <label>: <elapsed>s

    All times are in seconds with millisecond precision (3 decimal places).
    Nested timers are indented for readability.

    Usage:
        # Context manager (recommended):
        with HybXTimer("sensor init"):
            status = Bridge.call("get_sensor_status", timeout=120)
        # prints: [timer] sensor init: 8.342s

        # Decorator:
        @HybXTimer.timed("build")
        def run_build():
            ...

        # Manual start/stop:
        t = HybXTimer("flash")
        t.start()
        elapsed = t.stop()

        # Nested timers:
        with HybXTimer("total init"):
            with HybXTimer("firmware upload"):
                ...
            with HybXTimer("sensor boot"):
                ...

        # Inline measurement:
        elapsed, result = HybXTimer.measure("bridge call", Bridge.call, "get_data")
    """

    _depth: int = 0   # class-level depth for nested timer indentation

    def __init__(self, label: str, print_start: bool = False):
        """
        label       : Human-readable name for this operation.
        print_start : If True, print a line when the timer starts.
                      Useful for long operations where you want immediate
                      feedback that timing has begun.
        """
        self.label       = label
        self.print_start = print_start
        self._start: float | None  = None
        self._elapsed: float | None = None

    def __enter__(self) -> "HybXTimer":
        self.start()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> bool:
        self.stop()
        return False   # never suppress exceptions

    def start(self) -> None:
        """Start the timer."""
        self._start = time.monotonic()
        HybXTimer._depth += 1
        if self.print_start and HybXTimer._enabled:
            indent = "  " * (HybXTimer._depth - 1)
            print(f"{indent}[timer] {self.label}: starting...")

    # Set HYBX_TIMING=1 in environment to enable timer output.
    _enabled: bool = os.environ.get("HYBX_TIMING", "0") == "1"

    def stop(self) -> float:
        """Stop the timer, print elapsed time if enabled, return elapsed seconds."""
        if self._start is None:
            raise RuntimeError(
                f"HybXTimer '{self.label}': stop() called before start()"
            )
        self._elapsed = time.monotonic() - self._start
        HybXTimer._depth = max(0, HybXTimer._depth - 1)
        if HybXTimer._enabled:
            indent = "  " * HybXTimer._depth
            print(f"{indent}[timer] {self.label}: {self._elapsed:.3f}s")
        return self._elapsed

    @property
    def elapsed(self) -> float | None:
        """Elapsed seconds, or None if the timer has not been stopped."""
        return self._elapsed

    @staticmethod
    def timed(label: str, print_start: bool = False):
        """Decorator that times a function call."""
        def decorator(func):
            @functools.wraps(func)
            def wrapper(*args, **kwargs):
                with HybXTimer(label, print_start=print_start):
                    return func(*args, **kwargs)
            return wrapper
        return decorator

    @staticmethod
    def measure(label: str, fn, *args, **kwargs):
        """Time a single callable and return (elapsed_seconds, result)."""
        t = HybXTimer(label)
        t.start()
        result = fn(*args, **kwargs)
        elapsed = t.stop()
        return elapsed, result


# ── Name validation ────────────────────────────────────────────────────────────

import re as _re

def validate_name(name: str, label: str = "Name") -> str:
    """
    Validate a user-supplied name (board, project, library).
    Rules:
      - No spaces or whitespace of any kind
      - No special characters except hyphen and underscore
      - Not empty
    Returns the name if valid. Raises ValueError with a clear message if not.
    """
    if not name:
        raise ValueError(f"{label} cannot be empty.")
    if " " in name or "\t" in name:
        raise ValueError(
            f"{label} cannot contain spaces: '{name}'\n"
            f"Use hyphens or underscores instead (e.g. '{name.replace(' ', '-')}')"
        )
    if not _re.match(r'^[A-Za-z0-9_\-\.]+$', name):
        raise ValueError(
            f"{label} contains invalid characters: '{name}'\n"
            f"Only letters, numbers, hyphens, underscores and dots are allowed."
        )
    return name


# ── Path and name validation ───────────────────────────────────────────────────

import re as _re


def validate_project_name(name: str) -> tuple[bool, str]:
    """
    Validate a project name.
    Rules: lowercase letters, digits, hyphens only. No spaces, no underscores,
    no leading/trailing hyphens. 1-64 characters.

    Returns (valid: bool, error_message: str).
    error_message is empty string on success.
    """
    if not name:
        return False, "Project name cannot be empty."
    if len(name) > 64:
        return False, f"Project name too long ({len(name)} chars, max 64)."
    if not _re.match(r'^[a-z0-9][a-z0-9-]*[a-z0-9]$|^[a-z0-9]$', name):
        return False, (
            f"Invalid project name '{name}'. "
            "Use lowercase letters, digits, and hyphens only."
        )
    return True, ""


def validate_app_path(path: str) -> tuple[bool, str]:
    """
    Validate that an app path exists and contains a sketch/ subdirectory.
    Returns (valid: bool, error_message: str).
    """
    expanded = os.path.expanduser(path)
    if not os.path.isdir(expanded):
        return False, f"App path not found: {safe_path(expanded)}"
    sketch_dir = os.path.join(expanded, "sketch")
    if not os.path.isdir(sketch_dir):
        return False, f"No sketch/ directory found in: {safe_path(expanded)}"
    return True, ""


def resolve_project(apps_path: str, arg: str | None) -> tuple[str, str]:
    """
    Resolve (app_path, project_name) from a project name, full path, or
    last_app (if arg is None).

    Raises SystemExit with a clear error message on failure.
    """
    if arg is None:
        # Check last_app (most recent build)
        LAST_APP_FILE = os.path.expanduser("~/.hybx/last_app")
        if os.path.isfile(LAST_APP_FILE):
            with open(LAST_APP_FILE) as f:
                project = f.read().strip()
            if project:
                app_path = os.path.join(apps_path, project)
                if os.path.isdir(app_path):
                    return app_path, project
        print("ERROR: No last_app. Run: build <project>")
        raise SystemExit(1)

    # Full or relative path
    if os.path.sep in arg or arg.startswith("~") or arg.startswith("."):
        app_path = os.path.expanduser(arg)
        if app_path.endswith("/sketch"):
            app_path = app_path[:-7]
        project = os.path.basename(app_path)
        valid, err = validate_app_path(app_path)
        if not valid:
            print(f"ERROR: {err}")
            raise SystemExit(1)
        return app_path, project

    # Bare project name
    candidate = os.path.join(apps_path, arg)
    if os.path.isdir(candidate):
        return candidate, arg

    print(f"ERROR: Project '{arg}' not found.")
    raise SystemExit(1)


# ── Git repo pull helpers ───────────────────────────────────────────────────────

def _run_quiet(cmd, cwd=None) -> tuple[int, str]:
    import subprocess
    result = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True)
    combined = (result.stdout.strip() + "\n" + result.stderr.strip()).strip()
    return result.returncode, combined


def pull_repo(dest: str, branch: str = "main"):
    """
    Pull the latest changes for a repo and print results.

    If the working tree is dirty, stash local changes first and restore
    them after the pull. Prints a clear summary of what happened.
    """
    import subprocess
    if not os.path.isdir(dest):
        print("WARNING: " + dest + " not found — skipping pull")
        return

    name = os.path.basename(dest)
    print("Pulling " + name + " ...")

    # Switch HTTPS remote to SSH
    code, url = _run_quiet(["git", "remote", "get-url", "origin"], cwd=dest)
    if url.startswith("https://github.com/"):
        ssh_url = url.replace("https://github.com/", "git@github.com:")
        subprocess.run(["git", "remote", "set-url", "origin", ssh_url],
                       cwd=dest, capture_output=True)
        print("  Switched remote to SSH: " + ssh_url)

    # Checkout the correct branch
    _run_quiet(["git", "checkout", branch], cwd=dest)

    # Stash if dirty
    stashed = False
    code, output = _run_quiet(["git", "status", "--porcelain"], cwd=dest)
    if code == 0 and output.strip():
        code, out = _run_quiet(
            ["git", "stash", "push", "-m", "hybx-update-autostash"], cwd=dest)
        if code != 0:
            print("  WARNING: git stash failed — attempting pull anyway")
        else:
            stashed = True
            print("  Stashed: " + out)

    code, out = _run_quiet(["git", "pull"], cwd=dest)
    if "Already up to date" in out:
        print("  Already up to date.")
    elif out:
        for line in out.splitlines():
            print("  " + line)
        # If this is a HybX library (lives in ~/Arduino/libraries/),
        # invalidate its cached .o files in all app caches so they
        # are rebuilt on next compile.
        arduino_libs = os.path.expanduser("~/Arduino/libraries")
        if dest.startswith(arduino_libs):
            lib_name = os.path.basename(dest)
            apps_root = os.path.expanduser("~/Arduino")
            for board in os.scandir(apps_root):
                if not board.is_dir() or board.name == "libraries":
                    continue
                for app in os.scandir(board.path):
                    if not app.is_dir():
                        continue
                    lib_cache = os.path.join(app.path, ".cache", "sketch",
                                             "libraries", lib_name)
                    if os.path.isdir(lib_cache):
                        import shutil as _shutil
                        _shutil.rmtree(lib_cache)
                        print(f"  Invalidated cache: {app.name}/{lib_name}")
    else:
        print("  Done.")

    if stashed:
        code, out = _run_quiet(["git", "stash", "pop"], cwd=dest)
        if code != 0:
            print("  WARNING: git stash pop failed — run: git stash pop in " + dest)
        else:
            print("  Restored: " + out)


def pull_all_repos(config: dict):
    """
    Pull Dev System repo, active board apps repo, and all HybX library repos.
    Prints a clear summary line for each repo. Called by both update and start.
    """
    import platform as _platform

    github_user = config.get("github_user", "")
    repo_dest   = os.path.expanduser("~/Repos/GitHub/" + github_user)
    dev_dest    = os.path.join(repo_dest, "HybX-Development-System")

    # Always pull Dev System on dev/v2.0
    pull_repo(dev_dest, branch="dev/v2.0")

    system  = _platform.system()
    machine = _platform.machine()
    if system == "Linux" and machine == "aarch64":
        active = config.get("active_board")
        if active:
            boards   = config.get("boards", {})
            board    = boards.get(active, {})
            repo_url = board.get("repo", "")
            if repo_url:
                repo_name = repo_url.rstrip("/").rstrip(".git").split("/")[-1]
                apps_dest = os.path.join(repo_dest, repo_name)
                pull_repo(apps_dest)

        hybx_libs_dir = os.path.expanduser("~/Arduino/libraries")
        if os.path.isdir(hybx_libs_dir):
            for entry in os.scandir(hybx_libs_dir):
                if entry.is_dir() and os.path.isdir(os.path.join(entry.path, ".git")):
                    pull_repo(entry.path)


# ── Logging tee ─────────────────────────────────────────────────────────────────

class HybXTee:
    """
    Tee sys.stdout to a log file.

    Usage:
        tee = HybXTee("~/update.log")
        ...
        tee.close()

    All print() calls made while the tee is active are written to both
    the terminal and the log file. close() restores sys.stdout.
    """
    def __init__(self, path: str):
        import sys
        self._path   = os.path.expanduser(path)
        self._file   = open(self._path, "w", buffering=1)
        self._stdout = sys.stdout
        sys.stdout   = self
        print(f"Logging to: {self._path}")

    def write(self, data):
        self._stdout.write(data)
        self._file.write(data)

    def flush(self):
        self._stdout.flush()
        self._file.flush()

    def close(self):
        import sys
        sys.stdout = self._stdout
        self._file.close()
