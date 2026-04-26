#!/usr/bin/env python3
"""
setup-v1.1.0.py
Hybrid RobotiX — HybX Development System

One-time setup for the UNO Q development environment.

What this does:
  - Installs ino.nanorc to ~/.local/share/nano/ for Arduino sketch syntax highlighting in nano
    (user-writable — no sudo required)

What this does NOT do (manual steps — see README):
  - Install nanorc to ~/.nanorc (optional, user preference)

Usage:
  setup
"""

import os
import shutil
import sys

REPO_ROOT      = os.path.expanduser("~/Repos/GitHub/hybotix/HybX-Development-System")
INO_NANORC_SRC = os.path.join(REPO_ROOT, "config", "ino.nanorc")
INO_NANORC_DST_DIR = os.path.expanduser("~/.local/share/nano")
INO_NANORC_DST     = os.path.join(INO_NANORC_DST_DIR, "ino.nanorc")


def main():
    os.system("clear")
    print("=== setup ===")
    print()

    # Install ino.nanorc
    if not os.path.exists(INO_NANORC_SRC):
        print(f"ERROR: {INO_NANORC_SRC} not found — run update first.")
        sys.exit(1)

    os.makedirs(INO_NANORC_DST_DIR, exist_ok=True)
    print(f"Installing: {INO_NANORC_SRC} -> {INO_NANORC_DST}")
    shutil.copy2(INO_NANORC_SRC, INO_NANORC_DST)
    print("Done: ino.nanorc installed — Arduino sketch syntax highlighting enabled in nano.")
    print()
    print("Optional: to use the recommended nanorc configuration:")
    print(f"  cp {REPO_ROOT}/config/nanorc ~/.nanorc")


if __name__ == "__main__":
    main()
