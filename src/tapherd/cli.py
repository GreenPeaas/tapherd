"""The TapHerd command-line entry point."""

import asyncio
import json
import platform
import sys
import webbrowser
from collections.abc import Iterator
from contextlib import contextmanager, suppress
from dataclasses import asdict
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path
from typing import Annotated
from uuid import uuid4

import typer

from tapherd.actions.android import AndroidActions, Direction, Key, TapSelector
from tapherd.config import waitlist_url
from tapherd.devices.action_log import recent_actions
from tapherd.devices.adb import AdbBackend, DeviceConnection
from tapherd.devices.registry import DeviceListing, DeviceRegistry
from tapherd.devices.state import StateStore
from tapherd.errors import TapHerdError
from tapherd.mcp_config import (
    MCPClient,
    configuration_location,
    configuration_snippet,
    temporary_install_warning,
)
from tapherd.recipes.runner import RecipeService
from tapherd.tease import pro_notice
from tapherd.ui.screen import DEFAULT_SCREENSHOT_WIDTH, read_screen, screenshot

app = typer.Typer(help="Herd your phones with AI.", no_args_is_help=True)
config_app = typer.Typer(no_args_is_help=True)
app.add_typer(config_app, name="config", help="Print client configuration.")


DOCS_URL = "https://github.com/asuopys/tapherd#readme"


def _version() -> str:
    try:
        return version("tapherd")
    except PackageNotFoundError:
        return "unknown"


def _utf8_console() -> None:
    """Keep labels and symbols printable when Windows redirects output."""
    for stream in (sys.stdout, sys.stderr):
        encoding = (getattr(stream, "encoding", None) or "").lower().replace("-", "")
        if encoding != "utf8" and hasattr(stream, "reconfigure"):
            with suppress(ValueError, OSError):
                stream.reconfigure(encoding="utf-8", errors="replace")


def _welcome_once(command: str | None) -> None:
    """Point first-time users to the docs once, in interactive terminals only."""
    if command in (None, "mcp") or not sys.stderr.isatty():
        return
    try:
        with StateStore.from_environment().edit() as state:
            if state.welcomed:
                return
            state.welcomed = True
    except TapHerdError:
        return
    typer.echo(
        f"Welcome to TapHerd {_version()}. Run `tapherd doctor` to check your setup. "
        f"Docs: {DOCS_URL}",
        err=True,
    )


def _print_version(value: bool) -> None:
    if value:
        typer.echo(f"tapherd {_version()}")
        raise typer.Exit()


@app.callback()
def main(
    ctx: typer.Context,
    show_version: Annotated[
        bool,
        typer.Option(
            "--version",
            callback=_print_version,
            is_eager=True,
            help="Show the TapHerd version and exit.",
        ),
    ] = False,
) -> None:
    """Manage TapHerd from the command line."""
    _utf8_console()
    _welcome_once(ctx.invoked_subcommand)


@app.command("mcp")
def mcp_command(
    http: Annotated[
        bool, typer.Option("--http", help="Serve Streamable HTTP on loopback.")
    ] = False,
) -> None:
    """Start the local MCP server over stdio or loopback HTTP."""
    from tapherd.mcp_server import run_server

    run_server(http=http)


@config_app.command("mcp")
def config_mcp(
    client: Annotated[MCPClient, typer.Option(help="MCP client to configure.")],
) -> None:
    """Print the local stdio configuration snippet for your MCP client."""
    typer.echo(configuration_snippet(client))
    # The location goes to stderr so `> file` captures only the snippet.
    typer.echo(configuration_location(client), err=True)
    if warning := temporary_install_warning():
        typer.echo(warning, err=True)


@app.command("recipes")
def recipes_command() -> None:
    """Print the available recipes and their parameters as JSON."""
    with _registry() as registry:
        recipes = RecipeService(registry).list_recipes()
    typer.echo(json.dumps(recipes, ensure_ascii=False, indent=2))


@app.command()
def pro() -> None:
    """Open the TapHerd Pro waitlist in your browser."""
    url = waitlist_url()
    typer.echo(url)
    try:
        opened = webbrowser.open(url)
    except (OSError, webbrowser.Error):
        opened = False
    if not opened:
        typer.echo("Open the printed address in your browser.", err=True)
        raise typer.Exit(1)


def _show_pro_notice(store: StateStore) -> None:
    if notice := pro_notice(store):
        typer.echo(notice, err=True)


@app.command("run")
def run_command(
    recipe: str,
    devices: Annotated[
        str, typer.Option("--devices", help="Comma-separated active device serials.")
    ],
    param: Annotated[
        list[str] | None,
        typer.Option("--param", help="Repeat key=value for recipe parameters."),
    ] = None,
) -> None:
    """Run a recipe on active devices and print a JSON result per device."""
    with _registry() as registry:
        params: dict[str, str] = {}
        for entry in param or []:
            key, separator, value = entry.partition("=")
            if not key or not separator:
                raise TapHerdError("Use --param key=value for each recipe parameter.")
            if key in params:
                raise TapHerdError(f"Provide recipe parameter {key} only once.")
            params[key] = value
        result = asyncio.run(
            RecipeService(registry).run(
                recipe, [serial.strip() for serial in devices.split(",")], params
            )
        )
    typer.echo(json.dumps(asdict(result), ensure_ascii=False, indent=2))
    _show_pro_notice(registry.store)
    if not result.completed:
        raise typer.Exit(1)


@contextmanager
def _registry() -> Iterator[DeviceRegistry]:
    try:
        yield DeviceRegistry(AdbBackend(), StateStore.from_environment())
    except TapHerdError as error:
        typer.echo(str(error), err=True)
        raise typer.Exit(1) from None


@contextmanager
def _target(serial: str, action: str) -> Iterator[DeviceConnection]:
    with _registry() as registry, registry.target(serial, action=action) as device:
        yield device


@app.command()
def doctor() -> None:
    """Check Python, the local ADB server, and active devices."""
    typer.echo(f"Python {platform.python_version()}")
    with _registry() as registry:
        typer.echo(registry.backend.version())
        listing = registry.list_devices()
        ready = [
            device.serial
            for device in listing.devices
            if device.active and device.status == "device"
        ]
        if not ready:
            raise TapHerdError(_no_device_hint(listing))
    typer.echo(f"Active and online: {', '.join(ready)}")
    typer.echo(
        "Ready. Next, connect your AI: tapherd config mcp --client claude-code "
        "(or codex, claude-desktop, cursor)."
    )


def _no_device_hint(listing: DeviceListing) -> str:
    statuses = {device.status for device in listing.devices}
    if "unauthorized" in statuses:
        return (
            "A device is connected but not authorized. Unlock the phone, accept the "
            "“Allow USB debugging” prompt, then run `tapherd doctor` again."
        )
    if "offline" in statuses:
        return (
            "A device is offline. Run `adb reconnect offline` or restart the emulator, "
            "then run `tapherd doctor` again."
        )
    system = platform.system()
    if system == "Windows":
        extra = " For a USB phone, install its USB driver (see docs/SETUP_WINDOWS.md)."
    elif system == "Linux":
        extra = " For a USB phone, add a udev rule (see docs/SETUP_LINUX.md)."
    else:
        extra = ""
    return (
        "No active Android device is online. Start an emulator, or connect a phone "
        f"with USB debugging on, then run `tapherd devices`.{extra}"
    )


@app.command()
def devices(
    json_output: Annotated[bool, typer.Option("--json", help="Print JSON.")] = False,
) -> None:
    """List ADB devices and identify those TapHerd can use."""
    with _registry() as registry:
        listing = registry.list_devices()
    if json_output:
        typer.echo(json.dumps(asdict(listing), ensure_ascii=False))
    else:
        _print_device_listing(listing)
    _show_pro_notice(registry.store)


def _print_device_listing(listing: DeviceListing) -> None:
    typer.echo(
        f"TapHerd Free supports up to {listing.device_limit} active devices and "
        f"{listing.max_concurrency} concurrent operations."
    )
    if listing.selection_mode == "auto":
        typer.echo(
            "Automatic selection uses the first "
            f"{listing.device_limit} online devices in serial order."
        )
    else:
        typer.echo(
            "Explicit selection is on. Use `tapherd use` and `tapherd unuse` to change it."
        )
    if not listing.devices:
        typer.echo(
            "No ADB devices found. Start an emulator or attach a device and try again."
        )
        return

    for device in listing.devices:
        selection = "active" if device.active else "inactive"
        details = " | ".join(
            value
            for value in (
                device.label,
                f"group {device.group}" if device.group else None,
                device.model,
                f"Android {device.android_version}" if device.android_version else None,
            )
            if value
        )
        line = f"{device.serial}  {device.status}  {selection}"
        typer.echo(f"{line}  {details}" if details else line)


@app.command()
def connect(address: str) -> None:
    """Connect a remote ADB device at HOST:PORT."""
    with _registry() as registry:
        result, notice = registry.connect(address)
    typer.echo(result)
    if notice:
        typer.echo(notice)


@app.command()
def disconnect(address: str) -> None:
    """Disconnect one remote ADB address."""
    with _registry() as registry:
        typer.echo(registry.disconnect(address))


@app.command()
def use(serial: str) -> None:
    """Add an online device to the explicit active set."""
    with _registry() as registry:
        registry.use(serial)
    typer.echo(f"{serial} is explicitly selected.")


@app.command()
def unuse(serial: str) -> None:
    """Remove an explicit selection without disconnecting the device."""
    with _registry() as registry:
        explicit = registry.unuse(serial)
    typer.echo(f"Removed the explicit selection for {serial}.")
    if not explicit:
        typer.echo("Automatic selection is now on.")


@app.command()
def label(
    serial: str,
    name: str,
    group: Annotated[
        str | None, typer.Option(help="Group name. Pass an empty string to clear it.")
    ] = None,
) -> None:
    """Store a local label and optional group for a device."""
    with _registry() as registry:
        registry.label(serial, name, group)
    typer.echo(f"Saved the label for {serial}.")


@app.command()
def inspect(serial: str) -> None:
    """Print a compact JSON list of the screen's accessibility elements."""
    with _target(serial, "read_screen") as device:
        elements = [element.to_dict() for element in read_screen(device)]
    typer.echo(json.dumps(elements, ensure_ascii=False, separators=(",", ":")))


@app.command()
def logs(serial: str, limit: Annotated[int, typer.Option(min=1)] = 20) -> None:
    """Print recent local action records for one device."""
    with _registry() as registry:
        for line in recent_actions(registry.store.directory, serial, limit):
            typer.echo(line, nl=False)


@app.command()
def tap(
    serial: str,
    x: Annotated[int | None, typer.Argument()] = None,
    y: Annotated[int | None, typer.Argument()] = None,
    *,
    text: Annotated[str | None, typer.Option(help="Exact visible text.")] = None,
    resource_id: Annotated[
        str | None, typer.Option(help="Exact Android resource ID.")
    ] = None,
    content_desc: Annotated[
        str | None, typer.Option(help="Exact accessibility description.")
    ] = None,
) -> None:
    """Tap coordinates or one exact accessibility selector."""
    selector = TapSelector(text, resource_id, content_desc)
    with _target(serial, "tap") as device:
        chosen = (
            selector
            if any(value is not None for value in (text, resource_id, content_desc))
            else None
        )
        AndroidActions(device).tap(x, y, selector=chosen)


@app.command()
def swipe(
    serial: str,
    x1: Annotated[int | None, typer.Argument()] = None,
    y1: Annotated[int | None, typer.Argument()] = None,
    x2: Annotated[int | None, typer.Argument()] = None,
    y2: Annotated[int | None, typer.Argument()] = None,
    *,
    direction: Annotated[Direction | None, typer.Option()] = None,
    duration_ms: Annotated[
        int, typer.Option(min=1, help="Gesture duration in milliseconds.")
    ] = 300,
) -> None:
    """Swipe in a direction or between two coordinate pairs."""
    with _target(serial, "swipe") as device:
        AndroidActions(device).swipe(
            (x1, y1, x2, y2), direction=direction, duration_ms=duration_ms
        )


@app.command()
def type_text(serial: str, text: str) -> None:
    """Type into the focused Android field."""
    with _target(serial, "type_text") as device:
        AndroidActions(device).type_text(text)


@app.command()
def press_key(serial: str, key: Key) -> None:
    """Send back, home, enter, recents, or delete."""
    with _target(serial, "press_key") as device:
        AndroidActions(device).press_key(key)


@app.command()
def open_app(serial: str, package: str) -> None:
    """Open an installed Android app by package name."""
    with _target(serial, "open_app") as device:
        AndroidActions(device).open_app(package)
    typer.echo(f"Opened {package} on {serial}.")


@app.command("screenshot")
def screenshot_command(
    serial: str,
    out: Annotated[Path | None, typer.Option(help="Output PNG path.")] = None,
    max_width: Annotated[
        int, typer.Option(min=1, help="Maximum PNG width in pixels.")
    ] = DEFAULT_SCREENSHOT_WIDTH,
) -> None:
    """Save a PNG screenshot to the local machine."""
    output = out or Path(f"tapherd-{uuid4().hex[:8]}.png")
    with _target(serial, "screenshot") as device:
        png = screenshot(device, max_width)
        created = False
        try:
            with output.open("xb") as handle:
                created = True
                handle.write(png)
        except FileExistsError as error:
            raise TapHerdError(
                f"{output} already exists. Choose a new path with --out."
            ) from error
        except OSError as error:
            if created:
                with suppress(OSError):
                    output.unlink()
            raise TapHerdError(
                f"Could not save {output}. Choose a writable path with --out and check disk space."
            ) from error
    typer.echo(str(output))


@app.command()
def install_apk(serial: str, path: Path) -> None:
    """Install or update an app from a local APK file."""
    with _target(serial, "install_apk") as device:
        AndroidActions(device).install_apk(path)
    typer.echo(f"Installed {path.name} on {serial}.")


@app.command()
def push_media(serial: str, path: Path) -> None:
    """Copy a local video or image to the device and print its unique path."""
    with _target(serial, "push_media") as device:
        typer.echo(AndroidActions(device).push_media(path))


@app.command()
def prepare_app(serial: str, package: str) -> None:
    """Allow all photos and videos and turn off camera and mic for a posting app."""
    with _target(serial, "prepare_app") as device:
        result = AndroidActions(device).prepare_app(package)
    typer.echo(
        f"Prepared {package} on {serial}: all photos and videos allowed, "
        f"{len(result['denied'])} camera and microphone permissions turned off."
    )


@app.command()
def remove_media(serial: str, device_path: str) -> None:
    """Delete media that push-media copied to the device."""
    with _target(serial, "remove_media") as device:
        AndroidActions(device).remove_media(device_path)
    typer.echo(f"Removed {device_path} from {serial}.")
