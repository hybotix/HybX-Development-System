#!/usr/bin/env python3
"""
sync-v0.0.1.py
Hybrid RobotiX — HybX Development System

Syncs the active board's app repository and copies any new apps into
the board's apps directory. Always operates on the active board — use
'board use <n>' to switch boards before running sync.

Only NEW apps are added. Existing app directories are never overwritten
or modified. This ensures local changes to existing apps are preserved.

Usage:
  sync              - Sync apps for the active board
  sync --dry-run    - Show what would be added without making changes

Flags:
  --dry-run         - Preview only, no changes made
  --json            - Machine-readable JSON output (for GUI)

Exit codes:
  0  success
  1  user error (no active board, repo not configured, etc.)
  2  system error (git pull failed, filesystem error, etc.)
"""

import os
import sys
import shutil
import subprocess
import json

sys.path.insert(0, os.path.dirname(os.path.realpath(__file__)))

from hybx_config import get_active_board, get_push_url  # noqa: E402

# ── Argument parsing ───────────────────────────────────────────────────────────


def parse_args() -> tuple[bool, bool]:
    """Returns (dry_run, json_mode)."""
    args      = sys.argv[1:]
    dry_run   = "--dry-run" in args
    json_mode = "--json" in args
    return dry_run, json_mode


# ── Output helpers ─────────────────────────────────────────────────────────────


def out_json(data: dict):
    print(json.dumps(data, indent=2))


def out_error(msg: str, json_mode: bool, code: int = 1):
    if json_mode:
        out_json({"ok": False, "error": msg})
    else:
        print("ERROR: " + msg)
    sys.exit(code)


# ── Git helpers ────────────────────────────────────────────────────────────────


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
            ["git", "stash", "push", "-m", "hybx-sync-autostash"],
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


# ── App sync ───────────────────────────────────────────────────────────────────


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
    never modified.

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


# ── Main ───────────────────────────────────────────────────────────────────────


def main():
    dry_run, json_mode = parse_args()

    if not json_mode:
        os.system("clear")
        print("=== sync ===")
        if dry_run:
            print("(dry run — no changes will be made)")
        print()

    # Load active board
    board      = get_active_board()
    board_name = board["name"]
    apps_path  = board["apps_path"]
    repo_url   = board.get("repo", "")

    if not repo_url:
        out_error(
            "No repo configured for board '" + board_name + "'. "
            "Use: board use " + board_name + " and ensure repo is set.",
            json_mode, 1
        )

    # Derive local repo path from URL
    # Repo URL: https://github.com/<user>/<repo>.git
    # Local:    ~/Repos/GitHub/<user>/<repo>
    try:
        # Strip trailing .git and split on github.com/
        path_part = repo_url.replace("https://github.com/", "").rstrip("/")
        if path_part.endswith(".git"):
            path_part = path_part[:-4]
        github_user, repo_name = path_part.split("/", 1)
    except (ValueError, AttributeError):
        out_error(
            "Could not parse repo URL: " + repo_url,
            json_mode, 1
        )

    repo_path = os.path.expanduser(
        "~/Repos/GitHub/" + github_user + "/" + repo_name
    )

    if not os.path.isdir(repo_path):
        out_error(
            "Repo not found locally: " + repo_path + "\n"
            "Run 'update' first to clone the repo.",
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
            "ok":         True,
            "board":      board_name,
            "dry_run":    dry_run,
            "added":      added,
            "skipped":    skipped,
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
        print("Run 'sync' without --dry-run to apply.")
    else:
        summary = str(len(added)) + " app" + ("s" if len(added) != 1 else "") + " added"
        if skipped:
            summary += ", " + str(len(skipped)) + " already present"
        print("Sync complete — " + summary + ".")
    print()


if __name__ == "__main__":
    main()
