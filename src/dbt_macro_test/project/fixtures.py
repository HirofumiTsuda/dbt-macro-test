from dataclasses import dataclass
from pathlib import Path

from dbt_macro_test.spec import SpecFile

FIXTURE_FORMATS = {".csv": "csv", ".sql": "sql"}


class FixtureError(Exception):
    """A fixture a case names is missing, or ambiguous."""


@dataclass(frozen=True)
class Fixture:
    name: str
    format: str
    text: str

    @property
    def file_name(self) -> str:
        return f"{self.name}.{self.format}"


def find_fixtures(spec_files: list[SpecFile], test_dir: Path) -> dict[str, Fixture]:
    """The fixtures the cases name, read from `<test_dir>/fixtures/`, by name.

    A fixture is a .csv or a .sql file there; the extension is its format. One that is
    not there, or is there in both formats, is an error that names the case.
    """
    directory = test_dir / "fixtures"
    found: dict[str, Fixture] = {}
    for spec_file in spec_files:
        for macro_spec in spec_file.macros:
            for case in macro_spec.cases:
                name = case.expect_fixture
                if name is None or name in found:
                    continue
                where = f"{spec_file.path}: macro {macro_spec.macro!r}, case {case.name!r}"
                candidates = [directory / f"{name}{ext}" for ext in FIXTURE_FORMATS]
                present = [p for p in candidates if p.is_file()]
                if not present:
                    raise FixtureError(
                        f"{where}: no fixture {name!r} in {directory} (.csv or .sql)"
                    )
                if len(present) > 1:
                    raise FixtureError(
                        f"{where}: fixture {name!r} exists as both .csv and .sql in {directory}"
                    )
                found[name] = Fixture(
                    name, FIXTURE_FORMATS[present[0].suffix], present[0].read_text()
                )
    return found
