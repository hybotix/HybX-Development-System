#!/usr/bin/env python3

"""
project-v0.0.3.py
Hybrid RobotiX — HybX Development System

Manages projects for the active board.
Projects live under a project type directory within the board's apps directory.

Usage:
  project list                       - List projects for the active board
  project list --names               - List project names only
  project new <type> <name>          - Create a new project scaffold
  project use <name>                 - Set the active project
  project show                       - Show the active project
  project remove <name>              - Remove a project (local only)

Project types (case insensitive):
  arduino     → Arduino/
  micropython → MicroPython/
  ros2        → ROS2/

Examples:
  project new arduino    lis3dh
  project new micropython sensor-display
  project new ros2       navigation
"""

import os
import sys
sys.path.insert(0, os.path.dirname(os.path.realpath(__file__)))

import json  # noqa: E402
import shutil  # noqa: E402

from hybx_config import get_active_board, get_push_url, confirm_prompt  # noqa: E402

CONFIG_DIR    = os.path.expanduser("~/.hybx")
CONFIG_FILE   = os.path.join(CONFIG_DIR, "config.json")
LAST_APP_FILE = os.path.join(CONFIG_DIR, "last_app")

# ── Project type normalization ─────────────────────────────────────────────────
PROJECT_TYPES = {
    "arduino":     "Arduino",
    "micropython": "MicroPython",
    "ros2":        "ROS2",
    "ml":          "ML",
}


def normalize_project_type(raw: str) -> str | None:
    """Normalize project type string to canonical form. Returns None if unknown."""
    return PROJECT_TYPES.get(raw.lower())

# ── Config helpers ─────────────────────────────────────────────────────────────


def load_config() -> dict:
    if not os.path.exists(CONFIG_FILE):
        return {"boards": {}, "active_board": None}
    with open(CONFIG_FILE, "r") as f:
        return json.load(f)


def save_config(config: dict):
    os.makedirs(CONFIG_DIR, exist_ok=True)
    with open(CONFIG_FILE, "w") as f:
        json.dump(config, f, indent=2)


def save_last_app(app_name: str):
    os.makedirs(CONFIG_DIR, exist_ok=True)
    with open(LAST_APP_FILE, "w") as f:
        f.write(app_name)


def get_active_project(config: dict, board_name: str) -> str | None:
    return config.get("board_projects", {}).get(board_name, {}).get("active")


def set_active_project(config: dict, board_name: str, project_name: str | None):
    if "board_projects" not in config:
        config["board_projects"] = {}
    if board_name not in config["board_projects"]:
        config["board_projects"][board_name] = {}
    config["board_projects"][board_name]["active"] = project_name

# ── Scaffold templates ─────────────────────────────────────────────────────────


SKETCH_INO = """\
/**
 * {name}
 * Hybrid RobotiX
 *
 * Arduino sketch for {name}.
 */

#include <Arduino_RouterBridge.h>

// ── Bridge functions ──────────────────────────────────────────────────────────

// Add Bridge.provide() calls here before setup()

// ── Setup ─────────────────────────────────────────────────────────────────────

void setup() {{
    Bridge.begin();
    // Initialize sensors and hardware here
}}

// ── Loop ──────────────────────────────────────────────────────────────────────

void loop() {{
    // Main loop — keep empty when using Bridge
}}
"""

SKETCH_YAML = """\
profiles:
  default:
    platforms:
      - platform: arduino:zephyr
    libraries:
      - Arduino_RouterBridge (0.3.0)
      - dependency: Arduino_RPClite (0.2.1)
      - dependency: ArxContainer (0.7.0)
      - dependency: ArxTypeTraits (0.3.2)
      - dependency: DebugLog (0.8.4)
      - dependency: MsgPack (0.4.2)
default_profile: default
"""

MAIN_PY = """\
from arduino.app_utils import App, Bridge
import time

def loop():
    \"\"\"Main loop — called repeatedly by App.run().\"\"\"
    pass  # TODO: Add Bridge.call() reads and processing here

App.run(user_loop=loop)
"""

REQUIREMENTS_TXT = """\
# Python dependencies for {name}
# Add pip packages here, one per line
"""

APP_YAML = """\
name: {name}
icon: 🤖
description: {name} app for Hybrid RobotiX
type: {project_type}
"""

ML_MAIN_PY = """\
from arduino.app_utils import App, Bridge
from edge_impulse_linux.runner import ImpulseRunner
import time
import os

MODEL_PATH = os.path.join(os.path.dirname(__file__), "..", "ml", "models", "model.eim")

runner = ImpulseRunner(MODEL_PATH)
model_info = runner.init()

print("Model loaded: " + model_info["project"]["name"])
print("Labels: " + str(model_info["model_parameters"]["labels"]))

def loop():
    \"\"\"Main inferencing loop — reads sensor data via Bridge, runs classification.\"\"\"
    # TODO: Read sensor features from Bridge
    features = []  # Replace with actual sensor data
    if features:
        result = runner.classify(features)
        print("Classification: " + str(result["result"]["classification"]))
    time.sleep(0.1)

App.run(user_loop=loop)
"""

ML_REQUIREMENTS_TXT = """\
# Python dependencies for {name}
edge-impulse-linux
"""

# ── Commands ───────────────────────────────────────────────────────────────────


def cmd_list(names_only: bool = False):
    board     = get_active_board()
    apps_path = board["apps_path"]
    config    = load_config()
    active    = get_active_project(config, board["name"])

    if not os.path.exists(apps_path):
        print("Apps directory does not exist on this machine.")
        print("Run 'update' to set up the board environment.")
        return

    # Projects live directly in apps_path — identify them by presence of app.yaml
    all_projects = sorted([
        d for d in os.listdir(apps_path)
        if os.path.isdir(os.path.join(apps_path, d))
        and os.path.exists(os.path.join(apps_path, d, "app.yaml"))
    ])

    if not all_projects:
        print("No projects found. Use: project new <type> <n>")
        return

    if names_only:
        for p in all_projects:
            print(p)
        return

    print(f"Board: {board['name']} ({board['host']})")
    print(f"Apps path: {apps_path}")
    print()

    for p in all_projects:
        marker = " *" if p == active else "  "
        print(f"{marker} {p}")

    print()

    if active:
        print(f"Active project: {active}")
    else:
        print("No active project. Use: project use <n>")


def cmd_new(project_type_raw: str, name: str):
    project_type = normalize_project_type(project_type_raw)

    if not project_type:
        print(f"ERROR: Unknown project type '{project_type_raw}'")
        print(f"Valid types: {', '.join(PROJECT_TYPES.keys())}")
        sys.exit(1)

    board     = get_active_board()
    apps_path = board["apps_path"]

    # Local project path: <apps_path>/<n>
    # apps_path already includes the board name e.g. ~/Arduino/UNO-Q
    project_path = os.path.join(apps_path, name)

    # Repo path: ~/Repos/GitHub/hybotix/UNO-Q/Arduino/<board>/<n>
    repo_root = os.path.expanduser(
        f"~/Repos/GitHub/{board['repo'].split('github.com/')[-1].replace('.git', '')}"
    )
    repo_project_path = os.path.join(repo_root, "Arduino", board["name"], name)

    print(f"=== project new ===")
    print(f"Type:  {project_type}")
    print(f"Name:  {name}")
    print(f"Board: {board['name']} ({board['host']})")
    print()

    if os.path.exists(project_path):
        print(f"ERROR: Project '{name}' already exists at {project_path}")
        sys.exit(1)

    # Create directory structure
    sketch_dir = os.path.join(project_path, "sketch")
    python_dir = os.path.join(project_path, "python")
    os.makedirs(sketch_dir, exist_ok=True)
    os.makedirs(python_dir, exist_ok=True)
    print(f"Created: {project_path}/")

    # Write scaffold files
    files = {
        os.path.join(sketch_dir, "sketch.ino"):       SKETCH_INO.format(name=name),
        os.path.join(sketch_dir, "sketch.yaml"):      SKETCH_YAML,
        os.path.join(python_dir, "main.py"):          ML_MAIN_PY.format(name=name) if project_type == "ML" else MAIN_PY.format(name=name),
        os.path.join(python_dir, "requirements.txt"): ML_REQUIREMENTS_TXT.format(name=name) if project_type == "ML" else REQUIREMENTS_TXT.format(name=name),
        os.path.join(project_path, "app.yaml"):       APP_YAML.format(name=name, project_type=project_type),
    }

    for path, content in files.items():
        with open(path, "w") as f:
            f.write(content)
        print(f"Created: {os.path.relpath(path, apps_path)}")

    # ── ML project — create ml/ scaffold ──────────────────────────────────────
    if project_type == "ML":
        from ml_helpers import ML_DIR, DATA_DIR, MODELS_DIR, save_ml_yaml
        ml_dir     = os.path.join(project_path, ML_DIR)
        data_dir   = os.path.join(project_path, DATA_DIR)
        models_dir = os.path.join(project_path, MODELS_DIR)
        os.makedirs(data_dir,   exist_ok=True)
        os.makedirs(models_dir, exist_ok=True)
        print(f"Created: {os.path.relpath(data_dir, apps_path)}/")
        print(f"Created: {os.path.relpath(models_dir, apps_path)}/")

        # Write ml.yaml
        save_ml_yaml(project_path, {
            "project_name":  name,
            "ml_platform":   board.get("ml_platform", "edge-impulse"),
            "ml_project_id": board.get("ml_project_id", ""),
            "sensor_type":   "custom",
            "labels":        "",
        })
        print(f"Created: {os.path.relpath(os.path.join(project_path, 'ml', 'ml.yaml'), apps_path)}")

        # .gitignore for ml/ — exclude large model and data files
        gitignore = os.path.join(ml_dir, ".gitignore")
        with open(gitignore, "w") as f:
            f.write("# Exclude trained model files and collected data from repo\n")
            f.write("models/*.eim\n")
            f.write("data/\n")
        print(f"Created: {os.path.relpath(gitignore, apps_path)}")

    # Set as active project
    config = load_config()
    set_active_project(config, board["name"], name)
    save_config(config)
    save_last_app(name)
    print(f"\nActive project set to: {name}")
    print(f"\nProject '{name}' ready.")
    if project_type == "ML":
        print(f"Use 'project collect {name}' to collect training data.")
        print(f"Use 'project model download' after training in Studio.")
        print(f"Use 'start {name}' to run inferencing.")
    else:
        print(f"Use 'start {name}' to build and run.")


def cmd_use(name: str):
    board     = get_active_board()
    apps_path = board["apps_path"]

    # Search directly in apps_path first (flat layout)
    found_path = None
    direct = os.path.join(apps_path, name)
    if os.path.isdir(direct):
        found_path = direct

    # Fall back to searching inside type subdirectories
    if not found_path:
        for type_dir in os.listdir(apps_path):
            candidate = os.path.join(apps_path, type_dir, name)
            if os.path.isdir(candidate):
                found_path = candidate
                break

    if not found_path:
        print(f"ERROR: Project '{name}' not found in {apps_path}")
        sys.exit(1)

    config = load_config()
    set_active_project(config, board["name"], name)
    save_config(config)
    save_last_app(name)
    print(f"Active project set to: {name}")


def cmd_show():
    board  = get_active_board()
    config = load_config()
    active = get_active_project(config, board["name"])

    print(f"Board: {board['name']} ({board['host']})")

    if active:
        print(f"Active project: {active}")
    else:
        print("No active project. Use: project use <name>")


def cmd_remove(name: str):
    board     = get_active_board()
    apps_path = board["apps_path"]

    # Search directly in apps_path first (flat layout)
    found_path = None
    direct = os.path.join(apps_path, name)
    if os.path.isdir(direct):
        found_path = direct

    # Fall back to searching inside type subdirectories
    if not found_path:
        for type_dir in os.listdir(apps_path):
            candidate = os.path.join(apps_path, type_dir, name)
            if os.path.isdir(candidate):
                found_path = candidate
                break

    if not found_path:
        print(f"ERROR: Project '{name}' not found in {apps_path}")
        sys.exit(1)

    if not confirm_prompt("Remove project '" + name + "' from local disk"):
        print("Cancelled.")
        return

    shutil.rmtree(found_path)
    print(f"Removed: {found_path}")

    config = load_config()

    if get_active_project(config, board["name"]) == name:
        set_active_project(config, board["name"], None)
        save_config(config)
        print(f"Note: Active project cleared. Use: project use <name>")


# ── ML subcommands ─────────────────────────────────────────────────────────────


def cmd_collect(name: str):
    """
    Collect sensor data from the active board and upload to the ML platform.
    Data is saved locally in ml/data/ and uploaded to the configured platform.
    """
    board     = get_active_board()
    apps_path = board["apps_path"]

    project_path = os.path.join(apps_path, name)
    if not os.path.isdir(project_path):
        print(f"ERROR: Project '{name}' not found in {apps_path}")
        sys.exit(1)

    from ml_helpers import is_ml_project, get_backend, MLError, DATA_DIR
    if not is_ml_project(project_path):
        print(f"ERROR: '{name}' is not an ML project.")
        print("Use: project new ml <n>   to create an ML project")
        sys.exit(1)

    try:
        backend = get_backend(board)
    except MLError as e:
        print("ERROR: " + str(e))
        sys.exit(1)

    data_dir = os.path.join(project_path, DATA_DIR)
    os.makedirs(data_dir, exist_ok=True)

    print(f"=== project collect ===")
    print(f"Project: {name}")
    print(f"Data directory: {data_dir}")
    print()
    print("Collecting sensor data via data forwarder ...")
    print("Press Ctrl+C to stop collection.")
    print()

    import subprocess
    result = subprocess.run([
        "edge-impulse-data-forwarder",
        "--api-key", board.get("ml_api_key", ""),
        "--frequency", "100",
    ])

    if result.returncode != 0:
        print("ERROR: Data collection failed.")
        sys.exit(result.returncode)

    print()
    print("Data collection complete.")


def cmd_model(subcommand: str):
    """
    Manage ML models for the active project.

    Subcommands:
      download  -- Download the latest trained model from the ML platform
      info      -- Show model details and performance metrics
      list      -- List available trained models
    """
    board     = get_active_board()
    apps_path = board["apps_path"]

    config = load_config()
    name   = get_active_project(config, board["name"])

    if not name:
        print("ERROR: No active project. Use: project use <n>")
        sys.exit(1)

    project_path = os.path.join(apps_path, name)

    from ml_helpers import is_ml_project, get_backend, get_model_path, MLError, MODEL_FILE, MODELS_DIR
    if not is_ml_project(project_path):
        print(f"ERROR: '{name}' is not an ML project.")
        print("Use: project new ml <n>   to create an ML project")
        sys.exit(1)

    try:
        backend = get_backend(board)
    except MLError as e:
        print("ERROR: " + str(e))
        sys.exit(1)

    model_path = os.path.join(project_path, MODEL_FILE)

    if subcommand == "download":
        print(f"=== project model download ===")
        print(f"Project: {name}")
        print(f"Destination: {model_path}")
        print()
        print("Downloading trained model ...")
        try:
            backend.download_model(model_path)
            print("Model downloaded: " + model_path)
            size = os.path.getsize(model_path)
            print(f"Size: {size // 1024} KB")
        except MLError as e:
            print("ERROR: " + str(e))
            sys.exit(1)

    elif subcommand == "info":
        print(f"=== project model info ===")
        print(f"Project: {name}")
        model = get_model_path(project_path)
        if not model:
            print("ERROR: No model found. Run: project model download")
            sys.exit(1)
        try:
            info = backend.model_info(model)
            print()
            for key, value in info.items():
                print(f"  {key}: {value}")
        except MLError as e:
            print("ERROR: " + str(e))
            sys.exit(1)

    elif subcommand == "list":
        print(f"=== project model list ===")
        try:
            models = backend.list_models()
            if not models:
                print("No trained models found.")
            else:
                for m in models:
                    print(f"  {m}")
        except MLError as e:
            print("ERROR: " + str(e))
            sys.exit(1)

    else:
        print(f"ERROR: Unknown model subcommand '{subcommand}'")
        print("Usage: project model download|info|list")
        sys.exit(1)


def usage():
    print("Usage:")
    print("  project list                  - List projects for the active board")
    print("  project list --names          - List project names only, one per line")
    print("  project new <type> <name>     - Create a new project scaffold")
    print("  project use <name>            - Set the active project")
    print("  project show                  - Show the active project")
    print("  project remove <name>         - Remove a project (local only)")
    print()
    print()
    print("ML subcommands:")
    print("  project collect <n>           - Collect sensor data and upload to ML platform")
    print("  project model download        - Download trained model from ML platform")
    print("  project model info            - Show model details and performance metrics")
    print("  project model list            - List available trained models")
    print()
    print("Project types: arduino, micropython, ros2, ml")

# ── Main ───────────────────────────────────────────────────────────────────────


def main():
    os.system("clear")
    print("=== project ===")

    if len(sys.argv) < 2:
        usage()
        sys.exit(1)

    command = sys.argv[1]

    if command == "list":
        names_only = "--names" in sys.argv
        cmd_list(names_only=names_only)
    elif command == "show":
        cmd_show()
    elif command == "new":
        if len(sys.argv) < 4:
            print("Usage: project new <type> <name>")
            print("Example: project new arduino lis3dh")
            sys.exit(1)
        cmd_new(sys.argv[2], " ".join(sys.argv[3:]))
    elif command == "use":
        if len(sys.argv) < 3:
            print("Usage: project use <name>")
            sys.exit(1)
        cmd_use(" ".join(sys.argv[2:]))
    elif command == "remove":
        if len(sys.argv) < 3:
            print("Usage: project remove <name>")
            sys.exit(1)
        cmd_remove(" ".join(sys.argv[2:]))
    else:
        print(f"ERROR: Unknown command '{command}'")
        usage()
        sys.exit(1)


if __name__ == "__main__":
    main()