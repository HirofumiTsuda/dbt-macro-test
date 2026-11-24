from pathlib import Path

from dbt.cli.main import dbtRunner


def run_unit_tests(
    project_dir: Path,
    *,
    profiles_dir: Path | None = None,
    target: str | None = None,
    install_packages: bool = False,
) -> bool:
    """Run the unit tests of a generated project through dbt. True when all pass."""
    common = ["--project-dir", str(project_dir)]
    if profiles_dir is not None:
        common += ["--profiles-dir", str(profiles_dir)]
    if target is not None:
        common += ["--target", target]

    if install_packages:
        _invoke(["deps", *common])
    return _invoke(["test", "--select", "test_type:unit", *common])


def _invoke(args: list[str]) -> bool:
    result = dbtRunner().invoke(args)
    if result.exception is not None:
        raise RuntimeError(f"dbt {args[0]} failed: {result.exception}")
    return result.success
