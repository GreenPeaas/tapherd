#!/bin/sh
# Install TapHerd on macOS or Linux.
#
#   curl -LsSf https://raw.githubusercontent.com/GreenPeaas/tapherd/main/scripts/install.sh | sh
#
# What it does, in order:
#   1. Installs uv (Python package manager) for your user if it's missing.
#   2. Checks for adb (Android Platform-Tools). If it's missing, it shows the
#      install command and asks before running it. Commands that need sudo are
#      explained first and never run without a yes.
#   3. Installs TapHerd as a uv tool for your user.
#   4. Runs `tapherd doctor`.
# Nothing here needs admin rights except your package manager on Linux.
#
# Options (environment variables):
#   TAPHERD_INSTALL_SOURCE  Where to install from (default: PyPI "tapherd", falling
#                           back to the GitHub repository).
#   TAPHERD_INSTALL_YES=1   Answer yes to every question (for scripts and CI).

set -eu

REPO_URL="git+https://github.com/GreenPeaas/tapherd"
DOCS_URL="https://github.com/GreenPeaas/tapherd#readme"

say() { printf '%s\n' "$*"; }
step() { printf '\n==> %s\n' "$*"; }

ask() {
    # Read the answer from the terminal, because stdin is this script when piped.
    if [ "${TAPHERD_INSTALL_YES:-}" = "1" ]; then
        return 0
    fi
    if [ ! -r /dev/tty ]; then
        say "(No terminal to ask. Skipping. Run the command above yourself.)"
        return 1
    fi
    printf '%s [y/N] ' "$1" > /dev/tty
    read -r reply < /dev/tty || reply=""
    case "$reply" in
        y | Y | yes | YES) return 0 ;;
        *) return 1 ;;
    esac
}

os="$(uname -s)"
case "$os" in
    Darwin) platform="macOS" ;;
    Linux) platform="Linux" ;;
    *)
        say "This installer is for macOS and Linux. On Windows, use scripts/install.ps1."
        exit 1
        ;;
esac
say "Installing TapHerd on $platform."

# 1. uv
step "Checking for uv"
if command -v uv > /dev/null 2>&1; then
    say "uv is installed: $(uv --version)"
else
    say "uv installs Python and TapHerd for your user only (no sudo)."
    say "Running the official installer from https://astral.sh/uv/install.sh"
    curl -LsSf https://astral.sh/uv/install.sh | sh
    # Make uv available in this shell.
    PATH="$HOME/.local/bin:$HOME/.cargo/bin:$PATH"
    export PATH
    command -v uv > /dev/null 2>&1 || {
        say "uv was installed but isn't on PATH yet. Open a new terminal and run this installer again."
        exit 1
    }
fi

# 2. adb
step "Checking for adb (Android Platform-Tools)"
if command -v adb > /dev/null 2>&1; then
    say "adb is installed: $(adb version | head -n 1)"
else
    if [ "$platform" = "macOS" ]; then
        if command -v brew > /dev/null 2>&1; then
            cmd="brew install --cask android-platform-tools"
            say "adb is missing. Homebrew can install it for your user:"
            say "  $cmd"
            if ask "Run it now?"; then
                HOMEBREW_NO_INSTALL_CLEANUP=1 brew install --cask android-platform-tools
            fi
        else
            say "adb is missing. Install Homebrew from https://brew.sh, then run:"
            say "  brew install --cask android-platform-tools"
            say "Or install Android Studio, which includes it. See docs/SETUP_MAC.md."
        fi
    else
        if command -v apt-get > /dev/null 2>&1; then
            cmd="sudo apt-get install -y adb"
        elif command -v dnf > /dev/null 2>&1; then
            cmd="sudo dnf install -y android-tools"
        elif command -v pacman > /dev/null 2>&1; then
            cmd="sudo pacman -S --needed android-tools"
        else
            cmd=""
        fi
        if [ -n "$cmd" ]; then
            say "adb is missing. Your package manager can install it:"
            say "  $cmd"
            say "This needs sudo because the package manager installs adb for every user on this computer."
            if ask "Run it now? You'll be asked for your password."; then
                sh -c "$cmd"
            fi
        else
            say "adb is missing. Install Android Platform-Tools with your package manager"
            say "or from https://developer.android.com/tools/releases/platform-tools. See docs/SETUP_LINUX.md."
        fi
    fi
fi

# 3. TapHerd
step "Installing TapHerd"
# Recent uv versions skip packages uploaded in the last few days, as a safety
# delay. Exempt TapHerd only, so a fresh release installs right away; older uv
# versions don't know the flag, so fall back to a plain install.
pypi_install() {
    uv tool install --force --exclude-newer-package tapherd=false tapherd 2> /dev/null ||
        uv tool install --force tapherd 2> /dev/null
}
if [ -n "${TAPHERD_INSTALL_SOURCE:-}" ]; then
    uv tool install --force "$TAPHERD_INSTALL_SOURCE"
elif ! pypi_install; then
    say "TapHerd isn't on PyPI yet here. Installing from GitHub instead."
    uv tool install --force "$REPO_URL"
fi

tool_bin="$(uv tool dir --bin 2> /dev/null || printf '%s' "$HOME/.local/bin")"
if command -v tapherd > /dev/null 2>&1; then
    tapherd_cmd="tapherd"
else
    tapherd_cmd="$tool_bin/tapherd"
    say "Add TapHerd to your PATH for new terminals with: uv tool update-shell"
fi

# 4. Doctor
step "Running tapherd doctor"
TAPHERD_NO_TEASE=1 "$tapherd_cmd" doctor || true

say ""
say "Done. Next: start an emulator or connect a phone, then connect your AI client:"
say "  tapherd config mcp --client claude-code   # or codex, claude-desktop, cursor"
say "Docs: $DOCS_URL"
