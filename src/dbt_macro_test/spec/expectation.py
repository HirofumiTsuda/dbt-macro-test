from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any, TypedDict


class InlineExpect(TypedDict):
    """The `expect` of a native unit test whose rows are written out."""

    format: str
    rows: list[dict[str, Any]] | str


class FixtureExpect(TypedDict):
    """The `expect` of a native unit test whose rows are in a fixture file."""

    format: str
    fixture: str


UnitTestExpect = InlineExpect | FixtureExpect


@dataclass(frozen=True)
class InlineRows:
    """Rows written in the case: a list of mappings (format `dict`), or csv or sql text."""

    format: str
    content: list[dict[str, Any]] | str

    @property
    def fixture_name(self) -> None:
        return None

    @property
    def isolated(self) -> bool:
        return False

    def for_unit_test(self, fixture_formats: Mapping[str, str]) -> InlineExpect:
        """The `expect` of the native unit test."""
        return InlineExpect(format=self.format, rows=self.content)


@dataclass(frozen=True)
class FixtureRef:
    """Rows kept in a file under the fixtures directory, whose extension is its format."""

    name: str

    @property
    def fixture_name(self) -> str:
        return self.name

    @property
    def isolated(self) -> bool:
        return False

    def for_unit_test(self, fixture_formats: Mapping[str, str]) -> FixtureExpect:
        return FixtureExpect(format=fixture_formats[self.name], fixture=self.name)


@dataclass(frozen=True)
class ExpectedError:
    """The case ends in an error whose text contains `message`: a raise or a warehouse error."""

    message: str

    @property
    def fixture_name(self) -> None:
        return None

    @property
    def isolated(self) -> bool:
        """Whether the case runs on its own: a raise that is not guarded stops the whole run."""
        return True

    def for_unit_test(self, fixture_formats: Mapping[str, str]) -> InlineExpect:
        """Rows that the case cannot match: it is expected to end before they are compared."""
        return InlineExpect(format="dict", rows=[])


@dataclass(frozen=True)
class ExpectedWarning:
    """A warning whose text contains `message` is given while the case runs.

    It comes with rows (written out or in a fixture), which must match as well: the case runs,
    gives its warning and returns what it returns.
    """

    message: str


Expectation = InlineRows | FixtureRef | ExpectedError
