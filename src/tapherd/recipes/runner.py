"""Execute validated steps with one device lease and no action replay."""

import asyncio
import os
import re
import time
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from pathlib import Path, PurePosixPath
from typing import Literal
from uuid import uuid4

from tapherd.actions.android import AndroidActions
from tapherd.config import DEVICE_LIMIT, device_limit_message
from tapherd.devices.action_log import record_action
from tapherd.devices.adb import DeviceConnection
from tapherd.devices.registry import DeviceRegistry
from tapherd.devices.state import serial_key
from tapherd.errors import TapHerdError
from tapherd.recipes.catalog import RecipeCatalog
from tapherd.recipes.schema import (
    AssertStep,
    ChooseMediaStep,
    OpenStep,
    PrepareStep,
    PushStep,
    Recipe,
    ScreenshotStep,
    Selector,
    Step,
    SwipeStep,
    TapStep,
    TypeStep,
    WaitStep,
    prepare,
)
from tapherd.ui import screen
from tapherd.ui.screen import UIElement

PublishState = Literal["not_attempted", "unknown", "confirmed"]
UITree = list[dict[str, str | tuple[int, ...] | bool]]


@dataclass(frozen=True, slots=True)
class DeviceRun:
    serial: str
    status: Literal["completed", "needs_ai"]
    failed_step: str | None = None
    reason: str | None = None
    screenshot_path: str | None = None
    ui_tree: UITree | None = None
    ui_tree_source: Literal["current", "last_observed", "unavailable"] | None = None
    media_path: str | None = None
    publish_state: PublishState = "not_attempted"


@dataclass(frozen=True, slots=True)
class RecipeRun:
    recipe: str
    recipe_status: Literal["verified", "unverified"]
    run_id: str
    results: list[DeviceRun]

    @property
    def completed(self) -> bool:
        return all(result.status == "completed" for result in self.results)


def _matches(element: UIElement, selector: Selector) -> bool:
    if selector.text is not None:
        return selector.text == element.text
    if selector.text_contains is not None:
        return selector.text_contains in element.text
    if selector.resource_id is not None:
        return selector.resource_id == element.resource_id
    if selector.content_desc is not None:
        return selector.content_desc == element.content_desc
    assert selector.regex is not None
    return bool(
        re.search(selector.regex, element.text)
        or re.search(selector.regex, element.content_desc)
    )


def _unique(
    elements: Sequence[UIElement], matcher: Callable[[UIElement], bool]
) -> tuple[int, int] | None:
    locations = {element.center for element in elements if matcher(element)}
    if len(locations) > 1:
        raise TapHerdError(
            "Multiple locations match. Inspect the screen and choose a unique target."
        )
    return next(iter(locations), None)


def _find(
    elements: Sequence[UIElement], selectors: Sequence[Selector]
) -> tuple[int, int] | None:
    for selector in selectors:
        found = _unique(
            elements, lambda element, selector=selector: _matches(element, selector)
        )
        if found is not None:
            return found
    return None


@dataclass(slots=True)
class _DeviceRecipe:
    device: DeviceConnection
    directory: Path
    recipe: Recipe
    ui: list[UIElement] = field(default_factory=list)
    media_path: str | None = None
    publish_state: PublishState = "not_attempted"
    failed_step: str = "device"
    last_screenshot: str | None = None

    def _read(self, timeout: float = 20) -> list[UIElement]:
        self.ui = screen.read_screen(self.device, limit=None, dump_timeout=timeout)
        return self.ui

    def _wait(
        self,
        find: Callable[[Sequence[UIElement]], tuple[int, int] | None],
        timeout: float,
        reason: str,
    ) -> tuple[int, int]:
        deadline = time.monotonic() + timeout
        while (remaining := deadline - time.monotonic()) > 0:
            elements = self._read(timeout=min(20, remaining))
            found = find(elements)
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                break
            if found is not None:
                return found
            time.sleep(min(0.25, remaining))
        raise TapHerdError(reason)

    def _save_screen(self, filename: str) -> str:
        path = self.directory / filename
        png = screen.screenshot(self.device)
        try:
            path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
            fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
            with os.fdopen(fd, "wb") as handle:
                handle.write(png)
        except OSError as error:
            raise TapHerdError(
                "Could not save the recipe screenshot. Check the local registry directory."
            ) from error
        self.last_screenshot = str(path)
        return self.last_screenshot

    def _tap(self, step: TapStep, actions: AndroidActions) -> None:
        if step.publish and self.device.foreground_app() != self.recipe.app_package:
            raise TapHerdError(
                "Open the recipe's app before verifying the publish screen."
            )
        elements = self._read()
        for guard in step.require:
            if _find(elements, (guard,)) is None:
                raise TapHerdError(
                    "A required on-screen check did not match. Inspect the screen before proceeding."
                )
        point = _find(elements, step.selectors)
        if point is None:
            raise TapHerdError(
                "No tap selector matched. Inspect the screen and check the recipe selectors."
            )
        if step.publish:
            self.publish_state = "unknown"
        actions.tap(*point)

    def _choose_media(self, step: ChooseMediaStep, actions: AndroidActions) -> None:
        if self.media_path is None:
            raise TapHerdError("Push the media file before selecting it in the picker.")
        filename = PurePosixPath(self.media_path).name
        point = self._wait(
            lambda elements: _unique(
                elements, lambda node: filename in (node.text, node.content_desc)
            ),
            step.timeout,
            f"The picker did not display the exact filename {filename}. Find that file in the picker.",
        )
        actions.tap(*point)

    def _step(self, step: Step, actions: AndroidActions) -> None:
        match step:
            case PrepareStep():
                actions.prepare_app(self.recipe.app_package)
            case OpenStep():
                actions.open_app(self.recipe.app_package)
            case WaitStep():
                self._wait(
                    lambda elements: _find(elements, step.selectors),
                    step.timeout,
                    "The expected screen did not appear. Inspect the device and check the recipe selectors.",
                )
            case AssertStep():
                if _find(self._read(), step.selectors) is None:
                    raise TapHerdError(
                        "The expected screen element is missing. Inspect the device."
                    )
            case TapStep():
                self._tap(step, actions)
            case TypeStep():
                actions.type_text(step.text)
            case PushStep():
                self.media_path = actions.push_media(Path(step.path).expanduser())
            case ChooseMediaStep():
                self._choose_media(step, actions)
            case SwipeStep():
                actions.swipe(
                    step.coordinates,
                    direction=step.direction,
                    duration_ms=step.duration_ms,
                )
            case ScreenshotStep():
                self._save_screen(f"step-{step.id}.png")

    def run(self) -> DeviceRun:
        actions = AndroidActions(self.device)
        for step in self.recipe.steps:
            self.failed_step = step.id
            self._step(step, actions)
            if self.publish_state == "unknown" and isinstance(
                step, (WaitStep, AssertStep)
            ):
                self.publish_state = "confirmed"
        if not isinstance(self.recipe.steps[-1], ScreenshotStep):
            self.failed_step = "final_screenshot"
            self._save_screen("final.png")
        return DeviceRun(
            self.device.serial,
            "completed",
            screenshot_path=self.last_screenshot,
            media_path=self.media_path,
            publish_state=self.publish_state,
        )

    def recovery(self, error: TapHerdError) -> DeviceRun:
        reason = str(error)
        if self.publish_state != "not_attempted":
            reason += " The publish tap may have taken effect. Check your uploads before retrying."
        screenshot_path = None
        try:
            screenshot_path = self._save_screen("recovery.png")
        except TapHerdError:
            reason += (
                " A fresh screenshot was unavailable. Check the emulator directly."
            )
        source: Literal["current", "last_observed", "unavailable"]
        try:
            self._read()
            source = "current"
        except TapHerdError:
            source = "last_observed" if self.ui else "unavailable"
        return DeviceRun(
            self.device.serial,
            "needs_ai",
            failed_step=self.failed_step,
            reason=reason,
            screenshot_path=screenshot_path,
            ui_tree=[node.to_dict() for node in self.ui[: screen.MAX_UI_ELEMENTS]],
            ui_tree_source=source,
            media_path=self.media_path,
            publish_state=self.publish_state,
        )


@dataclass(frozen=True, slots=True)
class RecipeService:
    registry: DeviceRegistry

    @property
    def catalog(self) -> RecipeCatalog:
        return RecipeCatalog(self.registry.store.directory / "recipes")

    def list_recipes(self) -> list[dict[str, object]]:
        return [
            {"name": name, **recipe.model_dump(mode="json", exclude={"steps"})}
            for name, recipe in self.catalog.list().items()
        ]

    async def run(
        self, name: str, serials: list[str], params: dict[str, str]
    ) -> RecipeRun:
        if not serials or any(not serial.strip() for serial in serials):
            raise TapHerdError(
                "Provide at least one active device serial. Run `tapherd devices` to check serials."
            )
        if len(set(serials)) != len(serials):
            raise TapHerdError("List each device serial once.")
        if len(serials) > DEVICE_LIMIT:
            raise TapHerdError(device_limit_message())
        recipe = await asyncio.to_thread(
            lambda: prepare(self.catalog.load(name), params)
        )
        run_id = uuid4().hex
        root = (self.registry.store.directory / "runs" / run_id).absolute()
        results = await asyncio.gather(
            *(
                asyncio.to_thread(
                    self._run_device, serial, root / serial_key(serial), recipe
                )
                for serial in serials
            )
        )
        return RecipeRun(name, recipe.status, run_id, results)

    def _run_device(self, serial: str, directory: Path, recipe: Recipe) -> DeviceRun:
        try:
            with self.registry.target(serial) as device:
                runner = _DeviceRecipe(device, directory, recipe)
                try:
                    with record_action(
                        self.registry.store.directory, serial, "run_recipe"
                    ):
                        return runner.run()
                except TapHerdError as error:
                    return runner.recovery(error)
        except TapHerdError as error:
            return DeviceRun(
                serial,
                "needs_ai",
                failed_step="device",
                reason=str(error),
                ui_tree=[],
                ui_tree_source="unavailable",
            )
