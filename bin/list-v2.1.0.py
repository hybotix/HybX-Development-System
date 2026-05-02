#!/usr/bin/env python3

"""
list-v1.2.0.py
Hybrid RobotiX — HybX Development System
"""

import os
import sys
sys.path.insert(0, os.path.dirname(os.path.realpath(__file__)))
sys.path.insert(0, os.path.expanduser("~/lib"))

import subprocess  # noqa: E402
from hybx_config import get_active_board, install_sigint_handler  # noqa: E402


def main():
    install_sigint_handler()
    board = get_active_board()
    print(f"Board: {board['name']} ({board['host']})")
    subprocess.run(["arduino-app-cli", "app", "list"])


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nInterrupted.")
        sys.exit(1)
