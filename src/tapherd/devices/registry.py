"""Discover ADB devices and enforce TapHerd's active device selection."""

import re
import time
from collections.abc import Iterator
from contextlib import contextmanager, suppress
from dataclasses import dataclass
from ipaddress import IPv6Address
from typing import Literal

from tapherd.config import DEVICE_LIMIT, device_limit_message, max_concurrency
from tapherd.devices.action_log import record_action
from tapherd.devices.adb import DeviceBackend, DeviceConnection, DiscoveredDevice
from tapherd.devices.state import DeviceLabel, RegistryState, StateStore
from tapherd.errors import TapHerdError


@dataclass(frozen=True, slots=True)
class Device:
    serial: str
    status: str
    active: bool
    label: str | None
    group: str | None
    model: str | None
    android_version: str | None


@dataclass(frozen=True, slots=True)
class DeviceListing:
    devices: list[Device]
    selection_mode: Literal["auto", "explicit"]
    tier: Literal["free"] = "free"
    device_limit: int = DEVICE_LIMIT
    max_concurrency: int = DEVICE_LIMIT


@dataclass(frozen=True, slots=True)
class DeviceDetails:
    device: Device
    screen_size: tuple[int, int]
    foreground_app: str


def _active_serials(
    state: RegistryState, devices: dict[str, DiscoveredDevice]
) -> list[str]:
    if state.selected:
        return state.selected
    return sorted(
        serial for serial, info in devices.items() if info.status == "device"
    )[:DEVICE_LIMIT]


def _address(value: str) -> str:
    error = TapHerdError(
        "Enter an ADB address as host:port, such as 192.168.1.20:5555 or [::1]:5555."
    )
    match = re.fullmatch(r"([a-zA-Z0-9._-]+|\[[^\[\]]+\]):([0-9]{1,5})", value)
    if not match:
        raise error
    host, port = match.group(1), int(match.group(2))
    if host.startswith("["):
        try:
            IPv6Address(host[1:-1])
        except ValueError:
            raise error from None
    if not 1 <= port <= 65535:
        raise error
    return f"{host}:{port}"


@dataclass(frozen=True, slots=True)
class DeviceRegistry:
    backend: DeviceBackend
    store: StateStore

    def _discover(self) -> dict[str, DiscoveredDevice]:
        return {info.serial: info for info in self.backend.list_devices()}

    def list_devices(self) -> DeviceListing:
        limit = max_concurrency()
        with self.store.lock(shared=True):
            state = self.store.read()
            discovered = self._discover()
            active = _active_serials(state, discovered)
        devices = []
        for serial in sorted(discovered.keys() | set(active)):
            info = discovered.get(serial, DiscoveredDevice(serial, "disconnected"))
            label = state.labels.get(serial)
            android_version = None
            if serial in active and info.status == "device":
                # Recheck selection before reading a property from the device.
                with (
                    suppress(TapHerdError),
                    self.target(serial, recover=False) as device,
                ):
                    android_version = (
                        device.shell("getprop", "ro.build.version.release") or None
                    )
            devices.append(
                Device(
                    serial=serial,
                    status=info.status,
                    active=serial in active,
                    label=label.name if label else None,
                    group=label.group if label else None,
                    model=info.model,
                    android_version=android_version,
                )
            )
        return DeviceListing(
            devices, "explicit" if state.selected else "auto", max_concurrency=limit
        )

    def active_group(self, group: str) -> list[str]:
        with self.store.lock(shared=True):
            state = self.store.read()
            return [
                serial
                for serial in _active_serials(state, self._discover())
                if (label := state.labels.get(serial)) is not None
                and label.group == group
            ]

    @staticmethod
    def _require_ready(serial: str, discovered: dict[str, DiscoveredDevice]) -> None:
        info = discovered.get(serial)
        if info is None:
            raise TapHerdError(
                f"ADB cannot see {serial}. Start the emulator, attach the device, or run "
                "`tapherd connect <host:port>` for a remote device. Then run `tapherd devices`."
            )
        if info.status == "unauthorized":
            raise TapHerdError(
                f"ADB has not been authorized on {serial}. Unlock it and accept the USB "
                "debugging prompt, then run `tapherd devices`."
            )
        if info.status != "device":
            raise TapHerdError(
                f"{serial} is {info.status}. Wait for Android to boot or reconnect the device, "
                "then run `tapherd devices`."
            )

    def _recover(
        self, serial: str, state: RegistryState, discovered: dict[str, DiscoveredDevice]
    ) -> dict[str, DiscoveredDevice]:
        info = discovered.get(serial)
        if info is not None and info.status != "offline":
            return discovered
        active = _active_serials(state, discovered)
        eligible = serial in active if state.selected else len(active) < DEVICE_LIMIT
        if not eligible:
            return discovered
        address = state.remote_addresses.get(serial) if info is None else None
        if info is None and address is None:
            return discovered

        with suppress(TapHerdError):
            self.backend.reconnect(serial, address)
        # Only recovery is retried here. The requested device action has not run yet.
        for attempt in range(7):
            if attempt:
                time.sleep(0.25)
            discovered = self._discover()
            info = discovered.get(serial)
            if info is not None and info.status != "offline":
                break
        return discovered

    @contextmanager
    def target(
        self, serial: str, *, action: str | None = None, recover: bool = True
    ) -> Iterator[DeviceConnection]:
        with self.store.operation(serial), self.store.lock(shared=True):
            state = self.store.read()
            discovered = self._discover()
            if recover:
                discovered = self._recover(serial, state, discovered)
            self._require_ready(serial, discovered)
            active = _active_serials(state, discovered)
            if serial not in active:
                if len(active) >= DEVICE_LIMIT:
                    raise TapHerdError(
                        f"{serial} is inactive. {device_limit_message()}"
                    )
                raise TapHerdError(
                    f"{serial} is inactive. Run `tapherd use {serial}` first."
                )
            with record_action(self.store.directory, serial, action):
                yield self.backend.device(serial)

    def device_info(self, serial: str) -> DeviceDetails:
        with self.target(serial, action="device_info") as connection:
            label = self.store.read().labels.get(serial)
            device = Device(
                serial=serial,
                status="device",
                active=True,
                label=label.name if label else None,
                group=label.group if label else None,
                model=connection.shell("getprop", "ro.product.model") or None,
                android_version=connection.shell("getprop", "ro.build.version.release")
                or None,
            )
            return DeviceDetails(
                device, connection.screen_size(), connection.foreground_app()
            )

    def use(self, serial: str) -> None:
        with self.store.edit() as state:
            if serial in state.selected:
                return
            self._require_ready(serial, self._discover())
            if len(state.selected) >= DEVICE_LIMIT:
                raise TapHerdError(device_limit_message())
            state.selected.append(serial)

    def unuse(self, serial: str) -> bool:
        with self.store.edit() as state:
            if serial not in state.selected:
                raise TapHerdError(
                    f"{serial} is not explicitly selected. Run `tapherd devices` to check "
                    "selection mode, or use `tapherd use <serial>` to choose devices explicitly."
                )
            state.selected.remove(serial)
            return bool(state.selected)

    def label(self, serial: str, name: str, group: str | None = None) -> None:
        name = name.strip()
        if not name or not name.isprintable() or (group and not group.isprintable()):
            raise TapHerdError(
                "Choose a non-empty, printable label and a printable group."
            )
        with self.store.edit() as state:
            previous = state.labels.get(serial)
            if (
                not previous
                and serial not in state.selected
                and serial not in self._discover()
            ):
                raise TapHerdError(
                    f"ADB cannot see {serial}. Run `tapherd devices` for valid serials."
                )
            group_name = previous.group if previous else None
            if group is not None:
                group_name = group.strip() or None
            state.labels[serial] = DeviceLabel(name=name, group=group_name)

    def connect(self, value: str) -> tuple[str, str | None]:
        address = _address(value)
        with self.store.edit() as state:
            result = self.backend.connect(address)
            if not result.lower().startswith(
                ("connected to ", "already connected to ")
            ):
                raise TapHerdError(
                    f"Could not connect to {address}. ADB reported {result or 'no response'}. "
                    "Check the address, port, and device's remote ADB settings, then try again."
                )
            discovered = self._discover()
            active = _active_serials(state, discovered)
            connected_serial = result.rsplit(maxsplit=1)[-1]
            state.remote_addresses[connected_serial] = address
            if connected_serial in active:
                return result, None
            if len(active) >= DEVICE_LIMIT:
                return result, device_limit_message()
            return (
                result,
                "Run `tapherd devices` to see its status and choose the active set.",
            )

    def disconnect(self, value: str) -> str:
        address = _address(value)
        with self.store.edit() as state:
            managed = [
                serial
                for serial, endpoint in state.remote_addresses.items()
                if address in (serial, endpoint)
            ]
            if managed and set(managed).isdisjoint(self._discover()):
                result = f"{address} is already disconnected. TapHerd will stop reconnecting it."
            else:
                result = self.backend.disconnect(address)
                if not result.lower().startswith("disconnected "):
                    raise TapHerdError(
                        f"Could not disconnect {address}. Run `tapherd devices` and check the address."
                    )
            for serial in managed:
                del state.remote_addresses[serial]
            return result
