from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class InlineRows:
    """Rows written in the case: a list of mappings (format `dict`), or csv or sql text."""

    format: str
    content: list[dict[str, Any]] | str

    @property
    def fixture_name(self) -> None:
        return None

    def for_unit_test(self, fixture_formats: Mapping[str, str]) -> dict[str, Any]:
        """The `expect` of the native unit test."""
        return {"format": self.format, "rows": self.content}


@dataclass(frozen=True)
class FixtureRef:
    """Rows kept in a file under the fixtures directory, whose extension is its format."""

    name: str

    @property
    def fixture_name(self) -> str:
        return self.name

    def for_unit_test(self, fixture_formats: Mapping[str, str]) -> dict[str, Any]:
        return {"format": fixture_formats[self.name], "fixture": self.name}


Expectation = InlineRows | FixtureRef
