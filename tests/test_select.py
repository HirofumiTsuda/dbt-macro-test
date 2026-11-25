from pathlib import Path

from dbt_macro_test.runner import RunOutcome
from dbt_macro_test.select import case_ids, select_cases
from dbt_macro_test.spec import Case, MacroSpec, SpecFile


def case(name: str) -> Case:
    return Case(name=name, arguments={}, expect_rows=[])


def specs() -> list[SpecFile]:
    return [
        SpecFile(
            Path("a.yml"),
            [
                MacroSpec("safe_divide", [case("by_zero"), case("plain")]),
                MacroSpec("greeting", [case("default")]),
            ],
        ),
        SpecFile(Path("b.yml"), [MacroSpec("dbt_utils.star", [case("all"), case("by_zero")])]),
    ]


def test_without_patterns_everything_is_selected() -> None:
    assert case_ids(select_cases(specs(), [])) == [
        "safe_divide::by_zero",
        "safe_divide::plain",
        "greeting::default",
        "dbt_utils.star::all",
        "dbt_utils.star::by_zero",
    ]


def test_a_macro_name_selects_all_of_its_cases() -> None:
    assert case_ids(select_cases(specs(), ["safe_divide"])) == [
        "safe_divide::by_zero",
        "safe_divide::plain",
    ]


def test_macro_and_case_select_one_case() -> None:
    assert case_ids(select_cases(specs(), ["safe_divide::plain"])) == ["safe_divide::plain"]


def test_a_case_name_alone_is_not_a_macro_name() -> None:
    assert select_cases(specs(), ["plain"]) == []


def test_wildcards_work_on_the_macro_and_on_the_case() -> None:
    assert case_ids(select_cases(specs(), ["safe_*"])) == [
        "safe_divide::by_zero",
        "safe_divide::plain",
    ]
    assert case_ids(select_cases(specs(), ["*::by_zero"])) == [
        "safe_divide::by_zero",
        "dbt_utils.star::by_zero",
    ]


def test_patterns_are_ored_together() -> None:
    assert case_ids(select_cases(specs(), ["greeting", "safe_divide::plain"])) == [
        "safe_divide::plain",
        "greeting::default",
    ]


def test_a_package_qualified_macro_can_be_selected_by_its_full_name() -> None:
    assert case_ids(select_cases(specs(), ["dbt_utils.star"])) == [
        "dbt_utils.star::all",
        "dbt_utils.star::by_zero",
    ]


def test_files_and_macros_without_a_selected_case_are_dropped() -> None:
    selected = select_cases(specs(), ["greeting"])

    assert [f.path.name for f in selected] == ["a.yml"]
    assert [m.macro for m in selected[0].macros] == ["greeting"]


def test_the_original_specs_are_not_modified() -> None:
    original = specs()

    select_cases(original, ["greeting"])

    assert len(case_ids(original)) == 5


def test_the_summary_puts_problems_first_and_leaves_out_zeros() -> None:
    assert RunOutcome(False, counts={"pass": 8, "fail": 1}).summary() == "1 failed, 8 passed"
    assert RunOutcome(True, counts={"pass": 3}).summary() == "3 passed"
    assert (
        RunOutcome(False, counts={"error": 1, "fail": 2, "pass": 4}).summary()
        == "1 errored, 2 failed, 4 passed"
    )
    assert RunOutcome(True).summary() == "no cases ran"
