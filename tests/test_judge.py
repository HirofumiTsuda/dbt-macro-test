from dbt_macro_test.engine import CaseResult, RawRun, error_text, judge_error, judge_warning


def run(*results: CaseResult, exception: str | None = None) -> RawRun:
    return RawRun(success=False, exception=exception, results=list(results))


DBT_STOPPED = (
    "Compilation Error in model _dmt_x (models/_dmt_x.sql)\n"
    "  x must not be negative, got -5\n"
    "  \n"
    "  > in macro positive (macros/m.sql)\n"
    "  > called by model _dmt_x (models/_dmt_x.sql)"
)


def test_the_message_of_dbt_is_read_without_its_heading_and_its_trail() -> None:
    assert error_text(DBT_STOPPED) == "x must not be negative, got -5"


def test_a_warehouse_error_keeps_its_lines() -> None:
    text = (
        "Runtime Error in unit_test wh (m.yml)\n"
        "  Conversion Error: Could not convert 'abc'\n"
        "  LINE 8: x"
    )

    assert error_text(text) == "Conversion Error: Could not convert 'abc' LINE 8: x"


def test_a_heading_alone_is_what_there_is_to_show() -> None:
    assert error_text("Compilation Error in model m") == "Compilation Error in model m"
    assert error_text("") == ""


def test_an_error_that_stopped_dbt_is_judged_by_its_text() -> None:
    verdict = judge_error("must not be negative", run(exception=DBT_STOPPED))

    assert verdict.passed


def test_an_error_of_one_case_is_judged_by_its_message() -> None:
    raw = run(CaseResult("m", "error", "Compilation Error in unit_test c\n  guarded: boom"))

    assert judge_error("boom", raw).passed


def test_other_text_fails_and_shows_what_the_error_said() -> None:
    verdict = judge_error("something else", run(exception=DBT_STOPPED))

    assert not verdict.passed
    assert "expected an error containing 'something else'" in verdict.detail
    assert "but the error was: x must not be negative, got -5" in verdict.detail


def test_no_error_fails_and_says_what_the_case_did_instead() -> None:
    verdict = judge_error("boom", run(CaseResult("m", "pass", "")))

    assert not verdict.passed
    assert "but there was none (pass)" in verdict.detail


def test_a_run_with_no_result_at_all_says_so() -> None:
    verdict = judge_error("boom", run())

    assert not verdict.passed
    assert "(no result)" in verdict.detail


def test_a_case_that_passed_next_to_one_that_errored_does_not_hide_the_error() -> None:
    raw = run(CaseResult("a", "pass", ""), CaseResult("b", "error", "Runtime Error\n  boom"))

    assert judge_error("boom", raw).passed


def given(*warnings: str, status: str = "pass") -> RawRun:
    return RawRun(
        success=status == "pass",
        exception=None,
        results=[CaseResult("m", status, "")],
        warnings=list(warnings),
    )


def test_a_warning_that_contains_the_text_passes() -> None:
    verdict = judge_warning("careful", given("careful: 7"))

    assert verdict.passed
    assert verdict.detail == "the warning contains 'careful'"


def test_any_of_the_warnings_may_be_the_one() -> None:
    assert judge_warning("second", given("first one", "the second one")).passed


def test_no_warning_fails_and_says_so() -> None:
    verdict = judge_warning("careful", given())

    assert not verdict.passed
    assert verdict.detail == "expected a warning containing 'careful', but there was none"


def test_other_warnings_fail_and_are_listed() -> None:
    verdict = judge_warning("careful", given("one thing", "another thing"))

    assert not verdict.passed
    assert "but the warnings were: one thing | another thing" in verdict.detail


def test_a_case_whose_rows_do_not_match_fails_whatever_it_warned() -> None:
    verdict = judge_warning("careful", given("careful: 7", status="fail"))

    assert not verdict.passed
    assert "the case did not pass (fail)" in verdict.detail


def test_a_case_that_ended_in_an_error_fails_and_shows_the_error() -> None:
    raw = RawRun(
        success=False,
        exception=None,
        results=[CaseResult("m", "error", "Compilation Error in unit_test c\n  boom")],
        warnings=["careful: 7"],
    )

    verdict = judge_warning("careful", raw)

    assert not verdict.passed
    assert verdict.detail == "the case ended in an error: boom"
