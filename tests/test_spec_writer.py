from pathlib import Path

from dbt_macro_test.spec import Output, load_spec_file
from tests.spec_writer import write_spec


def test_the_parts_given_come_back_when_the_spec_is_read(tmp_path: Path) -> None:
    path = write_spec(
        tmp_path,
        "s.yml",
        "schema_for",
        "c",
        arguments={"name": "x"},
        output="columns",
        overrides={"vars": {"region": "us"}},
        rows=[{"result": "x|us"}],
    )

    (macro_spec,) = load_spec_file(path).macros
    (case,) = macro_spec.cases

    assert macro_spec.macro == "schema_for"
    assert case.name == "c"
    assert case.arguments == {"name": "x"}
    assert case.output is Output.COLUMNS
    assert case.overrides == {"vars": {"region": "us"}}
    assert case.expect_rows == [{"result": "x|us"}]


def test_what_is_left_out_is_left_out_of_the_file(tmp_path: Path) -> None:
    path = write_spec(tmp_path, "s.yml", "m", "c", rows=[])

    text = path.read_text()

    assert "given" not in text
    assert "output" not in text
    assert "overrides" not in text
    assert load_spec_file(path).macros[0].cases[0].arguments == {}


def test_strings_that_need_quoting_survive(tmp_path: Path) -> None:
    value = "a: b, {c} #d 'e'"
    path = write_spec(tmp_path, "s.yml", "m", "c", arguments={"x": value}, rows=[{"r": value}])

    (case,) = load_spec_file(path).macros[0].cases

    assert case.arguments == {"x": value}
    assert case.expect_rows == [{"r": value}]
