import sys
from pathlib import Path

import click

from dbt_macro_test.discovery import ProjectNotFoundError, find_project_root
from dbt_macro_test.generate import generate_project
from dbt_macro_test.runner import run_unit_tests
from dbt_macro_test.spec import SpecError, load_specs


@click.group()
def main() -> None:
    """Unit tests for dbt macros."""


@main.command()
@click.argument(
    "path",
    default="macro_test",
    type=click.Path(exists=True, path_type=Path, resolve_path=True),
)
@click.option(
    "--profiles-dir",
    type=click.Path(exists=True, file_okay=False, path_type=Path),
    help="Directory with profiles.yml. Defaults to the project root if it has one, else dbt's own.",
)
@click.option("--target", help="The profile target to run against.")
def run(path: Path, profiles_dir: Path | None, target: str | None) -> None:
    """Run the macro tests in PATH (a spec file or a directory; default: ./macro_test)."""
    try:
        root = find_project_root(path)
        spec_files = load_specs(path)
    except (ProjectNotFoundError, SpecError) as e:
        raise click.ClickException(str(e)) from e

    if profiles_dir is None and (root / "profiles.yml").is_file():
        profiles_dir = root

    test_dir = path if path.is_dir() else path.parent
    project_dir = generate_project(root, test_dir, spec_files)
    passed = run_unit_tests(
        project_dir,
        profiles_dir=profiles_dir,
        target=target,
        install_packages=(root / "packages.yml").is_file(),
    )
    sys.exit(0 if passed else 1)
