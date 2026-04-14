#!/usr/bin/env python3
"""
board-v0.0.7.py
Hybrid RobotiX — HybX Development System

Manages board configurations for the HybX Development System.
All other commands read the active board from ~/.hybx/config.json.

Board names are always stored and matched in lowercase, regardless
of how they are entered.

PAT is NEVER stored — git operations use the system keychain or
the remote URL configured in the repo.

Usage:
  board list              - List all configured boards
  board show              - Show active board details
  board add <n>           - Add a new board configuration
  board use <n>           - Set the active board
  board remove <n>        - Remove a board configuration
  board sync              - Pull repo and sync new apps for the active board
  board sync --dry-run    - Preview what would be synced without making changes

Flags (board sync only):
  --dry-run               - Preview only, no changes made
  --json                  - Machine-readable JSON output

Exit codes:
  0  success
  1  user error
  2  system error (board sync git/filesystem failure)
"""

import os
import sys
sys.path.insert(0, os.path.dirname(os.path.realpath(__file__)))

from hybx_config import confirm_prompt, get_active_board  # noqa: E402

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


# ── Git helpers (used by board sync) ──────────────────────────────────────────


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
            ["git", "stash", "push", "-m", "hybx-boardsync-autostash"],
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
        json_mode: bool) -> tuple[list, list]:
    """
    Copy new app directories from the repo into the board's apps directory.

    Walks <repo_path>/Arduino/<board_name>/ and copies any app directory
    that does not already exist in apps_path. Existing directories are
    never modified — local changes are always preserved.

    Returns (added, skipped) lists of app names.
    """
    arduino_src = os.path.join(repo_path, "Arduino", board_name)

    if not os.path.isdir(arduino_src):
        return [], []

    os.makedirs(apps_path, exist_ok=True)

    added   = []
    skipped = []

    for entry in sorted(os.scandir(arduino_src), key=lambda e: e.name):
        if not entry.is_dir():
            continue
        dst = os.path.join(apps_path, entry.name)
        if os.path.isdir(dst):
            skipped.append(entry.name)
        else:
            if not dry_run:
                shutil.copytree(entry.path, dst)
            added.append(entry.name)

    return added, skipped


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
        print("  Run 'board sync' to add any new apps from the repo")
    else:
        if os.path.isdir(apps_src):
            print("  Copy apps: " + apps_src)
            print("    into:    " + apps_path)
        else:
            print("  Apps source not found in repo yet: " + apps_src)
            print("  Run 'board sync' after the repo is populated")
    print()
    print("=" * 55)
    print()

    # ── Confirm ────────────────────────────────────────────────────────────────
    while True:
        answer = input("Proceed? (yes/no): ").strip().lower()
        if answer == "yes":
            break
        if answer == "no":
            print("\nCancelled. Nothing was changed.")
            return
        print("Please type exactly 'yes' or 'no'.")

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
            print("Run 'board sync' to retry.")
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
            print("Run 'board sync' to retry after fixing SSH/network access.")
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


def cmd_show():
    config = load_config()
    active = config.get("active_board")

    if not active:
        print("No active board set. Use: board use <n>")
        sys.exit(1)

    info = config.get("boards", {}).get(active, {})

    print("Active board: " + active)
    print("  host:      " + info.get("host", "(not set)"))
    print("  apps_path: " + info.get("apps_path", "(not set)"))
    print("  repo:      " + info.get("repo", "(not set)"))


def cmd_sync(dry_run: bool, json_mode: bool):
    """
    Pull the active board's repo and copy any new apps into apps_path.
    Only NEW apps are added — existing directories are never modified.
    """
    if not json_mode:
        if dry_run:
            print("(dry run — no changes will be made)")
        print()

    board      = get_active_board()
    board_name = board["name"]
    apps_path  = board["apps_path"]
    repo_url   = board.get("repo", "")

    if not repo_url:
        out_error(
            "No repo configured for board '" + board_name + "'. "
            "Re-add the board with: board add " + board_name,
            json_mode, 1
        )

    # Derive local repo path from URL
    # https://github.com/<user>/<repo>.git -> ~/Repos/GitHub/<user>/<repo>
    try:
        path_part = repo_url.replace("https://github.com/", "").rstrip("/")
        if path_part.endswith(".git"):
            path_part = path_part[:-4]
        github_user, repo_name = path_part.split("/", 1)
    except (ValueError, AttributeError):
        out_error("Could not parse repo URL: " + repo_url, json_mode, 1)

    repo_path = os.path.expanduser(
        "~/Repos/GitHub/" + github_user + "/" + repo_name
    )

    if not os.path.isdir(repo_path):
        out_error(
            "Repo not found locally: " + repo_path +
            " — run 'update' first.",
            json_mode, 1
        )

    if not json_mode:
        print("Board:     " + board_name)
        print("Repo:      " + repo_url)
        print("Apps path: " + apps_path)
        print()

    # Pull latest repo
    if not dry_run:
        if not json_mode:
            print("Pulling " + repo_name + " ...")
        ok = pull_repo(repo_path, json_mode)
        if not ok:
            out_error("git pull failed for " + repo_name, json_mode, 2)
        print()
    else:
        if not json_mode:
            print("(dry run — skipping git pull)")
            print()

    # Sync apps
    if not json_mode:
        print("Syncing apps to " + apps_path + " ...")
        print()

    added, skipped = sync_apps(
        repo_path, board_name, apps_path, dry_run, json_mode
    )

    if json_mode:
        out_json({
            "ok":      True,
            "board":   board_name,
            "dry_run": dry_run,
            "added":   added,
            "skipped": skipped,
        })
        return

    if added:
        for name in added:
            prefix = "  Would add: " if dry_run else "  Added:     "
            print(prefix + name)
    else:
        print("  No new apps to add.")

    if skipped:
        print()
        print("  Already present (" + str(len(skipped)) + "):")
        for name in skipped:
            print("    " + name)

    print()
    if dry_run:
        print("Dry run complete — no changes were made.")
        print("Run 'board sync' to apply.")
    else:
        summary = str(len(added)) + " app" + ("s" if len(added) != 1 else "") + " added"
        if skipped:
            summary += ", " + str(len(skipped)) + " already present"
        print("Sync complete — " + summary + ".")
    print()


def usage():
    print("Usage:")
    print("  board list              - List all configured boards")
    print("  board show              - Show active board details")
    print("  board add <n>           - Add a new board configuration")
    print("  board use <n>           - Set the active board")
    print("  board remove <n>        - Remove a board configuration")
    print("  board sync              - Pull repo and sync new apps")
    print("  board sync --dry-run    - Preview sync without making changes")


# ── Main ───────────────────────────────────────────────────────────────────────


def main():
    os.system("clear")
    print("=== board ===")

    if len(sys.argv) < 2:
        usage()
        sys.exit(1)

    command = sys.argv[1]

    if command == "list":
        cmd_list()

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

    elif command == "sync":
        dry_run   = "--dry-run" in sys.argv
        json_mode = "--json"    in sys.argv
        cmd_sync(dry_run, json_mode)

    else:
        print("ERROR: Unknown command '" + command + "'")
        usage()
        sys.exit(1)


if __name__ == "__main__":
    main()
