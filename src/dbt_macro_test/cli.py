import os
import sys
import tempfile
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

import click
from dbt.config.project import load_raw_project

from dbt_macro_test.discovery import (
    ProjectNotFoundError,
    resolve_profiles_dir,
    resolve_project_root,
)
from dbt_macro_test.generate import carried_over, generate_project, macro_directories
from dbt_macro_test.packages import installed_packages_dir
from dbt_macro_test.runner import DbtError, run_unit_tests
from dbt_macro_test.select import case_ids, select_cases
from dbt_macro_test.spec import SpecError, load_specs
from dbt_macro_test.validate import check_arguments


class CouldNotRun(click.ClickException):
    """The tests could not be run at all, as opposed to a case failing (exit code 1)."""

    exit_code = 2


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
    required=False,
    type=click.Path(exists=True, path_type=Path, resolve_path=True),
)
@click.option(
    "--project-dir",
    type=click.Path(exists=True, file_okay=False, path_type=Path, resolve_path=True),
    help="The dbt project. Defaults to the nearest one at or above PATH.",
)
@click.option(
    "--profiles-dir",
    type=click.Path(exists=True, file_okay=False, path_type=Path),
    help=(
        "Directory with profiles.yml. Defaults to $DBT_PROFILES_DIR, then the project's own "
        "profiles.yml, then dbt's default location."
    ),
)
@click.option("--target", help="The profile target to run against.")
@click.option(
    "--select",
    "selectors",
    multiple=True,
    help=(
        "Run only the cases that match: a macro name, or macro::case. * and ? stand for any "
        "characters, and the option can be given more than once."
    ),
)
@click.option(
    "--list",
    "list_only",
    is_flag=True,
    help="Print the cases that would run, as macro::case, and stop.",
)
@click.option(
    "--keep-generated",
    is_flag=True,
    help="Keep the generated dbt project (a temporary directory) and print where it is.",
)
@click.option("--verbose", is_flag=True, help="Say what is carried over from the project.")
def run(
    path: Path | None,
    project_dir: Path | None,
    profiles_dir: Path | None,
    target: str | None,
    selectors: tuple[str, ...],
    list_only: bool,
    keep_generated: bool,
    verbose: bool,
) -> None:
    """Run the macro tests in PATH: a spec file or a directory (default: macro_test/).

    Exit code 0 means every case passed, 1 that a case failed or errored, and 2
    that the tests could not be run (an invalid spec, a wrong argument, no
    project, dbt itself failing, or nothing matching --select).
    """
    try:
        root = resolve_project_root(project_dir, path if path is not None else Path.cwd())
        if path is None:
            path = root / "macro_test"
            if not path.exists():
                raise CouldNotRun(f"{path} does not exist; put the specs there or give their path")
        spec_files = load_specs(path)
    except (ProjectNotFoundError, SpecError) as e:
        raise CouldNotRun(str(e)) from e

    everything = case_ids(spec_files)
    spec_files = select_cases(spec_files, selectors)
    chosen = case_ids(spec_files)
    if not chosen:
        raise CouldNotRun(
            f"no case matches {', '.join(selectors)}; the cases are: {', '.join(everything)}"
        )
    if selectors:
        click.echo(f"Selected {len(chosen)} of {len(everything)} cases.", err=True)
    if list_only:
        for identifier in chosen:
            click.echo(identifier)
        return

    raw_config = load_raw_project(str(root))
    problems = check_arguments(spec_files, macro_directories(raw_config, root))
    if problems:
        raise CouldNotRun("\n".join(problems))

    profiles = resolve_profiles_dir(profiles_dir, root, os.environ)

    test_dir = path if path.is_dir() else path.parent
    packages_dir = installed_packages_dir(raw_config, root)
    with _workspace(keep_generated) as out_dir:
        project_dir = generate_project(
            root, test_dir, spec_files, raw_config, out_dir, packages_dir
        )
        if verbose:
            click.echo("Carried over from the project:", err=True)
            for line in carried_over(raw_config, root, packages_dir):
                click.echo(f"  {line}", err=True)
            click.echo(f"  profiles.yml from: {profiles.source}", err=True)
        try:
            outcome = run_unit_tests(
                project_dir,
                profiles_dir=profiles.directory,
                target=target,
                install_packages=(root / "packages.yml").is_file() and packages_dir is None,
            )
        except DbtError as e:
            raise CouldNotRun(f"{e.command} could not run; see dbt's message above") from e
        for model in outcome.errored_models:
            sql = (project_dir / "models" / f"{model}.sql").read_text().strip()
            click.echo(f"\nSQL generated for the case that errored ({model}):\n  {sql}", err=True)
        click.echo(f"\n{outcome.summary()}", err=True)
        if keep_generated:
            click.echo(f"Generated project kept at {project_dir}", err=True)
    sys.exit(0 if outcome.passed else 1)
