"""Adapt adbutils to the operations TapHerd needs from the local ADB server."""

import platform
import shutil
import subprocess
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from adbutils import AdbClient, AdbDevice, AdbError
from PIL import Image

from tapherd.errors import TapHerdError


def install_adb_hint() -> str:
    """Tell the operator how to install ADB on this operating system."""
    system = platform.system()
    if system == "Windows":
        return (
            "Install Android Platform-Tools with "
            "`winget install --id Google.PlatformTools`, or add "
            "%LOCALAPPDATA%\\Android\\Sdk\\platform-tools to PATH. "
            "Then open a new terminal. See docs/SETUP_WINDOWS.md."
        )
    if system == "Linux":
        return (
            "Install Android Platform-Tools with your package manager, for example "
            "`sudo apt install adb` or `sudo dnf install android-tools`, or add the "
            "SDK's platform-tools folder to PATH. See docs/SETUP_LINUX.md."
        )
    return (
        "Install Android Platform-Tools with "
        "`brew install --cask android-platform-tools`, or add the Android SDK's "
        "platform-tools folder to PATH. See docs/SETUP_MAC.md."
    )


@dataclass(frozen=True, slots=True)
class DiscoveredDevice:
    serial: str
    status: str
    model: str | None = None


class DeviceConnection(Protocol):
    @property
    def serial(self) -> str: ...

    def shell(self, *arguments: str, timeout: float = 15) -> str: ...

    def screenshot(self) -> Image.Image: ...

    def screen_size(self) -> tuple[int, int]: ...

    def foreground_app(self) -> str: ...

    def read_file(self, path: str) -> bytes: ...

    def push_file(self, source: Path, destination: str) -> None: ...


class DeviceBackend(Protocol):
    def version(self) -> str: ...

    def list_devices(self) -> list[DiscoveredDevice]: ...

    def connect(self, address: str) -> str: ...

    def disconnect(self, address: str) -> str: ...

    def reconnect(self, serial: str, address: str | None = None) -> None: ...

    def device(self, serial: str) -> DeviceConnection: ...


class AdbBackend:
    def __init__(self) -> None:
        self.client = AdbClient(host="127.0.0.1", port=5037, socket_timeout=15)

    @staticmethod
    def _executable() -> str:
        executable = shutil.which("adb")
        if not executable:
            raise TapHerdError(f"ADB is missing. {install_adb_hint()}")
        return executable

    def version(self) -> str:
        executable = self._executable()
        try:
            result = subprocess.run(
                [executable, "version"],
                capture_output=True,
                text=True,
                check=True,
                timeout=5,
            )
        except (OSError, subprocess.SubprocessError) as error:
            raise TapHerdError(
                f"Could not run `adb version`. {install_adb_hint()}"
            ) from error
        return result.stdout.splitlines()[0] if result.stdout.strip() else executable

    @contextmanager
    def _server_request(self) -> Iterator[None]:
        self._executable()
        try:
            yield
        except (AdbError, OSError, subprocess.SubprocessError) as error:
            raise TapHerdError(
                "The local ADB request failed. Run `adb start-server` and "
                "`adb devices -l`, then try again."
            ) from error

    def list_devices(self) -> list[DiscoveredDevice]:
        with self._server_request():
            return [
                DiscoveredDevice(info.serial, info.state, info.tags.get("model"))
                for info in self.client.list(extended=True)
            ]

    def connect(self, address: str) -> str:
        with self._server_request():
            return self.client.connect(address).strip()

    def disconnect(self, address: str) -> str:
        with self._server_request():
            return self.client.disconnect(address, raise_error=True).strip()

    def reconnect(self, serial: str, address: str | None = None) -> None:
        with self._server_request():
            if address is not None:
                self.client.connect(address, timeout=4)
                return
            subprocess.run(
                [
                    self._executable(),
                    "-H",
                    self.client.host,
                    "-P",
                    str(self.client.port),
                    "-s",
                    serial,
                    "reconnect",
                ],
                capture_output=True,
                check=True,
                timeout=5,
            )

    def device(self, serial: str) -> DeviceConnection:
        return _AdbConnection(self.client.device(serial=serial))


@dataclass(frozen=True, slots=True)
class _AdbConnection:
    device: AdbDevice

    @property
    def serial(self) -> str:
        return self.device.serial

    @contextmanager
    def _request(self, operation: str) -> Iterator[None]:
        try:
            yield
        except (
            AdbError,
            OSError,
            subprocess.SubprocessError,
            Image.DecompressionBombError,
        ) as error:
            raise TapHerdError(
                f"Could not {operation} on {self.serial}. "
                "Run `tapherd devices`, check that the device is online, and try again."
            ) from error

    def shell(self, *arguments: str, timeout: float = 15) -> str:
        operation = f"run Android's `{arguments[0]}` command"
        with self._request(operation):
            result = self.device.shell2(arguments, timeout=timeout)
        if result.returncode:
            raise TapHerdError(
                f"Android's `{arguments[0]}` command failed on {self.serial} "
                f"(exit {result.returncode}). Check the device screen and try again."
            )
        return result.output.strip()

    def screenshot(self) -> Image.Image:
        with self._request("capture a screenshot"):
            image = self.device.screenshot(error_ok=False)
            image.load()
            return image

    def screen_size(self) -> tuple[int, int]:
        with self._request("read the screen size"):
            size = self.device.window_size()
            return size.width, size.height

    def foreground_app(self) -> str:
        with self._request("identify the foreground app"):
            return self.device.app_current().package

    def read_file(self, path: str) -> bytes:
        with self._request("read the device file"):
            return self.device.sync.read_bytes(path)

    def push_file(self, source: Path, destination: str) -> None:
        try:
            with source.open("rb") as handle:
                self.device.sync.push(handle, destination, mode=0o644, check=True)
            return
        except (AdbError, OSError):
            # The Python sync client intermittently gets FAIL from current
            # emulators when writing to shared storage. The adb tool's own
            # push is reliable there, so retry once with it.
            pass
        executable = shutil.which("adb")
        if not executable:
            raise TapHerdError(f"ADB is missing. {install_adb_hint()}")
        with self._request("transfer the file"):
            subprocess.run(
                [executable, "-s", self.serial, "push", str(source), destination],
                check=True,
                capture_output=True,
                timeout=300,
            )
