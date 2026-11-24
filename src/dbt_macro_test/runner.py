from dataclasses import dataclass, field
from pathlib import Path

from dbt.cli.main import dbtRunner


@dataclass(frozen=True)
class RunOutcome:
    passed: bool
    errored_models: list[str] = field(default_factory=list)


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
            raise RuntimeError(f"dbt deps failed: {deps.exception}")

    result = dbtRunner().invoke(["test", "--select", "test_type:unit", *common])
    if result.exception is not None:
        raise RuntimeError(f"dbt test failed: {result.exception}")

    errored = []
    for item in getattr(result.result, "results", []):
        status = getattr(item.status, "value", item.status)
        model = getattr(item.node, "model", None)
        if status == "error" and isinstance(model, str):
            errored.append(model)
    return RunOutcome(passed=result.success, errored_models=errored)
