#!/usr/bin/env python3
"""
install-v0.0.3.py
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

The installer shows a complete pre-flight summary of ALL changes it
will make and requires explicit confirmation before doing anything.

Usage:
  python3 install-v0.0.3.py
"""

import os
import sys
import platform
import subprocess
import shutil
import json
import re

# Import shared prompting utility from lib/
# The installer clones the repo before any confirmation prompt is shown,
# so lib/hybx_config.py is available when confirm_prompt() is first called.
sys.path.insert(0, os.path.join(os.path.dirname(os.path.realpath(__file__)), "..", "lib"))
from hybx_config import confirm_prompt  # noqa: E402

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
    Returns (shell_name, rc_file_path).

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


def find_ssh_key() -> str | None:
    """Return path to the first usable SSH private key, or None."""
    ssh_dir = os.path.expanduser("~/.ssh")
    for name in ["id_rsa", "id_ed25519", "id_ecdsa"]:
        path = os.path.join(ssh_dir, name)
        if os.path.exists(path):
            return path
    return None


def keychain_line(shell_name: str, key_path: str) -> str:
    """Return the correct keychain rc line for the given shell."""
    if shell_name == "fish":
        return "keychain --eval --quiet " + key_path + " | source"
    else:
        return "eval $(keychain --eval --quiet " + key_path + ")"


def path_line(shell_name: str) -> str:
    """Return the correct PATH entry line for the given shell."""
    if shell_name == "fish":
        return "fish_add_path $HOME/bin"
    else:
        return 'export PATH="$HOME/bin:$PATH"'


# ── Pre-flight Summary ─────────────────────────────────────────────────────────


def build_preflight(
        plat: str,
        shell_name: str,
        rc_file: str,
        github_user: str,
        apps_repo_name: str) -> list[str]:
    """
    Build the complete list of changes the installer will make.
    Nothing is done yet — this is purely informational.
    Returns a list of human-readable change descriptions.
    """
    changes = []
    bin_dir     = os.path.expanduser("~/bin")
    repo_dest   = os.path.expanduser("~/Repos/GitHub/" + github_user)
    dev_dest    = os.path.join(repo_dest, "HybX-Development-System")
    ssh_dir     = os.path.expanduser("~/.ssh")
    existing_key = find_ssh_key()

    # ── Config ────────────────────────────────────────────────────────────────
    changes.append("CONFIG")
    changes.append("  Write github_user = '" + github_user + "' to " + CONFIG_FILE)

    # ── ~/bin ─────────────────────────────────────────────────────────────────
    changes.append("")
    changes.append("~/bin")
    if not os.path.isdir(bin_dir):
        changes.append("  Create directory: " + bin_dir)
    else:
        changes.append("  Directory already exists: " + bin_dir)

    # Check if PATH line already in rc file
    pl = path_line(shell_name)
    try:
        with open(rc_file, "r") as f:
            rc_content = f.read()
    except FileNotFoundError:
        rc_content = ""

    if pl not in rc_content:
        changes.append("  Add to " + rc_file + ":")
        changes.append("    # HybX Development System")
        changes.append("    " + pl)
    else:
        changes.append("  PATH already configured in " + rc_file + " — no change needed")

    # ── SSH ───────────────────────────────────────────────────────────────────
    changes.append("")
    changes.append("SSH")
    if not existing_key:
        changes.append("  Generate new 4096-bit RSA SSH key: " + ssh_dir + "/id_rsa")
        key_path = os.path.join(ssh_dir, "id_rsa")
    else:
        changes.append("  Use existing SSH key: " + existing_key)
        key_path = existing_key

    changes.append("  You will be asked to add the public key to your GitHub account")
    changes.append("  GitHub SSH connection will be tested")

    # ── Keychain (Linux only) ─────────────────────────────────────────────────
    if plat.startswith("linux"):
        changes.append("")
        changes.append("KEYCHAIN (Linux — persistent SSH agent)")
        kc_available = run_quiet(["which", "keychain"])[0] == 0
        if not kc_available:
            changes.append("  Install keychain via: sudo apt install -y keychain")
        else:
            changes.append("  keychain is already installed")

        kl = keychain_line(shell_name, key_path)
        if "keychain" not in rc_content:
            changes.append("  Add to " + rc_file + ":")
            changes.append("    # HybX SSH agent (keychain)")
            changes.append("    " + kl)
        else:
            changes.append("  keychain already configured in " + rc_file + " — no change needed")

    # ── Repos ─────────────────────────────────────────────────────────────────
    changes.append("")
    changes.append("REPOSITORIES")
    if os.path.isdir(dev_dest):
        changes.append("  Pull latest: " + dev_dest)
    else:
        changes.append("  Clone: git@github.com:" + github_user + "/HybX-Development-System.git")
        changes.append("    into: " + dev_dest)

    if plat == "linux-arm64" and apps_repo_name:
        apps_dest   = os.path.join(repo_dest, apps_repo_name)
        arduino_src = os.path.join(apps_dest, "Arduino")
        arduino_dst = os.path.expanduser("~/Arduino")
        if os.path.isdir(apps_dest):
            changes.append("  Pull latest: " + apps_dest)
        else:
            changes.append("  Clone: git@github.com:" + github_user + "/" + apps_repo_name + ".git")
            changes.append("    into: " + apps_dest)
        changes.append("  Copy Arduino apps: " + arduino_src + " -> " + arduino_dst)
        if os.path.isdir(arduino_dst):
            changes.append("  WARNING: " + arduino_dst + " already exists and will be REPLACED")

    # ── Commands ──────────────────────────────────────────────────────────────
    changes.append("")
    changes.append("HybX COMMANDS  (installed as symlinks in ~/bin)")
    for cmd in COMMANDS:
        changes.append("  ~/bin/" + cmd)

    return changes


def show_preflight(changes: list[str]):
    """Print the pre-flight summary."""
    print()
    print("=" * 60)
    print("  PRE-FLIGHT SUMMARY — CHANGES TO BE MADE")
    print("=" * 60)
    print()
    for line in changes:
        print(line)
    print()
    print("=" * 60)
    print()


def confirm_preflight() -> bool:
    """
    Ask the user to confirm they have reviewed the pre-flight summary
    and want to proceed. Delegates to confirm_prompt() in lib/hybx_config.py
    so all confirmation prompts across the system behave identically.
    """
    print("Please review the above carefully.")
    print()
    return confirm_prompt("Proceed with installation")


# ── Installation Steps ─────────────────────────────────────────────────────────


def setup_bin_dir(shell_name: str, rc_file: str) -> str:
    bin_dir = os.path.expanduser("~/bin")
    if not os.path.isdir(bin_dir):
        print("Creating ~/bin ...")
        os.makedirs(bin_dir)

    if shell_name == "fish":
        os.makedirs(os.path.dirname(rc_file), exist_ok=True)

    pl = path_line(shell_name)
    try:
        with open(rc_file, "r") as f:
            rc_content = f.read()
    except FileNotFoundError:
        rc_content = ""

    if pl not in rc_content:
        with open(rc_file, "a") as f:
            f.write("\n# HybX Development System\n")
            f.write(pl + "\n")
        print("Added ~/bin to PATH in " + rc_file)

    return bin_dir


def setup_ssh(plat: str, shell_name: str, rc_file: str):
    print()
    print("=== SSH Authentication Setup ===")
    print()

    ssh_dir  = os.path.expanduser("~/.ssh")
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

    if plat.startswith("linux"):
        code, _ = run_quiet(["which", "keychain"])
        if code != 0:
            print()
            print("Installing keychain for persistent SSH agent ...")
            run(["sudo", "apt", "install", "-y", "keychain"])

        kl = keychain_line(shell_name, key_path)
        try:
            with open(rc_file, "r") as f:
                rc_content = f.read()
        except FileNotFoundError:
            rc_content = ""

        if "keychain" not in rc_content:
            with open(rc_file, "a") as f:
                f.write("\n# HybX SSH agent (keychain)\n")
                f.write(kl + "\n")
            print("Added keychain to " + rc_file)
            print("SSH key will persist across sessions after next login.")

    print()


def clone_or_pull(ssh_url: str, dest: str):
    if os.path.isdir(dest):
        print(os.path.basename(dest) + " already exists — pulling latest ...")
        run(["git", "pull"], cwd=dest)
    else:
        print("Cloning " + os.path.basename(dest) + " ...")
        run(["git", "clone", ssh_url, dest])


def install_symlinks(bin_dir: str, dev_dest: str):
    bin_src = os.path.join(dev_dest, "bin")
    print("\nInstalling HybX commands to ~/bin ...")

    def _ver(fname):
        m = re.search(r"v(\d+)\.(\d+)\.(\d+)", fname)
        return tuple(int(x) for x in m.groups()) if m else (0, 0, 0)

    # Always set 755 after copy — never inherit repo permissions.
    for fname in os.listdir(bin_src):
        src = os.path.join(bin_src, fname)
        dst = os.path.join(bin_dir, fname)
        if os.path.isfile(src):
            shutil.copy2(src, dst)
            if fname.endswith(".py"):
                os.chmod(dst, 0o755)

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

    # Gather all inputs FIRST — before showing the summary or touching anything
    github_user = input("GitHub username: ").strip()
    if not github_user:
        print("ERROR: GitHub username is required.")
        sys.exit(1)

    apps_repo_name = ""
    if plat == "linux-arm64":
        apps_repo_name = input("Apps repo name (e.g. UNO-Q, or Enter to skip): ").strip()

    # Build and show the complete pre-flight summary
    changes = build_preflight(plat, shell_name, rc_file, github_user, apps_repo_name)
    show_preflight(changes)

    # Require explicit confirmation before doing anything
    if not confirm_preflight():
        print()
        print("Installation cancelled. Nothing was changed.")
        print()
        sys.exit(0)

    print()
    print("Starting installation ...")
    print()

    # ── Now do everything ──────────────────────────────────────────────────────

    save_config(github_user)
    bin_dir = setup_bin_dir(shell_name, rc_file)
    setup_ssh(plat, shell_name, rc_file)

    repo_dest = os.path.expanduser("~/Repos/GitHub/" + github_user)
    dev_ssh   = "git@github.com:" + github_user + "/HybX-Development-System.git"
    dev_dest  = os.path.join(repo_dest, "HybX-Development-System")

    os.makedirs(repo_dest, exist_ok=True)
    clone_or_pull(dev_ssh, dev_dest)

    if plat == "linux-arm64" and apps_repo_name:
        apps_ssh  = "git@github.com:" + github_user + "/" + apps_repo_name + ".git"
        apps_dest = os.path.join(repo_dest, apps_repo_name)
        clone_or_pull(apps_ssh, apps_dest)

        arduino_src = os.path.join(apps_dest, "Arduino")
        arduino_dst = os.path.expanduser("~/Arduino")
        if os.path.isdir(arduino_src):
            print("\nCopying Arduino apps to " + arduino_dst + " ...")
            if os.path.isdir(arduino_dst):
                shutil.rmtree(arduino_dst)
            shutil.copytree(arduino_src, arduino_dst)
            print("  Done.")

    install_symlinks(bin_dir, dev_dest)

    # ── Done ───────────────────────────────────────────────────────────────────

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
