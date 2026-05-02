#!/usr/bin/env python3
"""
setup-v1.3.0.py
Hybrid RobotiX — HybX Development System

One-time setup for the UNO Q development environment.

What this does:
  - Installs ino.nanorc to ~/.local/share/nano/ for Arduino sketch syntax highlighting
  - Adds pcd() shell function to ~/.bashrc for easy project directory navigation

What this does NOT do (manual steps — see README):
  - Install nanorc to ~/.nanorc (optional, user preference)

Usage:
  setup

v1.3.0: Added pcd() shell function to ~/.bashrc
"""

import os
import shutil
import sys

REPO_ROOT          = os.path.expanduser("~/Repos/GitHub/hybotix/HybX-Development-System")
INO_NANORC_SRC     = os.path.join(REPO_ROOT, "config", "ino.nanorc")
INO_NANORC_DST_DIR = os.path.expanduser("~/.local/share/nano")
INO_NANORC_DST     = os.path.join(INO_NANORC_DST_DIR, "ino.nanorc")
BASHRC             = os.path.expanduser("~/.bashrc")

# Shell function added to ~/.bashrc
# pcd        — cd to active project (reads ~/.hybx/last_app)
# pcd <name> — cd to named project
PCD_MARKER   = "# HybX: pcd — project directory shortcut"
PCD_FUNCTION = """\
# HybX: pcd — project directory shortcut
# Usage: pcd          (active project)
#        pcd <name>   (named project)
pcd() { cd ~/Arduino/UNO-Q/${1:-$(cat ~/.hybx/last_app)}; }
"""


def install_pcd():
    """Add pcd() shell function to ~/.bashrc if not already present."""
    # Check if already installed
    if os.path.exists(BASHRC):
        with open(BASHRC, "r") as f:
            content = f.read()
        if PCD_MARKER in content:
            print("pcd(): already in ~/.bashrc — skipping.")
            return

    # Append to ~/.bashrc
    with open(BASHRC, "a") as f:
        f.write("\n" + PCD_FUNCTION)

    print("Added pcd() to ~/.bashrc")
    print("  pcd          — cd to active project")
    print("  pcd <name>   — cd to named project")
    print("  Run: source ~/.bashrc  (or open a new shell)")


def main():
    install_sigint_handler()
    print("=== setup ===")
    print()

    # Install ino.nanorc
    if not os.path.exists(INO_NANORC_SRC):
        print(f"ERROR: {INO_NANORC_SRC} not found — run update first.")
        sys.exit(1)

    os.makedirs(INO_NANORC_DST_DIR, exist_ok=True)
    print(f"Installing: {INO_NANORC_SRC} -> {INO_NANORC_DST}")
    shutil.copy2(INO_NANORC_SRC, INO_NANORC_DST)
    print("Done: ino.nanorc installed.")
    print()

    # Install pcd()
    install_pcd()
    print()

    print("Optional: to use the recommended nanorc configuration:")
    print(f"  cp {REPO_ROOT}/config/nanorc ~/.nanorc")


if __name__ == "__main__":
    main()
