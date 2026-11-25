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
