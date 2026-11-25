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
    common = ["--project-dir", str(project_dir)]
    if profiles_dir is not None:
        common += ["--profiles-dir", str(profiles_dir)]
    if target is not None:
        common += ["--target", target]

    if install_packages:
        deps = dbtRunner().invoke(["deps", *common])
        if deps.exception is not None:
            raise DbtError("deps", deps.exception)

    result = dbtRunner().invoke(["test", "--select", "test_type:unit", *common])
    if result.exception is not None:
        raise DbtError("test", result.exception)

    errored = []
    counts: dict[str, int] = {}
    for item in getattr(result.result, "results", []):
        status = str(getattr(item.status, "value", item.status))
        counts[status] = counts.get(status, 0) + 1
        model = getattr(item.node, "model", None)
        if status == "error" and isinstance(model, str):
            errored.append(model)
    return RunOutcome(passed=result.success, errored_models=errored, counts=counts)
