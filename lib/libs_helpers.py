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
USER_LIBS_DIR    = os.path.expanduser("~/Arduino/libraries")

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
    Return paths to every library.properties found across all library roots.

    Two roots are scanned:
      ARDUINO_LIBS_DIR (~/.arduino15/internal) — App Lab managed libraries.
        Layout: <root>/<hash_dir>/<lib_name>/library.properties  (nested)
             or <root>/<lib_name>/library.properties             (flat)
      USER_LIBS_DIR (~~/Arduino/libraries) — arduino-cli lib install target.
        Layout: <root>/<lib_name>/library.properties             (flat only)
    """
    paths = []
    seen  = set()

    def _scan_root(root: str) -> None:
        if not os.path.isdir(root):
            return
        for top in os.scandir(root):
            if not top.is_dir():
                continue
            # Flat: <root>/<lib>/library.properties
            flat = os.path.join(top.path, "library.properties")
            if os.path.exists(flat):
                if flat not in seen:
                    seen.add(flat)
                    paths.append(flat)
                continue
            # Nested: <root>/<hash>/<lib>/library.properties  (App Lab layout)
            try:
                for sub in os.scandir(top.path):
                    if not sub.is_dir():
                        continue
                    nested = os.path.join(sub.path, "library.properties")
                    if os.path.exists(nested) and nested not in seen:
                        seen.add(nested)
                        paths.append(nested)
            except PermissionError:
                pass

    _scan_root(ARDUINO_LIBS_DIR)
    _scan_root(USER_LIBS_DIR)
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


# ── Sketch scanning ────────────────────────────────────────────────────────────


def build_include_to_lib_map(libs_data: dict) -> dict[str, str]:
    """
    Build a mapping of header filename -> library name by scanning
    library.properties files for the includes= field, and also by
    deriving likely header names from library names.

    Returns: {"Adafruit_SCD30.h": "Adafruit SCD30", ...}
    """
    mapping = {}

    for props_path in find_library_properties_files():
        lib_dir = os.path.dirname(props_path)
        props   = read_library_properties(lib_dir)
        if not props:
            continue
        lib_name = props["name"]

        # Read includes= field from library.properties if present
        try:
            with open(props_path, "r", errors="replace") as f:
                for line in f:
                    line = line.strip()
                    if line.startswith("includes="):
                        _, _, val = line.partition("=")
                        for header in val.split(","):
                            header = header.strip()
                            if header:
                                mapping[header] = lib_name
        except OSError:
            pass

        # Also derive likely header names from library name:
        #   "Adafruit SCD30"    -> "Adafruit_SCD30.h"
        #   "ArduinoGraphics"   -> "ArduinoGraphics.h"
        #   "Adafruit BusIO"    -> "Adafruit_BusIO.h"
        derived = lib_name.replace(" ", "_") + ".h"
        if derived not in mapping:
            mapping[derived] = lib_name

        # Also map the directory name as a header
        dir_name = os.path.basename(lib_dir) + ".h"
        if dir_name not in mapping:
            mapping[dir_name] = lib_name

    return mapping


def scan_sketch_includes(sketch_ino_path: str) -> list[str]:
    """
    Parse #include lines from a sketch.ino file.
    Returns a list of header filenames (e.g. ["Adafruit_SCD30.h", ...]).
    Only active includes are returned — commented-out lines are skipped.
    """
    headers = []
    try:
        with open(sketch_ino_path, "r", errors="replace") as f:
            for line in f:
                stripped = line.strip()
                # Skip commented-out includes
                if stripped.startswith("//"):
                    continue
                if stripped.startswith("#include"):
                    # Extract header name from #include <header.h> or "header.h"
                    import re
                    m = re.search(r'[<"]([^>"]+)[>"]', stripped)
                    if m:
                        headers.append(m.group(1))
    except OSError:
        pass
    return headers


def auto_assign_project_libraries(
        apps_path: str,
        libs_data: dict,
        json_mode: bool = False) -> dict[str, list[str]]:
    """
    Walk apps_path, find every project's sketch.ino, scan its #include
    lines, match them against installed libraries, and return a dict of
    project -> [library names] assignments.

    Only active (non-commented) includes are considered.
    Only libraries present in libs_data["installed"] are assigned.
    Dependencies are never directly assigned — only direct includes.
    """
    include_map  = build_include_to_lib_map(libs_data)
    assignments  = {}
    installed    = set(libs_data["installed"].keys())
    # Build a set of all dependency library names so we can exclude them
    all_deps = set()
    for deps in libs_data["dependencies"].values():
        all_deps.update(deps)

    if not os.path.isdir(apps_path):
        return assignments

    for entry in os.scandir(apps_path):
        if not entry.is_dir():
            continue
        project     = entry.name
        sketch_path = os.path.join(entry.path, "sketch", "sketch.ino")
        if not os.path.exists(sketch_path):
            continue

        headers      = scan_sketch_includes(sketch_path)
        project_libs = []

        for header in headers:
            lib_name = include_map.get(header)
            if lib_name and lib_name in installed:
                # Only assign direct libraries, not dependencies
                if lib_name not in all_deps and lib_name not in project_libs:
                    project_libs.append(lib_name)

        if project_libs:
            assignments[project] = sorted(project_libs)
            if not json_mode:
                print("Auto-assigned " + str(len(project_libs)) +
                      " libraries to: " + project)

    return assignments

# ── Sync inner logic ───────────────────────────────────────────────────────────


def cmd_sync_inner(
        json_mode: bool = False,
        apps_path: str = "") -> dict:
    """
    Rebuild installed + dependencies sections of libraries.json from the
    filesystem. Also auto-assigns project libraries by scanning sketch.ino
    #include statements and matching them against installed libraries.

    Returns a dict: {"added": [...], "removed": [...], "total": N,
                     "assigned": {project: [libs]}}
    Can be called directly by migrate after reinstall.
    """
    libs    = load_libraries()
    current = cli_lib_list()

    if not json_mode:
        print("Syncing library registry from arduino-cli...")

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

    # Auto-assign project libraries from sketch #include statements
    assigned = {}
    if apps_path and os.path.isdir(apps_path):
        assigned = auto_assign_project_libraries(apps_path, libs, json_mode)
        for project, project_libs in assigned.items():
            libs["projects"][project] = project_libs

    save_libraries(libs)

    result = {"added": added, "removed": removed,
              "total": len(libs["installed"]), "assigned": assigned}

    if not json_mode:
        if added:
            print("Added to registry:   " + ", ".join(added))
        if removed:
            print("Removed from registry: " + ", ".join(removed))
        if not added and not removed:
            print("Registry already in sync.")
        print("Total installed: " + str(result["total"]))
        if assigned:
            print("Auto-assigned libraries to " +
                  str(len(assigned)) + " projects.")
        print()
        if not apps_path:
            print("Note: project assignments were not modified "
                  "(no apps_path provided).")

    return result
