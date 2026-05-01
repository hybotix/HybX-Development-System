#!/usr/bin/env python3

"""
clone-v1.0.0.py
Hybrid RobotiX — HybX Development System

Clone an existing app to a new app with a new name.
Updates app.yaml name field. Preserves all sketch and Python code.

Usage:
  clone <source_app> <new_app_name>
"""

import os
import sys
import shutil
sys.path.insert(0, os.path.dirname(os.path.realpath(__file__)))
sys.path.insert(0, os.path.expanduser("~/lib"))

from hybx_config import get_active_board  # noqa: E402

LAST_APP_FILE = os.path.expanduser("~/.hybx/last_app")


def main():
    print("=== clone ===")

    board = get_active_board()
    print(f"Board: {board['name']} ({board['host']})")

    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    if len(args) < 2:
        print("Usage: clone <source_app> <new_app_name>")
        sys.exit(1)

    source_name = args[0]
    new_name     = args[1]

    apps_path   = os.path.expanduser(board["apps_path"])
    source_path = os.path.join(apps_path, source_name)
    new_path    = os.path.join(apps_path, new_name)

    if not os.path.isdir(source_path):
        print(f"ERROR: Source app not found: {source_path}")
        sys.exit(1)

    if os.path.exists(new_path):
        print(f"ERROR: Destination already exists: {new_path}")
        sys.exit(1)

    # Copy the app directory — exclude .cache
    def ignore_cache(src, names):
        return [n for n in names if n == ".cache"]

    shutil.copytree(source_path, new_path, ignore=ignore_cache)
    print(f"Cloned: {source_name} → {new_name}")

    # Update app.yaml name field if it exists
    app_yaml = os.path.join(new_path, "app.yaml")
    if os.path.exists(app_yaml):
        with open(app_yaml, "r") as f:
            content = f.read()
        # Replace the name field
        import re
        content = re.sub(
            r'^name:.*$',
            f'name: {new_name}',
            content,
            flags=re.MULTILINE
        )
        with open(app_yaml, "w") as f:
            f.write(content)
        print(f"Updated app.yaml: name → {new_name}")

    # Save as last app
    os.makedirs(os.path.dirname(LAST_APP_FILE), exist_ok=True)
    with open(LAST_APP_FILE, "w") as f:
        f.write(new_name)

    print(f"Done. Run 'clean {new_name}' to build and start.")


if __name__ == "__main__":
    main()
