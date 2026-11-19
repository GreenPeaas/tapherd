# Set up TapHerd on Linux (beta)

TapHerd's automated tests pass on Ubuntu with Python 3.11–3.13. Real devices haven't been tried on Linux yet, so treat it as beta and [report anything that breaks](https://github.com/asuopys/tapherd/issues/new/choose).

## Fastest path: the installer

```sh
curl -LsSf https://raw.githubusercontent.com/asuopys/tapherd/main/scripts/install.sh | sh
```

The script installs uv for your user, then TapHerd, and runs `tapherd doctor`. If `adb` is missing, it prints the package-manager command to run. It asks before running anything with `sudo` and explains why. To read it first, open [scripts/install.sh](../scripts/install.sh).

## Manual install

```sh
curl -LsSf https://astral.sh/uv/install.sh | sh     # uv, for your user only
sudo apt install adb                                 # Debian and Ubuntu; Fedora: sudo dnf install android-tools
uv tool install tapherd
tapherd doctor
```

`sudo` is only needed for the package manager, which installs `adb` system-wide.

## Check KVM

The Android emulator needs KVM for usable speed.

```sh
ls -l /dev/kvm                 # should exist
sudo usermod -aG kvm "$USER"   # then log out and back in
```

If `/dev/kvm` is missing, turn on virtualization (VT-x or AMD-V) in your BIOS or UEFI.

## Download the Android emulator

1. Download [Android Studio](https://developer.android.com/studio) for Linux, extract it, and run `bin/studio.sh`. Choose the **Standard** setup.
2. Open **More Actions → Virtual Device Manager** and create a **Pixel** device with a **Google Play** system image at **API 34 or later**. Use **x86_64** on Intel and AMD computers, or **arm64-v8a** on Arm.
3. Start it and wait for the home screen. `adb devices -l` should list `emulator-5554  device`.

The command-line route in the [macOS guide](SETUP_MAC.md#option-b-command-line-only) also works on Linux. Download the command-line tools zip from Android's site instead of using Homebrew.

## Let ADB reach a USB phone

Most distributions need a udev rule before your user can talk to a phone.

```sh
sudo apt install android-sdk-platform-tools-common   # Debian and Ubuntu ship ready-made rules
# Or write a rule yourself, using your phone's vendor ID from `lsusb` (18d1 is Google):
echo 'SUBSYSTEM=="usb", ATTR{idVendor}=="18d1", MODE="0660", GROUP="plugdev"' | sudo tee /etc/udev/rules.d/51-android.rules
sudo udevadm control --reload-rules && sudo usermod -aG plugdev "$USER"
```

Reconnect the phone, accept **Allow USB debugging**, and run `tapherd devices`.

## Connect your AI

Claude Desktop isn't available on Linux. Use Claude Code, Codex, or Cursor. [Connect your AI](CONNECT_YOUR_AI.md)

Problems? See [Troubleshooting](TROUBLESHOOTING.md).
