#!/usr/bin/env python3
"""
install-v0.0.2.py
Hybrid RobotiX — HybX Development System Installer

Multi-platform installer for the HybX Development System.
Detects the platform and the user's current shell, sets up SSH
authentication, clones repos via SSH, and installs versioned
symlinks in ~/bin.

No PATs. No passwords. SSH keys only.

Supported platforms:
  - macOS (Apple Silicon)
  - macOS (Intel)
  - Linux ARM64 (UNO Q, Raspberry Pi 5, etc.)
  - Linux x86_64

Supported shells:
  - bash   (~/.bashrc)
  - zsh    (~/.zshrc)
  - fish   (~/.config/fish/config.fish)
  - other  (~/.bashrc, with a warning)

Shell is detected from the $SHELL environment variable — not assumed
from the platform. Any shell can be used on any platform.

Usage:
  python3 install-v0.0.2.py
"""

import os
import sys
import platform
import subprocess
import shutil
import json
import re

# ── Constants ──────────────────────────────────────────────────────────────────

COMMANDS = [
    "board", "build", "clean", "libs",
    "list", "logs", "migrate", "project", "restart",
    "setup", "start", "stop", "update"
]

CONFIG_DIR  = os.path.expanduser("~/.hybx")
CONFIG_FILE = os.path.join(CONFIG_DIR, "config.json")

# ── Platform Detection ─────────────────────────────────────────────────────────


def detect_platform() -> str:
    system  = platform.system()
    machine = platform.machine()
    if system == "Darwin":
        return "macos-arm64" if machine == "arm64" else "macos-x86_64"
    elif system == "Linux":
        return "linux-arm64" if machine == "aarch64" else "linux-x86_64"
    else:
        print("ERROR: Unsupported platform: " + system + " " + machine)
        sys.exit(1)


# ── Shell Detection ────────────────────────────────────────────────────────────


def detect_shell() -> tuple[str, str]:
    """
    Detect the user's current shell from the $SHELL environment variable.
    Returns (shell_name, rc_file_path) — shell_name is e.g. 'bash', 'zsh', 'fish'.

    Shell is NEVER assumed from platform — any shell can run on any platform.
    Defaults to bash/~/.bashrc if $SHELL is unset or unrecognized, with a warning.
    """
    shell_path = os.environ.get("SHELL", "")
    shell_name = os.path.basename(shell_path) if shell_path else "bash"

    rc_map = {
        "bash": "~/.bashrc",
        "zsh":  "~/.zshrc",
        "fish": "~/.config/fish/config.fish",
    }

    if shell_name not in rc_map:
        print("WARNING: Unrecognized shell '" + shell_name + "' — defaulting to bash (~/.bashrc)")
        print("         You may need to manually add ~/bin to your PATH.")
        shell_name = "bash"

    rc_file = os.path.expanduser(rc_map[shell_name])
    return shell_name, rc_file


# ── Helpers ────────────────────────────────────────────────────────────────────


def run(cmd, cwd=None):
    result = subprocess.run(cmd, cwd=cwd)
    if result.returncode != 0:
        print("ERROR: Command failed: " + " ".join(cmd))
        sys.exit(1)


def run_quiet(cmd, cwd=None) -> tuple[int, str]:
    result = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True)
    return result.returncode, result.stdout.strip()


def setup_bin_dir(shell_name: str, rc_file: str) -> str:
    """
    Create ~/bin if needed and add it to PATH in the user's shell rc file.
    Uses the correct syntax for each supported shell.
    """
    bin_dir = os.path.expanduser("~/bin")
    if not os.path.isdir(bin_dir):
        print("Creating ~/bin ...")
        os.makedirs(bin_dir)

    # fish uses fish_add_path; bash and zsh use export PATH=
    if shell_name == "fish":
        path_line = "fish_add_path $HOME/bin"
        # fish config dir may not exist yet
        os.makedirs(os.path.dirname(rc_file), exist_ok=True)
    else:
        path_line = 'export PATH="$HOME/bin:$PATH"'

    try:
        with open(rc_file, "r") as f:
            rc_content = f.read()
    except FileNotFoundError:
        rc_content = ""

    if path_line not in rc_content:
        with open(rc_file, "a") as f:
            f.write("\n# HybX Development System\n")
            f.write(path_line + "\n")
        print("Added ~/bin to PATH in " + rc_file)

    return bin_dir


# ── SSH Setup ──────────────────────────────────────────────────────────────────


def find_ssh_key() -> str | None:
    """Return path to the first usable SSH private key, or None."""
    ssh_dir = os.path.expanduser("~/.ssh")
    for name in ["id_rsa", "id_ed25519", "id_ecdsa"]:
        path = os.path.join(ssh_dir, name)
        if os.path.exists(path):
            return path
    return None


def setup_ssh(plat: str, shell_name: str, rc_file: str):
    """
    Ensure an SSH key exists, set up keychain on Linux for persistent
    agent across sessions, and print the public key for GitHub setup.
    No PATs. No passwords stored anywhere.

    Keychain rc line syntax varies by shell:
      bash/zsh: eval $(keychain --eval --quiet <key>)
      fish:     keychain --eval --quiet <key> | source
    """
    print()
    print("=== SSH Authentication Setup ===")
    print()

    ssh_dir = os.path.expanduser("~/.ssh")
    os.makedirs(ssh_dir, mode=0o700, exist_ok=True)

    key_path = find_ssh_key()

    if not key_path:
        print("No SSH key found. Generating a 4096-bit RSA key ...")
        key_path = os.path.join(ssh_dir, "id_rsa")
        run(["ssh-keygen", "-t", "rsa", "-b", "4096",
             "-C", "hybx@" + platform.node(),
             "-f", key_path])
        print("SSH key generated: " + key_path)
    else:
        print("Using existing SSH key: " + key_path)

    pub_key_path = key_path + ".pub"
    with open(pub_key_path, "r") as f:
        pub_key = f.read().strip()

    print()
    print("Add this public key to your GitHub account:")
    print("  https://github.com/settings/ssh/new")
    print()
    print(pub_key)
    print()
    input("Press Enter when you have added the key to GitHub ...")

    # Test GitHub SSH connection
    print()
    print("Testing GitHub SSH connection ...")
    result = subprocess.run(
        ["ssh", "-T", "-o", "StrictHostKeyChecking=no", "git@github.com"],
        capture_output=True, text=True
    )
    if "successfully authenticated" in result.stderr.lower():
        print("GitHub SSH authentication: OK")
    else:
        print("WARNING: Could not verify GitHub SSH connection.")
        print("         Continuing anyway — verify manually with:")
        print("         ssh -T git@github.com")

    # Set up keychain on Linux for persistent SSH agent across sessions
    if plat.startswith("linux"):
        code, _ = run_quiet(["which", "keychain"])
        if code != 0:
            print()
            print("Installing keychain for persistent SSH agent ...")
            run(["sudo", "apt", "install", "-y", "keychain"])

        # Keychain line syntax depends on the shell
        if shell_name == "fish":
            keychain_line = (
                "keychain --eval --quiet " + key_path + " | source"
            )
        else:
            # bash and zsh
            keychain_line = (
                "eval $(keychain --eval --quiet " + key_path + ")"
            )

        try:
            with open(rc_file, "r") as f:
                rc_content = f.read()
        except FileNotFoundError:
            rc_content = ""

        if "keychain" not in rc_content:
            with open(rc_file, "a") as f:
                f.write("\n# HybX SSH agent (keychain)\n")
                f.write(keychain_line + "\n")
            print("Added keychain to " + rc_file)
            print("SSH key will persist across sessions after next login.")

    print()


# ── Git / Repo Setup ───────────────────────────────────────────────────────────


def clone_or_pull(ssh_url: str, dest: str):
    if os.path.isdir(dest):
        print(os.path.basename(dest) + " already exists — pulling latest ...")
        run(["git", "pull"], cwd=dest)
    else:
        print("Cloning " + os.path.basename(dest) + " ...")
        run(["git", "clone", ssh_url, dest])


# ── Symlink Installation ───────────────────────────────────────────────────────


def install_symlinks(bin_dir: str, dev_dest: str):
    bin_src = os.path.join(dev_dest, "bin")
    print("\nInstalling HybX commands to ~/bin ...")

    def _ver(fname):
        m = re.search(r"v(\d+)\.(\d+)\.(\d+)", fname)
        return tuple(int(x) for x in m.groups()) if m else (0, 0, 0)

    # Copy all files from repo bin/ to ~/bin/
    for fname in os.listdir(bin_src):
        src = os.path.join(bin_src, fname)
        dst = os.path.join(bin_dir, fname)
        if os.path.isfile(src):
            shutil.copy2(src, dst)

    # Relink symlinks to latest versioned file within ~/bin/
    for cmd in COMMANDS:
        try:
            files = [f for f in os.listdir(bin_dir)
                     if f.startswith(cmd + "-v") and f.endswith(".py")]
            files.sort(key=_ver)
            if not files:
                print("  WARNING: No versioned file found for " + cmd)
                continue
            latest      = files[-1]
            latest_path = os.path.join(bin_dir, latest)
            dst         = os.path.join(bin_dir, cmd)
            if os.path.islink(dst):
                os.remove(dst)
            os.symlink(latest_path, dst)
            os.chmod(latest_path, 0o755)
            print("  Linked: " + cmd + " -> " + latest)
        except Exception as e:
            print("  WARNING: Could not link " + cmd + ": " + str(e))


# ── Config ─────────────────────────────────────────────────────────────────────


def save_config(github_user: str):
    os.makedirs(CONFIG_DIR, exist_ok=True)
    if os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE) as f:
            config = json.load(f)
    else:
        config = {"boards": {}, "active_board": None}
    config["github_user"] = github_user
    with open(CONFIG_FILE, "w") as f:
        json.dump(config, f, indent=2)
    print("Saved github_user to " + CONFIG_FILE)


# ── Main ───────────────────────────────────────────────────────────────────────


def main():
    plat                = detect_platform()
    shell_name, rc_file = detect_shell()

    print()
    print("Hybrid RobotiX — HybX Development System Installer")
    print("====================================================")
    print("Platform: " + plat)
    print("Shell:    " + shell_name + " (" + rc_file + ")")
    print()

    github_user = input("GitHub username: ").strip()
    if not github_user:
        print("ERROR: GitHub username is required.")
        sys.exit(1)

    save_config(github_user)

    # ~/bin setup — uses correct PATH syntax for detected shell
    bin_dir = setup_bin_dir(shell_name, rc_file)

    # SSH setup — no PATs, ever
    setup_ssh(plat, shell_name, rc_file)

    # Repo paths — SSH URLs only
    repo_dest = os.path.expanduser("~/Repos/GitHub/" + github_user)
    dev_ssh   = "git@github.com:" + github_user + "/HybX-Development-System.git"
    dev_dest  = os.path.join(repo_dest, "HybX-Development-System")

    os.makedirs(repo_dest, exist_ok=True)
    clone_or_pull(dev_ssh, dev_dest)

    # On embedded Linux, also clone the apps repo
    if plat == "linux-arm64":
        apps_repo_name = input("Apps repo name (e.g. UNO-Q): ").strip()
        if apps_repo_name:
            apps_ssh  = "git@github.com:" + github_user + "/" + apps_repo_name + ".git"
            apps_dest = os.path.join(repo_dest, apps_repo_name)
            clone_or_pull(apps_ssh, apps_dest)

            # Copy Arduino apps to ~/Arduino if present
            arduino_src = os.path.join(apps_dest, "Arduino")
            arduino_dst = os.path.expanduser("~/Arduino")
            if os.path.isdir(arduino_src):
                print("\nCopying Arduino apps to " + arduino_dst + " ...")
                if os.path.isdir(arduino_dst):
                    shutil.rmtree(arduino_dst)
                shutil.copytree(arduino_src, arduino_dst)
                print("  Done.")

    install_symlinks(bin_dir, dev_dest)

    print()
    print("====================================================")
    print("HybX Development System installed successfully!")
    print()
    print("Next steps:")
    if shell_name == "fish":
        print("  1. Run: source " + rc_file + "   (or open a new terminal)")
    elif shell_name == "zsh":
        print("  1. Run: source ~/.zshrc   (or open a new terminal)")
    else:
        print("  1. Run: source ~/.bashrc   (or open a new terminal)")
    if plat.startswith("linux"):
        print("     Note: keychain activates fully after next login.")
    print("  2. Run: board add <n>  to configure your first board")
    print("====================================================")
    print()


if __name__ == "__main__":
    main()
