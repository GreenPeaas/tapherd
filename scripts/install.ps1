# Install TapHerd on Windows (beta).
#
#   irm https://raw.githubusercontent.com/GreenPeaas/tapherd/main/scripts/install.ps1 | iex
#
# What it does, in order:
#   1. Installs uv (Python package manager) for your user if it's missing.
#   2. Checks for adb (Android Platform-Tools). If it's missing, it shows the winget
#      command and asks before running it. winget installs it for your user.
#   3. Installs TapHerd as a uv tool for your user.
#   4. Runs `tapherd doctor`.
# Run it in a normal PowerShell window. It never needs administrator rights.
#
# Options (environment variables):
#   TAPHERD_INSTALL_SOURCE  Where to install from (default: PyPI "tapherd", falling
#                           back to the GitHub repository).
#   TAPHERD_INSTALL_YES=1   Answer yes to every question (for scripts and CI).

$ErrorActionPreference = "Stop"
$RepoUrl = "git+https://github.com/GreenPeaas/tapherd"
$DocsUrl = "https://github.com/GreenPeaas/tapherd#readme"

function Step($Text) { Write-Host ""; Write-Host "==> $Text" }
function Ask($Question) {
    if ($env:TAPHERD_INSTALL_YES -eq "1") { return $true }
    $reply = Read-Host "$Question [y/N]"
    return $reply -match '^(y|yes)$'
}
function Refresh-Path {
    $machine = [Environment]::GetEnvironmentVariable("Path", "Machine")
    $user = [Environment]::GetEnvironmentVariable("Path", "User")
    $env:Path = "$user;$machine;$env:USERPROFILE\.local\bin"
}

Write-Host "Installing TapHerd on Windows (beta)."

# 1. uv
Step "Checking for uv"
if (Get-Command uv -ErrorAction SilentlyContinue) {
    Write-Host "uv is installed: $(uv --version)"
} else {
    Write-Host "uv installs Python and TapHerd for your user only (no administrator rights)."
    Write-Host "Running the official installer from https://astral.sh/uv/install.ps1"
    powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
    Refresh-Path
    if (-not (Get-Command uv -ErrorAction SilentlyContinue)) {
        Write-Host "uv was installed but isn't on PATH yet. Open a new PowerShell window and run this installer again."
        # `return`, not `exit`: under `irm | iex`, exit would close the window.
        return
    }
}

# 2. adb
Step "Checking for adb (Android Platform-Tools)"
if (Get-Command adb -ErrorAction SilentlyContinue) {
    Write-Host "adb is installed: $((adb version | Select-Object -First 1))"
} elseif (Get-Command winget -ErrorAction SilentlyContinue) {
    Write-Host "adb is missing. winget can install it for your user:"
    Write-Host "  winget install --id Google.PlatformTools --scope user"
    if (Ask "Run it now?") {
        winget install --id Google.PlatformTools --scope user --accept-source-agreements --accept-package-agreements
        Refresh-Path
    }
} else {
    Write-Host "adb is missing. Install Android Studio (it includes Platform-Tools) or download"
    Write-Host "Platform-Tools from https://developer.android.com/tools/releases/platform-tools and add it to PATH."
    Write-Host "See docs/SETUP_WINDOWS.md."
}

# 3. TapHerd
Step "Installing TapHerd"
if ($env:TAPHERD_INSTALL_SOURCE) {
    uv tool install --force $env:TAPHERD_INSTALL_SOURCE
} else {
    # Recent uv versions skip packages uploaded in the last few days, as a safety
    # delay. Exempt TapHerd only; older uv versions don't know the flag.
    uv tool install --force --exclude-newer-package tapherd=false tapherd 2>$null
    if ($LASTEXITCODE -ne 0) { uv tool install --force tapherd 2>$null }
    if ($LASTEXITCODE -ne 0) {
        Write-Host "TapHerd isn't on PyPI yet here. Installing from GitHub instead."
        uv tool install --force $RepoUrl
    }
}
Refresh-Path
$tapherd = "tapherd"
if (-not (Get-Command tapherd -ErrorAction SilentlyContinue)) {
    $tapherd = Join-Path (uv tool dir --bin) "tapherd.exe"
    Write-Host "Add TapHerd to your PATH for new windows with: uv tool update-shell"
}

# 4. Doctor
Step "Running tapherd doctor"
$env:TAPHERD_NO_TEASE = "1"
& $tapherd doctor
Remove-Item Env:TAPHERD_NO_TEASE
# doctor reports a missing device with a non-zero code; the install itself worked.
$global:LASTEXITCODE = 0

Write-Host ""
Write-Host "Done. Next: start an emulator or connect a phone, then connect your AI client:"
Write-Host "  tapherd config mcp --client claude-desktop   # or codex, claude-code, cursor"
Write-Host "Docs: $DocsUrl"
