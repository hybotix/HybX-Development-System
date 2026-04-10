#!/usr/bin/env python3
"""
setup-v0.0.1.py
Hybrid RobotiX — HybX Development System

One-time setup for the UNO Q development environment.

What this does:
  - Installs ino.nanorc to /usr/share/nano/ for Arduino sketch syntax highlighting in nano

What this does NOT do (manual steps — see README):
  - Install nanorc to ~/.nanorc (optional, user preference)

Usage:
  setup
"""

import os
import shutil
import sys

REPO_ROOT = os.path.expanduser("~/Repos/GitHub/hybotix/HybX-Development-System")
INO_NANORC_SRC = os.path.join(REPO_ROOT, "config", "ino.nanorc")
INO_NANORC_DST = "/usr/share/nano/ino.nanorc"


def main():
    os.system("clear")
    print("=== setup ===")
    print()

    # Install ino.nanorc
    if not os.path.exists(INO_NANORC_SRC):
        print(f"ERROR: {INO_NANORC_SRC} not found — run update first.")
        sys.exit(1)

    print(f"Installing: {INO_NANORC_SRC} -> {INO_NANORC_DST}")
    result = os.system(f"sudo cp {INO_NANORC_SRC} {INO_NANORC_DST}")
    if result != 0:
        print("ERROR: Failed to install ino.nanorc — sudo required.")
        sys.exit(1)
    print("Done: ino.nanorc installed — Arduino sketch syntax highlighting enabled in nano.")
    print()
    print("Optional: to use the recommended nanorc configuration:")
    print(f"  cp {REPO_ROOT}/config/nanorc ~/.nanorc")


if __name__ == "__main__":
    main()
