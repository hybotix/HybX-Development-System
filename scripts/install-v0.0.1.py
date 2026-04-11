#!/usr/bin/env python3
"""
install-v0.0.1.py
Hybrid RobotiX — HybX Development System Installer

Multi-platform installer for the HybX Development System.
Detects the platform, prompts for GitHub username, clones
the required repos, and installs versioned symlinks in ~/bin.

Supported platforms:
  - macOS (Apple Silicon)
  - macOS (Intel)
  - Linux ARM64 (Raspberry Pi 5, UNO Q, etc.)
  - Linux x86_64 (Galileo, etc.)

Usage:
  python3 install-v0.0.1.py
"""

import os
import sys
import platform
import subprocess
import shutil

# ── Constants ──────────────────────────────────────────────────────────────────

COMMANDS = [
    "board", "build", "clean", "FINALIZE", "libs",
    "list", "logs", "migrate", "project", "restart",
    "setup", "start", "stop", "update"
]

# ── Platform Detection ─────────────────────────────────────────────────────────

def detect_platform():
    system = platform.system()
    machine = platform.machine()

    if system == "Darwin":
        if machine == "arm64":
            return "macos-arm64"
        elif machine == "x86_64":
            return "macos-x86_64"
        else:
            return f"macos-{machine}"
    elif system == "Linux":
        if machine == "aarch64":
            return "linux-arm64"
        elif machine == "x86_64":
            return "linux-x86_64"
        else:
            return f"linux-{machine}"
    else:
        print(f"ERROR: Unsupported platform: {system} {machine}")
        sys.exit(1)

# ── Helpers ────────────────────────────────────────────────────────────────────

def run(cmd, cwd=None):
    result = subprocess.run(cmd, cwd=cwd)
    if result.returncode != 0:
        print(f"ERROR: Command failed: {' '.join(cmd)}")
        sys.exit(1)

def setup_bin_dir(shell_rc):
    bin_dir = os.path.expanduser("~/bin")
    if not os.path.isdir(bin_dir):
        print("Creating ~/bin ...")
        os.makedirs(bin_dir)
        with open(shell_rc, "a") as f:
            f.write("\n# HybX Development System\n")
            f.write('export PATH="$HOME/bin:$PATH"\n')
        print(f"Added ~/bin to PATH in {shell_rc}")
    return bin_dir

def clone_or_pull(repo_url, dest):
    if os.path.isdir(dest):
        print(f"{os.path.basename(dest)} already exists — pulling latest ...")
        run(["git", "pull"], cwd=dest)
    else:
        print(f"Cloning {os.path.basename(dest)} ...")
        run(["git", "clone", repo_url, dest])

def install_symlinks(bin_dir, dev_dest):
    bin_src = os.path.join(dev_dest, "bin")
    print("\nInstalling HybX commands to ~/bin ...")
    for cmd in COMMANDS:
        # Find latest versioned file
        try:
            files = [f for f in os.listdir(bin_src)
                     if f.startswith(f"{cmd}-v") and f.endswith(".py")]
            files.sort()
            if not files:
                print(f"  WARNING: No versioned file found for {cmd}")
                continue
            latest = files[-1]
            src = os.path.join(bin_src, latest)
            dst = os.path.join(bin_dir, cmd)
            if os.path.islink(dst):
                os.remove(dst)
            os.symlink(src, dst)
            os.chmod(src, 0o755)
            print(f"  Linked: {cmd} -> {latest}")
        except Exception as e:
            print(f"  WARNING: Could not link {cmd}: {e}")

# ── Main ───────────────────────────────────────────────────────────────────────

def main():
    plat = detect_platform()

    print("")
    print("Hybrid RobotiX — HybX Development System Installer")
    print("====================================================")
    print(f"Platform: {plat}")
    print("")

    # Prompt for GitHub username
    github_user = input("GitHub username: ").strip()
    if not github_user:
        print("ERROR: GitHub username is required.")
        sys.exit(1)

    # Repo paths
    repo_base  = f"https://github.com/{github_user}"
    dev_repo   = f"{repo_base}/HybX-Development-System.git"
    repo_dest  = os.path.expanduser(f"~/Repos/GitHub/{github_user}")
    dev_dest   = os.path.join(repo_dest, "HybX-Development-System")

    # Shell RC file
    if plat.startswith("macos"):
        shell_rc = os.path.expanduser("~/.zshrc")
    else:
        shell_rc = os.path.expanduser("~/.bashrc")

    # ~/bin setup
    bin_dir = setup_bin_dir(shell_rc)

    # Clone Dev System repo
    os.makedirs(repo_dest, exist_ok=True)
    clone_or_pull(dev_repo, dev_dest)

    # Platform-specific setup
    if plat in ("macos-arm64", "macos-x86_64", "linux-x86_64"):
        # Desktop/laptop — symlink only
        install_symlinks(bin_dir, dev_dest)

    elif plat == "linux-arm64":
        # Embedded Linux — also clone apps repo
        apps_repo_name = input("Apps repo name (e.g. UNO-Q): ").strip()
        if apps_repo_name:
            apps_repo = f"{repo_base}/{apps_repo_name}.git"
            apps_dest = os.path.join(repo_dest, apps_repo_name)
            clone_or_pull(apps_repo, apps_dest)

        install_symlinks(bin_dir, dev_dest)

    print("")
    print("====================================================")
    print("HybX Development System installed successfully!")
    print("")
    print("Next steps:")
    if plat.startswith("macos"):
        print("  1. Run: source ~/.zshrc   (or open a new terminal)")
    else:
        print("  1. Run: source ~/.bashrc  (or open a new terminal)")
    print("  2. Run: board add <n>  to configure your first board")
    print("====================================================")
    print("")

if __name__ == "__main__":
    main()
