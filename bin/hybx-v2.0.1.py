#!/usr/bin/env python3

"""
hybx-v2.0.1.py
Hybrid RobotiX — HybX Development System

Main dispatcher with prefix matching.
Allows abbreviated command names (minimum 3 characters) as long as
the abbreviation is unambiguous.

Usage:
  hybx <command> [args...]
  hybx           (show available commands)

Examples:
  hybx cle vl53-diag    → clean vl53-diag
  hybx pro clone monitor-vl53l5cx robot-ranger → project clone ...
  hybx upd              → update
  hybx mon              → mon
"""

import os
import sys
import subprocess

sys.path.insert(0, os.path.expanduser("~/lib"))
from hybx_config import HYBX_MIN_PREFIX  # noqa: E402

COMMANDS = [
    "board",
    "build",
    "clean",
    "flash",
    "libs",
    "list",
    "mon",
    "project",
    "restart",
    "setup",
    "start",
    "stop",
    "update",
]

# Minimum prefix length imported from hybx_config (HYBX_MIN_PREFIX = 3)
# To change the minimum, update HYBX_MIN_PREFIX in hybx_config.
MIN_PREFIX = HYBX_MIN_PREFIX


def find_command(prefix: str) -> str | None:
    """
    Find the command that matches the given prefix.
    Returns the command name if exactly one match, None if no match,
    raises SystemExit if ambiguous.
    """
    if len(prefix) < MIN_PREFIX:
        print(f"ERROR: Command prefix must be at least {MIN_PREFIX} characters (got '{prefix}').")
        sys.exit(1)

    # Exact match first
    if prefix in COMMANDS:
        return prefix

    # Prefix match
    matches = [c for c in COMMANDS if c.startswith(prefix)]

    if len(matches) == 1:
        return matches[0]
    elif len(matches) == 0:
        return None
    else:
        print(f"ERROR: Ambiguous command '{prefix}' — matches:")
        for m in matches:
            print(f"  {m}")
        sys.exit(1)


def usage():
    print("=== HybX Development System ===")
    print()
    print("Usage: hybx <command> [args...]")
    print()
    print("Commands:")
    for cmd in sorted(COMMANDS):
        print(f"  {cmd}")
    print()
    print(f"Abbreviated commands are accepted (minimum {MIN_PREFIX} characters).")
    print("Example: hybx cle vl53-diag   →   clean vl53-diag")


def main():
    if len(sys.argv) < 2:
        usage()
        sys.exit(0)

    prefix  = sys.argv[1]
    cmd     = find_command(prefix)

    if cmd is None:
        print(f"ERROR: Unknown command '{prefix}'.")
        print()
        usage()
        sys.exit(1)

    # Find the command in ~/bin/
    bin_dir  = os.path.expanduser("~/bin")
    cmd_path = os.path.join(bin_dir, cmd)

    if not os.path.exists(cmd_path):
        print(f"ERROR: Command '{cmd}' not found in {bin_dir}.")
        print("Run 'update' to deploy the latest commands.")
        sys.exit(1)

    # Execute the command with remaining args
    os.execv(cmd_path, [cmd_path] + sys.argv[2:])


if __name__ == "__main__":
    main()
