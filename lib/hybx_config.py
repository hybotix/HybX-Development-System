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
        return json.load(f)


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
        if self.print_start:
            indent = "  " * (HybXTimer._depth - 1)
            print(f"{indent}[timer] {self.label}: starting...")

    def stop(self) -> float:
        """Stop the timer, print elapsed time, and return elapsed seconds."""
        if self._start is None:
            raise RuntimeError(
                f"HybXTimer '{self.label}': stop() called before start()"
            )
        self._elapsed = time.monotonic() - self._start
        HybXTimer._depth = max(0, HybXTimer._depth - 1)
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
