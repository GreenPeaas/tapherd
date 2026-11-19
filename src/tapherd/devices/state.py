"""Persist the active device selection and labels on the local machine."""

import hashlib
import os
import sys
import time
from collections.abc import Iterator
from contextlib import ExitStack, contextmanager, suppress
from dataclasses import dataclass
from pathlib import Path
from tempfile import NamedTemporaryFile
from typing import Annotated, BinaryIO

from pydantic import BaseModel, Field, ValidationError

from tapherd.config import DEVICE_LIMIT, max_concurrency, state_directory
from tapherd.errors import TapHerdError

if sys.platform == "win32":
    import ctypes
    import msvcrt
    from ctypes import wintypes

    class _Overlapped(ctypes.Structure):
        _fields_ = [
            ("Internal", ctypes.c_void_p),
            ("InternalHigh", ctypes.c_void_p),
            ("Offset", wintypes.DWORD),
            ("OffsetHigh", wintypes.DWORD),
            ("hEvent", wintypes.HANDLE),
        ]

    _kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    _LockFileEx = _kernel32.LockFileEx
    _LockFileEx.argtypes = [
        wintypes.HANDLE,
        wintypes.DWORD,
        wintypes.DWORD,
        wintypes.DWORD,
        wintypes.DWORD,
        ctypes.POINTER(_Overlapped),
    ]
    _LockFileEx.restype = wintypes.BOOL
    _EXCLUSIVE, _FAIL_IMMEDIATELY = 0x2, 0x1
    _LOCK_BUSY = {33, 167}  # ERROR_LOCK_VIOLATION, ERROR_LOCK_FAILED

    def _lock_file(handle: BinaryIO, *, exclusive: bool, blocking: bool) -> None:
        # LockFileEx gives real shared and exclusive locks, like flock. Closing
        # the file releases the lock.
        flags = (_EXCLUSIVE if exclusive else 0) | (
            0 if blocking else _FAIL_IMMEDIATELY
        )
        overlapped = _Overlapped()
        os_handle = msvcrt.get_osfhandle(handle.fileno())
        if not _LockFileEx(os_handle, flags, 0, 1, 0, ctypes.byref(overlapped)):
            code = ctypes.get_last_error()
            if code in _LOCK_BUSY:
                raise BlockingIOError(
                    code, "The lock is held by another TapHerd process."
                )
            raise OSError(code, "Windows could not lock the TapHerd registry file.")

else:
    import fcntl

    def _lock_file(handle: BinaryIO, *, exclusive: bool, blocking: bool) -> None:
        mode = fcntl.LOCK_EX if exclusive else fcntl.LOCK_SH
        fcntl.flock(handle, mode if blocking else mode | fcntl.LOCK_NB)


class DeviceLabel(BaseModel):
    name: str
    group: str | None = None


class RegistryState(BaseModel):
    selected: Annotated[list[str], Field(max_length=DEVICE_LIMIT)] = Field(
        default_factory=list
    )
    labels: dict[str, DeviceLabel] = Field(default_factory=dict)
    remote_addresses: dict[str, str] = Field(default_factory=dict)
    last_pro_notice_at: float | None = None
    welcomed: bool = False


def serial_key(serial: str) -> str:
    return hashlib.sha256(serial.encode("utf-8")).hexdigest()


@dataclass(frozen=True, slots=True)
class StateStore:
    directory: Path

    @classmethod
    def from_environment(cls) -> "StateStore":
        return cls(state_directory())

    @property
    def path(self) -> Path:
        return self.directory / "devices.json"

    def read(self) -> RegistryState:
        try:
            data = self.path.read_bytes()
        except FileNotFoundError:
            return RegistryState()
        except OSError as error:
            raise TapHerdError(
                f"Cannot read {self.path}. Check its permissions."
            ) from error

        try:
            state = RegistryState.model_validate_json(data)
        except ValidationError as error:
            raise TapHerdError(
                f"Cannot read the device configuration in {self.path}. "
                "Restore a valid copy or move the file aside and run `tapherd devices`."
            ) from error
        state.selected = list(dict.fromkeys(state.selected))
        return state

    @contextmanager
    def _lockfile(self, name: str) -> Iterator[BinaryIO]:
        try:
            self.directory.mkdir(mode=0o700, parents=True, exist_ok=True)
            handle = (self.directory / name).open("a+b")
        except OSError as error:
            raise TapHerdError(
                f"Cannot open the device registry in {self.directory}. Check its permissions."
            ) from error
        with handle:
            yield handle

    def _acquire(
        self, handle: BinaryIO, *, exclusive: bool = True, blocking: bool = True
    ) -> None:
        try:
            _lock_file(handle, exclusive=exclusive, blocking=blocking)
        except BlockingIOError:
            raise
        except OSError as error:
            raise TapHerdError(
                f"Cannot lock the device registry in {self.directory}. "
                "Try again with a writable local state directory."
            ) from error

    @contextmanager
    def lock(self, *, shared: bool = False) -> Iterator[None]:
        # This file stays in place while devices.json is replaced atomically.
        with self._lockfile("devices.lock") as handle:
            self._acquire(handle, exclusive=not shared)
            yield

    @contextmanager
    def operation(self, serial: str) -> Iterator[None]:
        limit = max_concurrency()
        # Queued calls on one device wait before competing for a global slot.
        with self._lockfile(f"device-{serial_key(serial)}.lock") as device:
            self._acquire(device)
            with ExitStack() as stack:
                slots = [
                    stack.enter_context(self._lockfile(f"slot-{index}.lock"))
                    for index in range(limit)
                ]
                while True:
                    for slot in slots:
                        try:
                            self._acquire(slot, blocking=False)
                        except BlockingIOError:
                            continue
                        yield
                        return
                    time.sleep(0.025)

    @contextmanager
    def edit(self) -> Iterator[RegistryState]:
        with self.lock():
            state = self.read()
            previous = state.model_dump()
            yield state
            if state.model_dump() != previous:
                self._write(state)

    def _write(self, state: RegistryState) -> None:
        temporary_path = None
        try:
            with NamedTemporaryFile(dir=self.directory, delete=False) as handle:
                temporary_path = Path(handle.name)
                handle.write((state.model_dump_json(indent=2) + "\n").encode("utf-8"))
            os.replace(temporary_path, self.path)
        except OSError as error:
            raise TapHerdError(
                f"Cannot save {self.path}. Check disk space and permissions."
            ) from error
        finally:
            if temporary_path:
                with suppress(OSError):
                    temporary_path.unlink(missing_ok=True)
