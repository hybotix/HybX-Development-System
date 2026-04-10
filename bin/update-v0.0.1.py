#!/usr/bin/env python3
"""
update-v0.0.1.py
Hybrid RobotiX — HybX Development System

Wrapper for update.bash. Changes the working directory to $HOME before
running update.bash so that the shell never loses its cwd when the Repos
directory is wiped and recreated during bootstrap.

update.bash is untouchable. This wrapper is the fix for the getcwd errors
that occur when update is run from inside the Repos directory.
"""

import os
import sys
import subprocess


def main():
    home = os.path.expanduser("~")

    # Always change to $HOME before running update.bash.
    # This prevents the shell from losing its cwd when REPO_DEST
    # is wiped during bootstrap.
    os.chdir(home)

    update_bash = os.path.join(home, "update.bash")

    if not os.path.exists(update_bash):
        print("ERROR: ~/update.bash not found.")
        print("Copy it manually: cp <repo>/scripts/update.bash ~/update.bash")
        sys.exit(1)

    result = subprocess.run(["bash", update_bash])
    sys.exit(result.returncode)


if __name__ == "__main__":
    main()
