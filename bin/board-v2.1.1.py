#!/usr/bin/env python3
"""
board-v2.1.0.py
Hybrid RobotiX — HybX Development System

Manages board configurations for the HybX Development System.
All other commands read the active board from ~/.hybx/config.json.

Board names are always stored and matched in lowercase, regardless
of how they are entered.

Push and pull operations are handled by 'project push' and 'project pull'.

Usage:
  board list              - List all configured boards
  board show              - Show active board details
  board add <n>           - Add a new board configuration
  board use <n>           - Set the active board
  board remove <n>        - Remove a board configuration
  board pat <token>       - Store GitHub PAT for push operations
  board branch <name>     - Switch all repos to branch and run update

Exit codes:
  0  success
  1  user error
"""

import os
import sys
sys.path.insert(0, os.path.dirname(os.path.realpath(__file__)))
sys.path.insert(0, os.path.expanduser("~/lib"))

from hybx_config import confirm_prompt, get_active_board, validate_name, resolve_subcommand, install_sigint_handler  # noqa: E402

import shutil       # noqa: E402
import subprocess   # noqa: E402
import json         # noqa: E402

CONFIG_DIR  = os.path.expanduser("~/.hybx")
CONFIG_FILE = os.path.join(CONFIG_DIR, "config.json")

# ── Config helpers ─────────────────────────────────────────────────────────────


def load_config() -> dict:
    if not os.path.exists(CONFIG_FILE):
        return {"boards": {}, "active_board": None}
    with open(CONFIG_FILE, "r") as f:
        return json.load(f)


def save_config(config: dict):
    os.makedirs(CONFIG_DIR, exist_ok=True)
    with open(CONFIG_FILE, "w") as f:
        json.dump(config, f, indent=2)
    print("Config saved: " + CONFIG_FILE)


# ── Output helpers ─────────────────────────────────────────────────────────────


def out_json(data: dict):
    print(json.dumps(data, indent=2))


def out_error(msg: str, json_mode: bool = False, code: int = 1):
    if json_mode:
        out_json({"ok": False, "error": msg})
    else:
        print("ERROR: " + msg)
    sys.exit(code)


# ── Git helpers (used by board pull) ──────────────────────────────────────────


def run_quiet(cmd: list, cwd: str = None) -> tuple[int, str, str]:
    result = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True)
    return result.returncode, result.stdout.strip(), result.stderr.strip()


def is_dirty(repo_path: str) -> bool:
    """Return True if the repo has uncommitted local changes."""
    code, out, _ = run_quiet(["git", "status", "--porcelain"], cwd=repo_path)
    return code == 0 and bool(out)


def pull_repo(repo_path: str, json_mode: bool) -> bool:
    """
    Pull latest changes for the repo at repo_path.
    Stashes local changes before pulling and restores them after.
    Returns True on success, False on failure.
    """
    stashed = False

    if is_dirty(repo_path):
        if not json_mode:
            print("  Local changes detected — stashing ...")
        code, out, err = run_quiet(
            ["git", "stash", "push", "-m", "hybx-board-sync-autostash"],
            cwd=repo_path
        )
        if code != 0:
            if not json_mode:
                print("  WARNING: git stash failed — attempting pull anyway")
        else:
            stashed = True
            if not json_mode:
                print("  Stashed: " + out)

    code, out, err = run_quiet(["git", "pull"], cwd=repo_path)
    if code != 0:
        if not json_mode:
            print("  ERROR: git pull failed: " + err)
        if stashed:
            run_quiet(["git", "stash", "pop"], cwd=repo_path)
        return False

    if not json_mode:
        print(out if out else "  Already up to date.")

    if stashed:
        if not json_mode:
            print("  Restoring stashed changes ...")
        code, out, err = run_quiet(["git", "stash", "pop"], cwd=repo_path)
        if code != 0:
            if not json_mode:
                print("  WARNING: git stash pop failed.")
                print("  Your local changes are still in the stash.")
                print("  Run: git stash pop   in " + repo_path)
        else:
            if not json_mode:
                print("  Restored: " + out)

    return True


def sync_apps(
        repo_path: str,
        board_name: str,
        apps_path: str,
        dry_run: bool,
        json_mode: bool,
        force: bool = False,
        app_filter: str = None) -> tuple[list, list, list]:
    """
    Copy app directories from the repo into the board's apps directory.

    Default: only NEW apps are added — existing directories are never modified.
    With force=True: existing apps are overwritten (local changes will be lost).
    With app_filter: only the named app is synced (force applies only to it).

    Returns (added, updated, skipped) lists of app names.
    """
    arduino_src = os.path.join(repo_path, "Arduino", board_name)

    # The repo directory may use a different case than the board name in config.
    # Search for the best match: exact, then case-insensitive.
    if not os.path.isdir(arduino_src):
        arduino_parent = os.path.join(repo_path, "Arduino")
        if os.path.isdir(arduino_parent):
            for entry in os.scandir(arduino_parent):
                if entry.name.lower() == board_name.lower():
                    arduino_src = entry.path
                    break

    if not os.path.isdir(arduino_src):
        return [], [], []

    os.makedirs(apps_path, exist_ok=True)

    added   = []
    updated = []
    skipped = []

    for entry in sorted(os.scandir(arduino_src), key=lambda e: e.name):
        if not entry.is_dir():
            continue
        # If a specific app was requested, skip all others
        if app_filter and entry.name.lower() != app_filter.lower():
            continue
        dst = os.path.join(apps_path, entry.name)
        if os.path.isdir(dst):
            if force:
                if not dry_run:
                    shutil.rmtree(dst)
                    shutil.copytree(entry.path, dst)
                updated.append(entry.name)
            else:
                skipped.append(entry.name)
        else:
            if not dry_run:
                shutil.copytree(entry.path, dst)
            added.append(entry.name)

    return added, updated, skipped


# ── Commands ───────────────────────────────────────────────────────────────────


def cmd_list():
    config = load_config()
    boards = config.get("boards", {})
    active = config.get("active_board")

    if not boards:
        print("No boards configured. Use: board add <n>")
        return

    print("Configured boards:")
    for name, info in boards.items():
        marker = " *" if name == active else "  "
        print(marker + " " + name)
        print("      host:      " + info.get("host", "(not set)"))
        print("      apps_path: " + info.get("apps_path", "(not set)"))
        print("      repo:      " + info.get("repo", "(not set)"))

    if active:
        print("\nActive board: " + active)
    else:
        print("\nNo active board set. Use: board use <n>")


def cmd_use(name: str):
    config = load_config()

    if name not in config.get("boards", {}):
        print("ERROR: Board '" + name + "' not found. Use: board list")
        sys.exit(1)

    config["active_board"] = name
    save_config(config)
    print("Active board: " + name)


def cmd_add(name: str):
    config = load_config()
    boards = config.setdefault("boards", {})

    if name in boards:
        print("Board '" + name + "' already exists. Use: board remove " + name + " first.")
        sys.exit(1)

    print("Adding board: " + name)
    print()

    # GitHub username — stored globally in config
    github_user = config.get("github_user")

    if not github_user:
        github_user = input("  GitHub username: ").strip()
        if github_user:
            config["github_user"] = github_user

    default_host      = "arduino@" + name + ".local"
    default_apps_path = "~/Arduino/" + name
    default_repo_name = name

    try:
        validate_name(name, "Board name")
    except ValueError as e:
        print(f"ERROR: {e}")
        sys.exit(1)
    host_input = input("  SSH host [" + default_host + "]: ").strip()
    host       = (host_input if host_input else default_host).lower()

    apps_path_input = input("  Apps path on board [" + default_apps_path + "]: ").strip()
    apps_path       = os.path.expanduser(apps_path_input if apps_path_input else default_apps_path)

    repo_name_input = input("  Repo name [" + default_repo_name + "]: ").strip()
    repo_name       = repo_name_input if repo_name_input else default_repo_name
    repo            = "https://github.com/" + github_user + "/" + repo_name + ".git"

    is_first        = config.get("active_board") is None
    repo_dest       = os.path.expanduser("~/Repos/GitHub/" + github_user)
    repo_local_path = os.path.join(repo_dest, repo_name)
    apps_src        = os.path.join(repo_local_path, "Arduino", name)
    already_cloned  = os.path.isdir(repo_local_path)
    already_synced  = os.path.isdir(os.path.expanduser(apps_path))

    # ── Pre-flight summary ─────────────────────────────────────────────────────
    print()
    print("=" * 55)
    print("  PRE-FLIGHT SUMMARY — CHANGES TO BE MADE")
    print("=" * 55)
    print()
    print("BOARD CONFIG  (saved to ~/.hybx/config.json)")
    print("  Name:      " + name)
    print("  Host:      " + host)
    print("  Apps path: " + apps_path)
    print("  Repo:      " + repo)
    if is_first:
        print("  Note:      First board — will be set as active board")
    print()
    print("REPOSITORY")
    if already_cloned:
        print("  Already cloned: " + repo_local_path + " — will pull latest")
    else:
        print("  Clone: " + repo)
        print("    into: " + repo_local_path)
    print()
    print("APPS")
    if already_synced:
        print("  Apps path already exists: " + apps_path + " — no copy needed")
        print("  Run 'board pull' to add any new apps from the repo")
    else:
        if os.path.isdir(apps_src):
            print("  Copy apps: " + apps_src)
            print("    into:    " + apps_path)
        else:
            print("  Apps source not found in repo yet: " + apps_src)
            print("  Run 'board pull' after the repo is populated")
    print()
    print("=" * 55)
    print()

    # ── Confirm ────────────────────────────────────────────────────────────────
    if not confirm_prompt("Proceed with adding board '" + name + "'"):
        print("\nCancelled. Nothing was changed.")
        return

    # ── Save config ────────────────────────────────────────────────────────────
    boards[name] = {
        "host":      host,
        "apps_path": apps_path,
        "repo":      repo,
    }

    if is_first:
        config["active_board"] = name

    save_config(config)

    # ── Clone or pull repo ─────────────────────────────────────────────────────
    print()
    os.makedirs(repo_dest, exist_ok=True)
    if already_cloned:
        print("Pulling " + repo_name + " ...")
        result = subprocess.run(
            ["git", "pull"], cwd=repo_local_path,
            capture_output=True, text=True
        )
        if result.returncode != 0:
            print("WARNING: git pull failed: " + result.stderr.strip())
            print("Run 'board pull' to retry.")
        else:
            print(result.stdout.strip() if result.stdout.strip() else "Already up to date.")
    else:
        print("Cloning " + repo_name + " ...")
        result = subprocess.run(
            ["git", "clone", repo, repo_local_path],
            capture_output=True, text=True
        )
        if result.returncode != 0:
            print("WARNING: git clone failed: " + result.stderr.strip())
            print("Run 'board pull' to retry after fixing SSH/network access.")
        else:
            print("Cloned: " + repo_local_path)

    # ── Copy apps if source exists ─────────────────────────────────────────────
    if not already_synced and os.path.isdir(apps_src):
        print()
        print("Copying apps to " + apps_path + " ...")
        os.makedirs(apps_path, exist_ok=True)
        for entry in sorted(os.scandir(apps_src), key=lambda e: e.name):
            if entry.is_dir():
                dst = os.path.join(apps_path, entry.name)
                if not os.path.isdir(dst):
                    shutil.copytree(entry.path, dst)
                    print("  Copied: " + entry.name)

    print()
    if is_first:
        print("First board added — set as active board.")
    print("Board '" + name + "' added successfully.")


def cmd_remove(name: str):
    config = load_config()
    boards = config.get("boards", {})

    if name not in boards:
        print("ERROR: Board '" + name + "' not found. Use: board list")
        sys.exit(1)

    if not confirm_prompt("Remove board '" + name + "'"):
        print("Cancelled.")
        return

    del boards[name]

    if config.get("active_board") == name:
        config["active_board"] = None
        print("WARNING: '" + name + "' was the active board. Use: board use <n>")

    save_config(config)
    print("Board '" + name + "' removed.")


def cmd_pat(pat: str):
    """Store a GitHub PAT for the active board in ~/.hybx/config.json."""
    config = load_config()
    active = config.get("active_board")

    if not active:
        print("No active board set. Use: board use <n>")
        sys.exit(1)

    boards = config.get("boards", {})
    if active not in boards:
        print(f"ERROR: Board '{active}' not found in config.")
        sys.exit(1)

    boards[active]["pat"] = pat
    config["boards"] = boards
    save_config(config)
    print(f"PAT stored for board: {active}")
    print(f"Git push will now use PAT-embedded URL automatically.")


def cmd_show():
    config = load_config()
    active = config.get("active_board")

    if not active:
        print("No active board set. Use: board use <n>")
        sys.exit(1)

    info = config.get("boards", {}).get(active, {})

    print("Active board: " + active)
    print("  host:       " + info.get("host", "(not set)"))
    print("  apps_path:  " + info.get("apps_path", "(not set)"))
    print("  repo:       " + info.get("repo", "(not set)"))
    print("  branch:     " + config.get("dev_branch", "main"))


def cmd_branch(branch: str):
    """
    Switch all HybX repos to the specified branch and run update.

    Repos switched:
      - HybX-Development-System
      - Active board apps repo (e.g. UNO-Q)
      - All HybX library repos in ~/Arduino/libraries/

    Stores dev_branch in ~/.hybx/config.json so pull_all_repos
    always knows which branch to pull.
    """
    config      = load_config()
    github_user = config.get("github_user")

    if not github_user:
        print("ERROR: github_user not set in config. Run: board add")
        sys.exit(1)

    repo_dest = os.path.expanduser("~/Repos/GitHub/" + github_user)
    dev_dest  = os.path.join(repo_dest, "HybX-Development-System")

    # Collect all repos to switch
    repos = [dev_dest]

    active = config.get("active_board")
    if active:
        boards   = config.get("boards", {})
        board    = boards.get(active, {})
        repo_url = board.get("repo", "")
        if repo_url:
            repo_name = repo_url.rstrip("/").rstrip(".git").split("/")[-1]
            repos.append(os.path.join(repo_dest, repo_name))

    hybx_libs_dir = os.path.expanduser("~/Arduino/libraries")
    if os.path.isdir(hybx_libs_dir):
        for entry in os.scandir(hybx_libs_dir):
            if entry.is_dir() and os.path.isdir(os.path.join(entry.path, ".git")):
                repos.append(entry.path)

    # Switch each repo
    errors = []
    for repo_path in repos:
        if not os.path.isdir(repo_path):
            print(f"  WARNING: repo not found — skipping: {repo_path}")
            continue
        name = os.path.basename(repo_path)
        code, out, err = run_quiet(["git", "checkout", branch], cwd=repo_path)
        if code != 0:
            print(f"  ERROR: {name}: {err}")
            errors.append(name)
        else:
            code2, out2, _ = run_quiet(["git", "pull"], cwd=repo_path)
            status = "Already up to date." if "Already up to date" in out2 else out2
            print(f"  {name}: {branch} — {status}")

    if errors:
        print(f"ERROR: Failed to switch: {', '.join(errors)}")
        sys.exit(1)

    # Store dev_branch in config
    config["dev_branch"] = branch
    save_config(config)

    # Run update to deploy everything from the new branch
    print()
    print(f"Running update...")
    subprocess.run(["update"])


def usage():
    print("Usage:")
    print("  board list              - List all configured boards")
    print("  board show              - Show active board details")
    print("  board add <n>           - Add a new board configuration")
    print("  board use <n>           - Set the active board")
    print("  board remove <n>        - Remove a board configuration")
    print("  board pat <token>       - Store GitHub PAT for push operations")
    print("  board branch <name>     - Switch all repos to branch and run update")


# ── Main ───────────────────────────────────────────────────────────────────────


def main():
    install_sigint_handler()
    print("=== board ===")

    SUBCOMMANDS = ["list", "show", "use", "add", "remove", "pat", "branch"]

    if len(sys.argv) < 2:
        usage()
        sys.exit(1)

    command = resolve_subcommand(sys.argv[1], SUBCOMMANDS)

    if command == "list":
        cmd_list()

    elif command == "pat":
        if len(sys.argv) < 3:
            print("Usage: board pat <github_pat>")
            sys.exit(1)
        cmd_pat(sys.argv[2])
    elif command == "show":
        cmd_show()

    elif command == "use":
        if len(sys.argv) < 3:
            print("Usage: board use <n>")
            sys.exit(1)
        cmd_use(" ".join(sys.argv[2:]).lower())

    elif command == "add":
        if len(sys.argv) < 3:
            print("Usage: board add <n>")
            sys.exit(1)
        cmd_add(" ".join(sys.argv[2:]).lower())

    elif command == "remove":
        if len(sys.argv) < 3:
            print("Usage: board remove <n>")
            sys.exit(1)
        cmd_remove(" ".join(sys.argv[2:]).lower())

    elif command == "branch":
        if len(sys.argv) < 3:
            print("Usage: board branch <name>")
            sys.exit(1)
        cmd_branch(sys.argv[2])

    else:
        print("ERROR: Unknown command '" + command + "'")
        usage()
        sys.exit(1)


if __name__ == "__main__":
    main()
