from pathlib import Path

from dbt_macro_test.engine import RunOutcome
from dbt_macro_test.spec import (
    Case,
    ExpectedError,
    ExpectedWarning,
    InlineRows,
    MacroSpec,
    SpecFile,
    case_ids,
    select_cases,
    split_isolated,
    without_case,
)


def case(name: str) -> Case:
    return Case(name=name, arguments={}, expect=InlineRows("dict", []))


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


def error_case(name: str) -> Case:
    return Case(name=name, arguments={}, expect=ExpectedError("boom"))


def test_cases_that_expect_an_error_are_split_off_one_to_a_spec() -> None:
    spec = SpecFile(
        Path("s.yml"),
        [
            MacroSpec("m", [case("a"), error_case("raises"), case("b")]),
            MacroSpec("n", [error_case("x")]),
        ],
    )

    together, alone = split_isolated([spec])

    assert case_ids(together) == ["m::a", "m::b"]
    assert [case_ids([one]) for one in alone] == [["m::raises"], ["n::x"]]
    assert all(len(one.macros) == 1 and len(one.macros[0].cases) == 1 for one in alone)


def test_a_case_that_expects_a_warning_runs_alone_too() -> None:
    warned = Case(
        name="warns",
        arguments={},
        expect=InlineRows("dict", []),
        warning=ExpectedWarning("careful"),
    )
    spec = SpecFile(Path("s.yml"), [MacroSpec("m", [case("a"), warned])])

    together, alone = split_isolated([spec])

    assert case_ids(together) == ["m::a"]
    assert [case_ids([one]) for one in alone] == [["m::warns"]]


def test_nothing_is_split_off_when_no_case_expects_an_error() -> None:
    together, alone = split_isolated(specs())

    assert case_ids(together) == case_ids(specs())
    assert alone == []


def test_a_file_whose_cases_all_expect_an_error_is_not_left_empty_in_the_batch() -> None:
    spec = SpecFile(Path("s.yml"), [MacroSpec("m", [error_case("a"), error_case("b")])])

    together, alone = split_isolated([spec])

    assert together == []
    assert len(alone) == 2


def test_the_summary_puts_problems_first_and_leaves_out_zeros() -> None:
    assert RunOutcome(False, counts={"pass": 8, "fail": 1}).summary() == "1 failed, 8 passed"
    assert RunOutcome(True, counts={"pass": 3}).summary() == "3 passed"
    assert (
        RunOutcome(False, counts={"error": 1, "fail": 2, "pass": 4}).summary()
        == "1 errored, 2 failed, 4 passed"
    )
    assert RunOutcome(True).summary() == "no cases ran"


def test_without_case_drops_one_case_and_what_it_leaves_empty() -> None:
    first, second = case("one"), case("two")
    path = Path("a.yml")
    specs = [SpecFile(path, [MacroSpec("m", [first, second]), MacroSpec("n", [first])])]

    one_left = without_case(specs, "m", first, path)
    assert [c.name for c in one_left[0].macros[0].cases] == ["two"]
    assert [m.macro for m in one_left[0].macros] == ["m", "n"]

    assert without_case(without_case(one_left, "n", first, path), "m", second, path) == []
    assert without_case(specs, "m", first, Path("other.yml")) == specs
