"""Find packaged recipes and recipes authored in the local registry."""

from dataclasses import dataclass
from importlib.resources import files
from importlib.resources.abc import Traversable
from pathlib import Path

import yaml
from pydantic import ValidationError

from tapherd.errors import TapHerdError
from tapherd.recipes.schema import Recipe, validation_message


@dataclass(frozen=True, slots=True)
class RecipeCatalog:
    local_directory: Path

    def _sources(self) -> dict[str, Traversable]:
        included = files("tapherd.recipes").joinpath("bundled")
        try:
            sources = {
                path.name[:-5]: path
                for path in included.iterdir()
                if path.name.endswith(".yaml")
            }
            for local in sorted(self.local_directory.glob("*.yaml")):
                if local.stem in sources:
                    raise TapHerdError(
                        f"Choose a different name for {local.name}. A bundled recipe uses that name."
                    )
                sources[local.stem] = local
        except OSError as error:
            raise TapHerdError(
                f"Could not list recipes. Check access to {self.local_directory}."
            ) from error
        return sources

    def load(self, name: str) -> Recipe:
        source = self._sources().get(name)
        if source is None:
            raise TapHerdError(
                f"Unknown recipe {name}. Run `tapherd recipes` to see available names."
            )
        return self._read(source)

    def list(self) -> dict[str, Recipe]:
        return {
            name: self._read(source) for name, source in sorted(self._sources().items())
        }

    @staticmethod
    def _read(source: Traversable) -> Recipe:
        try:
            return Recipe.model_validate(
                yaml.safe_load(source.read_text(encoding="utf-8"))
            )
        except ValidationError as error:
            raise TapHerdError(
                f"Check {source.name}. {validation_message(error)}"
            ) from error
        except (OSError, UnicodeError, yaml.YAMLError) as error:
            raise TapHerdError(
                f"Could not read {source.name}. Check its permissions and YAML syntax."
            ) from error
