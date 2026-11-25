from pathlib import Path

from dbt_macro_test.engine import Signature, find_signatures, problems_with, signatures_in


def test_required_and_optional_parameters_are_told_apart() -> None:
    found = signatures_in("{% macro m(a, b, c=1, d=none) %}x{% endmacro %}")

    assert found["m"] == Signature(["a", "b"], ["c", "d"], accepts_any_name=False)


def test_a_macro_without_parameters_takes_none() -> None:
    assert signatures_in("{% macro m() %}x{% endmacro %}")["m"].names == []


def test_every_macro_in_the_source_is_found_and_other_blocks_are_ignored() -> None:
    source = (
        "{% macro a(x) %}1{% endmacro %}\n"
        "{% test not_a_macro(model) %}select 1{% endtest %}\n"
        "{% macro b(y=2) %}2{% endmacro %}\n"
    )

    assert set(signatures_in(source)) == {"a", "b"}


def test_a_macro_that_reads_kwargs_accepts_any_argument_name() -> None:
    found = signatures_in("{% macro m(a) %}{{ kwargs.get('b') }}{% endmacro %}")

    assert found["m"].accepts_any_name is True


def test_dbt_specific_tags_in_the_body_do_not_stop_the_signature_being_read() -> None:
    source = (
        "{% macro m(a) %}{% do log('x') %}"
        "{% call statement('s') %}select 1{% endcall %}{% endmacro %}"
    )

    assert signatures_in(source)["m"].required == ["a"]


def test_signatures_are_collected_from_every_file_under_the_directories(tmp_path: Path) -> None:
    (tmp_path / "sub").mkdir()
    (tmp_path / "a.sql").write_text("{% macro a(x) %}1{% endmacro %}")
    (tmp_path / "sub" / "b.sql").write_text("{% macro b(y) %}2{% endmacro %}")

    assert set(find_signatures([tmp_path])) == {"a", "b"}


def test_a_file_that_cannot_be_parsed_is_skipped(tmp_path: Path) -> None:
    (tmp_path / "broken.sql").write_text("{% macro broken(x %}")
    (tmp_path / "ok.sql").write_text("{% macro ok(x) %}1{% endmacro %}")

    assert set(find_signatures([tmp_path])) == {"ok"}


def test_a_macro_defined_twice_has_two_definitions(tmp_path: Path) -> None:
    (tmp_path / "a.sql").write_text("{% macro m(x) %}1{% endmacro %}")
    (tmp_path / "b.sql").write_text("{% macro m(y) %}2{% endmacro %}")

    assert len(find_signatures([tmp_path])["m"]) == 2


def test_matching_arguments_have_no_problems() -> None:
    signature = Signature(["a"], ["b"], accepts_any_name=False)

    assert problems_with(signature, ["a"]) == []
    assert problems_with(signature, ["a", "b"]) == []


def test_an_unknown_argument_names_what_the_macro_takes() -> None:
    signature = Signature(["numerator", "denominator"], [], accepts_any_name=False)

    problems = problems_with(signature, ["numerator", "denominator", "numeratr"])

    assert problems == ["unknown argument 'numeratr' (the macro takes: numerator, denominator)"]


def test_a_missing_required_argument_is_reported() -> None:
    signature = Signature(["a", "b"], ["c"], accepts_any_name=False)

    assert problems_with(signature, ["a"]) == ["missing argument 'b', which has no default"]


def test_unknown_names_are_allowed_when_the_macro_reads_kwargs() -> None:
    signature = Signature(["a"], [], accepts_any_name=True)

    assert problems_with(signature, ["a", "anything"]) == []
    assert problems_with(signature, []) == ["missing argument 'a', which has no default"]


def test_a_macro_without_parameters_says_so() -> None:
    signature = Signature([], [], accepts_any_name=False)

    assert problems_with(signature, ["x"]) == [
        "unknown argument 'x' (the macro takes: no arguments)"
    ]
