"""Run Android input, app launch, and transfer operations on an active device."""

import base64
import mimetypes
import re
from contextlib import suppress
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from uuid import uuid4

from tapherd.devices.adb import DeviceConnection
from tapherd.errors import TapHerdError
from tapherd.ui.screen import read_screen

_ADB_KEYBOARD_PACKAGE = "com.android.adbkeyboard"
_ADB_KEYBOARD_INPUT_METHODS = {
    f"{_ADB_KEYBOARD_PACKAGE}/.AdbIME",
    f"{_ADB_KEYBOARD_PACKAGE}/{_ADB_KEYBOARD_PACKAGE}.AdbIME",
}
_MEDIA_DIRECTORY = "/sdcard/DCIM/TapHerd"
_POSTING_ALLOW = (
    "android.permission.READ_MEDIA_IMAGES",
    "android.permission.READ_MEDIA_VIDEO",
    "android.permission.READ_EXTERNAL_STORAGE",
)
_SELECTED_MEDIA_ONLY = "android.permission.READ_MEDIA_VISUAL_USER_SELECTED"
_POSTING_DENY = ("android.permission.CAMERA", "android.permission.RECORD_AUDIO")
_TYPE_CHUNK = 50
_MEDIA_NAME = re.compile(r"[A-Za-z0-9_-]+-[0-9a-f]{32}\.[a-z0-9]{1,5}")
_PACKAGE = re.compile(r"[A-Za-z][A-Za-z0-9_]*(?:\.[A-Za-z][A-Za-z0-9_]*)+")
_COMPONENT = re.compile(r"[A-Za-z][\w.]*/[\w.$]+")


class Key(StrEnum):
    BACK = "back"
    HOME = "home"
    ENTER = "enter"
    RECENTS = "recents"
    DELETE = "delete"


_KEYCODES = {
    Key.BACK: "KEYCODE_BACK",
    Key.HOME: "KEYCODE_HOME",
    Key.ENTER: "KEYCODE_ENTER",
    Key.RECENTS: "KEYCODE_APP_SWITCH",
    Key.DELETE: "KEYCODE_DEL",
}


class Direction(StrEnum):
    UP = "up"
    DOWN = "down"
    LEFT = "left"
    RIGHT = "right"


@dataclass(frozen=True, slots=True)
class TapSelector:
    text: str | None = None
    resource_id: str | None = None
    content_desc: str | None = None

    def coordinates(self, device: DeviceConnection) -> tuple[int, int]:
        fields = [
            (name, value)
            for name, value in (
                ("text", self.text),
                ("resource_id", self.resource_id),
                ("content_desc", self.content_desc),
            )
            if value is not None
        ]
        if len(fields) != 1 or fields[0][1] == "":
            raise TapHerdError("Choose one non-empty selector field for the tap.")
        field, value = fields[0]
        matches = {
            element.center
            for element in read_screen(device, limit=None)
            if getattr(element, field) == value
        }
        if len(matches) != 1:
            cause = "found no match" if not matches else "matched several locations"
            raise TapHerdError(
                f"The {field} selector {cause}. Run `tapherd inspect` or "
                "`tapherd screenshot`, then choose a unique selector or use coordinates."
            )
        return matches.pop()


@dataclass(frozen=True, slots=True)
class AndroidActions:
    device: DeviceConnection

    def tap(
        self,
        x: int | None = None,
        y: int | None = None,
        *,
        selector: TapSelector | None = None,
    ) -> None:
        if selector is not None and x is None and y is None:
            x, y = selector.coordinates(self.device)
        elif selector is not None or x is None or y is None:
            raise TapHerdError("Provide both x and y coordinates or one tap selector.")
        if min(x, y) < 0:
            raise TapHerdError(
                "Choose non-negative tap coordinates from the device screen."
            )
        self.device.shell("input", "tap", str(x), str(y))

    def swipe(
        self,
        coordinates: tuple[int | None, int | None, int | None, int | None]
        | None = None,
        *,
        direction: Direction | None = None,
        duration_ms: int = 300,
    ) -> None:
        if coordinates and coordinates != (None, None, None, None):
            x1, y1, x2, y2 = coordinates
            if (
                x1 is None
                or y1 is None
                or x2 is None
                or y2 is None
                or direction is not None
            ):
                raise TapHerdError(
                    "Provide all four swipe coordinates or a swipe direction."
                )
            points = (x1, y1, x2, y2)
        elif direction is not None:
            width, height = self.device.screen_size()
            mid_x, mid_y = width // 2, height // 2
            start_x, end_x = width // 5, width * 4 // 5
            start_y, end_y = height // 5, height * 4 // 5
            points = {
                Direction.UP: (mid_x, end_y, mid_x, start_y),
                Direction.DOWN: (mid_x, start_y, mid_x, end_y),
                Direction.LEFT: (end_x, mid_y, start_x, mid_y),
                Direction.RIGHT: (start_x, mid_y, end_x, mid_y),
            }[direction]
        else:
            raise TapHerdError(
                "Provide all four swipe coordinates or a swipe direction."
            )
        if min(points) < 0 or duration_ms < 1:
            raise TapHerdError(
                "Use non-negative coordinates and a positive swipe duration."
            )
        self.device.shell(
            "input",
            "swipe",
            *map(str, points),
            str(duration_ms),
            timeout=15 + duration_ms / 1_000,
        )

    def type_text(self, text: str) -> None:
        if not text:
            return
        ime = self.device.shell(
            "settings", "--user", "current", "get", "secure", "default_input_method"
        )
        if ime in _ADB_KEYBOARD_INPUT_METHODS:
            payload = base64.b64encode(text.encode("utf-8")).decode("ascii")
            self.device.shell(
                "am",
                "broadcast",
                "--user",
                "current",
                "-a",
                "ADB_INPUT_B64",
                "-p",
                _ADB_KEYBOARD_PACKAGE,
                "--es",
                "msg",
                payload,
            )
            return
        if not (text.isascii() and text.isprintable()):
            raise TapHerdError(
                "Type single-line plain ASCII, or install and select ADBKeyboard to type "
                "emoji, other Unicode, or several lines. See docs/TROUBLESHOOTING.md."
            )
        # Android treats %s as a space. Put a literal percent and s in separate commands.
        # Long text is sent in short pieces because `input text` can drop the end.
        for part in text.replace("%s", "%\0s").split("\0"):
            for start in range(0, len(part), _TYPE_CHUNK):
                chunk = part[start : start + _TYPE_CHUNK]
                self.device.shell("input", "text", chunk.replace(" ", "%s"))

    def press_key(self, key: Key) -> None:
        self.device.shell("input", "keyevent", _KEYCODES[key])

    def open_app(self, package: str) -> None:
        if not _PACKAGE.fullmatch(package):
            raise TapHerdError(
                "Enter an Android package name such as com.android.settings."
            )
        try:
            # Apps such as TikTok and Instagram declare several launcher entries,
            # so a package-only launch can't resolve. Start the exact launcher
            # activity when Android can name it.
            component = self._launcher_activity(package)
            target = ("-n", component) if component else ("-p", package)
            output = self.device.shell(
                "am",
                "start",
                "-W",
                "-a",
                "android.intent.action.MAIN",
                "-c",
                "android.intent.category.LAUNCHER",
                *target,
                timeout=25,
            )
            if "Status: ok" not in output:
                raise TapHerdError("Android did not confirm that the app opened.")
        except TapHerdError as error:
            raise TapHerdError(
                f"Could not open {package} on {self.device.serial}. "
                "Check that the app is installed and has a launcher, then try again."
            ) from error

    def _launcher_activity(self, package: str) -> str | None:
        """Return the activity Android's launcher would open, such as pkg/.Main."""
        try:
            output = self.device.shell(
                "cmd",
                "package",
                "resolve-activity",
                "--brief",
                "-a",
                "android.intent.action.MAIN",
                "-c",
                "android.intent.category.LAUNCHER",
                package,
            )
        except TapHerdError:
            return None
        lines = [line.strip() for line in output.splitlines() if line.strip()]
        component = lines[-1] if lines else ""
        if _COMPONENT.fullmatch(component) and component.startswith(f"{package}/"):
            return component
        return None

    def install_apk(self, path: Path) -> None:
        if not path.is_file() or path.suffix.lower() != ".apk":
            raise TapHerdError("Choose an existing local .apk file to install.")
        remote = f"/data/local/tmp/tapherd-{uuid4().hex}.apk"
        try:
            self.device.push_file(path, remote)
            if (
                self.device.shell("pm", "install", "-r", remote, timeout=120)
                != "Success"
            ):
                raise TapHerdError("Android did not confirm the APK installation.")
        except TapHerdError as error:
            raise TapHerdError(
                f"Could not install {path.name} on {self.device.serial}. "
                "Check that the APK is signed and compatible, then check for prompts on the device."
            ) from error
        finally:
            with suppress(TapHerdError):
                self.device.shell("rm", "-f", remote)

    def push_media(self, path: Path) -> str:
        kind, _ = mimetypes.guess_type(path.name)
        if not path.is_file() or not kind or not kind.startswith(("image/", "video/")):
            raise TapHerdError("Choose an existing local image or video to push.")

        token = uuid4().hex
        name = re.sub(r"[^A-Za-z0-9_-]+", "-", path.stem).strip("-_")[:64] or "media"
        destination = f"{_MEDIA_DIRECTORY}/{name}-{token}{path.suffix.lower()}"
        temporary = f"{_MEDIA_DIRECTORY}/.tapherd-{token}.part"
        self.device.shell("mkdir", "-p", _MEDIA_DIRECTORY)
        try:
            self.device.push_file(path, temporary)
            self.device.shell("mv", temporary, destination)
        except TapHerdError:
            with suppress(TapHerdError):
                self.device.shell("rm", "-f", temporary)
            raise

        # MediaStore can synchronously index the file on current Android versions.
        with suppress(TapHerdError):
            result = self.device.shell(
                "content",
                "call",
                "--uri",
                "content://media",
                "--method",
                "scan_file",
                "--arg",
                destination,
                timeout=30,
            )
            if "content://media/" in result:
                return destination

        try:
            result = self.device.shell(
                "am",
                "broadcast",
                "-a",
                "android.intent.action.MEDIA_SCANNER_SCAN_FILE",
                "-d",
                f"file://{destination}",
            )
            if "Broadcast completed:" not in result:
                raise TapHerdError("Android did not accept the media scan broadcast.")
        except TapHerdError as error:
            raise TapHerdError(
                f"Copied media to {destination} but could not request a scan. "
                "Find that file in Android's Files app before retrying."
            ) from error
        return destination

    def prepare_app(self, package: str) -> dict[str, list[str]]:
        """Get a posting app ready for uploads without permission prompts.

        Gives the app access to all photos and videos (not just selected ones)
        and turns off its camera and microphone so Android stops asking. Android
        closes the app if it is running when a permission is turned off.
        """
        if not _PACKAGE.fullmatch(package):
            raise TapHerdError(
                "Enter an Android package name such as com.google.android.youtube."
            )
        result: dict[str, list[str]] = {"allowed": [], "denied": [], "skipped": []}
        for permission in _POSTING_ALLOW:
            try:
                self.device.shell("pm", "grant", package, permission)
                result["allowed"].append(permission)
            except TapHerdError:
                # The app doesn't request this permission on this Android version.
                result["skipped"].append(permission)
        with suppress(TapHerdError):
            self.device.shell("pm", "revoke", package, _SELECTED_MEDIA_ONLY)
        for permission in _POSTING_DENY:
            try:
                self.device.shell("pm", "revoke", package, permission)
                self.device.shell(
                    "pm",
                    "set-permission-flags",
                    package,
                    permission,
                    "user-set",
                    "user-fixed",
                )
                result["denied"].append(permission)
            except TapHerdError:
                result["skipped"].append(permission)
        if not result["allowed"]:
            raise TapHerdError(
                f"{package} on {self.device.serial} did not accept photo and video "
                "access. Check that the app is installed, then try again."
            )
        return result

    def remove_media(self, device_path: str) -> None:
        """Delete a file that push_media copied, and drop it from the gallery."""
        name = device_path.removeprefix(f"{_MEDIA_DIRECTORY}/")
        if (
            name == device_path
            or not _MEDIA_NAME.fullmatch(name)
            or name.startswith(".")
        ):
            raise TapHerdError(
                f"Only files that push_media copied into {_MEDIA_DIRECTORY} can be "
                "removed. Pass the device_path that push_media returned."
            )
        self.device.shell("rm", "-f", device_path)
        # Ask MediaStore to rescan the now-missing path so the gallery forgets it.
        with suppress(TapHerdError):
            self.device.shell(
                "content",
                "call",
                "--uri",
                "content://media",
                "--method",
                "scan_file",
                "--arg",
                device_path,
                timeout=30,
            )
        if self.device.shell("ls", _MEDIA_DIRECTORY).split().count(name):
            raise TapHerdError(
                f"Android still lists {device_path}. Check the device's Files app."
            )
