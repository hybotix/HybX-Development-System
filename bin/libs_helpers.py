"""
libs_helpers.py
Hybrid RobotiX — HybX Development System

Shared library helpers. Imported by libs and migrate.
Contains all filesystem scanning, arduino-cli wrappers, and the
sync inner logic that both commands need.

Do not run directly.
"""

import os
import subprocess
from datetime import datetime, timezone

from hybx_config import load_libraries, save_libraries

# ── Constants ──────────────────────────────────────────────────────────────────

ARDUINO_LIBS_DIR = os.path.expanduser("~/.arduino15/internal")

# ── Filesystem helpers ─────────────────────────────────────────────────────────


def read_library_properties(lib_dir: str) -> dict | None:
    """
    Parse a library's library.properties file.
    Returns a dict with name, version, description keys, or None if
    the file does not exist or cannot be parsed.
    """
    props_path = os.path.join(lib_dir, "library.properties")
    if not os.path.exists(props_path):
        return None
    props = {}
    try:
        with open(props_path, "r", errors="replace") as f:
            for line in f:
                line = line.strip()
                if "=" in line and not line.startswith("#"):
                    key, _, val = line.partition("=")
                    props[key.strip()] = val.strip()
    except OSError:
        return None
    name    = props.get("name", os.path.basename(lib_dir))
    version = props.get("version", "0.0.0")
    desc    = props.get("sentence", props.get("description", ""))
    return {"name": name, "version": version, "description": desc}


def scan_library_deps(lib_dir: str) -> list[str]:
    """
    Parse the depends= line from library.properties and return a list
    of dependency names. Returns an empty list if none declared.
    """
    props_path = os.path.join(lib_dir, "library.properties")
    if not os.path.exists(props_path):
        return []
    try:
        with open(props_path, "r", errors="replace") as f:
            for line in f:
                line = line.strip()
                if line.startswith("depends="):
                    _, _, val = line.partition("=")
                    return [d.strip() for d in val.split(",") if d.strip()]
    except OSError:
        pass
    return []


def find_library_properties_files() -> list[str]:
    """
    Walk ARDUINO_LIBS_DIR and return paths to every library.properties found.
    Handles both flat layout and the arduino-cli/App Lab nested layout:
      ~/.arduino15/internal/<hash_dir>/<lib_name>/library.properties
    Also handles flat layout for future-proofing:
      <ARDUINO_LIBS_DIR>/<lib_name>/library.properties
    """
    paths = []
    if not os.path.isdir(ARDUINO_LIBS_DIR):
        return paths
    for top in os.scandir(ARDUINO_LIBS_DIR):
        if not top.is_dir():
            continue
        # Flat: ARDUINO_LIBS_DIR/<lib>/library.properties
        flat = os.path.join(top.path, "library.properties")
        if os.path.exists(flat):
            paths.append(flat)
            continue
        # Nested: ARDUINO_LIBS_DIR/<hash>/<lib>/library.properties
        try:
            for sub in os.scandir(top.path):
                if not sub.is_dir():
                    continue
                nested = os.path.join(sub.path, "library.properties")
                if os.path.exists(nested):
                    paths.append(nested)
        except PermissionError:
            pass
    return paths


def cli_lib_list() -> list[dict]:
    """
    Scan ARDUINO_LIBS_DIR and parse each library's library.properties.
    Returns a sorted list of dicts:
      [{"name": ..., "version": ..., "description": ...}, ...]

    arduino-cli lib list is NOT used -- it cannot see libraries installed
    via App Lab. The filesystem is the ground truth.
    """
    entries = []
    seen    = set()
    for props_path in sorted(find_library_properties_files()):
        props = read_library_properties(os.path.dirname(props_path))
        if props and props["name"] not in seen:
            entries.append(props)
            seen.add(props["name"])
    return sorted(entries, key=lambda e: e["name"])

# ── arduino-cli wrappers ───────────────────────────────────────────────────────


def cli_lib_install(lib_name: str) -> tuple[int, str, str]:
    result = subprocess.run(
        ["arduino-cli", "lib", "install", lib_name],
        capture_output=True,
        text=True,
    )
    return result.returncode, result.stdout, result.stderr


def cli_lib_uninstall(lib_name: str) -> tuple[int, str, str]:
    result = subprocess.run(
        ["arduino-cli", "lib", "uninstall", lib_name],
        capture_output=True,
        text=True,
    )
    return result.returncode, result.stdout, result.stderr


def cli_lib_upgrade(lib_name: str | None = None) -> tuple[int, str, str]:
    cmd = ["arduino-cli", "lib", "upgrade"]
    if lib_name:
        cmd.append(lib_name)
    result = subprocess.run(cmd, capture_output=True, text=True)
    return result.returncode, result.stdout, result.stderr


def cli_lib_search(query: str) -> tuple[int, str, str]:
    result = subprocess.run(
        ["arduino-cli", "lib", "search", query],
        capture_output=True,
        text=True,
    )
    return result.returncode, result.stdout, result.stderr


def cli_lib_version(lib_name: str) -> str | None:
    """
    Return the installed version of lib_name by scanning ARDUINO_LIBS_DIR.
    Returns None if not found.
    """
    for entry in cli_lib_list():
        if entry["name"].lower() == lib_name.lower():
            return entry["version"]
    return None


def cli_lib_deps(lib_name: str) -> list[str]:
    """
    Return declared dependency names for lib_name by reading its
    library.properties depends= field from ARDUINO_LIBS_DIR.
    Returns an empty list if the library is not found or has no deps.
    """
    for props_path in find_library_properties_files():
        lib_dir = os.path.dirname(props_path)
        props   = read_library_properties(lib_dir)
        if props and props["name"].lower() == lib_name.lower():
            return scan_library_deps(lib_dir)
    return []

# ── Sync inner logic ───────────────────────────────────────────────────────────


def cmd_sync_inner(json_mode: bool = False) -> dict:
    """
    Rebuild installed + dependencies sections of libraries.json from the
    filesystem. Project assignments are preserved.

    Returns a dict: {"added": [...], "removed": [...], "total": N}
    Can be called directly by migrate after reinstall.
    """
    libs    = load_libraries()
    current = cli_lib_list()

    if not json_mode:
        print("Syncing library registry from " + ARDUINO_LIBS_DIR + "...")

    added   = []
    removed = []

    fs_names = {e["name"] for e in current}

    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S")
    for entry in current:
        name = entry["name"]
        if name not in libs["installed"]:
            libs["installed"][name] = {
                "version":      entry["version"],
                "installed_at": now,
                "description":  entry.get("description", ""),
            }
            added.append(name)
        else:
            libs["installed"][name]["version"]     = entry["version"]
            libs["installed"][name]["description"] = entry.get("description", "")

    # Refresh dependencies from library.properties
    for props_path in find_library_properties_files():
        lib_dir = os.path.dirname(props_path)
        props   = read_library_properties(lib_dir)
        if not props:
            continue
        deps = scan_library_deps(lib_dir)
        if deps and props["name"] in libs["installed"]:
            libs["dependencies"][props["name"]] = deps

    # Remove entries no longer on filesystem
    for name in list(libs["installed"].keys()):
        if name not in fs_names:
            del libs["installed"][name]
            libs["dependencies"].pop(name, None)
            removed.append(name)

    save_libraries(libs)

    result = {"added": added, "removed": removed, "total": len(libs["installed"])}

    if not json_mode:
        if added:
            print("Added to registry:   " + ", ".join(added))
        if removed:
            print("Removed from registry: " + ", ".join(removed))
        if not added and not removed:
            print("Registry already in sync.")
        print("Total installed: " + str(result["total"]))
        print()
        print("Note: project assignments were not modified.")

    return result
