#!/bin/bash
#
# update-v0.0.1.bash
# Hybrid RobotiX — HybX Development System Bootstrap
#
# Clones the UNO-Q and HybX-Development-System repos fresh, copies
# Arduino apps and bin commands to $HOME, copies secrets to each app
# that needs them, and creates versioned symlinks for all bin commands.
#
# This script lives in $HOME and is NEVER stored in the repo root.
# Copy it manually to $HOME on any new UNO Q for the first run:
#   cp ~/Repos/GitHub/hybotix/HybX-Development-System/scripts/update-v0.0.1.bash ~/update-v0.0.1.bash
#
# After the first run, the start command installs ~/bin/update automatically.
#
# Usage:
#   bash ~/update-v0.0.1.bash   # first time
#   update               # after first start
#
REPO_DEST="$HOME/Repos/GitHub/hybotix"
REPO="https://github.com/hybotix/UNO-Q.git"
DEV_REPO="https://github.com/hybotix/HybX-Development-System.git"
SECRETS_DEST="securesmars"
COMMANDS="libs board build clean FINALIZE list logs migrate project restart setup start stop update"

cd "$HOME" || exit 1
rm -rf "$HOME/Arduino" "$HOME/bin" "$HOME/Repos"
mkdir -p "$REPO_DEST"
cd "$REPO_DEST" || exit 1
git clone $REPO
git clone $DEV_REPO

cp -rp "$REPO_DEST/UNO-Q/Arduino" "$HOME"
cp -rp "$REPO_DEST/HybX-Development-System/bin" "$HOME"

#
#   Copy secrets.py.template to app directories (only if template exists)
#
cd "$HOME" || exit 1
for dest in $SECRETS_DEST; do
    if [ -f "$HOME/secrets.py.template" ]; then
        cp "$HOME/secrets.py.template" "Arduino/$dest/python/secrets.py"
        echo "Secrets: copied to Arduino/$dest/python/secrets.py"
    else
        echo "WARNING: secrets.py.template not found — skipping $dest"
    fi
done

#
# Make the symbolic links to the latest version of each command
#
cd "$HOME/bin" || exit 1
for cmd in $COMMANDS; do
    latest=$(ls ${cmd}-v*.py 2>/dev/null | sort -V | tail -1)
    if [ -n "$latest" ]; then
        ln -sf "$HOME/bin/$latest" "$HOME/bin/$cmd"
        chmod +x "$HOME/bin/$cmd"
        echo "Linked: $cmd -> $latest"
    else
        echo "WARNING: No versioned file found for $cmd"
    fi
done
