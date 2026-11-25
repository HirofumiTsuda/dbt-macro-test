from dataclasses import dataclass

from dbt_macro_test.engine.runner import RawRun


@dataclass(frozen=True)
class Verdict:
    passed: bool
    detail: str


def error_text(text: str) -> str:
    """The message in one of dbt's errors, without its heading and its `> in macro ...` trail.

    dbt writes a heading (`Compilation Error in model ...`), then the message, then lines that
    start with `>` saying where it came from. A warehouse error has a heading and a few lines.
    """
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    body = [line for line in lines[1:] if not line.startswith(">")]
    return " ".join(body) if body else (lines[0] if lines else "")


def errors_in(raw: RawRun) -> list[str]:
    """The texts of the errors in a run: dbt stopping altogether, or a case that errored."""
    if raw.exception is not None:
        return [raw.exception]
    return [case.message for case in raw.results if case.status == "error"]


def judge_error(expected: str, raw: RawRun) -> Verdict:
    """Whether a run of one case ended in an error that contains `expected`."""
    errors = errors_in(raw)
    if not errors:
        statuses = ", ".join(sorted({case.status for case in raw.results})) or "no result"
        return Verdict(
            False, f"expected an error containing {expected!r}, but there was none ({statuses})"
        )
    if any(expected in text for text in errors):
        return Verdict(True, f"the error contains {expected!r}")
    return Verdict(
        False,
        f"expected an error containing {expected!r}, but the error was: {error_text(errors[0])}",
    )


def judge_warning(expected: str, raw: RawRun) -> Verdict:
    """Whether a run of one case gave a warning that contains `expected`, and the case passed.

    The warning comes with rows that must match as well, so a case that did not pass is a failure
    whatever it warned, and the reason is said first.
    """
    problems = errors_in(raw)
    if problems:
        return Verdict(False, f"the case ended in an error: {error_text(problems[0])}")
    not_passed = [case for case in raw.results if case.status != "pass"]
    if not_passed:
        return Verdict(False, f"the warning aside, the case did not pass ({not_passed[0].status})")
    if any(expected in warning for warning in raw.warnings):
        return Verdict(True, f"the warning contains {expected!r}")
    if not raw.warnings:
        return Verdict(False, f"expected a warning containing {expected!r}, but there was none")
    given = " | ".join(raw.warnings)
    return Verdict(
        False, f"expected a warning containing {expected!r}, but the warnings were: {given}"
    )
