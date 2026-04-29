"""
repo_helpers.py
Hybrid RobotiX — HybX Development System

Shared git repo pull helpers. Imported by update and start.

Functions:
    pull_repo(dest)           -- pull one repo, print results, stash/pop if dirty
    pull_all_repos(config)    -- pull Dev System, apps repo, and all HybX libraries
"""

import os
import subprocess


# ── Helpers ────────────────────────────────────────────────────────────────────


def _run_quiet(cmd, cwd=None) -> tuple[int, str]:
    result = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True)
    combined = (result.stdout.strip() + "\n" + result.stderr.strip()).strip()
    return result.returncode, combined


def _ensure_ssh_remote(dest: str):
    """If the repo's origin remote uses HTTPS, switch it to SSH."""
    code, url = _run_quiet(["git", "remote", "get-url", "origin"], cwd=dest)
    if url.startswith("https://github.com/"):
        ssh_url = url.replace("https://github.com/", "git@github.com:")
        subprocess.run(
            ["git", "remote", "set-url", "origin", ssh_url],
            cwd=dest, capture_output=True
        )
        print("  Switched remote to SSH: " + ssh_url)


def _is_dirty(dest: str) -> bool:
    """Return True if the repo has uncommitted local changes."""
    code, output = _run_quiet(["git", "status", "--porcelain"], cwd=dest)
    return code == 0 and bool(output.strip())


# ── Public API ─────────────────────────────────────────────────────────────────


def pull_repo(dest: str):
    """
    Pull the latest changes for a repo and print results.

    If the working tree is dirty, stash local changes first and restore
    them after the pull. Prints a clear summary of what happened.
    """
    if not os.path.isdir(dest):
        print("WARNING: " + dest + " not found — skipping pull")
        return

    name = os.path.basename(dest)
    print("Pulling " + name + " ...")
    _ensure_ssh_remote(dest)

    stashed = False
    if _is_dirty(dest):
        print("  Local changes detected — stashing ...")
        code, out = _run_quiet(
            ["git", "stash", "push", "-m", "hybx-update-autostash"],
            cwd=dest
        )
        if code != 0:
            print("  WARNING: git stash failed — attempting pull anyway")
        else:
            stashed = True
            print("  Stashed: " + out)

    code, out = _run_quiet(["git", "pull"], cwd=dest)
    if "Already up to date" in out:
        print("  Already up to date.")
    elif out:
        for line in out.splitlines():
            print("  " + line)
    else:
        print("  Done.")

    if stashed:
        print("  Restoring stashed changes ...")
        code, out = _run_quiet(["git", "stash", "pop"], cwd=dest)
        if code != 0:
            print("  WARNING: git stash pop failed.")
            print("  Your local changes are still in the stash.")
            print("  Run: git stash pop   in " + dest + " to restore them.")
        else:
            print("  Restored: " + out)


def pull_all_repos(config: dict):
    """
    Pull Dev System repo, active board apps repo, and all HybX library repos.
    Prints a clear summary line for each repo.

    Called by both `update` and `start`.
    """
    import platform as _platform

    github_user = config.get("github_user", "")
    repo_dest   = os.path.expanduser("~/Repos/GitHub/" + github_user)
    dev_dest    = os.path.join(repo_dest, "HybX-Development-System")

    # Always pull Dev System
    pull_repo(dev_dest)

    # On embedded Linux (the board itself), also pull apps repo + HybX libraries
    system  = _platform.system()
    machine = _platform.machine()
    if system == "Linux" and machine == "aarch64":
        active = config.get("active_board")
        if active:
            boards   = config.get("boards", {})
            board    = boards.get(active, {})
            repo_url = board.get("repo", "")
            if repo_url:
                repo_name = repo_url.rstrip("/").rstrip(".git").split("/")[-1]
                apps_dest = os.path.join(repo_dest, repo_name)
                pull_repo(apps_dest)

        # Pull all installed HybX library repos
        hybx_libs_dir = os.path.expanduser("~/Arduino/libraries")
        if os.path.isdir(hybx_libs_dir):
            for entry in os.scandir(hybx_libs_dir):
                if entry.is_dir() and os.path.isdir(os.path.join(entry.path, ".git")):
                    pull_repo(entry.path)
