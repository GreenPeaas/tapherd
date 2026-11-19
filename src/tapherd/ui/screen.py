"""Read the Android accessibility hierarchy and capture PNG screenshots."""

import io
import re
from collections.abc import Iterator
from contextlib import suppress
from dataclasses import dataclass
from itertools import islice
from uuid import uuid4
from xml.etree import ElementTree

from PIL import Image

from tapherd.devices.adb import DeviceConnection
from tapherd.errors import TapHerdError

MAX_UI_ELEMENTS = 150
DEFAULT_SCREENSHOT_WIDTH = 720
_BOUNDS = re.compile(r"\[(\d+),(\d+)\]\[(\d+),(\d+)\]")


@dataclass(frozen=True, slots=True)
class UIElement:
    text: str
    resource_id: str
    content_desc: str
    class_name: str
    bounds: tuple[int, int, int, int]
    center: tuple[int, int]
    clickable: bool
    scrollable: bool

    def to_dict(self) -> dict[str, str | tuple[int, ...] | bool]:
        return {
            "text": self.text,
            "resource_id": self.resource_id,
            "content_desc": self.content_desc,
            "class": self.class_name,
            "bounds": self.bounds,
            "center": self.center,
            "clickable": self.clickable,
            "scrollable": self.scrollable,
        }


def _elements(root: ElementTree.Element) -> Iterator[UIElement]:
    for node in root.iter("node"):
        text = node.get("text", "")
        resource_id = node.get("resource-id", "")
        content_desc = node.get("content-desc", "")
        clickable = node.get("clickable") == "true"
        scrollable = node.get("scrollable") == "true"
        if not (text or resource_id or content_desc or clickable or scrollable):
            continue
        bounds = _BOUNDS.fullmatch(node.get("bounds", ""))
        if not bounds:
            continue
        left, top, right, bottom = map(int, bounds.groups())
        if left >= right or top >= bottom:
            continue
        yield UIElement(
            text=text,
            resource_id=resource_id,
            content_desc=content_desc,
            class_name=node.get("class", ""),
            bounds=(left, top, right, bottom),
            center=((left + right) // 2, (top + bottom) // 2),
            clickable=clickable,
            scrollable=scrollable,
        )


def read_screen(
    device: DeviceConnection,
    limit: int | None = MAX_UI_ELEMENTS,
    *,
    dump_timeout: float = 20,
) -> list[UIElement]:
    remote = f"/data/local/tmp/tapherd-ui-{uuid4().hex}.xml"
    try:
        output = device.shell("uiautomator", "dump", remote, timeout=dump_timeout)
        if "dumped to:" not in output:
            raise TapHerdError("Android did not return a UI hierarchy.")
        root = ElementTree.fromstring(device.read_file(remote))
        if root.tag != "hierarchy":
            raise TapHerdError("Android did not return a UI hierarchy.")
        return list(islice(_elements(root), limit))
    except (TapHerdError, ElementTree.ParseError) as error:
        raise TapHerdError(
            f"Could not read the UI tree on {device.serial}. "
            "Unlock the device, wait for its screen to settle, and run `tapherd inspect` again."
        ) from error
    finally:
        with suppress(TapHerdError):
            device.shell("rm", "-f", remote)


def screenshot(
    device: DeviceConnection, max_width: int = DEFAULT_SCREENSHOT_WIDTH
) -> bytes:
    if max_width < 1:
        raise TapHerdError("Choose a positive screenshot width in pixels.")
    with device.screenshot() as image:
        if image.width > max_width:
            image.thumbnail((max_width, image.height), Image.Resampling.LANCZOS)
        output = io.BytesIO()
        image.save(output, format="PNG")
        return output.getvalue()
