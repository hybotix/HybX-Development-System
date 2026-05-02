#!/usr/bin/env python3

"""
libs-v2.0.0.py
Hybrid RobotiX — HybX Development System

Library Manager — the single source of truth for all Arduino libraries.
Replaces the old addlib command entirely. No library operation should ever bypass this command.

Libraries are GLOBAL to the board. Projects declare which global libraries
they use. A library cannot be removed while any project still uses it.

Usage:
  libs list                        - List all installed libraries
  libs search <name>               - Search Arduino Library Manager
  libs install <name>              - Install library globally
  libs remove <name>               - Remove library (blocked if any project uses it)
  libs upgrade                     - Upgrade all installed libraries
  libs upgrade <name>              - Upgrade one library
  libs show <name>                 - Show library details and which projects use it
  libs use <project> <name>        - Declare that a project uses a library
  libs unuse <project> <name>      - Remove a project's use of a library
  libs update <project>            - Rewrite one project's sketch.yaml from registry
  libs update --all                - Rewrite all projects' sketch.yaml files
  libs sync                        - Rebuild installed registry from arduino-cli
  libs check <project>             - Verify all project libraries are installed

Flags (all subcommands):
  --json                           - Machine-readable JSON output (for GUI)
  --confirm                        - Skip interactive confirmation prompts (for GUI)

Exit codes:
  0  success
  1  user error (bad args, not found, etc.)
  2  system error (arduino-cli failure, file I/O error, etc.)
  3  conflict (remove blocked because project uses this library)
"""

import os
import sys
sys.path.insert(0, os.path.dirname(os.path.realpath(__file__)))
sys.path.insert(0, os.path.expanduser("~/lib"))

import json  # noqa: E402
import subprocess  # noqa: E402
import re  # noqa: E402
from datetime import datetime, timezone  # noqa: E402

from hybx_config import (  # noqa: E402
    get_active_board,
    load_libraries,
    save_libraries,
    get_library_users,
    get_dependent_libraries,
    LIBRARIES_FILE,
    confirm_prompt,
    resolve_subcommand,
)
from libs_helpers import (  # noqa: E402
    ARDUINO_LIBS_DIR,
    HYBX_LIBS_DIR,
    read_library_properties,
    scan_library_deps,
    find_library_properties_files,
    cli_lib_list,
    cli_lib_install,
    cli_lib_uninstall,
    cli_lib_upgrade,
    cli_lib_search,
    cli_lib_version,
    cli_lib_deps,
    cli_lib_install_git,
    copy_hybx_lib_to_sketch,
    get_hybx_lib_name_from_url,
    cmd_sync_inner,
)

# ── Constants ──────────────────────────────────────────────────────────────────

FQBN = "arduino:zephyr:unoq"

# Base libraries always present in every sketch.yaml (Bridge infrastructure).
# These are never in libraries.json — they are structural, not managed.
SKETCH_YAML_BASE_LIBS = [
    "Arduino_RouterBridge (0.3.0)",
    "dependency: Arduino_RPClite (0.2.1)",
    "dependency: ArxContainer (0.7.0)",
    "dependency: ArxTypeTraits (0.3.2)",
    "dependency: DebugLog (0.8.4)",
    "dependency: MsgPack (0.4.2)",
]

SKETCH_YAML_BASE_PLATFORM = "arduino:zephyr"

# ── Argument parsing ───────────────────────────────────────────────────────────


def parse_args() -> tuple[list[str], bool, bool]:
    """
    Returns (positional_args, json_mode, confirm_mode).
    Strips --json and --confirm from argv before returning positionals.
    """
    args     = sys.argv[1:]
    json_mode    = "--json" in args
    confirm_mode = "--confirm" in args
    positionals  = [a for a in args if not a.startswith("--")]
    return positionals, json_mode, confirm_mode

# ── Name normalization ────────────────────────────────────────────────────────


def normalize_lib_name(name: str) -> str:
    """
    Normalize a library name: strip whitespace and title-case each word.
    Handles both quoted and unquoted input consistently.
    Examples:
      adafruit scd30          -> Adafruit SCD30
      ADAFRUIT BNO055         -> Adafruit Bno055
      Adafruit Motor Shield V2 Library -> Adafruit Motor Shield V2 Library
    """
    return " ".join(w[0].upper() + w[1:] if w else w for w in name.strip().split())


# ── Output helpers ─────────────────────────────────────────────────────────────


def out_json(data: dict):
    print(json.dumps(data, indent=2))


def out_error(msg: str, json_mode: bool, code: int = 1):
    if json_mode:
        out_json({"ok": False, "error": msg})
    else:
        print("ERROR: " + msg)
    sys.exit(code)


def out_ok(data: dict, json_mode: bool):
    if json_mode:
        out_json({"ok": True, **data})

# ── sketch.yaml management ─────────────────────────────────────────────────────


def project_sketch_yaml_path(apps_path: str, project: str) -> str | None:
    """
    Return the path to a project's sketch.yaml, or None if not found.
    Searches apps_path/<project>/sketch/sketch.yaml.
    """
    candidate = os.path.join(apps_path, project, "sketch", "sketch.yaml")
    if os.path.exists(candidate):
        return candidate
    return None


def rewrite_sketch_yaml(yaml_path: str, project_libs: list[str], libs: dict):
    """
    Rewrite sketch.yaml for a project.

    The libraries section contains:
      - The base Bridge infrastructure entries (always present, unmanaged)
      - One entry per library in project_libs, in the form: Name (version)
      - Dependency entries for each library's declared deps

    Only description fields in app.yaml are quoted strings. sketch.yaml
    library entries are bare identifiers with version in parentheses.
    """
    # Build the managed library lines
    managed_lines = []
    seen = set()

    for lib_name in sorted(project_libs):
        entry = libs["installed"].get(lib_name)
        if not entry:
            continue
        version = entry.get("version", "0.0.0")
        line    = lib_name + " (" + version + ")"
        if line not in seen:
            managed_lines.append(line)
            seen.add(line)
        # Add declared dependencies
        for dep in sorted(libs["dependencies"].get(lib_name, [])):
            dep_entry = libs["installed"].get(dep)
            dep_ver   = dep_entry.get("version", "0.0.0") if dep_entry else "0.0.0"
            dep_line  = "dependency: " + dep + " (" + dep_ver + ")"
            if dep_line not in seen:
                managed_lines.append(dep_line)
                seen.add(dep_line)

    # Collect HybX dir: entries for this project
    hybx_dir_lines = []
    hybx_section   = libs.get("hybx", {})
    for lib_name, hybx_entry in hybx_section.items():
        if project in hybx_entry.get("embedded_in", []):
            install_dir = os.path.join(HYBX_LIBS_DIR, lib_name)
            hybx_dir_lines.append("dir: " + install_dir)

    all_lib_lines = SKETCH_YAML_BASE_LIBS + managed_lines

    with open(yaml_path, "w") as f:
        f.write("profiles:\n")
        f.write("  default:\n")
        f.write("    platforms:\n")
        f.write("      - platform: " + SKETCH_YAML_BASE_PLATFORM + "\n")
        f.write("    libraries:\n")
        for line in all_lib_lines:
            f.write("      - " + line + "\n")
        for line in hybx_dir_lines:
            f.write("      - " + line + "\n")
        f.write("default_profile: default\n")


def rewrite_all_sketch_yamls(libs: dict, apps_path: str, json_mode: bool):
    """
    Rewrite sketch.yaml for every project that has a registered project entry
    in libraries.json and a discoverable sketch.yaml on disk.
    """
    updated = []
    skipped = []

    for project, project_libs in libs["projects"].items():
        yaml_path = project_sketch_yaml_path(apps_path, project)
        if yaml_path:
            rewrite_sketch_yaml(yaml_path, project_libs, libs)
            updated.append(project)
        else:
            skipped.append(project)

    if not json_mode:
        for p in updated:
            print("Updated sketch.yaml: " + p)
        for p in skipped:
            print("Skipped (no sketch.yaml on disk): " + p)

    return updated, skipped

# ── arduino-cli helpers ────────────────────────────────────────────────────────


# ── Commands ───────────────────────────────────────────────────────────────────

def cmd_list(json_mode: bool):
    libs = load_libraries()

    if not libs["installed"]:
        if json_mode:
            out_json({"ok": True, "installed": {}})
        else:
            print("No libraries installed. Use: libs install <name>")
        return

    if json_mode:
        out_json({"ok": True, "installed": libs["installed"]})
        return

    print("Installed libraries:")
    print()
    col_w = max(len(n) for n in libs["installed"]) + 2
    print("  " + "Library".ljust(col_w) + "Version".ljust(12) + "Used By")
    print("  " + "-" * (col_w + 12 + 30))
    for name in sorted(libs["installed"]):
        entry   = libs["installed"][name]
        version = entry.get("version", "?")
        users   = get_library_users(libs, name)
        user_str = ", ".join(users) if users else "(no projects)"
        print("  " + name.ljust(col_w) + version.ljust(12) + user_str)
    print()
    print(str(len(libs["installed"])) + " librar" +
          ("y" if len(libs["installed"]) == 1 else "ies") + " installed.")


def cmd_search(query: str, json_mode: bool):
    code, stdout, stderr = cli_lib_search(query)
    if code != 0:
        out_error("arduino-cli search failed: " + stderr.strip(), json_mode, 2)

    if json_mode:
        # Parse results into structured list
        results = []
        for line in stdout.splitlines():
            if line.startswith("Name:"):
                results.append({"name": line.split("Name:", 1)[1].strip()})
            elif results and line.strip().startswith("Version:"):
                results[-1]["version"] = line.split("Version:", 1)[1].strip()
            elif results and line.strip().startswith("Author:"):
                results[-1]["author"] = line.split("Author:", 1)[1].strip()
            elif results and line.strip().startswith("Sentence:"):
                results[-1]["description"] = line.split("Sentence:", 1)[1].strip()
        out_json({"ok": True, "results": results})
    else:
        print(stdout)


def cmd_install(lib_name: str, json_mode: bool):
    libs = load_libraries()

    if lib_name in libs["installed"]:
        if json_mode:
            out_json({"ok": True, "status": "already_installed",
                      "name": lib_name,
                      "version": libs["installed"][lib_name].get("version")})
        else:
            print(lib_name + " is already installed (" +
                  libs["installed"][lib_name].get("version", "?") + ").")
            print("Use: libs upgrade " + lib_name + "   to upgrade")
        return

    if not json_mode:
        print("Installing: " + lib_name)

    # Capture deps before install
    deps = cli_lib_deps(lib_name)

    code, stdout, stderr = cli_lib_install(lib_name)
    if code != 0:
        out_error("arduino-cli install failed: " + stderr.strip(), json_mode, 2)

    if not json_mode:
        print(stdout.strip())

    # Determine installed version
    version = cli_lib_version(lib_name) or "0.0.0"

    # Record in registry
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S")
    libs["installed"][lib_name] = {
        "version":      version,
        "installed_at": now,
        "description":  "",
    }
    if deps:
        libs["dependencies"][lib_name] = deps
        # Also record each dep in installed if not already there
        for dep in deps:
            if dep not in libs["installed"]:
                dep_ver = cli_lib_version(dep) or "0.0.0"
                libs["installed"][dep] = {
                    "version":      dep_ver,
                    "installed_at": now,
                    "description":  "",
                }

    save_libraries(libs)

    if json_mode:
        out_json({"ok": True, "status": "installed", "name": lib_name,
                  "version": version, "dependencies": deps})
    else:
        print("Installed: " + lib_name + " " + version)
        if deps:
            print("Dependencies: " + ", ".join(deps))
        print()
        print("Use: libs use <project> " + lib_name)
        print("     to add this library to a project.")


def cmd_remove(lib_name: str, json_mode: bool, confirm_mode: bool):
    libs = load_libraries()

    if lib_name not in libs["installed"]:
        out_error(lib_name + " is not installed.", json_mode, 1)

    # ── Hard block: check direct project users ─────────────────────────────────
    users = get_library_users(libs, lib_name)
    if users:
        msg = (lib_name + " is used by: " + ", ".join(users) +
               ". Use 'libs unuse <project> " + lib_name +
               "' for each project first.")
        if json_mode:
            out_json({"ok": False, "error": msg,
                      "conflict": "in_use", "projects": users})
        else:
            print("ERROR: " + msg)
        sys.exit(3)

    # ── Hard block: check dependent library users ──────────────────────────────
    dependents = get_dependent_libraries(libs, lib_name)
    dependent_users = []
    for dep_parent in dependents:
        dep_users = get_library_users(libs, dep_parent)
        if dep_users:
            dependent_users.append((dep_parent, dep_users))

    if dependent_users:
        lines = []
        for dep_parent, dep_users in dependent_users:
            lines.append(dep_parent + " (used by: " + ", ".join(dep_users) + ")")
        msg = (lib_name + " is a dependency of: " + "; ".join(lines) +
               ". Remove those libraries from their projects first.")
        if json_mode:
            out_json({"ok": False, "error": msg,
                      "conflict": "is_dependency",
                      "dependents": [{"library": d, "projects": u}
                                     for d, u in dependent_users]})
        else:
            print("ERROR: " + msg)
        sys.exit(3)

    # ── Confirmation (CLI only) ────────────────────────────────────────────────
    if not json_mode and not confirm_mode:
        if not confirm_prompt("Remove " + lib_name):
            print("Cancelled.")
            return

    # ── Uninstall ──────────────────────────────────────────────────────────────
    code, stdout, stderr = cli_lib_uninstall(lib_name)
    if code != 0:
        out_error("arduino-cli uninstall failed: " + stderr.strip(), json_mode, 2)

    # Remove from registry
    del libs["installed"][lib_name]
    libs["dependencies"].pop(lib_name, None)

    # Clean up any deps that are now orphaned (not depended on by anything else,
    # not directly used by any project)
    orphans = []
    all_remaining_deps = set()
    for dep_list in libs["dependencies"].values():
        all_remaining_deps.update(dep_list)

    for dep in list(libs.get("dependencies", {}).pop(lib_name, [])):
        if dep not in all_remaining_deps and not get_library_users(libs, dep):
            orphans.append(dep)

    save_libraries(libs)

    if json_mode:
        out_json({"ok": True, "status": "removed", "name": lib_name,
                  "orphaned_deps": orphans})
    else:
        print("Removed: " + lib_name)
        if orphans:
            print("Note: the following dependencies may now be orphaned:")
            for o in orphans:
                print("  " + o)
            print("Run 'libs sync' to reconcile, or 'libs remove <name>' for each.")


def cmd_upgrade(lib_name: str | None, json_mode: bool):
    libs = load_libraries()

    if lib_name and lib_name not in libs["installed"]:
        out_error(lib_name + " is not installed.", json_mode, 1)

    if not json_mode:
        if lib_name:
            print("Upgrading: " + lib_name)
        else:
            print("Upgrading all installed libraries...")

    code, stdout, stderr = cli_lib_upgrade(lib_name)
    if code != 0:
        out_error("arduino-cli upgrade failed: " + stderr.strip(), json_mode, 2)

    if not json_mode:
        print(stdout.strip())

    # Refresh versions in registry from what arduino-cli now reports
    updated = []
    for entry in cli_lib_list():
        name = entry["name"]
        if name in libs["installed"]:
            old_ver = libs["installed"][name].get("version")
            new_ver = entry["version"]
            if old_ver != new_ver:
                libs["installed"][name]["version"] = new_ver
                updated.append({"name": name, "from": old_ver, "to": new_ver})

    save_libraries(libs)

    if json_mode:
        out_json({"ok": True, "upgraded": updated})
    else:
        if updated:
            for u in updated:
                print("  " + u["name"] + ": " + u["from"] + " -> " + u["to"])
        else:
            print("All libraries already at latest versions.")


def cmd_show(lib_name: str, json_mode: bool):
    libs = load_libraries()

    if lib_name not in libs["installed"]:
        out_error(lib_name + " is not installed.", json_mode, 1)

    entry   = libs["installed"][lib_name]
    deps    = libs["dependencies"].get(lib_name, [])
    users   = get_library_users(libs, lib_name)
    dep_of  = get_dependent_libraries(libs, lib_name)

    if json_mode:
        out_json({"ok": True, "name": lib_name, "entry": entry,
                  "dependencies": deps, "used_by_projects": users,
                  "dependency_of": dep_of})
        return

    print("Library: " + lib_name)
    print("  Version:       " + entry.get("version", "?"))
    print("  Installed:     " + entry.get("installed_at", "?"))
    if entry.get("description"):
        print("  Description:   " + entry["description"])
    if deps:
        print("  Dependencies:  " + ", ".join(deps))
    if dep_of:
        print("  Dependency of: " + ", ".join(dep_of))
    if users:
        print("  Used by:       " + ", ".join(users))
    else:
        print("  Used by:       (no projects)")


def cmd_use(project: str, lib_name: str, json_mode: bool, apps_path: str):
    libs = load_libraries()

    if lib_name not in libs["installed"]:
        out_error(lib_name + " is not installed. Use: libs install " + lib_name,
                  json_mode, 1)

    project_libs = libs["projects"].setdefault(project, [])

    if lib_name in project_libs:
        if json_mode:
            out_json({"ok": True, "status": "already_assigned",
                      "project": project, "library": lib_name})
        else:
            print(lib_name + " is already assigned to " + project + ".")
        return

    project_libs.append(lib_name)
    project_libs.sort()

    # Rewrite this project's sketch.yaml
    yaml_path = project_sketch_yaml_path(apps_path, project)
    if yaml_path:
        rewrite_sketch_yaml(yaml_path, project_libs, libs)

    save_libraries(libs)

    if json_mode:
        out_json({"ok": True, "status": "assigned",
                  "project": project, "library": lib_name,
                  "sketch_yaml_updated": yaml_path is not None})
    else:
        print("Assigned: " + lib_name + " -> " + project)
        if yaml_path:
            print("Updated:  " + yaml_path)
        else:
            print("Note: no sketch.yaml found for " + project +
                  " — run 'libs update " + project + "' after creating the project.")


def cmd_unuse(project: str, lib_name: str, json_mode: bool, apps_path: str):
    libs = load_libraries()

    project_libs = libs["projects"].get(project, [])

    if lib_name not in project_libs:
        out_error(lib_name + " is not assigned to " + project + ".", json_mode, 1)

    project_libs.remove(lib_name)

    if not project_libs:
        # Keep the project key but with an empty list — preserves intent
        libs["projects"][project] = []
    else:
        libs["projects"][project] = sorted(project_libs)

    # Rewrite this project's sketch.yaml
    yaml_path = project_sketch_yaml_path(apps_path, project)
    if yaml_path:
        rewrite_sketch_yaml(yaml_path, libs["projects"][project], libs)

    save_libraries(libs)

    if json_mode:
        out_json({"ok": True, "status": "unassigned",
                  "project": project, "library": lib_name,
                  "sketch_yaml_updated": yaml_path is not None})
    else:
        print("Unassigned: " + lib_name + " from " + project)
        if yaml_path:
            print("Updated:  " + yaml_path)


def cmd_update(project: str | None, all_projects: bool,
               json_mode: bool, apps_path: str):
    libs = load_libraries()

    if all_projects:
        updated, skipped = rewrite_all_sketch_yamls(libs, apps_path, json_mode)
        if json_mode:
            out_json({"ok": True, "updated": updated, "skipped": skipped})
        return

    if not project:
        out_error("Usage: libs update <project>  or  libs update --all",
                  json_mode, 1)

    project_libs = libs["projects"].get(project)
    if project_libs is None:
        out_error(project + " has no library assignments in registry. "
                  "Use: libs use " + project + " <name>", json_mode, 1)

    yaml_path = project_sketch_yaml_path(apps_path, project)
    if not yaml_path:
        out_error("No sketch.yaml found for " + project + " under " + apps_path,
                  json_mode, 1)

    rewrite_sketch_yaml(yaml_path, project_libs, libs)

    if json_mode:
        out_json({"ok": True, "updated": [project], "path": yaml_path})
    else:
        print("Updated: " + yaml_path)


def cmd_sync(json_mode: bool, apps_path: str = ""):
    """
    Rebuild installed + dependencies from filesystem scan.
    Also auto-assigns project libraries by scanning sketch.ino #include
    statements. Delegates to cmd_sync_inner in libs_helpers.
    """
    result = cmd_sync_inner(json_mode=json_mode, apps_path=apps_path)
    if json_mode:
        out_json({"ok": True, "added": result["added"],
                  "removed": result["removed"], "total": result["total"],
                  "assigned": result.get("assigned", {})})



def cmd_install_git(url: str, json_mode: bool):
    """
    Install a HybX library from a git URL.

    Clones the repo into HYBX_LIBS_DIR/<lib_name>/ or pulls if already
    present. Registers the library in libraries.json under "hybx".
    Does NOT add the library to sketch.yaml — HybX libraries are not in
    the Arduino Library Manager and must be embedded per-project via
    'libs embed'.
    """
    if not url.startswith("http") and not url.startswith("git@"):
        out_error("URL must be a git URL (https:// or git@)", json_mode, 1)

    lib_name = get_hybx_lib_name_from_url(url)

    if not json_mode:
        print("Installing HybX library: " + lib_name)
        print("From: " + url)

    code, msg = cli_lib_install_git(url)
    if code != 0:
        out_error(msg, json_mode, 2)

    # Read version from library.properties
    lib_dir   = os.path.join(HYBX_LIBS_DIR, lib_name)
    props     = read_library_properties(lib_dir)
    version   = props["version"] if props else "0.0.0"
    desc      = props["description"] if props else ""

    # Register in libraries.json under "hybx" section
    libs = load_libraries()
    if "hybx" not in libs:
        libs["hybx"] = {}
    existing = libs["hybx"].get(lib_name, {})
    import datetime as _dt
    now = _dt.datetime.now(_dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%S")
    libs["hybx"][lib_name] = {
        "url":          url,
        "version":      version,
        "description":  desc,
        "installed_at": existing.get("installed_at", now),
        "updated_at":   now,
        "embedded_in":  existing.get("embedded_in", []),
    }
    save_libraries(libs)

    if json_mode:
        out_json({"ok": True, "status": "installed", "name": lib_name,
                  "version": version, "url": url})
    else:
        print()
        print("Installed: " + lib_name + " " + version)
        print("Location:  " + lib_dir)
        print()
        print("arduino-cli will auto-discover this library during compilation.")
        print("In sketch.ino, use: #include <" + lib_name + ".h>")
        print("No sketch.yaml entry required.")


def cmd_embed(project: str, lib_name: str,
              json_mode: bool, apps_path: str):
    """
    Link a HybX library into a project by adding a dir: entry to sketch.yaml.

    arduino-cli sketch profiles support 'dir: /path/to/library' references
    (LocalLibrary RPC type). arduino-cli compiles them using RecursiveLayout,
    meaning src/ subdirectories are compiled recursively. This is the correct
    mechanism for local libraries that are not in the Arduino Library Manager.

    The library must already be installed via:
      libs install-git <url>

    This command:
    1. Verifies the library is installed in HYBX_LIBS_DIR
    2. Records the project in libraries.json hybx[lib][embedded_in]
    3. Rewrites sketch.yaml to add: - dir: /path/to/library

    The sketch uses #include <lib_name.h> (angle brackets).
    """
    libs = load_libraries()

    if "hybx" not in libs or lib_name not in libs.get("hybx", {}):
        out_error(
            lib_name + " is not installed as a HybX library.\n"
            "Run: libs install-git <url>  first.",
            json_mode, 1
        )

    sketch_dir = os.path.join(apps_path, project, "sketch")
    if not os.path.isdir(sketch_dir):
        out_error(
            "Sketch directory not found: " + sketch_dir + "\n"
            "Check that the project exists: project list",
            json_mode, 1
        )

    # Verify the library is installed and get its path
    ok, install_dir = copy_hybx_lib_to_sketch(lib_name, sketch_dir)
    if not ok:
        out_error(install_dir, json_mode, 2)

    # Record the embedding so rewrite_sketch_yaml emits the dir: entry
    embedded_in = libs["hybx"][lib_name].get("embedded_in", [])
    if project not in embedded_in:
        embedded_in.append(project)
        embedded_in.sort()
        libs["hybx"][lib_name]["embedded_in"] = embedded_in
        save_libraries(libs)
        libs = load_libraries()  # reload so rewrite sees updated embedded_in

    # Rewrite sketch.yaml to include the dir: entry
    yaml_path = os.path.join(apps_path, project, "sketch", "sketch.yaml")
    if os.path.exists(yaml_path):
        project_libs = libs["projects"].get(project, [])
        rewrite_sketch_yaml(yaml_path, project_libs, libs)
        if not json_mode:
            print("Updated: " + yaml_path)

    if json_mode:
        out_json({"ok": True, "status": "embedded", "library": lib_name,
                  "project": project, "install_dir": install_dir})
    else:
        print()
        print("dir: entry added to sketch.yaml pointing to:")
        print("  " + install_dir)
        print()
        print("In sketch.ino, use:")
        print('  #include <' + lib_name + '.h>')


def cmd_check(project: str, json_mode: bool):
    """
    Verify every library assigned to a project is actually installed.
    Used by build as a pre-flight check.
    Exit code 0 = all good. Exit code 1 = missing libraries.
    """
    libs = load_libraries()

    project_libs = libs["projects"].get(project, [])
    missing      = [n for n in project_libs if n not in libs["installed"]]

    if json_mode:
        out_json({"ok": len(missing) == 0, "project": project,
                  "assigned": project_libs, "missing": missing})
    else:
        if missing:
            print("ERROR: " + project + " requires libraries that are not installed:")
            for m in missing:
                print("  " + m)
            print("Run: libs install <name>   for each missing library.")
            sys.exit(1)
        else:
            print("OK: all libraries for " + project + " are installed.")

# ── Usage ──────────────────────────────────────────────────────────────────────


def usage():
    print("Usage:")
    print("  libs list                        - List all installed libraries")
    print("  libs search <name>               - Search Arduino Library Manager")
    print("  libs install <name>              - Install library globally")
    print("  libs remove <name>               - Remove library (blocked if in use)")
    print("  libs upgrade                     - Upgrade all installed libraries")
    print("  libs upgrade <name>              - Upgrade one library")
    print("  libs show <name>                 - Show library details")
    print("  libs use <project> <name>        - Assign library to a project")
    print("  libs unuse <project> <name>      - Remove library from a project")
    print("  libs update <project>            - Rewrite project sketch.yaml")
    print("  libs update --all                - Rewrite all sketch.yaml files")
    print("  libs sync                        - Rebuild registry from arduino-cli")
    print("  libs check <project>             - Verify project libraries installed")
    print()
    print("HybX library subcommands (not in Arduino Library Manager):")
    print("  libs install-git <url>           - Install HybX library from git URL")
    print("  libs embed <project> <lib>       - Embed HybX library into project sketch")
    print()
    print("Flags:")
    print("  --json      Machine-readable JSON output")
    print("  --confirm   Skip confirmation prompts")

# ── Main ───────────────────────────────────────────────────────────────────────


def main():
    args, json_mode, confirm_mode = parse_args()

    if not json_mode:
        print("=== libs ===")

    if not args:
        usage()
        sys.exit(1)

    SUBCOMMANDS = [
        "list", "search", "install", "remove", "upgrade", "show",
        "use", "unuse", "update", "sync", "check", "install-git", "embed"
    ]

    subcommand = resolve_subcommand(args[0], SUBCOMMANDS)

    # Board context needed for apps_path (used by use/unuse/update)
    # Loaded lazily — not all subcommands need it
    _board_cache = {}

    def get_apps_path() -> str:
        if "apps_path" not in _board_cache:
            board = get_active_board()
            _board_cache["apps_path"] = board["apps_path"]
        return _board_cache["apps_path"]

    if subcommand == "list":
        cmd_list(json_mode)

    elif subcommand == "search":
        if len(args) < 2:
            out_error("Usage: libs search <name>", json_mode, 1)
        cmd_search(normalize_lib_name(" ".join(args[1:])), json_mode)

    elif subcommand == "install":
        if len(args) < 2:
            out_error("Usage: libs install <name>", json_mode, 1)
        cmd_install(normalize_lib_name(" ".join(args[1:])), json_mode)

    elif subcommand == "remove":
        if len(args) < 2:
            out_error("Usage: libs remove <name>", json_mode, 1)
        cmd_remove(normalize_lib_name(" ".join(args[1:])), json_mode, confirm_mode)

    elif subcommand == "upgrade":
        lib_name = normalize_lib_name(" ".join(args[1:])) if len(args) >= 2 else None
        cmd_upgrade(lib_name, json_mode)

    elif subcommand == "show":
        if len(args) < 2:
            out_error("Usage: libs show <name>", json_mode, 1)
        cmd_show(normalize_lib_name(" ".join(args[1:])), json_mode)

    elif subcommand == "use":
        if len(args) < 3:
            out_error("Usage: libs use <project> <name>", json_mode, 1)
        cmd_use(args[1], normalize_lib_name(" ".join(args[2:])), json_mode, get_apps_path())

    elif subcommand == "unuse":
        if len(args) < 3:
            out_error("Usage: libs unuse <project> <name>", json_mode, 1)
        cmd_unuse(args[1], normalize_lib_name(" ".join(args[2:])), json_mode, get_apps_path())

    elif subcommand == "update":
        all_flag = "--all" in sys.argv
        project  = args[1] if len(args) >= 2 else None
        cmd_update(project, all_flag, json_mode, get_apps_path())

    elif subcommand == "sync":
        cmd_sync(json_mode, apps_path=get_apps_path())

    elif subcommand == "check":
        if len(args) < 2:
            out_error("Usage: libs check <project>", json_mode, 1)
        cmd_check(args[1], json_mode)

    elif subcommand == "install-git":
        if len(args) < 2:
            out_error("Usage: libs install-git <url>", json_mode, 1)
        cmd_install_git(args[1], json_mode)

    elif subcommand == "embed":
        if len(args) < 3:
            out_error("Usage: libs embed <project> <lib_name>", json_mode, 1)
        cmd_embed(args[1], args[2], json_mode, get_apps_path())

    else:
        out_error("Unknown subcommand: " + subcommand, json_mode, 1)


if __name__ == "__main__":
    main()
