#!/bin/bash
#
# install-v0.0.1.bash
# Hybrid RobotiX — HybX Development System Installer
#
# Multi-platform installer for the HybX Development System.
# Detects the platform, prompts for GitHub credentials, clones
# the required repos, and installs versioned symlinks in ~/bin.
#
# Supported platforms:
#   - macOS (Apple Silicon)
#   - macOS (Intel)
#   - Linux ARM64 (Raspberry Pi 5, UNO Q, etc.)
#   - Linux x86_64 (Galileo, etc.)
#
# Usage:
#   bash install-v0.0.1.bash
#

set -e

# ── Platform Detection ─────────────────────────────────────────────────────────

OS="$(uname -s)"
ARCH="$(uname -m)"

case "$OS" in
    Darwin)
        case "$ARCH" in
            arm64)  PLATFORM="macos-arm64" ;;
            x86_64) PLATFORM="macos-x86_64" ;;
            *)      PLATFORM="macos-unknown" ;;
        esac
        ;;
    Linux)
        case "$ARCH" in
            aarch64) PLATFORM="linux-arm64" ;;
            x86_64)  PLATFORM="linux-x86_64" ;;
            *)       PLATFORM="linux-unknown" ;;
        esac
        ;;
    *)
        echo "ERROR: Unsupported platform: $OS $ARCH"
        exit 1
        ;;
esac

echo ""
echo "Hybrid RobotiX — HybX Development System Installer"
echo "===================================================="
echo "Platform: $PLATFORM"
echo ""

# ── Prompt for GitHub credentials ─────────────────────────────────────────────

read -p "GitHub username: " GITHUB_USER
if [ -z "$GITHUB_USER" ]; then
    echo "ERROR: GitHub username is required."
    exit 1
fi

read -s -p "GitHub PAT: " GITHUB_PAT
echo ""
if [ -z "$GITHUB_PAT" ]; then
    echo "ERROR: GitHub PAT is required."
    exit 1
fi

# ── Repo configuration ─────────────────────────────────────────────────────────

REPO_BASE="https://${GITHUB_PAT}@github.com/${GITHUB_USER}"
DEV_REPO="${REPO_BASE}/HybX-Development-System.git"
REPO_DEST="$HOME/Repos/GitHub/${GITHUB_USER}"

# ── Commands to install ────────────────────────────────────────────────────────

COMMANDS="board build clean FINALIZE libs list logs migrate project restart setup start stop update"

# ── ~/bin setup ────────────────────────────────────────────────────────────────

BIN_DIR="$HOME/bin"
if [ ! -d "$BIN_DIR" ]; then
    echo "Creating ~/bin ..."
    mkdir -p "$BIN_DIR"

    # Add to PATH in shell config
    case "$OS" in
        Darwin)
            SHELL_RC="$HOME/.zshrc"
            ;;
        Linux)
            SHELL_RC="$HOME/.bashrc"
            ;;
    esac

    echo "" >> "$SHELL_RC"
    echo "# HybX Development System" >> "$SHELL_RC"
    echo "export PATH=\"\$HOME/bin:\$PATH\"" >> "$SHELL_RC"
    echo "Added ~/bin to PATH in $SHELL_RC"
    export PATH="$BIN_DIR:$PATH"
fi

# ── Clone repos ────────────────────────────────────────────────────────────────

mkdir -p "$REPO_DEST"

DEV_DEST="$REPO_DEST/HybX-Development-System"
if [ -d "$DEV_DEST" ]; then
    echo "HybX-Development-System already exists — pulling latest ..."
    cd "$DEV_DEST"
    git pull
else
    echo "Cloning HybX-Development-System ..."
    cd "$REPO_DEST"
    git clone "$DEV_REPO"
fi

# ── Platform-specific setup ────────────────────────────────────────────────────

case "$PLATFORM" in
    macos-arm64|macos-x86_64|linux-x86_64)
        # Desktop/laptop platforms — symlink only, no app copying
        echo ""
        echo "Installing HybX commands to ~/bin ..."
        cd "$DEV_DEST/bin"
        for cmd in $COMMANDS; do
            latest=$(ls ${cmd}-v*.py 2>/dev/null | sort -V | tail -1)
            if [ -n "$latest" ]; then
                ln -sf "$DEV_DEST/bin/$latest" "$BIN_DIR/$cmd"
                chmod +x "$BIN_DIR/$cmd"
                echo "  Linked: $cmd -> $latest"
            else
                echo "  WARNING: No versioned file found for $cmd"
            fi
        done
        ;;

    linux-arm64)
        # Embedded Linux boards (UNO Q, Raspberry Pi, etc.)
        # Prompt for which repo to clone for apps
        echo ""
        read -p "Apps repo name (e.g. UNO-Q): " APPS_REPO_NAME
        if [ -n "$APPS_REPO_NAME" ]; then
            APPS_REPO="${REPO_BASE}/${APPS_REPO_NAME}.git"
            APPS_DEST="$REPO_DEST/${APPS_REPO_NAME}"
            if [ -d "$APPS_DEST" ]; then
                echo "${APPS_REPO_NAME} already exists — pulling latest ..."
                cd "$APPS_DEST"
                git pull
            else
                echo "Cloning ${APPS_REPO_NAME} ..."
                cd "$REPO_DEST"
                git clone "$APPS_REPO"
            fi
        fi

        echo ""
        echo "Installing HybX commands to ~/bin ..."
        cd "$DEV_DEST/bin"
        for cmd in $COMMANDS; do
            latest=$(ls ${cmd}-v*.py 2>/dev/null | sort -V | tail -1)
            if [ -n "$latest" ]; then
                ln -sf "$DEV_DEST/bin/$latest" "$BIN_DIR/$cmd"
                chmod +x "$BIN_DIR/$cmd"
                echo "  Linked: $cmd -> $latest"
            else
                echo "  WARNING: No versioned file found for $cmd"
            fi
        done
        ;;
esac

# ── Done ───────────────────────────────────────────────────────────────────────

echo ""
echo "===================================================="
echo "HybX Development System installed successfully!"
echo ""
echo "Next steps:"
echo "  1. Run: source ~/.zshrc   (or open a new terminal)"
echo "  2. Run: board add <name>  to configure your first board"
echo "===================================================="
echo ""
