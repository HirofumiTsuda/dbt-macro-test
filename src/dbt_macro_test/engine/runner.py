from dataclasses import dataclass, field
from pathlib import Path

from dbt.cli.main import dbtRunner


class DbtError(Exception):
    """dbt itself could not run (a compile error, for instance), as opposed to a test failing."""

    def __init__(self, command: str, reason: object) -> None:
        super().__init__(f"dbt {command} failed: {reason}")
        self.command = f"dbt {command}"


@dataclass(frozen=True)
class RunOutcome:
    passed: bool
    errored_models: list[str] = field(default_factory=list)
    counts: dict[str, int] = field(default_factory=dict)

    def summary(self) -> str:
        """For example `1 failed, 8 passed`; failures first."""
        order = [("error", "errored"), ("fail", "failed"), ("pass", "passed")]
        parts = [f"{self.counts[key]} {word}" for key, word in order if self.counts.get(key)]
        return ", ".join(parts) if parts else "no cases ran"


@dataclass(frozen=True)
class CaseResult:
    """What dbt reported for one unit test."""

    model: str
    status: str
    message: str


@dataclass(frozen=True)
class RawRun:
    """What one `dbt test` came to, as dbt reported it, with nothing judged.

    `exception` is set when dbt stopped altogether, before or while running the cases (an error
    raised while the project is parsed, for instance); it is the text of the error.
    """

    success: bool
    exception: str | None
    results: list[CaseResult]


def _common_args(project_dir: Path, profiles_dir: Path | None, target: str | None) -> list[str]:
    common = ["--project-dir", str(project_dir)]
    if profiles_dir is not None:
        common += ["--profiles-dir", str(profiles_dir)]
    if target is not None:
        common += ["--target", target]
    return common


def run_deps(
    project_dir: Path, *, profiles_dir: Path | None = None, target: str | None = None
) -> None:
    """`dbt deps` for a generated project."""
    deps = dbtRunner().invoke(["deps", *_common_args(project_dir, profiles_dir, target)])
    if deps.exception is not None:
        raise DbtError("deps", deps.exception)


def invoke_unit_tests(
    project_dir: Path,
    *,
    profiles_dir: Path | None = None,
    target: str | None = None,
    quiet: bool = False,
) -> RawRun:
    """Run the unit tests of a generated project and report what dbt said, even when it failed.

    `quiet` keeps dbt from printing (`--log-level none`; `--quiet` still prints errors), for a
    case whose error is the point and would otherwise look like a failure on the screen. What
    dbt reported is still in the result.
    """
    args = ["test", "--select", "test_type:unit", *_common_args(project_dir, profiles_dir, target)]
    if quiet:
        args += ["--log-level", "none"]
    result = dbtRunner().invoke(args)
    results = []
    for item in getattr(result.result, "results", []):
        status = str(getattr(item.status, "value", item.status))
        model = getattr(item.node, "model", None)
        results.append(CaseResult(str(model), status, str(item.message or "")))
    exception = None if result.exception is None else str(result.exception)
    return RawRun(success=result.success, exception=exception, results=results)


def run_unit_tests(
    project_dir: Path,
    *,
    profiles_dir: Path | None = None,
    target: str | None = None,
    install_packages: bool = False,
) -> RunOutcome:
    """Run the unit tests of a generated project through dbt.

    `errored_models` names the models of the cases dbt could not run at all
    (a SQL error, for instance), as opposed to cases whose rows did not match.
    """
    if install_packages:
        run_deps(project_dir, profiles_dir=profiles_dir, target=target)

    raw = invoke_unit_tests(project_dir, profiles_dir=profiles_dir, target=target)
    if raw.exception is not None:
        raise DbtError("test", raw.exception)

    counts: dict[str, int] = {}
    for case in raw.results:
        counts[case.status] = counts.get(case.status, 0) + 1
    errored = [case.model for case in raw.results if case.status == "error"]
    return RunOutcome(passed=raw.success, errored_models=errored, counts=counts)
