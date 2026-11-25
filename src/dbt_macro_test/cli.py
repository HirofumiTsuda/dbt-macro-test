import sys
import tempfile
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

import click
from dbt.config.project import load_raw_project

from dbt_macro_test.discovery import ProjectNotFoundError, find_project_root
from dbt_macro_test.generate import carried_over, generate_project, macro_directories
from dbt_macro_test.runner import DbtError, run_unit_tests
from dbt_macro_test.spec import SpecError, load_specs
from dbt_macro_test.validate import check_arguments


@contextmanager
def _workspace(keep: bool) -> Iterator[Path]:
    """A fresh directory for the generated project, removed afterwards unless kept."""
    if keep:
        yield Path(tempfile.mkdtemp(prefix="dbt-macro-test-"))
    else:
        with tempfile.TemporaryDirectory(
            prefix="dbt-macro-test-", ignore_cleanup_errors=True
        ) as directory:
            yield Path(directory)


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
@click.option(
    "--keep-generated",
    is_flag=True,
    help="Keep the generated dbt project (a temporary directory) and print where it is.",
)
@click.option("--verbose", is_flag=True, help="Say what is carried over from the project.")
def run(
    path: Path,
    profiles_dir: Path | None,
    target: str | None,
    keep_generated: bool,
    verbose: bool,
) -> None:
    """Run the macro tests in PATH (a spec file or a directory; default: ./macro_test)."""
    try:
        root = find_project_root(path)
        spec_files = load_specs(path)
    except (ProjectNotFoundError, SpecError) as e:
        raise click.ClickException(str(e)) from e

    raw_config = load_raw_project(str(root))
    problems = check_arguments(spec_files, macro_directories(raw_config, root))
    if problems:
        raise click.ClickException("\n".join(problems))

    if profiles_dir is None and (root / "profiles.yml").is_file():
        profiles_dir = root

    test_dir = path if path.is_dir() else path.parent
    with _workspace(keep_generated) as out_dir:
        project_dir = generate_project(root, test_dir, spec_files, raw_config, out_dir)
        if verbose:
            click.echo("Carried over from the project:", err=True)
            for line in carried_over(raw_config, root):
                click.echo(f"  {line}", err=True)
        try:
            outcome = run_unit_tests(
                project_dir,
                profiles_dir=profiles_dir,
                target=target,
                install_packages=(root / "packages.yml").is_file(),
            )
        except DbtError as e:
            raise click.ClickException(f"{e.command} could not run; see dbt's message above") from e
        for model in outcome.errored_models:
            sql = (project_dir / "models" / f"{model}.sql").read_text().strip()
            click.echo(f"\nSQL generated for the case that errored ({model}):\n  {sql}", err=True)
        if keep_generated:
            click.echo(f"\nGenerated project kept at {project_dir}", err=True)
    sys.exit(0 if outcome.passed else 1)
