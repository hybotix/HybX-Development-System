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
        print("     board set <n>   to set the active board")
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


def confirm_prompt(question: str) -> bool:
    """
    Prompt the user with a yes/no question.
    Requires exactly "yes" or "no" — re-prompts until one is given.
    Returns True for yes, False for no.
    """
    while True:
        answer = input(question + " (yes/no): ").strip()
        if answer == "yes":
            return True
        if answer == "no":
            return False
        print("Please type exactly 'yes' or 'no'.")
