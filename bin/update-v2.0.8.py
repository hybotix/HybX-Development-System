#!/usr/bin/env python3
"""
update-v2.0.8.py
Hybrid RobotiX — HybX Development System Updater v2.0

Updates an existing HybX Development System installation.
Pulls the latest repos and refreshes versioned symlinks in ~/bin.

If a repo has local changes (dirty working tree), they are stashed
before the pull and restored afterward. This prevents the pull from
aborting due to uncommitted local modifications.

This script lives in ~/bin and is installed by the HybX installer.

Usage:
  update
  update --log   (also write all output to ~/update.log)
"""

import hashlib
import os
import shutil
import signal
import sys
import platform
import subprocess
import json
import re

sys.path.insert(0, os.path.expanduser("~/lib"))


# ── Constants ──────────────────────────────────────────────────────────────────

# FINALIZE is intentionally excluded — it must NEVER be on PATH.
# It lives in scripts/ and must always be invoked by its full path.
COMMANDS = [
    "board", "build", "clean", "flash", "libs",
    "list", "mon", "migrate", "project", "restart",
    "setup", "start", "stop", "hybx-test", "update"
]

# Shared library modules installed to ~/lib/ as bare names.
# Each entry is the bare module name — versioned files are named
# <module>-vX.Y.Z.py in lib/ and installed as <module>.py to ~/lib/.
LIBRARIES = [
    "hybx_config",
    "libs_helpers",
    "compiler",
    "flasher",
    "runner",
]

CONFIG_FILE = os.path.expanduser("~/.hybx/config.json")
CONFIG_DIR  = os.path.dirname(CONFIG_FILE)

# ── Helpers ────────────────────────────────────────────────────────────────────


def run(cmd, cwd=None):
    result = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True)
    if result.returncode != 0:
        print("ERROR: Command failed: " + " ".join(cmd))
        if result.stderr:
            print(result.stderr.strip())
        sys.exit(1)


def run_quiet(cmd, cwd=None) -> tuple[int, str]:
    result = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True)
    return result.returncode, result.stdout.strip()


def load_config():
    if not os.path.exists(CONFIG_FILE):
        print("ERROR: No HybX config found. Run install first.")
        sys.exit(1)
    with open(CONFIG_FILE) as f:
        return json.load(f)


def save_config(config: dict):
    os.makedirs(CONFIG_DIR, exist_ok=True)
    with open(CONFIG_FILE, "w") as f:
        json.dump(config, f, indent=2)


def detect_platform():
    system  = platform.system()
    machine = platform.machine()
    if system == "Darwin":
        return "macos-arm64" if machine == "arm64" else "macos-x86_64"
    elif system == "Linux":
        return "linux-arm64" if machine == "aarch64" else "linux-x86_64"
    else:
        print("ERROR: Unsupported platform: " + system + " " + machine)
        sys.exit(1)


def _file_changed(src: str, dst: str) -> bool:
    """Return True if dst does not exist or content differs from src."""
    if not os.path.exists(dst):
        return True
    h1 = hashlib.md5(open(src, "rb").read()).hexdigest()
    h2 = hashlib.md5(open(dst, "rb").read()).hexdigest()
    return h1 != h2


def refresh_symlinks(bin_dir: str, dev_dest: str, config: dict):
    bin_src = os.path.join(dev_dest, "bin")
    lib_src = os.path.join(dev_dest, "lib")

    def _ver(fname):
        m = re.search(r"v(\d+)\.(\d+)\.(\d+)", fname)
        return tuple(int(x) for x in m.groups()) if m else (0, 0, 0)

    # ── Rogue version purge — remove any versioned file higher than current release
    # that is not present in the repo (e.g. start-v1.5.0.py from a previous session)
    repo_bin_files = set(os.listdir(bin_src)) if os.path.isdir(bin_src) else set()
    for fname in list(os.listdir(bin_dir)):
        if not (fname.endswith(".py") and re.search(r"-v\d+\.\d+\.\d+\.py$", fname)):
            continue
        if fname not in repo_bin_files:
            # Versioned file on board that doesn't exist in repo — remove it
            rogue_path = os.path.join(bin_dir, fname)
            os.remove(rogue_path)

    # ── FINALIZE safety purge — runs BEFORE copy and link ─────────────────────
    # FINALIZE must NEVER exist in ~/bin. Purge the symlink and any versioned
    # files unconditionally. This self-heals any older install that put it there.
    finalize_link = os.path.join(bin_dir, "FINALIZE")
    if os.path.islink(finalize_link) or os.path.isfile(finalize_link):
        os.remove(finalize_link)
    for fname in list(os.listdir(bin_dir)):
        if fname.startswith("FINALIZE-v") and fname.endswith(".py"):
            os.remove(os.path.join(bin_dir, fname))

    # Copy all versioned files and shared modules from repo bin/ to ~/bin/.
    # FINALIZE is never in bin/ so it will never be copied here.
    # Always set 755 after copy — never inherit repo permissions.
    for fname in os.listdir(bin_src):
        repo_path = os.path.join(bin_src, fname)
        bin_path  = os.path.join(bin_dir, fname)
        if os.path.isfile(repo_path):
            changed = os.path.exists(bin_path) and _file_changed(repo_path, bin_path)
            if not os.path.exists(bin_path) or changed:
                shutil.copy2(repo_path, bin_path)
                if fname.endswith(".py"):
                    os.chmod(bin_path, 0o755)
                if changed:
                    print("  Deployed: " + fname)
            elif fname.endswith(".py"):
                os.chmod(bin_path, 0o755)

    # Deploy versioned shared modules from repo lib/ to ~/lib/.
    # Each module has versioned files (hybx_config-v1.2.1.py).
    # The latest version is installed as the bare name (hybx_config.py).
    # Older versioned files are purged from ~/lib/ — repo is the archive.
    lib_dir = os.path.join(os.path.expanduser("~"), "lib")
    os.makedirs(lib_dir, exist_ok=True)

    if os.path.isdir(lib_src):
        # Rogue lib version purge — remove versioned files not in repo
        repo_lib_files = set(os.listdir(lib_src))
        for fname in list(os.listdir(lib_dir)):
            if not (fname.endswith(".py") and re.search(r"-v\d+\.\d+\.\d+\.py$", fname)):
                continue
            if fname not in repo_lib_files:
                rogue_path = os.path.join(lib_dir, fname)
                os.remove(rogue_path)

        # Copy all versioned lib files from repo to ~/lib/
        for fname in os.listdir(lib_src):
            repo_path = os.path.join(lib_src, fname)
            lib_path  = os.path.join(lib_dir, fname)
            if os.path.isfile(repo_path) and fname.endswith(".py"):
                lib_exists = os.path.exists(lib_path)
                changed = lib_exists and _file_changed(repo_path, lib_path)
                if not lib_exists or changed:
                    shutil.copy2(repo_path, lib_path)
                    os.chmod(lib_path, 0o755)
                    if changed:
                        print("  Deployed: " + fname)
                else:
                    os.chmod(lib_path, 0o755)

        # Install latest version of each library as bare name
        for module in LIBRARIES:
            try:
                files = [f for f in os.listdir(lib_dir)
                         if f.startswith(module + "-v") and f.endswith(".py")]
                files.sort(key=_ver)
                if not files:
                    print("  WARNING: No versioned file found for " + module)
                    continue
                latest      = files[-1]
                latest_path = os.path.join(lib_dir, latest)
                bare_path   = os.path.join(lib_dir, module + ".py")

                # Symlink bare name to latest versioned file
                current_target = os.readlink(bare_path) if os.path.islink(bare_path) else None
                if current_target != latest_path:
                    if os.path.exists(bare_path) or os.path.islink(bare_path):
                        os.remove(bare_path)
                    os.symlink(latest_path, bare_path)
                    print("  Updated: " + module + ".py -> " + latest)

                # Remove older versioned files
                for old in files[:-1]:
                    old_path = os.path.join(lib_dir, old)
                    os.remove(old_path)
            except Exception as e:
                print("  WARNING: Could not install " + module + ": " + str(e))
    else:
        print("  WARNING: lib/ not found at " + lib_src)

    # Store lib_path in config so all commands can find lib/ at runtime
    github_user = config.get("github_user")
    if github_user:
        repo_dest = os.path.expanduser("~/Repos/GitHub/" + github_user)
        dev_dest  = os.path.join(repo_dest, "HybX-Development-System")
        lib_path = os.path.join(dev_dest, "lib")
        config["lib_path"] = lib_path
        save_config(config)
        print("  Config updated: lib_path")

    # Remove old shared module copies from ~/bin/ — they now live in ~/lib/.
    for old_module in ["hybx_config.py", "libs_helpers.py", "ml_helpers.py"]:
        old_path = os.path.join(bin_dir, old_module)
        if os.path.isfile(old_path):
            os.remove(old_path)

    # Relink symlinks to latest versioned file within ~/bin/
    # and remove all older versioned files — only the linked version is kept.
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
            # Only report if the link target is changing
            current = os.readlink(dst) if os.path.islink(dst) else None
            if current != latest_path:
                if os.path.islink(dst):
                    os.remove(dst)
                os.symlink(latest_path, dst)
                print("  Updated: " + cmd + " -> " + latest)
            else:
                if not os.path.islink(dst):
                    os.symlink(latest_path, dst)
            os.chmod(latest_path, 0o755)

            # Remove all older versioned files — repo is the archive, not ~/bin/
            for old in files[:-1]:
                old_path = os.path.join(bin_dir, old)
                os.remove(old_path)
        except Exception as e:
            print("  WARNING: Could not link " + cmd + ": " + str(e))

# ── Main ───────────────────────────────────────────────────────────────────────


def main():
    plat   = detect_platform()
    config = load_config()

    github_user = config.get("github_user")
    if not github_user:
        print("ERROR: github_user not found in ~/.hybx/config.json")
        print("Run install first.")
        sys.exit(1)

    repo_dest = os.path.expanduser("~/Repos/GitHub/" + github_user)
    dev_dest  = os.path.join(repo_dest, "HybX-Development-System")
    bin_dir   = os.path.expanduser("~/bin")

    log_mode = "--log" in sys.argv
    log_path = os.path.expanduser("~/update.log")
    tee = HybXTee(log_path) if log_mode else None

    def _sigint_handler(sig, frame):
        print("\nInterrupted.")
        if tee:
            tee.close()
        sys.exit(0)

    signal.signal(signal.SIGINT, _sigint_handler)

    # Pull all repos via shared helper
    from hybx_config import pull_all_repos, HybXTee
    pull_all_repos(config)

    # Refresh symlinks
    refresh_symlinks(bin_dir, dev_dest, config)

    if tee:
        tee.close()


if __name__ == "__main__":
    main()
