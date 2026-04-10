#!/usr/bin/env python3
"""
update-v0.0.1.py
Hybrid RobotiX — HybX Development System

Wrapper for update.bash. Ensures the working directory is set to $HOME
before running update.bash so that bash never loses its cwd when the
Repos directory is wiped and recreated during bootstrap.

update.bash is untouchable — this wrapper is the fix.
"""

import os
import sys
import subprocess


def main():
    home        = os.path.expanduser("~")
    update_bash = os.path.join(home, "bin", "update.bash")

    if not os.path.exists(update_bash):
        # Fall back to scripts location in the repo
        update_bash = os.path.join(
            home,
            "Repos", "GitHub", "hybotix",
            "HybX-Development-System", "scripts", "update.bash"
        )

    if not os.path.exists(update_bash):
        print("ERROR: update.bash not found.")
        sys.exit(1)

    # Change to $HOME before running so bash never loses its cwd
    # when REPO_DEST is wiped during bootstrap.
    os.chdir(home)

    result = subprocess.run(["bash", update_bash])
    sys.exit(result.returncode)


if __name__ == "__main__":
    main()
