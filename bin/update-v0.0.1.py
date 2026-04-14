#!/usr/bin/env python3
"""
update-v0.0.1.py
Hybrid RobotiX — HybX Development System Updater

Updates an existing HybX Development System installation.
Pulls the latest repos and refreshes versioned symlinks in ~/bin.

This script lives in $HOME and is NEVER stored in the repo root.
Copy it manually to $HOME on any new board for the first run:
  cp ~/Repos/GitHub/<username>/HybX-Development-System/scripts/update-v0.0.1.py ~/update-v0.0.1.py

After the first run, the start command installs ~/bin/update automatically.

Usage:
  python3 ~/update-v0.0.1.py   # first time
  update                        # after first install
"""

import os
import shutil
import sys
import platform
import subprocess
import json

# ── Constants ──────────────────────────────────────────────────────────────────

COMMANDS = [
    "board", "build", "clean", "FINALIZE", "libs",
    "list", "logs", "migrate", "project", "restart",
    "setup", "start", "stop", "update"
]

CONFIG_FILE = os.path.expanduser("~/.hybx/config.json")

# ── Helpers ────────────────────────────────────────────────────────────────────


def run(cmd, cwd=None):
    result = subprocess.run(cmd, cwd=cwd)
    if result.returncode != 0:
        print(f"ERROR: Command failed: {' '.join(cmd)}")
        sys.exit(1)


def load_config():
    if not os.path.exists(CONFIG_FILE):
        print("ERROR: No HybX config found. Run install first.")
        sys.exit(1)
    with open(CONFIG_FILE) as f:
        return json.load(f)


def detect_platform():
    system = platform.system()
    machine = platform.machine()
    if system == "Darwin":
        return "macos-arm64" if machine == "arm64" else "macos-x86_64"
    elif system == "Linux":
        return "linux-arm64" if machine == "aarch64" else "linux-x86_64"
    else:
        print(f"ERROR: Unsupported platform: {system} {machine}")
        sys.exit(1)


def pull_repo(dest):
    if not os.path.isdir(dest):
        print("WARNING: " + dest + " not found — skipping pull")
        return
    print("Pulling " + os.path.basename(dest) + " ...")
    run(["git", "pull"], cwd=dest)


def refresh_symlinks(bin_dir, dev_dest):
    bin_src = os.path.join(dev_dest, "bin")
    print("\nRefreshing HybX commands in ~/bin ...")

    import re as _re

    def _ver(fname):
        m = _re.search(r"v(\d+)\.(\d+)\.(\d+)", fname)
        return tuple(int(x) for x in m.groups()) if m else (0, 0, 0)

    # Copy all versioned files and shared modules from repo bin/ to ~/bin/
    for fname in os.listdir(bin_src):
        repo_path = os.path.join(bin_src, fname)
        bin_path  = os.path.join(bin_dir, fname)
        if os.path.isfile(repo_path):
            shutil.copy2(repo_path, bin_path)

    # Relink symlinks to latest versioned file within ~/bin/
    for cmd in COMMANDS:
        try:
            files = [f for f in os.listdir(bin_dir)
                     if f.startswith(cmd + "-v") and f.endswith(".py")]
            files.sort(key=_ver)
            if not files:
                print("  WARNING: No versioned file found for " + cmd)
                continue
            latest     = files[-1]
            latest_path = os.path.join(bin_dir, latest)
            dst        = os.path.join(bin_dir, cmd)
            if os.path.islink(dst):
                os.remove(dst)
            os.symlink(latest_path, dst)
            os.chmod(latest_path, 0o755)
            print("  Linked: " + cmd + " -> " + latest)
        except Exception as e:
            print("  WARNING: Could not link " + cmd + ": " + str(e))

# ── Main ───────────────────────────────────────────────────────────────────────


def main():
    plat = detect_platform()
    config = load_config()

    github_user = config.get("github_user")
    if not github_user:
        print("ERROR: github_user not found in ~/.hybx/config.json")
        print("Run install first.")
        sys.exit(1)

    repo_dest  = os.path.expanduser(f"~/Repos/GitHub/{github_user}")
    dev_dest   = os.path.join(repo_dest, "HybX-Development-System")
    bin_dir    = os.path.expanduser("~/bin")

    print("")
    print("Hybrid RobotiX — HybX Development System Updater")
    print("=================================================")
    print(f"Platform:  {plat}")
    print(f"User:      {github_user}")
    print("")

    # Pull Dev System repo
    pull_repo(dev_dest)

    # On embedded Linux, also pull the apps repo
    if plat == "linux-arm64":
        active = config.get("active_board")
        if active:
            boards = config.get("boards", {})
            board = boards.get(active, {})
            repo_url = board.get("repo", "")
            if repo_url:
                repo_name = repo_url.rstrip(".git").split("/")[-1]
                apps_dest = os.path.join(repo_dest, repo_name)
                pull_repo(apps_dest)

    # Refresh symlinks
    refresh_symlinks(bin_dir, dev_dest)

    print("")
    print("=================================================")
    print("HybX Development System updated successfully!")
    print("=================================================")
    print("")


if __name__ == "__main__":
    main()
