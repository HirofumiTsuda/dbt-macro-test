from pathlib import Path

import pytest

from dbt_macro_test.project import FixtureError, find_fixtures
from dbt_macro_test.spec import Case, FixtureRef, InlineRows, MacroSpec, SpecFile


def spec_naming(*fixtures: str | None) -> list[SpecFile]:
    cases = [
        Case(
            name=f"c{i}", arguments={}, expect=FixtureRef(name) if name else InlineRows("dict", [])
        )
        for i, name in enumerate(fixtures)
    ]
    return [SpecFile(Path("macro_test/s.yml"), [MacroSpec("m", cases)])]


def test_a_csv_and_a_sql_fixture_are_read_with_their_format(tmp_path: Path) -> None:
    (tmp_path / "fixtures").mkdir()
    (tmp_path / "fixtures" / "a.csv").write_text("x\n1\n")
    (tmp_path / "fixtures" / "b.sql").write_text("select 1 as x\n")

    found = find_fixtures(spec_naming("a", "b"), tmp_path)

    assert (found["a"].format, found["a"].text, found["a"].file_name) == ("csv", "x\n1\n", "a.csv")
    assert (found["b"].format, found["b"].file_name) == ("sql", "b.sql")


def test_a_fixture_used_twice_is_read_once(tmp_path: Path) -> None:
    (tmp_path / "fixtures").mkdir()
    (tmp_path / "fixtures" / "a.csv").write_text("x\n1\n")

    assert list(find_fixtures(spec_naming("a", "a"), tmp_path)) == ["a"]


def test_cases_without_a_fixture_need_no_directory(tmp_path: Path) -> None:
    assert find_fixtures(spec_naming(None, None), tmp_path) == {}


def test_a_missing_fixture_names_the_case_and_where_it_looked(tmp_path: Path) -> None:
    with pytest.raises(FixtureError) as error:
        find_fixtures(spec_naming("nope"), tmp_path)

    message = str(error.value)
    assert "macro 'm', case 'c0'" in message
    assert "no fixture 'nope'" in message
    assert str(tmp_path / "fixtures") in message


def test_a_fixture_in_both_formats_is_ambiguous(tmp_path: Path) -> None:
    (tmp_path / "fixtures").mkdir()
    (tmp_path / "fixtures" / "a.csv").write_text("x\n1\n")
    (tmp_path / "fixtures" / "a.sql").write_text("select 1 as x\n")

    with pytest.raises(FixtureError, match="exists as both .csv and .sql"):
        find_fixtures(spec_naming("a"), tmp_path)
