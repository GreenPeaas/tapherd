"""Validate recipe files and bind their parameters before touching a device."""

import mimetypes
import re
from datetime import date
from pathlib import Path
from typing import Annotated, Any, Literal, Self

from pydantic import BaseModel, ConfigDict, Field, ValidationError, model_validator

from tapherd.actions.android import Direction
from tapherd.errors import TapHerdError

Identifier = Annotated[str, Field(pattern=r"^[a-z][a-z0-9_-]*$", max_length=64)]
NonEmpty = Annotated[str, Field(min_length=1)]
Timeout = Annotated[float, Field(gt=0, le=120)]
_VARIABLE = re.compile(r"\{\{\s*([a-z][a-z0-9_-]*)\s*\}\}")


class Model(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Param(Model):
    type: Literal["text", "file", "video", "choice"] = "text"
    description: str = ""
    default: str | None = None
    choices: list[NonEmpty] = Field(default_factory=list)
    max_length: Annotated[int, Field(ge=1)] | None = None

    @model_validator(mode="after")
    def check_choices(self) -> Self:
        if (self.type == "choice") != bool(self.choices):
            raise ValueError("Choice parameters must declare choices.")
        if (
            self.type == "choice"
            and self.default is not None
            and self.default not in self.choices
        ):
            raise ValueError("The default must be an allowed choice.")
        return self


class Selector(Model):
    text: NonEmpty | None = None
    text_contains: NonEmpty | None = None
    resource_id: NonEmpty | None = None
    content_desc: NonEmpty | None = None
    regex: NonEmpty | None = None

    @model_validator(mode="after")
    def validate_selector(self) -> Self:
        if len(self.model_dump(exclude_none=True)) != 1:
            raise ValueError("Provide exactly one selector field.")
        if self.regex is not None:
            try:
                re.compile(self.regex)
            except re.error as error:
                raise ValueError("Provide a valid regular expression.") from error
        return self


class StepBase(Model):
    id: Identifier
    when_param: Identifier | None = None


class SelectStep(StepBase):
    selector: Selector
    fallbacks: list[Selector] = Field(default_factory=list)

    @property
    def selectors(self) -> tuple[Selector, ...]:
        return (self.selector, *self.fallbacks)


class OpenStep(StepBase):
    type: Literal["open_app"]


class PrepareStep(StepBase):
    type: Literal["prepare_app"]


class WaitStep(SelectStep):
    type: Literal["wait_for"]
    timeout: Timeout = 10


class AssertStep(SelectStep):
    type: Literal["assert"]


class TapStep(SelectStep):
    type: Literal["tap"]
    require: list[Selector] = Field(default_factory=list)
    publish: bool = False


class TypeStep(StepBase):
    type: Literal["type"]
    text: str


class PushStep(StepBase):
    type: Literal["push_media"]
    path: NonEmpty


class ChooseMediaStep(StepBase):
    type: Literal["choose_media"]
    timeout: Timeout = 10


class SwipeStep(StepBase):
    type: Literal["swipe"]
    direction: Direction | None = None
    coordinates: tuple[int, int, int, int] | None = None
    duration_ms: Annotated[int, Field(ge=1, le=2_147_483_647)] = 300

    @model_validator(mode="after")
    def check_gesture(self) -> Self:
        if (self.direction is None) == (self.coordinates is None):
            raise ValueError("Provide a swipe direction or four coordinates.")
        if self.coordinates is not None and min(self.coordinates) < 0:
            raise ValueError("Swipe coordinates must be non-negative.")
        return self


class ScreenshotStep(StepBase):
    type: Literal["screenshot"]


Step = Annotated[
    OpenStep
    | PrepareStep
    | WaitStep
    | AssertStep
    | TapStep
    | TypeStep
    | PushStep
    | ChooseMediaStep
    | SwipeStep
    | ScreenshotStep,
    Field(discriminator="type"),
]


class Recipe(Model):
    app_package: Annotated[
        str, Field(pattern=r"^[A-Za-z][A-Za-z0-9_]*(\.[A-Za-z][A-Za-z0-9_]*)+$")
    ]
    tested_app_version: str | None = None
    # When and where the recipe last completed a real post.
    tested_on: date | None = None
    tested_device: Literal["emulator", "real", "cloud"] | None = None
    status: Literal["verified", "unverified"]
    params: dict[Identifier, Param] = Field(default_factory=dict)
    steps: Annotated[list[Step], Field(min_length=1)]

    @model_validator(mode="after")
    def check_steps(self) -> Self:
        if self.status == "verified" and not (
            self.tested_app_version and self.tested_on and self.tested_device
        ):
            raise ValueError(
                "Record tested_app_version, tested_on, and tested_device "
                "for a verified recipe."
            )
        if len({step.id for step in self.steps}) != len(self.steps):
            raise ValueError("Give every step a unique ID.")
        published = False
        for index, step in enumerate(self.steps):
            if step.when_param is not None and step.when_param not in self.params:
                raise ValueError(f"Step {step.id} refers to an undeclared when_param.")
            if published and not isinstance(
                step, (WaitStep, AssertStep, ScreenshotStep)
            ):
                raise ValueError(
                    "Use only read-only checks and screenshots after a publish tap."
                )
            if isinstance(step, TapStep) and step.publish:
                following = self.steps[index + 1 : index + 2]
                if not step.require or step.when_param is not None:
                    raise ValueError(
                        "A publish tap needs on-screen guards and cannot be conditional."
                    )
                if (
                    not following
                    or not isinstance(following[0], (WaitStep, AssertStep))
                    or following[0].when_param
                ):
                    raise ValueError(
                        "Follow a publish tap with an unconditional confirmation check."
                    )
                published = True
        return self


def validation_message(error: ValidationError) -> str:
    return ". ".join(
        f"{'.'.join(map(str, issue['loc'])) or 'recipe'} ({issue['msg']})"
        for issue in error.errors(
            include_url=False, include_context=False, include_input=False
        )
    )


def _bind_param(name: str, spec: Param, value: str) -> str:
    if spec.max_length is not None and len(value) > spec.max_length:
        raise TapHerdError(f"Keep {name} at {spec.max_length} characters or fewer.")
    if spec.type == "choice" and value not in spec.choices:
        raise TapHerdError(f"Set {name} to one of {', '.join(spec.choices)}.")
    if spec.type in ("file", "video"):
        try:
            path = Path(value).expanduser().resolve()
            is_file = path.is_file()
        except (OSError, RuntimeError, ValueError):
            is_file = False
        if not is_file:
            raise TapHerdError(f"Set {name} to the path of an existing local file.")
        if spec.type == "video" and not (
            mimetypes.guess_type(path.name)[0] or ""
        ).startswith("video/"):
            raise TapHerdError(f"Set {name} to a local video file.")
        return str(path)
    return value


def _render(value: Any, params: dict[str, str], *, regex: bool = False) -> Any:
    if isinstance(value, dict):
        return {
            key: _render(item, params, regex=key == "regex")
            for key, item in value.items()
        }
    if isinstance(value, list):
        return [_render(item, params) for item in value]
    if isinstance(value, str):

        def substitute(match: re.Match[str]) -> str:
            name = match[1]
            if name not in params:
                raise TapHerdError(
                    f"Declare the recipe parameter {name} before using it in a template."
                )
            return re.escape(params[name]) if regex else params[name]

        return _VARIABLE.sub(substitute, value)
    return value


def prepare(recipe: Recipe, supplied: dict[str, str]) -> Recipe:
    unknown = supplied.keys() - recipe.params.keys()
    if unknown:
        raise TapHerdError(
            f"Unknown recipe parameters. Check list_recipes for {', '.join(sorted(unknown))}."
        )
    bound = {}
    for name, spec in recipe.params.items():
        value = supplied.get(name, spec.default)
        if value is None or (spec.default is None and not value.strip()):
            raise TapHerdError(f"Provide a value for recipe parameter {name}.")
        bound[name] = _bind_param(name, spec, value)
    data = recipe.model_dump(mode="json")
    data["steps"] = [
        _render(step.model_dump(mode="json"), bound)
        for step in recipe.steps
        if step.when_param is None or bound[step.when_param]
    ]
    try:
        return Recipe.model_validate(data)
    except ValidationError as error:
        raise TapHerdError(
            f"Check the rendered recipe. {validation_message(error)}"
        ) from error
