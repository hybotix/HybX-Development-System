#!/usr/bin/env python3

"""
list-v0.0.2.py
Hybrid RobotiX — HybX Development System
"""

import os
import sys
sys.path.insert(0, os.path.dirname(os.path.realpath(__file__)))

import subprocess  # noqa: E402
from hybx_config import get_active_board  # noqa: E402


def main():
    board = get_active_board()
    print(f"Board: {board['name']} ({board['host']})")
    subprocess.run(["arduino-app-cli", "app", "list"])


if __name__ == "__main__":
    main()
