from pathlib import Path

from dbt_macro_test.engine import check_arguments
from dbt_macro_test.spec import Case, InlineRows, MacroSpec, SpecFile


def spec(macro: str, case_name: str, arguments: dict[str, object]) -> SpecFile:
    case = Case(name=case_name, arguments=arguments, expect=InlineRows("dict", []))
    return SpecFile(Path("macro_test/x.yml"), [MacroSpec(macro, [case])])


def macros_dir(tmp_path: Path, source: str) -> Path:
    (tmp_path / "m.sql").write_text(source)
    return tmp_path


def test_valid_arguments_have_no_problems(tmp_path: Path) -> None:
    directory = macros_dir(tmp_path, "{% macro add(x, y=5) %}1{% endmacro %}")

    assert check_arguments([spec("add", "c", {"x": 1})], [directory]) == []


def test_a_problem_names_the_file_macro_and_case(tmp_path: Path) -> None:
    directory = macros_dir(tmp_path, "{% macro add(x, y=5) %}1{% endmacro %}")

    problems = check_arguments([spec("add", "typo", {"x": 1, "z": 2})], [directory])

    assert problems == [
        "macro_test/x.yml: macro 'add', case 'typo': unknown argument 'z' (the macro takes: x, y)"
    ]


def test_every_problem_in_every_case_is_reported_at_once(tmp_path: Path) -> None:
    directory = macros_dir(tmp_path, "{% macro add(x, y) %}1{% endmacro %}")
    cases = [
        Case("a", {"x": 1}, InlineRows("dict", [])),
        Case("b", {"x": 1, "y": 2, "w": 3}, InlineRows("dict", [])),
    ]
    files = [SpecFile(Path("s.yml"), [MacroSpec("add", cases)])]

    assert len(check_arguments(files, [directory])) == 2


def test_a_macro_that_is_not_defined_in_the_project_is_not_checked(tmp_path: Path) -> None:
    directory = macros_dir(tmp_path, "{% macro add(x) %}1{% endmacro %}")

    assert check_arguments([spec("dbt_utils.star", "c", {"anything": 1})], [directory]) == []
    assert check_arguments([spec("not_here", "c", {"anything": 1})], [directory]) == []


def test_a_macro_defined_more_than_once_is_not_checked(tmp_path: Path) -> None:
    (tmp_path / "a.sql").write_text("{% macro m(x) %}1{% endmacro %}")
    (tmp_path / "b.sql").write_text("{% macro m(y) %}2{% endmacro %}")

    assert check_arguments([spec("m", "c", {"x": 1})], [tmp_path]) == []
