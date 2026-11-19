# Set up TapHerd on macOS

## Install TapHerd

Open **Terminal** and run the installer. It sets up uv and TapHerd for your user, offers to install `adb` with Homebrew, and runs `tapherd doctor`.

```sh
curl -LsSf https://raw.githubusercontent.com/GreenPeaas/tapherd/main/scripts/install.sh | sh
```

Already have uv? Run `uv tool install tapherd` instead. Working on TapHerd's own code? See [Contributing](../CONTRIBUTING.md).

## Download the Android emulator

TapHerd works with any Android device that ADB can reach. The quickest free setup is the official Android Emulator, which Google ships with Android Studio. Plan for about 15 GB of disk space and 8 GB of free memory per two running emulators.

### Option A: Android Studio (recommended)

This is the path TapHerd was verified with.

1. Download Android Studio for **Mac with Apple chip** from [developer.android.com/studio](https://developer.android.com/studio). Open the `.dmg` file and drag Android Studio into Applications.
2. Open Android Studio and accept the **Standard** setup. The wizard downloads the Android SDK, the Android Emulator, and Platform-Tools. Accept the licenses when asked.
3. Open **More Actions → Virtual Device Manager** from the welcome screen, or **Tools → Device Manager** from an open project.
4. Click **+ → Create Virtual Device**. Choose a **Pixel** phone profile that shows the Play Store icon.
5. Choose a **Google Play** system image at **API 34 or later** with architecture **`arm64-v8a`**. Click the download arrow next to it and wait for the download to finish.
6. Name the device `TapHerd_Pixel_1`, finish setup, and press its **Play** button. Wait for the Android home screen.
7. To test apps such as YouTube, sign in to the Play Store on the emulator with a test Google account, then install or update the apps you plan to use. Android Settings, Chrome, and Maps work without signing in.

The Google Play image lets you install YouTube, Instagram, TikTok, and X from the Play Store when each app is available for your account and device profile. [Android Device Manager guide](https://developer.android.com/studio/run/managing-avds)

### Option B: command line only

Use this if you don't want Android Studio. It installs the same SDK packages with Homebrew. TapHerd's checks used Option A, and this path has not been run on this Mac yet.

```sh
HOMEBREW_NO_INSTALL_CLEANUP=1 brew install --cask temurin android-commandlinetools
export ANDROID_HOME=/opt/homebrew/share/android-commandlinetools
yes | sdkmanager --licenses
sdkmanager "platform-tools" "emulator" "system-images;android-34;google_apis_playstore;arm64-v8a"
avdmanager create avd -n TapHerd_Pixel_1 -d pixel_7 \
  -k "system-images;android-34;google_apis_playstore;arm64-v8a"
"$ANDROID_HOME/emulator/emulator" -avd TapHerd_Pixel_1 &
```

`temurin` provides the Java runtime that `sdkmanager` needs. Repeat the `avdmanager` and `emulator` lines with `TapHerd_Pixel_2` and `TapHerd_Pixel_3` for more devices. [sdkmanager reference](https://developer.android.com/tools/sdkmanager) · [avdmanager reference](https://developer.android.com/tools/avdmanager)

### Use a real phone instead

On the phone, open **Settings → About phone** and tap **Build number** seven times to turn on Developer options. Then open **Settings → System → Developer options**, turn on **USB debugging**, connect the phone by USB, and accept the prompt on the phone. It appears in `adb devices -l` like an emulator.

## Check that ADB sees the emulator

Install Android Platform-Tools and check that the running emulator appears with status `device`.

```sh
HOMEBREW_NO_INSTALL_CLEANUP=1 brew install --cask android-platform-tools
adb version
adb devices -l
```

If the list is empty, start the emulator in Device Manager, wait for it to boot, and run `adb devices -l` again.

## Open Settings and capture the screen

Run these commands with the emulator running. If `devices` shows a different serial, set `TAPHERD_SERIAL` to that serial.

```sh
tapherd doctor
tapherd devices
TAPHERD_SERIAL=emulator-5554
TAPHERD_SMOKE_DIR=$(mktemp -d)
tapherd open-app "$TAPHERD_SERIAL" com.android.settings
tapherd inspect "$TAPHERD_SERIAL" > "$TAPHERD_SMOKE_DIR/settings.json"
tapherd screenshot "$TAPHERD_SERIAL" --out "$TAPHERD_SMOKE_DIR/settings.png"
cat "$TAPHERD_SMOKE_DIR/settings.json"
open "$TAPHERD_SMOKE_DIR/settings.png"
```

Settings should open on the emulator. The JSON should contain visible Settings elements and the PNG should show the Settings screen.

## Choose active devices

With no explicit selections, TapHerd uses up to three online devices in serial order. The `devices` command reports this mode and marks each device active or inactive. Use `devices --json` for the same information as JSON.

```sh
tapherd use "$TAPHERD_SERIAL"
tapherd label "$TAPHERD_SERIAL" "Pixel test phone" --group Demo
tapherd devices
tapherd unuse "$TAPHERD_SERIAL"
```

The first `use` command starts an explicit set with that serial. Run it again for each device you want in the set. A selected device keeps its slot if it goes offline. Removing the last explicit selection restores automatic selection. ADB connections stay available to other tools as you change TapHerd's active set. The selection and labels are stored in `~/.config/tapherd/devices.json` by default.

## Run two or three emulators at once

Create two more virtual devices in Device Manager, or with `avdmanager` from Option B, using the same profile and system image, named `TapHerd_Pixel_2` and `TapHerd_Pixel_3`. Start each device you want to use with its own Play button. If the Mac runs low on memory, test with two emulators first.

To start separate emulator windows from Terminal, close any running copies of the selected devices and run the following. Set `TAPHERD_ANDROID_SDK` to the SDK location shown in Android Studio's SDK Manager if it differs from the default. Leave out the third launch command when testing with two devices.

```sh
TAPHERD_ANDROID_SDK="$HOME/Library/Android/sdk"
"$TAPHERD_ANDROID_SDK/emulator/emulator" -list-avds
"$TAPHERD_ANDROID_SDK/emulator/emulator" -avd TapHerd_Pixel_1 &
"$TAPHERD_ANDROID_SDK/emulator/emulator" -avd TapHerd_Pixel_2 &
"$TAPHERD_ANDROID_SDK/emulator/emulator" -avd TapHerd_Pixel_3 &
```

After the home screens appear, run `adb devices -l` and check for two or three different emulator serials, each with status `device`. [Android Emulator command-line reference](https://developer.android.com/studio/run/emulator-commandline)

## Tap, swipe, and type

Use coordinates from `tapherd inspect` or tap by exact text, resource ID, or accessibility description. Selectors that match several locations require a more specific target or coordinates. Coordinates are in native screen pixels. Screenshots default to a maximum width of 720 pixels. Pass `--max-width` at least as large as the native width when using pixel coordinates from a screenshot.

```sh
tapherd tap "$TAPHERD_SERIAL" --text "Network & internet"
tapherd swipe "$TAPHERD_SERIAL" --direction up
tapherd press-key "$TAPHERD_SERIAL" back
```

Focus a text field before using `tapherd type-text`. TapHerd uses Android's `input text` for single-line printable ASCII when using the standard keyboard. For emoji, other Unicode, and multiline text, use the optional [ADBKeyboard input method](https://github.com/senzhk/ADBKeyBoard) on the test device.

Download or build `ADBKeyboard.apk` from the upstream project, then run the following from the directory containing the APK. Save the prior keyboard so you can restore it after the test.

```sh
TAPHERD_PRIOR_IME=$(adb -s "$TAPHERD_SERIAL" shell settings --user current get secure default_input_method)
tapherd install-apk "$TAPHERD_SERIAL" ./ADBKeyboard.apk
adb -s "$TAPHERD_SERIAL" shell ime list -a -s
```

Wait until the list shows `com.android.adbkeyboard/.AdbIME`. Enable it in the same terminal, then focus a test field and restore the prior keyboard when you finish.

```sh
adb -s "$TAPHERD_SERIAL" shell ime enable com.android.adbkeyboard/.AdbIME
adb -s "$TAPHERD_SERIAL" shell ime set com.android.adbkeyboard/.AdbIME
tapherd type-text "$TAPHERD_SERIAL" "Hello, 世界 🐈"
adb -s "$TAPHERD_SERIAL" shell ime set "$TAPHERD_PRIOR_IME"
```

## Copy media to Android

`tapherd push-media "$TAPHERD_SERIAL" ./video.mp4` copies the file into `/sdcard/DCIM/TapHerd/`, asks Android to scan it into the gallery, and prints the exact device path. Each transfer uses a unique filename. Use the printed filename to identify the copy in the gallery or Files app.
