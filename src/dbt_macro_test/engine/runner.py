import json
import os
import re
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from dbt.cli.main import dbtRunner, dbtRunnerResult

from dbt_macro_test.spec import RELATION_MARK

_ANSI = re.compile(r"\x1b\[[0-9;]*m")


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
    left_behind: list[str] = field(default_factory=list)

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
    raised while the project is parsed, for instance); it is the text of the error. `warnings` are
    the warnings dbt gave, each once and in the order they came. `relations` are the relations the
    cases made (their database, schema, identifier and type), which the models logged as they made
    them, so that they can be dropped.
    """

    success: bool
    exception: str | None
    results: list[CaseResult]
    warnings: list[str] = field(default_factory=list)
    relations: list[dict[str, Any]] = field(default_factory=list)


def invoke_dbt(
    args: list[str], callbacks: list[Callable[[Any], None]] | None = None
) -> dbtRunnerResult:
    """Run one dbt command in this process, and leave the working directory where it was.

    dbt 1.8 moves into the project directory and stays there; the directory of a generated
    project is deleted when the run is over, and the next dbt command, which asks for the
    working directory, would fail. Later versions put it back themselves.
    """
    here = os.getcwd()
    try:
        return dbtRunner(callbacks=callbacks or []).invoke(args)
    finally:
        os.chdir(here)


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
    deps = invoke_dbt(["deps", *_common_args(project_dir, profiles_dir, target)])
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
    warnings: list[str] = []
    relations: list[dict[str, Any]] = []

    def collect(event: Any) -> None:
        text = _ANSI.sub("", event.info.msg)
        if RELATION_MARK in text:
            relation = json.loads(text.split(RELATION_MARK, 1)[1])
            if relation not in relations:
                relations.append(relation)
        elif event.info.level == "warn":
            text = text.removeprefix("[WARNING]: ").strip()
            if text not in warnings:
                warnings.append(text)

    result = invoke_dbt(args, [collect])
    results = []
    for item in getattr(result.result, "results", []):
        status = str(getattr(item.status, "value", item.status))
        model = getattr(item.node, "model", None)
        results.append(CaseResult(str(model), status, str(item.message or "")))
    exception = None if result.exception is None else str(result.exception)
    return RawRun(
        success=result.success,
        exception=exception,
        results=results,
        warnings=warnings,
        relations=relations,
    )


def drop_relations(
    project_dir: Path,
    relations: list[dict[str, Any]],
    *,
    profiles_dir: Path | None = None,
    target: str | None = None,
) -> list[str]:
    """Drop the relations that the cases made, by dbt's own `drop_relation_if_exists`, and return
    the names of those that could not be dropped (all of them, when dbt could not run).

    A temporary relation is gone with its connection on most adapters and stays on some (a table
    that expires, a normal table, ...), and the tool does not tell which: it drops what the models
    logged, which is a no-op for a relation that is already gone. Nothing here is specific to an
    adapter; the macro that drops (`_mt_drop`) is written into the generated project.
    """
    if not relations:
        return []
    arguments = json.dumps({"relations": relations})
    result = invoke_dbt(
        [
            "--log-level",
            "none",
            "run-operation",
            "_mt_drop",
            "--args",
            arguments,
            *_common_args(project_dir, profiles_dir, target),
        ]
    )
    if result.success and result.exception is None:
        return []
    return [str(r.get("identifier")) for r in relations]


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
    left = drop_relations(project_dir, raw.relations, profiles_dir=profiles_dir, target=target)
    return RunOutcome(passed=raw.success, errored_models=errored, counts=counts, left_behind=left)
